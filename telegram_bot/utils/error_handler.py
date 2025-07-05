"""Error handling utilities for OPTRIXTRADES Telegram Bot"""

import html
import json
import logging
import traceback
from functools import wraps
from typing import Callable, Dict, Any, Optional, Coroutine

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from config import BotConfig

logger = logging.getLogger(__name__)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors occurring in the dispatcher.
    
    This function provides comprehensive error handling with detailed logging
    and optional admin notifications for critical errors.
    
    Args:
        update: The update that caused the error
        context: The context object containing error information
    """
    # Log the error
    logger.error("Exception while handling an update:", exc_info=context.error)
    
    # Extract traceback info
    tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
    tb_string = ''.join(tb_list)
    
    # Format the error message
    update_str = update.to_dict() if isinstance(update, Update) else str(update)
    message = (
        f"An exception occurred while processing an update:\n"
        f"<pre>update = {html.escape(json.dumps(update_str, indent=2, ensure_ascii=False))}</pre>\n\n"
        f"<pre>context.chat_data = {html.escape(str(context.chat_data))}</pre>\n\n"
        f"<pre>context.user_data = {html.escape(str(context.user_data))}</pre>\n\n"
        f"<pre>{html.escape(tb_string)}</pre>"
    )
    
    # Only send first 4000 characters to avoid Telegram's message size limit
    truncated_message = message[:4000] + "..." if len(message) > 4000 else message
    
    # Notify admin if configured
    if BotConfig.ADMIN_USER_ID and BotConfig.ADMIN_ERROR_NOTIFICATIONS:
        try:
            admin_chat_id = BotConfig.ADMIN_USER_ID
            await context.bot.send_message(
                chat_id=admin_chat_id,
                text=truncated_message,
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.error(f"Failed to send error notification to admin: {e}")
    
    # If the update is a callback query, answer it to prevent the "loading" icon
    if isinstance(update, Update) and update.callback_query:
        try:
            await update.callback_query.answer(
                "An error occurred. Our team has been notified."
            )
        except Exception as e:
            logger.error(f"Failed to answer callback query: {e}")
    
    # If the update has a message, notify the user
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "Sorry, an error occurred while processing your request. "
                "Our team has been notified."
            )
        except Exception as e:
            logger.error(f"Failed to send error message to user: {e}")


def error_handler_decorator(func: Callable) -> Callable:
    """Decorator version of error handler for protecting individual functions.
    
    Args:
        func: The function to protect with error handling
        
    Returns:
        The wrapped function with error handling
    """
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        try:
            return await func(update, context, *args, **kwargs)
        except Exception as e:
            # Log the error
            logger.error(f"Error in {func.__name__}: {e}", exc_info=True)
            
            # Create a mock context with the error for the error handler
            error_context = context
            error_context.error = e
            
            # Call the main error handler
            await error_handler(update, error_context)
            
            # Re-raise the exception if needed
            raise
    
    return wrapper


def register_error_handlers(application) -> None:
    """Register error handlers with the application.
    
    Args:
        application: The telegram application instance
    """
    application.add_error_handler(error_handler)


# Create an alias for the decorator to match the expected usage
# Note: Keep original error_handler function intact for application.add_error_handler()
# Use error_handler_decorator for function decorating


class ErrorLogger:
    """Utility class for structured error logging."""
    
    @staticmethod
    def log_database_error(operation: str, error: Exception, details: Optional[Dict[str, Any]] = None) -> None:
        """Log database operation errors with structured information.
        
        Args:
            operation: The database operation that failed
            error: The exception that occurred
            details: Additional details about the operation
        """
        log_data = {
            "operation": operation,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "details": details or {}
        }
        logger.error(f"Database error: {json.dumps(log_data)}")
    
    @staticmethod
    def log_api_error(endpoint: str, error: Exception, details: Optional[Dict[str, Any]] = None) -> None:
        """Log API call errors with structured information.
        
        Args:
            endpoint: The API endpoint that failed
            error: The exception that occurred
            details: Additional details about the API call
        """
        log_data = {
            "endpoint": endpoint,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "details": details or {}
        }
        logger.error(f"API error: {json.dumps(log_data)}")
    
    @staticmethod
    def log_command_error(command: str, user_id: int, error: Exception, details: Optional[Dict[str, Any]] = None) -> None:
        """Log command execution errors with structured information.
        
        Args:
            command: The command that failed
            user_id: The ID of the user who triggered the command
            error: The exception that occurred
            details: Additional details about the command execution
        """
        log_data = {
            "command": command,
            "user_id": user_id,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "details": details or {}
        }
        logger.error(f"Command error: {json.dumps(log_data)}")