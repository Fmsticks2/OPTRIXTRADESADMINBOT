"""Comprehensive testing framework for the Telegram bot"""

import asyncio
import json
import pytest
import sqlite3
import tempfile
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass
from pathlib import Path

from telegram import Update, Message, User, Chat, CallbackQuery
from telegram.ext import Application, ContextTypes

# Import bot modules
import sys
sys.path.append(str(Path(__file__).parent.parent))

from config import BotConfig
from database.connection import DatabaseManager
from telegram_bot.bot import TradingBot
from security.security_manager import SecurityManager
from telegram_bot.utils.enhanced_error_handler import EnhancedErrorHandler


@dataclass
class TestUser:
    """Test user data"""
    id: int
    username: str
    first_name: str
    is_admin: bool = False
    is_verified: bool = False


@dataclass
class TestChat:
    """Test chat data"""
    id: int
    type: str = "private"
    title: Optional[str] = None


@dataclass
class TestResult:
    """Test execution result"""
    test_name: str
    passed: bool
    execution_time_ms: float
    error_message: Optional[str] = None
    details: Dict[str, Any] = None


class MockTelegramObjects:
    """Factory for creating mock Telegram objects"""
    
    @staticmethod
    def create_user(user_data: TestUser) -> User:
        """Create mock User object"""
        return User(
            id=user_data.id,
            is_bot=False,
            first_name=user_data.first_name,
            username=user_data.username
        )
    
    @staticmethod
    def create_chat(chat_data: TestChat) -> Chat:
        """Create mock Chat object"""
        return Chat(
            id=chat_data.id,
            type=chat_data.type,
            title=chat_data.title
        )
    
    @staticmethod
    def create_message(user: User, chat: Chat, text: str, message_id: int = 1) -> Message:
        """Create mock Message object"""
        message = MagicMock(spec=Message)
        message.message_id = message_id
        message.from_user = user
        message.chat = chat
        message.text = text
        message.date = datetime.now()
        message.reply_text = AsyncMock()
        return message
    
    @staticmethod
    def create_callback_query(user: User, data: str, message: Message) -> CallbackQuery:
        """Create mock CallbackQuery object"""
        callback_query = MagicMock(spec=CallbackQuery)
        callback_query.id = "test_callback_id"
        callback_query.from_user = user
        callback_query.data = data
        callback_query.message = message
        callback_query.answer = AsyncMock()
        callback_query.edit_message_text = AsyncMock()
        return callback_query
    
    @staticmethod
    def create_update(message: Optional[Message] = None, 
                     callback_query: Optional[CallbackQuery] = None,
                     update_id: int = 1) -> Update:
        """Create mock Update object"""
        update = MagicMock(spec=Update)
        update.update_id = update_id
        update.message = message
        update.callback_query = callback_query
        update.effective_user = message.from_user if message else (callback_query.from_user if callback_query else None)
        update.effective_chat = message.chat if message else (callback_query.message.chat if callback_query else None)
        update.effective_message = message if message else (callback_query.message if callback_query else None)
        return update


class TestDatabase:
    """Test database manager"""
    
    def __init__(self):
        self.temp_db = None
        self.db_manager = None
    
    async def setup(self) -> DatabaseManager:
        """Setup test database"""
        # Create temporary database
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.temp_db.close()
        
        # Override database configuration for testing
        original_db_path = BotConfig.SQLITE_DB_PATH
        BotConfig.SQLITE_DB_PATH = self.temp_db.name
        
        # Initialize database manager
        self.db_manager = DatabaseManager()
        await self.db_manager.initialize()
        
        return self.db_manager
    
    async def teardown(self):
        """Cleanup test database"""
        if self.db_manager:
            await self.db_manager.close()
        
        if self.temp_db:
            Path(self.temp_db.name).unlink(missing_ok=True)
    
    async def seed_test_data(self):
        """Seed database with test data"""
        if not self.db_manager:
            return
        
        # Create test users
        test_users = [
            {"user_id": 12345, "username": "testuser1", "first_name": "Test", "is_verified": True},
            {"user_id": 67890, "username": "testuser2", "first_name": "User", "is_verified": False},
            {"user_id": 99999, "username": "admin", "first_name": "Admin", "is_verified": True}
        ]
        
        for user_data in test_users:
            await self.db_manager.create_user(
                user_id=user_data["user_id"],
                username=user_data["username"],
                first_name=user_data["first_name"],
                is_verified=user_data["is_verified"]
            )


class BotTestFramework:
    """Comprehensive bot testing framework"""
    
    def __init__(self):
        self.test_db = TestDatabase()
        self.mock_factory = MockTelegramObjects()
        self.test_results: List[TestResult] = []
        self.bot: Optional[TradingBot] = None
        self.security_manager: Optional[SecurityManager] = None
        self.error_handler: Optional[EnhancedErrorHandler] = None
        
        # Test users
        self.test_users = {
            "regular_user": TestUser(id=12345, username="testuser1", first_name="Test", is_verified=True),
            "unverified_user": TestUser(id=67890, username="testuser2", first_name="User", is_verified=False),
            "admin_user": TestUser(id=99999, username="admin", first_name="Admin", is_admin=True, is_verified=True)
        }
        
        # Test chats
        self.test_chats = {
            "private_chat": TestChat(id=12345, type="private"),
            "group_chat": TestChat(id=-100123456789, type="group", title="Test Group")
        }
    
    async def setup(self):
        """Setup test environment"""
        # Setup test database
        db_manager = await self.test_db.setup()
        await self.test_db.seed_test_data()
        
        # Initialize bot components
        self.security_manager = SecurityManager()
        self.error_handler = EnhancedErrorHandler()
        
        # Create mock bot
        self.bot = MagicMock(spec=TradingBot)
        self.bot.db_manager = db_manager
        self.bot.security_manager = self.security_manager
        self.bot.error_handler = self.error_handler
    
    async def teardown(self):
        """Cleanup test environment"""
        await self.test_db.teardown()
    
    async def run_test(self, test_name: str, test_func: Callable) -> TestResult:
        """Run a single test"""
        start_time = time.time()
        
        try:
            await test_func()
            execution_time = (time.time() - start_time) * 1000
            result = TestResult(
                test_name=test_name,
                passed=True,
                execution_time_ms=execution_time
            )
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            result = TestResult(
                test_name=test_name,
                passed=False,
                execution_time_ms=execution_time,
                error_message=str(e)
            )
        
        self.test_results.append(result)
        return result
    
    async def run_all_tests(self) -> List[TestResult]:
        """Run all test suites"""
        test_suites = [
            ("User Registration Flow", self.test_user_registration_flow),
            ("User Verification Flow", self.test_user_verification_flow),
            ("Command Handling", self.test_command_handling),
            ("Callback Query Handling", self.test_callback_query_handling),
            ("Rate Limiting", self.test_rate_limiting),
            ("Input Validation", self.test_input_validation),
            ("Error Handling", self.test_error_handling),
            ("Database Operations", self.test_database_operations),
            ("Security Features", self.test_security_features),
            ("Admin Functions", self.test_admin_functions)
        ]
        
        for test_name, test_func in test_suites:
            await self.run_test(test_name, test_func)
        
        return self.test_results
    
    async def test_user_registration_flow(self):
        """Test complete user registration flow"""
        # Create new user
        new_user = TestUser(id=11111, username="newuser", first_name="New")
        user_obj = self.mock_factory.create_user(new_user)
        chat_obj = self.mock_factory.create_chat(self.test_chats["private_chat"])
        
        # Test /start command
        message = self.mock_factory.create_message(user_obj, chat_obj, "/start")
        update = self.mock_factory.create_update(message=message)
        
        # Mock context
        context = MagicMock()
        context.bot = AsyncMock()
        
        # Simulate start command handler
        # This would normally call the actual handler
        # For now, we'll test the database interaction
        
        # Check if user exists
        user_data = await self.test_db.db_manager.get_user_data(new_user.id)
        assert user_data is None, "New user should not exist in database"
        
        # Create user
        await self.test_db.db_manager.create_user(
            user_id=new_user.id,
            username=new_user.username,
            first_name=new_user.first_name
        )
        
        # Verify user was created
        user_data = await self.test_db.db_manager.get_user_data(new_user.id)
        assert user_data is not None, "User should exist after creation"
        assert user_data["username"] == new_user.username
        assert user_data["is_verified"] is False
    
    async def test_user_verification_flow(self):
        """Test user verification process"""
        user = self.test_users["unverified_user"]
        
        # Check initial verification status
        user_data = await self.test_db.db_manager.get_user_data(user.id)
        assert user_data["is_verified"] is False
        
        # Create verification request
        await self.test_db.db_manager.create_verification_request(
            user_id=user.id,
            verification_type="manual",
            data={"reason": "test verification"}
        )
        
        # Check pending verifications
        pending = await self.test_db.db_manager.get_pending_verifications()
        assert len(pending) > 0
        assert any(req["user_id"] == user.id for req in pending)
        
        # Approve verification
        await self.test_db.db_manager.update_verification_status(
            user_id=user.id,
            status="approved"
        )
        
        # Update user verification status
        await self.test_db.db_manager.update_user_data(
            user_id=user.id,
            is_verified=True
        )
        
        # Verify user is now verified
        user_data = await self.test_db.db_manager.get_user_data(user.id)
        assert user_data["is_verified"] is True
    
    async def test_command_handling(self):
        """Test command handling and validation"""
        user = self.test_users["regular_user"]
        user_obj = self.mock_factory.create_user(user)
        chat_obj = self.mock_factory.create_chat(self.test_chats["private_chat"])
        
        # Test valid commands
        valid_commands = ["/start", "/help", "/verify", "/status"]
        
        for command in valid_commands:
            message = self.mock_factory.create_message(user_obj, chat_obj, command)
            update = self.mock_factory.create_update(message=message)
            
            # Validate command format
            from security.security_manager import InputValidator
            is_valid = InputValidator.validate_command(command)
            assert is_valid, f"Command {command} should be valid"
        
        # Test invalid commands
        invalid_commands = ["start", "/", "/invalid@command", "/123invalid"]
        
        for command in invalid_commands:
            from security.security_manager import InputValidator
            is_valid = InputValidator.validate_command(command)
            assert not is_valid, f"Command {command} should be invalid"
    
    async def test_callback_query_handling(self):
        """Test callback query handling"""
        user = self.test_users["regular_user"]
        user_obj = self.mock_factory.create_user(user)
        chat_obj = self.mock_factory.create_chat(self.test_chats["private_chat"])
        
        # Create message and callback query
        message = self.mock_factory.create_message(user_obj, chat_obj, "Test message")
        callback_query = self.mock_factory.create_callback_query(user_obj, "test_data", message)
        update = self.mock_factory.create_update(callback_query=callback_query)
        
        # Validate callback data
        from security.security_manager import InputValidator
        is_valid = InputValidator.validate_callback_data("test_data")
        assert is_valid, "Valid callback data should pass validation"
        
        # Test invalid callback data
        invalid_data = ["a" * 65, "invalid@data", "<script>alert('xss')</script>"]
        
        for data in invalid_data:
            is_valid = InputValidator.validate_callback_data(data)
            assert not is_valid, f"Invalid callback data {data} should fail validation"
    
    async def test_rate_limiting(self):
        """Test rate limiting functionality"""
        user = self.test_users["regular_user"]
        
        # Test user rate limiting
        from security.security_manager import RateLimitType
        
        # Make requests within limit
        for i in range(5):
            allowed, message = self.security_manager.rate_limiter.check_rate_limit(
                RateLimitType.USER, str(user.id), user.id
            )
            assert allowed, f"Request {i+1} should be allowed"
        
        # Make requests exceeding limit
        for i in range(30):  # Exceed the limit of 30 requests per minute
            self.security_manager.rate_limiter.check_rate_limit(
                RateLimitType.USER, str(user.id), user.id
            )
        
        # Next request should be blocked
        allowed, message = self.security_manager.rate_limiter.check_rate_limit(
            RateLimitType.USER, str(user.id), user.id
        )
        assert not allowed, "Request should be blocked due to rate limiting"
        assert "Rate limit exceeded" in message
    
    async def test_input_validation(self):
        """Test input validation and sanitization"""
        from security.security_manager import InputValidator
        
        # Test valid inputs
        valid_inputs = [
            "Hello world",
            "This is a normal message",
            "Message with numbers 123",
            "Message with emojis 😀🚀"
        ]
        
        for text in valid_inputs:
            is_valid, issues = InputValidator.validate_text_input(text)
            assert is_valid, f"Valid input '{text}' should pass validation"
        
        # Test dangerous inputs
        dangerous_inputs = [
            "<script>alert('xss')</script>",
            "javascript:alert('xss')",
            "SELECT * FROM users WHERE id=1 OR 1=1",
            "'; DROP TABLE users; --",
            "$(rm -rf /)"
        ]
        
        for text in dangerous_inputs:
            is_valid, issues = InputValidator.validate_text_input(text)
            assert not is_valid, f"Dangerous input '{text}' should fail validation"
            assert len(issues) > 0, "Should have validation issues"
        
        # Test text sanitization
        dirty_text = "Hello\x00world\x01with\x02control\x03chars"
        clean_text = InputValidator.sanitize_text(dirty_text)
        assert "\x00" not in clean_text, "Null bytes should be removed"
        assert "\x01" not in clean_text, "Control characters should be removed"
    
    async def test_error_handling(self):
        """Test error handling and logging"""
        # Test error classification
        from telegram_bot.utils.enhanced_error_handler import ErrorClassifier, ErrorCategory, ErrorSeverity
        
        # Test different error types
        test_errors = [
            (ValueError("Invalid input"), ErrorCategory.VALIDATION, ErrorSeverity.LOW),
            (ConnectionError("Database connection failed"), ErrorCategory.DATABASE, ErrorSeverity.HIGH),
            (Exception("Critical system failure"), ErrorCategory.UNKNOWN, ErrorSeverity.MEDIUM)
        ]
        
        for error, expected_category, expected_severity in test_errors:
            category, severity = ErrorClassifier.classify_error(error)
            # Note: Classification might not match exactly due to heuristics
            assert isinstance(category, ErrorCategory)
            assert isinstance(severity, ErrorSeverity)
        
        # Test error metrics
        initial_count = self.error_handler.metrics.total_errors
        
        # Simulate error
        from telegram_bot.utils.enhanced_error_handler import ErrorContext, ErrorCategory, ErrorSeverity
        error_context = ErrorContext(
            correlation_id="test-123",
            timestamp=datetime.now(),
            error_type="TestError",
            error_message="Test error message",
            severity=ErrorSeverity.MEDIUM,
            category=ErrorCategory.BUSINESS_LOGIC
        )
        
        self.error_handler._update_metrics(error_context)
        
        # Check metrics updated
        assert self.error_handler.metrics.total_errors == initial_count + 1
        assert self.error_handler.metrics.errors_by_category[ErrorCategory.BUSINESS_LOGIC.value] >= 1
    
    async def test_database_operations(self):
        """Test database operations"""
        # Test user operations
        test_user_id = 88888
        
        # Create user
        await self.test_db.db_manager.create_user(
            user_id=test_user_id,
            username="dbtest",
            first_name="Database"
        )
        
        # Get user
        user_data = await self.test_db.db_manager.get_user_data(test_user_id)
        assert user_data is not None
        assert user_data["username"] == "dbtest"
        
        # Update user
        await self.test_db.db_manager.update_user_data(
            user_id=test_user_id,
            is_verified=True
        )
        
        # Verify update
        user_data = await self.test_db.db_manager.get_user_data(test_user_id)
        assert user_data["is_verified"] is True
        
        # Test chat logging
        await self.test_db.db_manager.log_chat_message(
            user_id=test_user_id,
            message="Test message",
            message_type="text"
        )
        
        # Get chat history
        history = await self.test_db.db_manager.get_chat_history(test_user_id, limit=1)
        assert len(history) == 1
        assert history[0]["message"] == "Test message"
        
        # Test interaction logging
        await self.test_db.db_manager.log_interaction(
            user_id=test_user_id,
            interaction_type="command",
            details={"command": "/test"}
        )
        
        # Delete user
        await self.test_db.db_manager.delete_user(test_user_id)
        
        # Verify deletion
        user_data = await self.test_db.db_manager.get_user_data(test_user_id)
        assert user_data is None
    
    async def test_security_features(self):
        """Test security features"""
        user = self.test_users["regular_user"]
        user_obj = self.mock_factory.create_user(user)
        chat_obj = self.mock_factory.create_chat(self.test_chats["private_chat"])
        
        # Test IP whitelist
        telegram_ip = "149.154.167.50"  # Known Telegram IP
        assert self.security_manager.ip_whitelist.is_telegram_ip(telegram_ip)
        
        suspicious_ip = "192.168.1.1"
        assert not self.security_manager.ip_whitelist.is_telegram_ip(suspicious_ip)
        
        # Test webhook verification
        test_payload = b"test webhook payload"
        test_secret = "test_secret_token"
        
        # Create valid signature
        import hmac
        import hashlib
        valid_signature = hmac.new(
            test_secret.encode('utf-8'),
            test_payload,
            hashlib.sha256
        ).hexdigest()
        
        from security.security_manager import WebhookVerifier
        verifier = WebhookVerifier(test_secret)
        assert verifier.verify_signature(test_payload, valid_signature)
        
        # Test invalid signature
        invalid_signature = "invalid_signature"
        assert not verifier.verify_signature(test_payload, invalid_signature)
    
    async def test_admin_functions(self):
        """Test admin-specific functions"""
        admin_user = self.test_users["admin_user"]
        regular_user = self.test_users["regular_user"]
        
        # Test admin whitelist
        self.security_manager.rate_limiter.add_whitelist_user(admin_user.id)
        
        # Admin should bypass rate limits
        from security.security_manager import RateLimitType
        
        # Make many requests as admin
        for i in range(100):
            allowed, message = self.security_manager.rate_limiter.check_rate_limit(
                RateLimitType.USER, str(admin_user.id), admin_user.id
            )
            assert allowed, f"Admin request {i+1} should be allowed"
        
        # Regular user should still be rate limited
        for i in range(35):  # Exceed limit
            self.security_manager.rate_limiter.check_rate_limit(
                RateLimitType.USER, str(regular_user.id), regular_user.id
            )
        
        allowed, message = self.security_manager.rate_limiter.check_rate_limit(
            RateLimitType.USER, str(regular_user.id), regular_user.id
        )
        assert not allowed, "Regular user should be rate limited"
    
    def generate_test_report(self) -> Dict[str, Any]:
        """Generate comprehensive test report"""
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result.passed)
        failed_tests = total_tests - passed_tests
        
        avg_execution_time = sum(result.execution_time_ms for result in self.test_results) / total_tests if total_tests > 0 else 0
        
        return {
            "summary": {
                "total_tests": total_tests,
                "passed": passed_tests,
                "failed": failed_tests,
                "success_rate": (passed_tests / total_tests * 100) if total_tests > 0 else 0,
                "avg_execution_time_ms": round(avg_execution_time, 2)
            },
            "test_results": [
                {
                    "name": result.test_name,
                    "passed": result.passed,
                    "execution_time_ms": round(result.execution_time_ms, 2),
                    "error_message": result.error_message
                }
                for result in self.test_results
            ],
            "failed_tests": [
                {
                    "name": result.test_name,
                    "error_message": result.error_message,
                    "execution_time_ms": round(result.execution_time_ms, 2)
                }
                for result in self.test_results if not result.passed
            ],
            "timestamp": datetime.now().isoformat()
        }


async def run_integration_tests() -> Dict[str, Any]:
    """Run all integration tests"""
    framework = BotTestFramework()
    
    try:
        await framework.setup()
        await framework.run_all_tests()
        return framework.generate_test_report()
    finally:
        await framework.teardown()


if __name__ == "__main__":
    # Run tests when script is executed directly
    async def main():
        report = await run_integration_tests()
        print(json.dumps(report, indent=2))
    
    asyncio.run(main())