#!/usr/bin/env python3
"""Test script to verify Forbidden error handling fix"""

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock
from telegram.error import Forbidden
from telegram.ext import ContextTypes, ApplicationBuilder

from config import BotConfig
from telegram_bot.utils.error_handler import error_handler
from telegram_bot.utils.follow_up_scheduler import FollowUpScheduler

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_forbidden_error_handling():
    """Test that Forbidden errors are handled correctly"""
    logger.info("Testing Forbidden error handling...")
    
    # Create mock objects
    mock_bot = AsyncMock()
    mock_bot.token = "test_token"
    
    # Create a mock update with user info
    class MockUpdate:
        def __init__(self, user_id):
            self.effective_user = MagicMock()
            self.effective_user.id = user_id
            self.id = user_id
    
    # Create mock context with Forbidden error
    application = ApplicationBuilder().token("test_token").build()
    context = ContextTypes.DEFAULT_TYPE(application=application)
    context.error = Forbidden("Forbidden: bot was blocked by the user")
    context._user_id = 12345
    
    # Create mock scheduler
    mock_scheduler = AsyncMock()
    mock_scheduler.cancel_follow_ups = AsyncMock()
    
    # Mock the get_follow_up_scheduler function
    import telegram_bot.utils.follow_up_scheduler
    original_get_scheduler = telegram_bot.utils.follow_up_scheduler.get_follow_up_scheduler
    telegram_bot.utils.follow_up_scheduler.get_follow_up_scheduler = lambda: mock_scheduler
    
    try:
        # Test the error handler
        update = MockUpdate(12345)
        await error_handler(update, context)
        
        # Verify that cancel_follow_ups was called
        mock_scheduler.cancel_follow_ups.assert_called_once_with(12345)
        logger.info("✅ Forbidden error handling test passed!")
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        raise
    finally:
        # Restore original function
        telegram_bot.utils.follow_up_scheduler.get_follow_up_scheduler = original_get_scheduler

async def test_follow_up_scheduler_forbidden_handling():
    """Test that FollowUpScheduler handles Forbidden errors correctly"""
    logger.info("Testing FollowUpScheduler Forbidden error handling...")
    
    # Create mock bot
    mock_bot = AsyncMock()
    mock_bot.token = "test_token"
    
    # Create scheduler instance
    scheduler = FollowUpScheduler(mock_bot)
    
    # Mock the cancel_follow_ups method
    scheduler.cancel_follow_ups = AsyncMock()
    
    # Mock handler that raises Forbidden error
    async def mock_handler_function(update, context):
        raise Forbidden("Forbidden: bot was blocked by the user")
    
    # Mock handler getter
    mock_handler_getter = lambda: mock_handler_function
    scheduler.follow_up_handlers = {1: mock_handler_getter}
    
    try:
        # Test _send_follow_up with Forbidden error
        user_data = {'first_name': 'Test', 'username': 'testuser'}
        await scheduler._send_follow_up(12345, 1, user_data)
        
        # Verify that cancel_follow_ups was called
        scheduler.cancel_follow_ups.assert_called_once_with(12345)
        logger.info("✅ FollowUpScheduler Forbidden error handling test passed!")
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        raise

async def main():
    """Run all tests"""
    logger.info("Starting Forbidden error handling tests...")
    
    try:
        await test_forbidden_error_handling()
        await test_follow_up_scheduler_forbidden_handling()
        logger.info("\n🎉 All tests passed! Forbidden error handling is working correctly.")
        
    except Exception as e:
        logger.error(f"\n💥 Tests failed: {e}")
        return False
    
    return True

if __name__ == "__main__":
    asyncio.run(main())