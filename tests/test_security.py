import unittest
import asyncio
import logging
from unittest.mock import patch, MagicMock, AsyncMock
import time
from datetime import datetime

from telegram import Update, User, Message, Chat
from telegram.ext import ContextTypes

from telegram_bot.utils.security import RateLimiter, SecurityUtils, rate_limit, admin_only

class TestSecurity(unittest.TestCase):
    """Test suite for security utilities"""
    
    def setUp(self):
        # Set up logging for tests
        self.logger = logging.getLogger('test_logger')
        self.logger.setLevel(logging.DEBUG)
        # Use a string IO handler to capture log output
        self.log_capture = MagicMock()
        self.logger.addHandler(self.log_capture)
    
    def test_rate_limiter(self):
        """Test rate limiting functionality"""
        rate_limiter = RateLimiter()
        
        # Test with rate limiting enabled
        with patch('telegram_bot.utils.security.BotConfig') as mock_config:
            mock_config.RATE_LIMIT_ENABLED = True
            mock_config.MAX_REQUESTS_PER_MINUTE = 5
            
            # User should not be rate limited initially
            self.assertFalse(rate_limiter.is_rate_limited(12345))
            
            # Make multiple requests
            for _ in range(4):  # 5 total with the one above
                self.assertFalse(rate_limiter.is_rate_limited(12345))
            
            # Next request should be rate limited
            self.assertTrue(rate_limiter.is_rate_limited(12345))
            
            # Different user should not be rate limited
            self.assertFalse(rate_limiter.is_rate_limited(67890))
        
        # Test with rate limiting disabled
        with patch('telegram_bot.utils.security.BotConfig') as mock_config:
            mock_config.RATE_LIMIT_ENABLED = False
            
            # User should not be rate limited even after many requests
            for _ in range(10):
                self.assertFalse(rate_limiter.is_rate_limited(12345))
    
    def test_block_user(self):
        """Test user blocking functionality"""
        rate_limiter = RateLimiter()
        
        # Block a user
        rate_limiter.block_user(12345, 0.01)  # Very short duration for testing
        
        # User should be rate limited
        self.assertTrue(rate_limiter.is_rate_limited(12345))
        
        # Wait for unblock
        time.sleep(0.02)  # Slightly longer than block duration
        
        # User should no longer be rate limited
        self.assertFalse(rate_limiter.is_rate_limited(12345))
    
    def test_suspicious_patterns(self):
        """Test suspicious pattern detection"""
        rate_limiter = RateLimiter()
        
        # Test with suspicious pattern detection enabled
        with patch('telegram_bot.utils.security.BotConfig') as mock_config:
            mock_config.BLOCK_SUSPICIOUS_PATTERNS = True
            
            # Test various suspicious patterns
            self.assertTrue(rate_limiter.is_suspicious("DROP TABLE users"))
            self.assertTrue(rate_limiter.is_suspicious("SELECT * FROM users WHERE 1=1"))
            self.assertTrue(rate_limiter.is_suspicious("<script>alert('XSS')</script>"))
            self.assertTrue(rate_limiter.is_suspicious("../../../etc/passwd"))
            self.assertTrue(rate_limiter.is_suspicious("exec('rm -rf /')"))
            
            # Test normal text
            self.assertFalse(rate_limiter.is_suspicious("Hello, how are you?"))
            self.assertFalse(rate_limiter.is_suspicious("I need help with verification"))
            self.assertFalse(rate_limiter.is_suspicious("My UID is 12345"))
        
        # Test with suspicious pattern detection disabled
        with patch('telegram_bot.utils.security.BotConfig') as mock_config:
            mock_config.BLOCK_SUSPICIOUS_PATTERNS = False
            
            # Even suspicious patterns should not be detected
            self.assertFalse(rate_limiter.is_suspicious("DROP TABLE users"))
    
    def test_security_utils_hmac(self):
        """Test HMAC generation and verification"""
        # Generate HMAC
        data = "test_data"
        secret = "test_secret"
        signature = SecurityUtils.generate_hmac(data, secret)
        
        # Verify valid HMAC
        self.assertTrue(SecurityUtils.verify_hmac(data, signature, secret))
        
        # Verify invalid HMAC
        self.assertFalse(SecurityUtils.verify_hmac(data, "invalid_signature", secret))
        self.assertFalse(SecurityUtils.verify_hmac("different_data", signature, secret))
        self.assertFalse(SecurityUtils.verify_hmac(data, signature, "different_secret"))
    
    def test_security_utils_password(self):
        """Test password hashing and verification"""
        # Hash password
        password = "secure_password"
        hashed, salt = SecurityUtils.hash_password(password)
        
        # Verify correct password
        self.assertTrue(SecurityUtils.verify_password(password, hashed, salt))
        
        # Verify incorrect password
        self.assertFalse(SecurityUtils.verify_password("wrong_password", hashed, salt))
    
    def test_security_utils_sanitize(self):
        """Test input sanitization"""
        # Test sanitization of dangerous input
        dangerous_input = "<script>alert('XSS');</script>"
        sanitized = SecurityUtils.sanitize_input(dangerous_input)
        self.assertNotIn("<script>", sanitized)
        
        # Test length limitation
        long_input = "a" * 2000
        sanitized = SecurityUtils.sanitize_input(long_input)
        self.assertEqual(len(sanitized), 1000)
    
    def test_security_utils_ip_validation(self):
        """Test IP address validation"""
        # Valid IPs
        self.assertTrue(SecurityUtils.is_valid_ip("192.168.1.1"))
        self.assertTrue(SecurityUtils.is_valid_ip("127.0.0.1"))
        self.assertTrue(SecurityUtils.is_valid_ip("::1"))  # IPv6
        
        # Invalid IPs
        self.assertFalse(SecurityUtils.is_valid_ip("256.256.256.256"))
        self.assertFalse(SecurityUtils.is_valid_ip("not_an_ip"))
        self.assertFalse(SecurityUtils.is_valid_ip("192.168.1"))  # Incomplete
    
    def test_security_utils_webhook_validation(self):
        """Test webhook request validation"""
        # Test with token configured
        with patch('telegram_bot.utils.security.BotConfig') as mock_config:
            mock_config.WEBHOOK_SECRET_TOKEN = "secret_token"
            
            # Valid request
            request_data = {"update_id": 123456789}
            headers = {"X-Telegram-Bot-Api-Secret-Token": "secret_token"}
            self.assertTrue(SecurityUtils.validate_webhook_request(request_data, headers))
            
            # Invalid token
            headers = {"X-Telegram-Bot-Api-Secret-Token": "wrong_token"}
            self.assertFalse(SecurityUtils.validate_webhook_request(request_data, headers))
            
            # Missing token
            headers = {}
            self.assertFalse(SecurityUtils.validate_webhook_request(request_data, headers))
        
        # Test with no token configured
        with patch('telegram_bot.utils.security.BotConfig') as mock_config:
            mock_config.WEBHOOK_SECRET_TOKEN = ""
            
            # Any request should be valid
            request_data = {"update_id": 123456789}
            headers = {}
            self.assertTrue(SecurityUtils.validate_webhook_request(request_data, headers))
    
    @patch('telegram_bot.utils.security.rate_limiter')
    async def test_rate_limit_decorator(self, mock_rate_limiter):
        """Test rate_limit decorator"""
        # Create a decorated function
        @rate_limit
        async def test_handler(update, context):
            return "success"
        
        # Create mock update and context
        mock_user = MagicMock(spec=User)
        mock_user.id = 12345
        
        mock_message = MagicMock(spec=Message)
        mock_message.text = "Hello"
        
        mock_update = MagicMock(spec=Update)
        mock_update.effective_user = mock_user
        mock_update.effective_message = mock_message
        
        mock_context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
        
        # Test when user is not rate limited
        mock_rate_limiter.is_rate_limited.return_value = False
        mock_rate_limiter.is_suspicious.return_value = False
        
        result = await test_handler(mock_update, mock_context)
        self.assertEqual(result, "success")
        
        # Test when user is rate limited
        mock_rate_limiter.is_rate_limited.return_value = True
        
        await test_handler(mock_update, mock_context)
        mock_update.effective_message.reply_text.assert_called_once()
        
        # Reset mock
        mock_update.effective_message.reply_text.reset_mock()
        
        # Test when message is suspicious
        mock_rate_limiter.is_rate_limited.return_value = False
        mock_rate_limiter.is_suspicious.return_value = True
        
        await test_handler(mock_update, mock_context)
        mock_update.effective_message.reply_text.assert_called_once()
        mock_rate_limiter.block_user.assert_called_once_with(12345)
    
    @patch('telegram_bot.utils.security.BotConfig')
    async def test_admin_only_decorator(self, mock_config):
        """Test admin_only decorator"""
        # Set admin user ID
        mock_config.ADMIN_USER_ID = "12345"
        
        # Create a decorated function
        @admin_only
        async def test_handler(update, context):
            return "admin_success"
        
        # Create mock update and context
        mock_user = MagicMock(spec=User)
        mock_message = MagicMock(spec=Message)
        mock_update = MagicMock(spec=Update)
        mock_update.effective_message = mock_message
        mock_update.effective_user = mock_user
        mock_context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
        
        # Test with admin user
        mock_user.id = 12345
        
        result = await test_handler(mock_update, mock_context)
        self.assertEqual(result, "admin_success")
        
        # Test with non-admin user
        mock_user.id = 67890
        
        await test_handler(mock_update, mock_context)
        mock_update.effective_message.reply_text.assert_called_once()

if __name__ == '__main__':
    unittest.main()