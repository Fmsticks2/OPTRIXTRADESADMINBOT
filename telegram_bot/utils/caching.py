"""Caching utilities for OPTRIXTRADES Telegram Bot"""

import time
import logging
import asyncio
from typing import Dict, Any, Optional, List, Callable, Tuple, TypeVar, Generic, Union
from functools import wraps
from datetime import datetime, timedelta
import json
import os
import hashlib

from config import BotConfig

logger = logging.getLogger(__name__)

# Type variable for generic caching
T = TypeVar('T')

class CacheEntry(Generic[T]):
    """Cache entry with expiration"""
    
    def __init__(self, value: T, ttl: int):
        self.value = value
        self.expiry = time.time() + ttl
    
    def is_expired(self) -> bool:
        """Check if entry is expired"""
        return time.time() > self.expiry


class MemoryCache:
    """In-memory cache implementation"""
    
    def __init__(self, default_ttl: int = 300):
        self.cache: Dict[str, CacheEntry] = {}
        self.default_ttl = default_ttl
        self.hits = 0
        self.misses = 0
        self._setup_cleanup_task()
    
    def _setup_cleanup_task(self):
        """Set up periodic cache cleanup"""
        asyncio.create_task(self._periodic_cleanup())
    
    async def _periodic_cleanup(self):
        """Periodically clean up expired cache entries"""
        while True:
            await asyncio.sleep(60)  # Run every minute
            self.cleanup()
    
    def cleanup(self):
        """Remove expired entries from cache"""
        keys_to_remove = []
        for key, entry in self.cache.items():
            if entry.is_expired():
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del self.cache[key]
        
        if keys_to_remove:
            logger.debug(f"Cleaned up {len(keys_to_remove)} expired cache entries")
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """Set a value in the cache"""
        if ttl is None:
            ttl = self.default_ttl
        
        self.cache[key] = CacheEntry(value, ttl)
    
    def get(self, key: str, default: Optional[T] = None) -> Optional[T]:
        """Get a value from the cache"""
        entry = self.cache.get(key)
        
        if entry is None:
            self.misses += 1
            return default
        
        if entry.is_expired():
            del self.cache[key]
            self.misses += 1
            return default
        
        self.hits += 1
        return entry.value
    
    def delete(self, key: str):
        """Delete a key from the cache"""
        if key in self.cache:
            del self.cache[key]
    
    def clear(self):
        """Clear all cache entries"""
        self.cache.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_requests = self.hits + self.misses
        hit_rate = (self.hits / total_requests) * 100 if total_requests > 0 else 0
        
        return {
            "entries": len(self.cache),
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": hit_rate,
            "total_requests": total_requests
        }


class RedisCache:
    """Redis-based cache implementation"""
    
    def __init__(self, default_ttl: int = 300):
        self.default_ttl = default_ttl
        self.redis = None
        self.hits = 0
        self.misses = 0
        self._initialize_redis()
    
    def _initialize_redis(self):
        """Initialize Redis connection if configured"""
        if not BotConfig.REDIS_URL:
            logger.warning("Redis URL not configured, Redis cache disabled")
            return
        
        try:
            import redis.asyncio as redis
            self.redis = redis.from_url(
                BotConfig.REDIS_URL,
                password=BotConfig.REDIS_PASSWORD,
                decode_responses=True
            )
            logger.info("Redis cache initialized")
        except ImportError:
            logger.warning("Redis package not installed, Redis cache disabled")
        except Exception as e:
            logger.error(f"Failed to initialize Redis: {e}")
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """Set a value in Redis cache"""
        if self.redis is None:
            return
        
        if ttl is None:
            ttl = self.default_ttl
        
        try:
            # Serialize value to JSON
            serialized = json.dumps(value)
            await self.redis.setex(key, ttl, serialized)
        except Exception as e:
            logger.error(f"Redis set error: {e}")
    
    async def get(self, key: str, default: Optional[T] = None) -> Optional[T]:
        """Get a value from Redis cache"""
        if self.redis is None:
            return default
        
        try:
            result = await self.redis.get(key)
            
            if result is None:
                self.misses += 1
                return default
            
            self.hits += 1
            return json.loads(result)
        except Exception as e:
            logger.error(f"Redis get error: {e}")
            return default
    
    async def delete(self, key: str):
        """Delete a key from Redis cache"""
        if self.redis is None:
            return
        
        try:
            await self.redis.delete(key)
        except Exception as e:
            logger.error(f"Redis delete error: {e}")
    
    async def clear(self):
        """Clear all cache entries with a specific prefix"""
        if self.redis is None:
            return
        
        try:
            # Use a prefix for all bot keys to avoid clearing other data
            keys = await self.redis.keys("optrixtrades:*")
            if keys:
                await self.redis.delete(*keys)
        except Exception as e:
            logger.error(f"Redis clear error: {e}")
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        if self.redis is None:
            return {"status": "disabled"}
        
        try:
            # Count keys with our prefix
            keys = await self.redis.keys("optrixtrades:*")
            total_requests = self.hits + self.misses
            hit_rate = (self.hits / total_requests) * 100 if total_requests > 0 else 0
            
            return {
                "status": "connected",
                "entries": len(keys),
                "hits": self.hits,
                "misses": self.misses,
                "hit_rate": hit_rate,
                "total_requests": total_requests
            }
        except Exception as e:
            logger.error(f"Redis stats error: {e}")
            return {"status": "error", "error": str(e)}


def cached(ttl: int = 300, key_prefix: str = ""):
    """Decorator for caching function results"""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Generate cache key
            key_parts = [key_prefix or func.__name__]
            # Add args and kwargs to key
            for arg in args:
                key_parts.append(str(arg))
            for k, v in sorted(kwargs.items()):
                key_parts.append(f"{k}={v}")
            
            # Create a hash of the key parts for a shorter key
            key = f"optrixtrades:{hashlib.md5(':'.join(key_parts).encode()).hexdigest()}"
            
            # Try to get from cache first
            if BotConfig.REDIS_URL and redis_cache.redis is not None:
                result = await redis_cache.get(key)
                if result is not None:
                    return result
                
                # Cache miss, execute function
                result = await func(*args, **kwargs)
                # Store in cache
                await redis_cache.set(key, result, ttl)
                return result
            else:
                # Use memory cache
                result = memory_cache.get(key)
                if result is not None:
                    return result
                
                # Cache miss, execute function
                result = await func(*args, **kwargs)
                # Store in cache
                memory_cache.set(key, result, ttl)
                return result
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Generate cache key
            key_parts = [key_prefix or func.__name__]
            # Add args and kwargs to key
            for arg in args:
                key_parts.append(str(arg))
            for k, v in sorted(kwargs.items()):
                key_parts.append(f"{k}={v}")
            
            # Create a hash of the key parts for a shorter key
            key = f"optrixtrades:{hashlib.md5(':'.join(key_parts).encode()).hexdigest()}"
            
            # Use memory cache for sync functions
            result = memory_cache.get(key)
            if result is not None:
                return result
            
            # Cache miss, execute function
            result = func(*args, **kwargs)
            # Store in cache
            memory_cache.set(key, result, ttl)
            return result
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator


# Create global cache instances
memory_cache = MemoryCache()
redis_cache = RedisCache()