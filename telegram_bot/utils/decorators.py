"""Utility decorators for OPTRIXTRADES Telegram Bot"""

import functools
import logging
import time
from typing import Callable, Any, Coroutine, TypeVar, cast, Optional

from telegram import Update
from telegram.ext import ContextTypes

from config import BotConfig
from telegram_bot.utils.logger import StructuredLogger

logger = logging.getLogger(__name__)

# Type variable for handler functions
HandlerType = TypeVar('HandlerType', bound=Callable[..., Coroutine[Any, Any, Any]])


def admin_only(func: HandlerType) -> HandlerType:
    """Decorator to restrict handler to admin users only.
    
    Args:
        func: The handler function to decorate
        
    Returns:
        The decorated function that checks for admin privileges
    """
    @functools.wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        if str(user_id) == BotConfig.ADMIN_USER_ID:
            return await func(update, context, *args, **kwargs)
        else:
            if update.callback_query:
                await update.callback_query.answer("⛔ You are not authorized to use this feature.")
            else:
                await update.effective_message.reply_text("⛔ You are not authorized to use this command.")
            return None
    return cast(HandlerType, wrapped)


def verified_only(func: HandlerType) -> HandlerType:
    """Decorator to restrict handler to verified users only.
    
    Args:
        func: The handler function to decorate
        
    Returns:
        The decorated function that checks for verification status
    """
    @functools.wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        
        # This would check the database for verification status
        # For now, just a placeholder
        is_verified = False  # Replace with actual verification check
        
        if is_verified:
            return await func(update, context, *args, **kwargs)
        else:
            if update.callback_query:
                await update.callback_query.answer("🔒 This feature is only available to verified users.")
                await update.callback_query.message.reply_text(
                    "Your account needs to be verified to access this feature. "
                    "Use /verify to start the verification process."
                )
            else:
                await update.effective_message.reply_text(
                    "🔒 This command is only available to verified users. "
                    "Use /verify to start the verification process."
                )
            return None
    return cast(HandlerType, wrapped)


def log_command(func: HandlerType) -> HandlerType:
    """Decorator to log command usage.
    
    Args:
        func: The handler function to decorate
        
    Returns:
        The decorated function that logs command usage
    """
    @functools.wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        command = update.effective_message.text if update.effective_message else "Unknown command"
        
        StructuredLogger.log_user_action(
            user_id=user.id,
            action="command",
            details={
                "command": command,
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name
            }
        )
        
        return await func(update, context, *args, **kwargs)
    return cast(HandlerType, wrapped)


def measure_performance(func: HandlerType) -> HandlerType:
    """Decorator to measure and log function performance.
    
    Args:
        func: The handler function to decorate
        
    Returns:
        The decorated function that measures execution time
    """
    @functools.wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        start_time = time.time()
        result = await func(update, context, *args, **kwargs)
        end_time = time.time()
        
        duration_ms = (end_time - start_time) * 1000
        
        # Get command name from the function name
        command_name = func.__name__
        
        StructuredLogger.log_performance(
            operation=f"command_{command_name}",
            duration_ms=duration_ms,
            details={
                "user_id": update.effective_user.id if update.effective_user else None
            }
        )
        
        return result
    return cast(HandlerType, wrapped)


def rate_limit(max_calls: int, time_frame: int) -> Callable[[HandlerType], HandlerType]:
    """Decorator factory to apply rate limiting to handlers.
    
    Args:
        max_calls: Maximum number of calls allowed in the time frame
        time_frame: Time frame in seconds
        
    Returns:
        Decorator function that applies rate limiting
    """
    def decorator(func: HandlerType) -> HandlerType:
        # Store rate limit data in function attributes
        if not hasattr(func, "_rate_limit_data"):
            func._rate_limit_data = {}
        
        @functools.wraps(func)
        async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            user_id = update.effective_user.id
            current_time = time.time()
            
            # Initialize user's rate limit data if not exists
            if user_id not in func._rate_limit_data:
                func._rate_limit_data[user_id] = []
            
            # Clean up old timestamps
            func._rate_limit_data[user_id] = [
                t for t in func._rate_limit_data[user_id] 
                if current_time - t < time_frame
            ]
            
            # Check if rate limit exceeded
            if len(func._rate_limit_data[user_id]) >= max_calls:
                if update.callback_query:
                    await update.callback_query.answer(
                        f"Rate limit exceeded. Please try again later."
                    )
                else:
                    await update.effective_message.reply_text(
                        f"⚠️ Rate limit exceeded. Please try again later."
                    )
                return None
            
            # Add current timestamp to user's rate limit data
            func._rate_limit_data[user_id].append(current_time)
            
            # Execute the handler
            return await func(update, context, *args, **kwargs)
        
        return cast(HandlerType, wrapped)
    
    return decorator