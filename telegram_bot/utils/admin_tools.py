"""Admin tools for OPTRIXTRADES Telegram Bot"""

import logging
from typing import Dict, Any, Optional, List, Union

from telegram import Update, Bot
from telegram.ext import ContextTypes

from telegram_bot.utils.error_handler import error_handler
from telegram_bot.utils.follow_up_scheduler import get_follow_up_scheduler

logger = logging.getLogger(__name__)

@error_handler
async def trigger_follow_up_manually(bot: Bot, user_id: int, day: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Manually trigger a specific follow-up message for a user
    
    Args:
        bot: The bot instance
        user_id: The user ID to send the follow-up to
        day: The follow-up day number (1-10)
        context: The context object
    
    Returns:
        bool: True if the follow-up was triggered, False otherwise
    """
    scheduler = get_follow_up_scheduler()
    if not scheduler:
        logger.error("Follow-up scheduler not initialized")
        return False
    
    if day < 1 or day > 10:
        logger.error(f"Invalid follow-up day: {day}. Must be between 1 and 10.")
        return False
    
    try:
        # Create a fake update object with the user_id
        class FakeUpdate:
            def __init__(self, user_id):
                self.effective_user = FakeUser(user_id)
        
        class FakeUser:
            def __init__(self, user_id):
                self.id = user_id
                # Try to get user data from context
                self.first_name = context.user_data.get('first_name', '')
                self.username = context.user_data.get('username', '')
        
        fake_update = FakeUpdate(user_id)
        
        # Get the handler for the specified day
        handler = scheduler.follow_up_handlers.get(day)
        if handler:
            # Call the handler
            await handler()(fake_update, context)
            logger.info(f"Manually triggered day {day} follow-up for user {user_id}")
            return True
        else:
            logger.error(f"No handler found for day {day}")
            return False
    except Exception as e:
        logger.error(f"Error triggering follow-up: {e}")
        return False

@error_handler
async def schedule_follow_ups_for_user(bot: Bot, user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Manually schedule all follow-ups for a user
    
    Args:
        bot: The bot instance
        user_id: The user ID to schedule follow-ups for
        context: The context object
    
    Returns:
        bool: True if follow-ups were scheduled, False otherwise
    """
    scheduler = get_follow_up_scheduler()
    if not scheduler:
        logger.error("Follow-up scheduler not initialized")
        return False
    
    try:
        await scheduler.schedule_follow_ups(user_id, context)
        logger.info(f"Manually scheduled follow-ups for user {user_id}")
        return True
    except Exception as e:
        logger.error(f"Error scheduling follow-ups: {e}")
        return False

@error_handler
async def cancel_follow_ups_for_user(bot: Bot, user_id: int) -> bool:
    """Manually cancel all follow-ups for a user
    
    Args:
        bot: The bot instance
        user_id: The user ID to cancel follow-ups for
    
    Returns:
        bool: True if follow-ups were cancelled, False otherwise
    """
    scheduler = get_follow_up_scheduler()
    if not scheduler:
        logger.error("Follow-up scheduler not initialized")
        return False
    
    try:
        await scheduler.cancel_follow_ups(user_id)
        logger.info(f"Manually cancelled follow-ups for user {user_id}")
        return True
    except Exception as e:
        logger.error(f"Error cancelling follow-ups: {e}")
        return False