"""Comprehensive caching system with Redis and in-memory fallback"""

import asyncio
import json
import pickle
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union, Callable, TypeVar, Generic
from dataclasses import dataclass, field
from enum import Enum
from collections import OrderedDict
import hashlib
import logging
from functools import wraps

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None

from config import BotConfig

logger = logging.getLogger(__name__)

T = TypeVar('T')


class CacheBackend(Enum):
    """Cache backend types"""
    REDIS = "redis"
    MEMORY = "memory"
    HYBRID = "hybrid"


class SerializationMethod(Enum):
    """Serialization methods for cache values"""
    JSON = "json"
    PICKLE = "pickle"
    STRING = "string"


@dataclass
class CacheEntry:
    """Cache entry with metadata"""
    key: str
    value: Any
    created_at: datetime
    expires_at: Optional[datetime]
    access_count: int = 0
    last_accessed: datetime = field(default_factory=datetime.now)
    serialization_method: SerializationMethod = SerializationMethod.PICKLE
    tags: List[str] = field(default_factory=list)
    size_bytes: int = 0


@dataclass
class CacheStats:
    """Cache statistics"""
    hits: int = 0
    misses: int = 0
    sets: int = 0
    deletes: int = 0
    evictions: int = 0
    total_size_bytes: int = 0
    entry_count: int = 0
    
    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate"""
        total = self.hits + self.misses
        return (self.hits / total * 100) if total > 0 else 0.0


class LRUCache(Generic[T]):
    """Thread-safe LRU cache implementation"""
    
    def __init__(self, max_size: int = 1000, max_size_bytes: int = 100 * 1024 * 1024):  # 100MB default
        self.max_size = max_size
        self.max_size_bytes = max_size_bytes
        self.cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self.stats = CacheStats()
        self._lock = asyncio.Lock()
    
    async def get(self, key: str) -> Optional[T]:
        """Get value from cache"""
        async with self._lock:
            if key in self.cache:
                entry = self.cache[key]
                
                # Check expiration
                if entry.expires_at and datetime.now() > entry.expires_at:
                    del self.cache[key]
                    self.stats.misses += 1
                    self.stats.entry_count -= 1
                    self.stats.total_size_bytes -= entry.size_bytes
                    return None
                
                # Move to end (most recently used)
                self.cache.move_to_end(key)
                entry.access_count += 1
                entry.last_accessed = datetime.now()
                
                self.stats.hits += 1
                return entry.value
            else:
                self.stats.misses += 1
                return None
    
    async def set(self, key: str, value: T, ttl_seconds: Optional[int] = None, 
                 tags: Optional[List[str]] = None) -> None:
        """Set value in cache"""
        async with self._lock:
            # Calculate size
            try:
                size_bytes = len(pickle.dumps(value))
            except Exception:
                size_bytes = len(str(value).encode('utf-8'))
            
            # Create cache entry
            expires_at = datetime.now() + timedelta(seconds=ttl_seconds) if ttl_seconds else None
            entry = CacheEntry(
                key=key,
                value=value,
                created_at=datetime.now(),
                expires_at=expires_at,
                tags=tags or [],
                size_bytes=size_bytes
            )
            
            # Remove existing entry if present
            if key in self.cache:
                old_entry = self.cache[key]
                self.stats.total_size_bytes -= old_entry.size_bytes
                self.stats.entry_count -= 1
            
            # Add new entry
            self.cache[key] = entry
            self.stats.sets += 1
            self.stats.entry_count += 1
            self.stats.total_size_bytes += size_bytes
            
            # Evict if necessary
            await self._evict_if_needed()
    
    async def delete(self, key: str) -> bool:
        """Delete value from cache"""
        async with self._lock:
            if key in self.cache:
                entry = self.cache[key]
                del self.cache[key]
                self.stats.deletes += 1
                self.stats.entry_count -= 1
                self.stats.total_size_bytes -= entry.size_bytes
                return True
            return False
    
    async def clear(self) -> None:
        """Clear all cache entries"""
        async with self._lock:
            self.cache.clear()
            self.stats = CacheStats()
    
    async def clear_by_tags(self, tags: List[str]) -> int:
        """Clear cache entries by tags"""
        async with self._lock:
            keys_to_delete = []
            for key, entry in self.cache.items():
                if any(tag in entry.tags for tag in tags):
                    keys_to_delete.append(key)
            
            for key in keys_to_delete:
                entry = self.cache[key]
                del self.cache[key]
                self.stats.deletes += 1
                self.stats.entry_count -= 1
                self.stats.total_size_bytes -= entry.size_bytes
            
            return len(keys_to_delete)
    
    async def _evict_if_needed(self) -> None:
        """Evict entries if cache limits are exceeded"""
        # Evict by count
        while len(self.cache) > self.max_size:
            key, entry = self.cache.popitem(last=False)  # Remove least recently used
            self.stats.evictions += 1
            self.stats.entry_count -= 1
            self.stats.total_size_bytes -= entry.size_bytes
        
        # Evict by size
        while self.stats.total_size_bytes > self.max_size_bytes and self.cache:
            key, entry = self.cache.popitem(last=False)
            self.stats.evictions += 1
            self.stats.entry_count -= 1
            self.stats.total_size_bytes -= entry.size_bytes
    
    async def get_stats(self) -> CacheStats:
        """Get cache statistics"""
        return self.stats
    
    async def get_keys_by_pattern(self, pattern: str) -> List[str]:
        """Get keys matching pattern (simple wildcard support)"""
        import fnmatch
        async with self._lock:
            return [key for key in self.cache.keys() if fnmatch.fnmatch(key, pattern)]


class RedisCache:
    """Redis-based cache implementation"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379", 
                 key_prefix: str = "optrixtrades:", max_connections: int = 10):
        self.redis_url = redis_url
        self.key_prefix = key_prefix
        self.max_connections = max_connections
        self.redis_client: Optional[redis.Redis] = None
        self.stats = CacheStats()
        self.connected = False
    
    async def connect(self) -> bool:
        """Connect to Redis"""
        if not REDIS_AVAILABLE:
            logger.warning("Redis not available, falling back to memory cache")
            return False
        
        try:
            self.redis_client = redis.from_url(
                self.redis_url,
                max_connections=self.max_connections,
                retry_on_timeout=True,
                socket_keepalive=True,
                socket_keepalive_options={}
            )
            
            # Test connection
            await self.redis_client.ping()
            self.connected = True
            logger.info(f"Connected to Redis at {self.redis_url}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.connected = False
            return False
    
    async def disconnect(self) -> None:
        """Disconnect from Redis"""
        if self.redis_client:
            await self.redis_client.close()
            self.connected = False
            logger.info("Disconnected from Redis")
    
    def _make_key(self, key: str) -> str:
        """Create prefixed key"""
        return f"{self.key_prefix}{key}"
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from Redis cache"""
        if not self.connected or not self.redis_client:
            self.stats.misses += 1
            return None
        
        try:
            redis_key = self._make_key(key)
            data = await self.redis_client.get(redis_key)
            
            if data is None:
                self.stats.misses += 1
                return None
            
            # Deserialize
            try:
                value = pickle.loads(data)
                self.stats.hits += 1
                return value
            except Exception:
                # Fallback to JSON
                try:
                    value = json.loads(data.decode('utf-8'))
                    self.stats.hits += 1
                    return value
                except Exception:
                    # Fallback to string
                    self.stats.hits += 1
                    return data.decode('utf-8')
                    
        except Exception as e:
            logger.error(f"Redis get error for key {key}: {e}")
            self.stats.misses += 1
            return None
    
    async def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None, 
                 tags: Optional[List[str]] = None) -> bool:
        """Set value in Redis cache"""
        if not self.connected or not self.redis_client:
            return False
        
        try:
            redis_key = self._make_key(key)
            
            # Serialize value
            try:
                data = pickle.dumps(value)
            except Exception:
                try:
                    data = json.dumps(value).encode('utf-8')
                except Exception:
                    data = str(value).encode('utf-8')
            
            # Set in Redis
            if ttl_seconds:
                await self.redis_client.setex(redis_key, ttl_seconds, data)
            else:
                await self.redis_client.set(redis_key, data)
            
            # Store tags if provided
            if tags:
                for tag in tags:
                    tag_key = self._make_key(f"tag:{tag}")
                    await self.redis_client.sadd(tag_key, redis_key)
                    if ttl_seconds:
                        await self.redis_client.expire(tag_key, ttl_seconds)
            
            self.stats.sets += 1
            return True
            
        except Exception as e:
            logger.error(f"Redis set error for key {key}: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete value from Redis cache"""
        if not self.connected or not self.redis_client:
            return False
        
        try:
            redis_key = self._make_key(key)
            result = await self.redis_client.delete(redis_key)
            
            if result > 0:
                self.stats.deletes += 1
                return True
            return False
            
        except Exception as e:
            logger.error(f"Redis delete error for key {key}: {e}")
            return False
    
    async def clear(self) -> None:
        """Clear all cache entries with prefix"""
        if not self.connected or not self.redis_client:
            return
        
        try:
            pattern = f"{self.key_prefix}*"
            keys = await self.redis_client.keys(pattern)
            
            if keys:
                await self.redis_client.delete(*keys)
                self.stats.deletes += len(keys)
                
        except Exception as e:
            logger.error(f"Redis clear error: {e}")
    
    async def clear_by_tags(self, tags: List[str]) -> int:
        """Clear cache entries by tags"""
        if not self.connected or not self.redis_client:
            return 0
        
        try:
            keys_to_delete = set()
            
            for tag in tags:
                tag_key = self._make_key(f"tag:{tag}")
                tagged_keys = await self.redis_client.smembers(tag_key)
                keys_to_delete.update(tagged_keys)
                # Delete tag set
                await self.redis_client.delete(tag_key)
            
            if keys_to_delete:
                # Convert bytes to strings if needed
                keys_list = [key.decode('utf-8') if isinstance(key, bytes) else key for key in keys_to_delete]
                await self.redis_client.delete(*keys_list)
                self.stats.deletes += len(keys_list)
                return len(keys_list)
            
            return 0
            
        except Exception as e:
            logger.error(f"Redis clear by tags error: {e}")
            return 0
    
    async def get_keys_by_pattern(self, pattern: str) -> List[str]:
        """Get keys matching pattern"""
        if not self.connected or not self.redis_client:
            return []
        
        try:
            redis_pattern = self._make_key(pattern)
            keys = await self.redis_client.keys(redis_pattern)
            # Remove prefix and convert bytes to strings
            return [key.decode('utf-8').replace(self.key_prefix, '', 1) if isinstance(key, bytes) else key.replace(self.key_prefix, '', 1) for key in keys]
            
        except Exception as e:
            logger.error(f"Redis keys pattern error: {e}")
            return []
    
    async def get_stats(self) -> CacheStats:
        """Get cache statistics"""
        if self.connected and self.redis_client:
            try:
                info = await self.redis_client.info('memory')
                self.stats.total_size_bytes = info.get('used_memory', 0)
                
                # Count keys with our prefix
                pattern = f"{self.key_prefix}*"
                keys = await self.redis_client.keys(pattern)
                self.stats.entry_count = len(keys)
                
            except Exception as e:
                logger.error(f"Redis stats error: {e}")
        
        return self.stats


class HybridCache:
    """Hybrid cache using both Redis and in-memory cache"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379", 
                 memory_max_size: int = 1000, memory_max_size_bytes: int = 50 * 1024 * 1024):
        self.redis_cache = RedisCache(redis_url)
        self.memory_cache = LRUCache(memory_max_size, memory_max_size_bytes)
        self.use_redis = False
    
    async def connect(self) -> None:
        """Connect to Redis (fallback to memory if fails)"""
        self.use_redis = await self.redis_cache.connect()
        if not self.use_redis:
            logger.info("Using memory cache only")
    
    async def disconnect(self) -> None:
        """Disconnect from Redis"""
        await self.redis_cache.disconnect()
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache (memory first, then Redis)"""
        # Try memory cache first
        value = await self.memory_cache.get(key)
        if value is not None:
            return value
        
        # Try Redis if available
        if self.use_redis:
            value = await self.redis_cache.get(key)
            if value is not None:
                # Store in memory cache for faster access
                await self.memory_cache.set(key, value)
                return value
        
        return None
    
    async def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None, 
                 tags: Optional[List[str]] = None) -> bool:
        """Set value in both caches"""
        # Always set in memory cache
        await self.memory_cache.set(key, value, ttl_seconds, tags)
        
        # Set in Redis if available
        if self.use_redis:
            return await self.redis_cache.set(key, value, ttl_seconds, tags)
        
        return True
    
    async def delete(self, key: str) -> bool:
        """Delete from both caches"""
        memory_result = await self.memory_cache.delete(key)
        redis_result = True
        
        if self.use_redis:
            redis_result = await self.redis_cache.delete(key)
        
        return memory_result or redis_result
    
    async def clear(self) -> None:
        """Clear both caches"""
        await self.memory_cache.clear()
        if self.use_redis:
            await self.redis_cache.clear()
    
    async def clear_by_tags(self, tags: List[str]) -> int:
        """Clear cache entries by tags from both caches"""
        memory_count = await self.memory_cache.clear_by_tags(tags)
        redis_count = 0
        
        if self.use_redis:
            redis_count = await self.redis_cache.clear_by_tags(tags)
        
        return memory_count + redis_count
    
    async def get_stats(self) -> Dict[str, CacheStats]:
        """Get statistics from both caches"""
        memory_stats = await self.memory_cache.get_stats()
        redis_stats = await self.redis_cache.get_stats() if self.use_redis else CacheStats()
        
        return {
            "memory": memory_stats,
            "redis": redis_stats
        }


class CacheManager:
    """Main cache manager with multiple backends"""
    
    def __init__(self, backend: CacheBackend = CacheBackend.HYBRID, 
                 redis_url: Optional[str] = None):
        self.backend = backend
        self.redis_url = redis_url or getattr(BotConfig, 'REDIS_URL', 'redis://localhost:6379')
        
        if backend == CacheBackend.REDIS:
            self.cache = RedisCache(self.redis_url)
        elif backend == CacheBackend.MEMORY:
            self.cache = LRUCache()
        else:  # HYBRID
            self.cache = HybridCache(self.redis_url)
        
        self.default_ttl = 3600  # 1 hour
        self.namespace_ttls = {
            "user:": 1800,      # 30 minutes
            "session:": 900,    # 15 minutes
            "temp:": 300,       # 5 minutes
            "config:": 7200,    # 2 hours
            "static:": 86400,   # 24 hours
        }
    
    async def initialize(self) -> None:
        """Initialize cache manager"""
        if hasattr(self.cache, 'connect'):
            await self.cache.connect()
        logger.info(f"Cache manager initialized with {self.backend.value} backend")
    
    async def shutdown(self) -> None:
        """Shutdown cache manager"""
        if hasattr(self.cache, 'disconnect'):
            await self.cache.disconnect()
        logger.info("Cache manager shutdown")
    
    def _get_ttl_for_key(self, key: str) -> int:
        """Get TTL based on key namespace"""
        for namespace, ttl in self.namespace_ttls.items():
            if key.startswith(namespace):
                return ttl
        return self.default_ttl
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        return await self.cache.get(key)
    
    async def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None, 
                 tags: Optional[List[str]] = None) -> bool:
        """Set value in cache"""
        if ttl_seconds is None:
            ttl_seconds = self._get_ttl_for_key(key)
        
        return await self.cache.set(key, value, ttl_seconds, tags)
    
    async def delete(self, key: str) -> bool:
        """Delete value from cache"""
        return await self.cache.delete(key)
    
    async def clear_namespace(self, namespace: str) -> int:
        """Clear all keys in a namespace"""
        if hasattr(self.cache, 'get_keys_by_pattern'):
            keys = await self.cache.get_keys_by_pattern(f"{namespace}*")
            count = 0
            for key in keys:
                if await self.cache.delete(key):
                    count += 1
            return count
        return 0
    
    async def clear_by_tags(self, tags: List[str]) -> int:
        """Clear cache entries by tags"""
        return await self.cache.clear_by_tags(tags)
    
    async def get_or_set(self, key: str, factory: Callable[[], Any], 
                        ttl_seconds: Optional[int] = None, 
                        tags: Optional[List[str]] = None) -> Any:
        """Get value from cache or set it using factory function"""
        value = await self.get(key)
        if value is not None:
            return value
        
        # Generate value
        if asyncio.iscoroutinefunction(factory):
            value = await factory()
        else:
            value = factory()
        
        # Cache the value
        await self.set(key, value, ttl_seconds, tags)
        return value
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics"""
        stats = await self.cache.get_stats()
        
        if isinstance(stats, dict):  # Hybrid cache
            return {
                "backend": self.backend.value,
                "memory": {
                    "hits": stats["memory"].hits,
                    "misses": stats["memory"].misses,
                    "hit_rate": stats["memory"].hit_rate,
                    "entries": stats["memory"].entry_count,
                    "size_bytes": stats["memory"].total_size_bytes
                },
                "redis": {
                    "hits": stats["redis"].hits,
                    "misses": stats["redis"].misses,
                    "hit_rate": stats["redis"].hit_rate,
                    "entries": stats["redis"].entry_count,
                    "size_bytes": stats["redis"].total_size_bytes
                } if "redis" in stats else None
            }
        else:
            return {
                "backend": self.backend.value,
                "hits": stats.hits,
                "misses": stats.misses,
                "hit_rate": stats.hit_rate,
                "entries": stats.entry_count,
                "size_bytes": stats.total_size_bytes
            }
    
    # Convenience methods for common use cases
    async def cache_user_data(self, user_id: int, data: Dict[str, Any]) -> bool:
        """Cache user data"""
        key = f"user:{user_id}"
        return await self.set(key, data, tags=["user_data"])
    
    async def get_user_data(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get cached user data"""
        key = f"user:{user_id}"
        return await self.get(key)
    
    async def cache_session_data(self, session_id: str, data: Dict[str, Any]) -> bool:
        """Cache session data"""
        key = f"session:{session_id}"
        return await self.set(key, data, tags=["session_data"])
    
    async def get_session_data(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get cached session data"""
        key = f"session:{session_id}"
        return await self.get(key)
    
    async def cache_config(self, config_key: str, config_value: Any) -> bool:
        """Cache configuration value"""
        key = f"config:{config_key}"
        return await self.set(key, config_value, tags=["config"])
    
    async def get_config(self, config_key: str) -> Optional[Any]:
        """Get cached configuration value"""
        key = f"config:{config_key}"
        return await self.get(key)
    
    async def invalidate_user_cache(self, user_id: int) -> bool:
        """Invalidate all cache entries for a user"""
        pattern = f"user:{user_id}*"
        if hasattr(self.cache, 'get_keys_by_pattern'):
            keys = await self.cache.get_keys_by_pattern(pattern)
            for key in keys:
                await self.delete(key)
            return len(keys) > 0
        return False


def cache_result(ttl_seconds: int = 3600, key_prefix: str = "", 
                tags: Optional[List[str]] = None):
    """Decorator to cache function results"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            key_parts = [key_prefix, func.__name__]
            
            # Add args to key
            for arg in args:
                if isinstance(arg, (int, str, float, bool)):
                    key_parts.append(str(arg))
                else:
                    # Hash complex objects
                    key_parts.append(hashlib.md5(str(arg).encode()).hexdigest()[:8])
            
            # Add kwargs to key
            for k, v in sorted(kwargs.items()):
                if isinstance(v, (int, str, float, bool)):
                    key_parts.append(f"{k}:{v}")
                else:
                    key_parts.append(f"{k}:{hashlib.md5(str(v).encode()).hexdigest()[:8]}")
            
            cache_key = ":".join(filter(None, key_parts))
            
            # Try to get from cache
            if hasattr(wrapper, '_cache_manager'):
                cached_result = await wrapper._cache_manager.get(cache_key)
                if cached_result is not None:
                    return cached_result
            
            # Execute function
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            # Cache result
            if hasattr(wrapper, '_cache_manager'):
                await wrapper._cache_manager.set(cache_key, result, ttl_seconds, tags)
            
            return result
        
        return wrapper
    return decorator


# Global cache manager instance
cache_manager: Optional[CacheManager] = None


async def initialize_cache_manager(backend: CacheBackend = CacheBackend.HYBRID, 
                                  redis_url: Optional[str] = None) -> CacheManager:
    """Initialize global cache manager"""
    global cache_manager
    cache_manager = CacheManager(backend, redis_url)
    await cache_manager.initialize()
    
    # Set cache manager for decorated functions
    import sys
    current_module = sys.modules[__name__]
    for name in dir(current_module):
        obj = getattr(current_module, name)
        if callable(obj) and hasattr(obj, '_cache_manager'):
            obj._cache_manager = cache_manager
    
    return cache_manager


def get_cache_manager() -> Optional[CacheManager]:
    """Get global cache manager instance"""
    return cache_manager


async def shutdown_cache_manager() -> None:
    """Shutdown global cache manager"""
    global cache_manager
    if cache_manager:
        await cache_manager.shutdown()
        cache_manager = None