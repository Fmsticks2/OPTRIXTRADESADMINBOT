import unittest
import asyncio
import logging
from unittest.mock import patch, MagicMock, AsyncMock
import time
from datetime import datetime

from telegram_bot.utils.caching import MemoryCache, RedisCache, cached

class TestCaching(unittest.TestCase):
    """Test suite for caching utilities"""
    
    def setUp(self):
        # Set up logging for tests
        self.logger = logging.getLogger('test_logger')
        self.logger.setLevel(logging.DEBUG)
        # Use a string IO handler to capture log output
        self.log_capture = MagicMock()
        self.logger.addHandler(self.log_capture)
    
    def test_memory_cache_basic(self):
        """Test basic memory cache operations"""
        cache = MemoryCache(default_ttl=1)  # 1 second TTL for testing
        
        # Test set and get
        cache.set("test_key", "test_value")
        self.assertEqual(cache.get("test_key"), "test_value")
        
        # Test default value for missing key
        self.assertEqual(cache.get("missing_key", "default"), "default")
        
        # Test delete
        cache.delete("test_key")
        self.assertIsNone(cache.get("test_key"))
        
        # Test clear
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.clear()
        self.assertIsNone(cache.get("key1"))
        self.assertIsNone(cache.get("key2"))
    
    def test_memory_cache_expiration(self):
        """Test memory cache entry expiration"""
        cache = MemoryCache(default_ttl=0.1)  # 100ms TTL for testing
        
        # Set a value
        cache.set("test_key", "test_value")
        self.assertEqual(cache.get("test_key"), "test_value")
        
        # Wait for expiration
        time.sleep(0.2)  # 200ms, longer than TTL
        
        # Value should be expired
        self.assertIsNone(cache.get("test_key"))
        
        # Test custom TTL
        cache.set("long_key", "long_value", ttl=1)  # 1 second TTL
        cache.set("short_key", "short_value", ttl=0.1)  # 100ms TTL
        
        # Wait for short TTL expiration
        time.sleep(0.2)  # 200ms
        
        # Short key should be expired, long key should still exist
        self.assertIsNone(cache.get("short_key"))
        self.assertEqual(cache.get("long_key"), "long_value")
    
    def test_memory_cache_cleanup(self):
        """Test memory cache cleanup"""
        cache = MemoryCache(default_ttl=0.1)  # 100ms TTL for testing
        
        # Set some values
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        
        # Wait for expiration
        time.sleep(0.2)  # 200ms, longer than TTL
        
        # Run cleanup
        cache.cleanup()
        
        # Cache should be empty
        self.assertEqual(len(cache.cache), 0)
    
    def test_memory_cache_stats(self):
        """Test memory cache statistics"""
        cache = MemoryCache()
        
        # Set some values
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        
        # Get some values (hits)
        cache.get("key1")
        cache.get("key2")
        cache.get("key1")
        
        # Get missing value (miss)
        cache.get("missing_key")
        
        # Get stats
        stats = cache.get_stats()
        
        # Verify stats
        self.assertEqual(stats["entries"], 2)
        self.assertEqual(stats["hits"], 3)
        self.assertEqual(stats["misses"], 1)
        self.assertEqual(stats["total_requests"], 4)
        self.assertEqual(stats["hit_rate"], 75.0)  # 3/4 * 100
    
    @patch('telegram_bot.utils.caching.redis.asyncio')
    async def test_redis_cache_initialization(self, mock_redis):
        """Test Redis cache initialization"""
        # Mock Redis client
        mock_redis_client = AsyncMock()
        mock_redis.from_url.return_value = mock_redis_client
        
        # Test with Redis URL configured
        with patch('telegram_bot.utils.caching.BotConfig') as mock_config:
            mock_config.REDIS_URL = "redis://localhost:6379/0"
            mock_config.REDIS_PASSWORD = "password"
            
            redis_cache = RedisCache()
            
            # Verify Redis client was initialized
            mock_redis.from_url.assert_called_once_with(
                "redis://localhost:6379/0",
                password="password",
                decode_responses=True
            )
            self.assertIsNotNone(redis_cache.redis)
        
        # Test with no Redis URL configured
        with patch('telegram_bot.utils.caching.BotConfig') as mock_config:
            mock_config.REDIS_URL = ""
            
            redis_cache = RedisCache()
            
            # Verify Redis client was not initialized
            self.assertIsNone(redis_cache.redis)
    
    @patch('telegram_bot.utils.caching.redis.asyncio')
    async def test_redis_cache_operations(self, mock_redis):
        """Test Redis cache operations"""
        # Mock Redis client
        mock_redis_client = AsyncMock()
        mock_redis.from_url.return_value = mock_redis_client
        
        # Configure mock methods
        mock_redis_client.setex = AsyncMock()
        mock_redis_client.get = AsyncMock(return_value='{"key": "value"}')
        mock_redis_client.delete = AsyncMock()
        mock_redis_client.keys = AsyncMock(return_value=["optrixtrades:key1", "optrixtrades:key2"])
        
        # Initialize Redis cache
        with patch('telegram_bot.utils.caching.BotConfig') as mock_config:
            mock_config.REDIS_URL = "redis://localhost:6379/0"
            
            redis_cache = RedisCache(default_ttl=300)
            
            # Test set
            await redis_cache.set("test_key", {"test": "value"})
            mock_redis_client.setex.assert_called_once()
            
            # Test get
            result = await redis_cache.get("test_key")
            mock_redis_client.get.assert_called_once_with("test_key")
            self.assertEqual(result, {"key": "value"})
            
            # Test delete
            await redis_cache.delete("test_key")
            mock_redis_client.delete.assert_called_once_with("test_key")
            
            # Test clear
            await redis_cache.clear()
            mock_redis_client.keys.assert_called_once_with("optrixtrades:*")
            mock_redis_client.delete.assert_called_with(*["optrixtrades:key1", "optrixtrades:key2"])
            
            # Test get_stats
            stats = await redis_cache.get_stats()
            self.assertEqual(stats["status"], "connected")
            self.assertEqual(stats["entries"], 2)
    
    @patch('telegram_bot.utils.caching.redis_cache')
    @patch('telegram_bot.utils.caching.memory_cache')
    @patch('telegram_bot.utils.caching.BotConfig')
    async def test_cached_decorator_redis(self, mock_config, mock_memory_cache, mock_redis_cache):
        """Test cached decorator with Redis"""
        # Configure mocks
        mock_config.REDIS_URL = "redis://localhost:6379/0"
        mock_redis_cache.redis = AsyncMock()  # Not None to indicate Redis is available
        mock_redis_cache.get = AsyncMock(return_value=None)  # Cache miss
        mock_redis_cache.set = AsyncMock()
        
        # Create a cached function
        @cached(ttl=60)
        async def test_function(arg1, arg2):
            return f"{arg1}_{arg2}"
        
        # Call the function
        result = await test_function("test", "value")
        
        # Verify result
        self.assertEqual(result, "test_value")
        
        # Verify Redis cache was used
        mock_redis_cache.get.assert_called_once()
        mock_redis_cache.set.assert_called_once()
        
        # Verify memory cache was not used
        mock_memory_cache.get.assert_not_called()
        mock_memory_cache.set.assert_not_called()
    
    @patch('telegram_bot.utils.caching.redis_cache')
    @patch('telegram_bot.utils.caching.memory_cache')
    @patch('telegram_bot.utils.caching.BotConfig')
    async def test_cached_decorator_memory(self, mock_config, mock_memory_cache, mock_redis_cache):
        """Test cached decorator with memory cache"""
        # Configure mocks
        mock_config.REDIS_URL = ""  # No Redis URL
        mock_redis_cache.redis = None  # Redis not available
        mock_memory_cache.get.return_value = None  # Cache miss
        
        # Create a cached function
        @cached(ttl=60)
        async def test_function(arg1, arg2):
            return f"{arg1}_{arg2}"
        
        # Call the function
        result = await test_function("test", "value")
        
        # Verify result
        self.assertEqual(result, "test_value")
        
        # Verify memory cache was used
        mock_memory_cache.get.assert_called_once()
        mock_memory_cache.set.assert_called_once()
        
        # Verify Redis cache was not used
        mock_redis_cache.get.assert_not_called()
        mock_redis_cache.set.assert_not_called()
    
    @patch('telegram_bot.utils.caching.memory_cache')
    def test_cached_decorator_sync(self, mock_memory_cache):
        """Test cached decorator with synchronous function"""
        # Configure mock
        mock_memory_cache.get.return_value = None  # Cache miss
        
        # Create a cached function
        @cached(ttl=60)
        def test_function(arg1, arg2):
            return f"{arg1}_{arg2}"
        
        # Call the function
        result = test_function("test", "value")
        
        # Verify result
        self.assertEqual(result, "test_value")
        
        # Verify memory cache was used
        mock_memory_cache.get.assert_called_once()
        mock_memory_cache.set.assert_called_once()

if __name__ == '__main__':
    unittest.main()