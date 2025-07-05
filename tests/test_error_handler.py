import unittest
import logging
from unittest.mock import patch, MagicMock
import asyncio
from telegram import Update
from telegram.ext import ContextTypes

# Import both error handlers to test
from telegram_bot.utils.error_handler import error_handler as telegram_error_handler
from utils.error_handler import ErrorHandler, error_handler as utils_error_handler

class TestErrorHandlers(unittest.TestCase):
    """Test suite for error handling utilities"""
    
    def setUp(self):
        # Set up logging for tests
        self.logger = logging.getLogger('test_logger')
        self.logger.setLevel(logging.DEBUG)
        # Use a string IO handler to capture log output
        self.log_capture = MagicMock()
        self.logger.addHandler(self.log_capture)
    
    @patch('telegram_bot.utils.error_handler.logger')
    async def test_telegram_error_handler(self, mock_logger):
        """Test the telegram bot error handler functionality"""
        # Create mock update and context
        mock_update = MagicMock(spec=Update)
        mock_update.to_dict.return_value = {"update_id": 123456789}
        mock_update.callback_query = MagicMock()
        mock_update.effective_message = MagicMock()
        
        mock_context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
        mock_error = Exception("Test error")
        mock_context.error = mock_error
        mock_context.chat_data = {"test": "data"}
        mock_context.user_data = {"user": "data"}
        
        # Call the error handler
        await telegram_error_handler(mock_update, mock_context)
        
        # Verify logger was called
        mock_logger.error.assert_called_once()
        
        # Verify callback query was answered
        mock_update.callback_query.answer.assert_called_once()
        
        # Verify message was sent to user
        mock_update.effective_message.reply_text.assert_called_once()
    
    @patch('utils.error_handler.logging')
    def test_utils_error_handler_class(self, mock_logging):
        """Test the utils ErrorHandler class functionality"""
        # Create an instance of ErrorHandler
        error_handler = ErrorHandler()
        
        # Test log_error method
        test_error = Exception("Test error")
        error_handler.log_error(test_error, "test_context", 12345)
        
        # Verify error was logged
        self.assertEqual(error_handler.error_count, 1)
        self.assertIsNotNone(error_handler.last_error_time)
    
    @patch('utils.error_handler.error_handler_instance')
    def test_error_handler_decorator(self, mock_error_handler_instance):
        """Test the error handler decorator functionality"""
        # Create a function to decorate
        @utils_error_handler("test_context")
        def test_function():
            raise ValueError("Test error")
        
        # Call the decorated function and expect it to raise
        with self.assertRaises(ValueError):
            test_function()
        
        # Verify error was logged
        mock_error_handler_instance.log_error.assert_called_once()
        args, kwargs = mock_error_handler_instance.log_error.call_args
        self.assertEqual(kwargs['context'], 'test_context')
        self.assertIsInstance(args[0], ValueError)

    @patch('utils.error_handler.error_handler_instance')
    async def test_safe_execute_async(self, mock_error_handler_instance):
        """Test the safe_execute_async function"""
        from utils.error_handler import safe_execute_async
        
        # Test with a successful async function
        async def success_func():
            return "success"
        
        success, result = await safe_execute_async(success_func)
        self.assertTrue(success)
        self.assertEqual(result, "success")
        
        # Test with a failing async function
        async def fail_func():
            raise ValueError("Async error")
        
        success, result = await safe_execute_async(fail_func)
        self.assertFalse(success)
        self.assertIsNone(result)
        mock_error_handler_instance.log_error.assert_called_once()

if __name__ == '__main__':
    unittest.main()