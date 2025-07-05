import unittest
import asyncio
import logging
from unittest.mock import patch, MagicMock, AsyncMock
import os
import sys
import sqlite3
import tempfile

# Add project root to path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.error_handler import ErrorHandler
from telegram_bot.utils.error_handler import error_handler, register_error_handlers, ErrorLogger

class IntegrationTestErrorHandler(unittest.TestCase):
    """Integration tests for error handling system"""
    
    def setUp(self):
        # Create a temporary database file
        self.db_fd, self.db_path = tempfile.mkstemp()
        
        # Set up a test database
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        
        # Create errors table
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS errors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            error_type TEXT NOT NULL,
            error_message TEXT NOT NULL,
            traceback TEXT,
            context TEXT,
            user_id INTEGER,
            chat_id INTEGER,
            severity TEXT,
            resolved INTEGER DEFAULT 0
        )
        """)
        self.conn.commit()
        
        # Configure test logger
        self.logger = logging.getLogger('test_logger')
        self.logger.setLevel(logging.DEBUG)
        self.log_capture = MagicMock()
        self.logger.addHandler(self.log_capture)
        
        # Create error handler with test database
        self.error_handler = ErrorHandler(
            db_path=self.db_path,
            logger=self.logger,
            notification_enabled=False  # Disable actual notifications
        )
    
    def tearDown(self):
        # Close and remove the temporary database
        self.conn.close()
        os.close(self.db_fd)
        os.unlink(self.db_path)
    
    def test_error_storage_and_retrieval(self):
        """Test that errors are properly stored in the database and can be retrieved"""
        # Log an error
        try:
            raise ValueError("Test error")
        except Exception as e:
            self.error_handler.log_error(
                error=e,
                error_type="ValueError",
                context={"test": True},
                user_id=123456,
                chat_id=123456,
                severity="medium"
            )
        
        # Verify error was stored in database
        self.cursor.execute("SELECT * FROM errors WHERE error_type = 'ValueError'")
        error_record = self.cursor.fetchone()
        
        self.assertIsNotNone(error_record)
        self.assertEqual(error_record[2], "ValueError")
        self.assertEqual(error_record[3], "Test error")
        self.assertIn("test", error_record[5])  # Context should contain test:True
        self.assertEqual(error_record[6], 123456)  # User ID
        self.assertEqual(error_record[7], 123456)  # Chat ID
        self.assertEqual(error_record[8], "medium")  # Severity
    
    @patch('telegram.ext.Application')
    def test_telegram_error_handler_integration(self, mock_application):
        """Test integration between Telegram error handler and error logging system"""
        # Create mock update and context
        mock_update = MagicMock()
        mock_update.effective_user.id = 123456
        mock_update.effective_chat.id = 123456
        
        mock_context = MagicMock()
        mock_error = Exception("Telegram API error")
        mock_context.error = mock_error
        
        # Set up the error handler
        with patch('telegram_bot.utils.error_handler.ErrorLogger') as mock_error_logger:
            # Register error handlers
            register_error_handlers(mock_application)
            
            # Get the error handler function
            error_handler_func = mock_application.add_error_handler.call_args[0][0]
            
            # Call the error handler
            error_handler_func(mock_update, mock_context)
            
            # Verify error was logged
            mock_error_logger.log_telegram_error.assert_called_once_with(
                mock_update, mock_context
            )
    
    @patch('utils.error_handler.ErrorHandler.notify_admins')
    def test_critical_error_notification(self, mock_notify_admins):
        """Test that critical errors trigger admin notifications"""
        # Enable notifications for this test
        self.error_handler.notification_enabled = True
        
        # Log a critical error
        try:
            raise RuntimeError("Critical system error")
        except Exception as e:
            self.error_handler.log_error(
                error=e,
                error_type="RuntimeError",
                context={"system": "core"},
                severity="critical"
            )
        
        # Verify admin notification was triggered
        mock_notify_admins.assert_called_once()
        
        # Verify the notification contains the error message
        notification_message = mock_notify_admins.call_args[0][0]
        self.assertIn("Critical system error", notification_message)
    
    def test_error_handler_decorator(self):
        """Test the error_handler decorator integration with error logging"""
        # Create a test function with the error_handler decorator
        @error_handler
        def test_function(update, context):
            raise ValueError("Decorated function error")
        
        # Create mock update and context
        mock_update = MagicMock()
        mock_update.effective_user.id = 123456
        mock_update.effective_chat.id = 123456
        
        mock_context = MagicMock()
        
        # Set up the error logger
        with patch('telegram_bot.utils.error_handler.ErrorLogger.log_command_error') as mock_log_error:
            # Call the decorated function
            test_function(mock_update, mock_context)
            
            # Verify error was logged
            mock_log_error.assert_called_once()
            
            # Verify the error details
            error = mock_log_error.call_args[0][0]
            self.assertIsInstance(error, ValueError)
            self.assertEqual(str(error), "Decorated function error")
    
    async def test_async_error_handling(self):
        """Test error handling in asynchronous functions"""
        # Create an async function that raises an error
        async def async_error_function():
            raise RuntimeError("Async function error")
        
        # Use safe_execute_async to handle the error
        with patch('utils.error_handler.ErrorHandler.log_error') as mock_log_error:
            from utils.error_handler import safe_execute_async
            
            # Execute the function with error handling
            result = await safe_execute_async(
                async_error_function,
                default_return_value="Error occurred",
                error_context={"async": True}
            )
            
            # Verify the default return value was used
            self.assertEqual(result, "Error occurred")
            
            # Verify error was logged
            mock_log_error.assert_called_once()
            
            # Verify error details
            error = mock_log_error.call_args[1]["error"]
            context = mock_log_error.call_args[1]["context"]
            self.assertIsInstance(error, RuntimeError)
            self.assertEqual(str(error), "Async function error")
            self.assertEqual(context, {"async": True})

if __name__ == '__main__':
    unittest.main()