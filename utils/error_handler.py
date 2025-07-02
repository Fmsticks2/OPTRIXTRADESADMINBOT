"""
Comprehensive error handling system for OPTRIXTRADES bot
Provides logging, monitoring, and notification capabilities
"""

import logging
import traceback
import asyncio
import functools
from datetime import datetime
from typing import Optional, Dict, Any, Callable
from telegram.error import TelegramError
from config import config

class ErrorHandler:
    """Centralized error handling and logging system"""
    
    def __init__(self):
        self.logger = logging.getLogger('error_handler')
        self.error_count = 0
        self.last_error_time = None
        self.setup_logging()
    
    def setup_logging(self):
        """Setup comprehensive logging configuration"""
        # Create formatters
        detailed_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
        )
        
        simple_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
        
        # File handler for errors
        if config.ENABLE_FILE_LOGGING:
            error_file_handler = logging.FileHandler('errors.log')
            error_file_handler.setLevel(logging.ERROR)
            error_file_handler.setFormatter(detailed_formatter)
            self.logger.addHandler(error_file_handler)
        
        # Console handler
        if config.ENABLE_CONSOLE_LOGGING:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.WARNING)
            console_handler.setFormatter(simple_formatter)
            self.logger.addHandler(console_handler)
        
        self.logger.setLevel(logging.DEBUG)
    
    def log_error(self, error: Exception, context: str = "", user_id: Optional[int] = None, extra_data: Optional[Dict] = None):
        """Log error with comprehensive details"""
        try:
            self.error_count += 1
            self.last_error_time = datetime.now()
            
            error_details = {
                'error_type': type(error).__name__,
                'error_message': str(error),
                'context': context,
                'user_id': user_id,
                'timestamp': self.last_error_time.isoformat(),
                'stack_trace': traceback.format_exc(),
                'extra_data': extra_data or {}
            }
            
            # Log to file/console
            self.logger.error(
                f"Error in {context}: {error_details['error_type']} - {error_details['error_message']}"
            )
            self.logger.debug(f"Full error details: {error_details}")
            
            # Store in database if available
            asyncio.create_task(self._store_error_in_db(error_details))
            
            # Send notification for critical errors
            if self._is_critical_error(error):
                asyncio.create_task(self._notify_admin_critical_error(error_details))
            
        except Exception as e:
            # Fallback logging if error handler itself fails
            print(f"Error handler failed: {e}")
            print(f"Original error: {error}")
    
    async def _store_error_in_db(self, error_details: Dict[str, Any]):
        """Store error details in database"""
        try:
            from database import db_manager
            
            if db_manager.db_type == 'postgresql':
                query = """
                    INSERT INTO error_logs (error_type, error_message, stack_trace, context, user_id, extra_data)
                    VALUES ($1, $2, $3, $4, $5, $6)
                """
                params = (
                    error_details['error_type'],
                    error_details['error_message'],
                    error_details['stack_trace'],
                    error_details['context'],
                    error_details['user_id'],
                    str(error_details['extra_data'])
                )
            else:
                query = """
                    INSERT INTO error_logs (error_type, error_message, stack_trace, context, user_id, extra_data)
                    VALUES (?, ?, ?, ?, ?, ?)
                """
                params = (
                    error_details['error_type'],
                    error_details['error_message'],
                    error_details['stack_trace'],
                    error_details['context'],
                    error_details['user_id'],
                    str(error_details['extra_data'])
                )
            
            await db_manager.execute_query(query, params)
            
        except Exception as e:
            self.logger.error(f"Failed to store error in database: {e}")
    
    def _is_critical_error(self, error: Exception) -> bool:
        """Determine if error is critical and requires immediate attention"""
        critical_errors = [
            'DatabaseError',
            'ConnectionError',
            'TimeoutError',
            'MemoryError',
            'SystemExit',
            'KeyboardInterrupt'
        ]
        
        return (
            type(error).__name__ in critical_errors or
            'database' in str(error).lower() or
            'connection' in str(error).lower() or
            'timeout' in str(error).lower()
        )
    
    async def _notify_admin_critical_error(self, error_details: Dict[str, Any]):
        """Notify admin of critical errors"""
        try:
            if not config.ERROR_NOTIFICATION_ENABLED:
                return
            
            from telegram import Bot
            bot = Bot(token=config.BOT_TOKEN)
            
            error_message = f"""🚨 **CRITICAL ERROR ALERT**

**Type:** {error_details['error_type']}
**Context:** {error_details['context']}
**Time:** {error_details['timestamp']}
**User ID:** {error_details.get('user_id', 'N/A')}

**Message:** {error_details['error_message'][:500]}

**Error Count:** {self.error_count}
**Last Error:** {self.last_error_time}

Check logs for full details."""

            await bot.send_message(
                chat_id=config.ADMIN_USER_ID,
                text=error_message,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            self.logger.error(f"Failed to notify admin of error: {e}")

    def handle_telegram_error(self, error: TelegramError, context: str = "", user_id: Optional[int] = None):
        """Handle Telegram-specific errors"""
        error_mapping = {
            'Bad Request: chat not found': 'User blocked the bot or chat deleted',
            'Forbidden: bot was blocked by the user': 'User blocked the bot',
            'Bad Request: message is not modified': 'Attempted to edit message with same content',
            'Bad Request: query is too old': 'Callback query expired',
            'Too Many Requests': 'Rate limited by Telegram',
        }
        
        error_description = error_mapping.get(str(error), str(error))
        
        self.logger.warning(
            f"Telegram Error in {context}: {error_description} (User: {user_id})"
        )
        
        return error_description

def error_handler(context: str = ""):
    """Decorator for automatic error handling"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                error_handler_instance.log_error(
                    error=e,
                    context=context or func.__name__,
                    extra_data={'args': str(args), 'kwargs': str(kwargs)}
                )
                raise
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                error_handler_instance.log_error(
                    error=e,
                    context=context or func.__name__,
                    extra_data={'args': str(args), 'kwargs': str(kwargs)}
                )
                raise
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator

def safe_execute(func: Callable, *args, **kwargs) -> tuple[bool, Any]:
    """Safely execute a function and return success status and result"""
    try:
        result = func(*args, **kwargs)
        return True, result
    except Exception as e:
        error_handler_instance.log_error(
            error=e,
            context=f"safe_execute: {func.__name__}",
            extra_data={'args': str(args), 'kwargs': str(kwargs)}
        )
        return False, None

async def safe_execute_async(func: Callable, *args, **kwargs) -> tuple[bool, Any]:
    """Safely execute an async function and return success status and result"""
    try:
        result = await func(*args, **kwargs)
        return True, result
    except Exception as e:
        error_handler_instance.log_error(
            error=e,
            context=f"safe_execute_async: {func.__name__}",
            extra_data={'args': str(args), 'kwargs': str(kwargs)}
        )
        return False, None

# Global error handler instance
error_handler_instance = ErrorHandler()
