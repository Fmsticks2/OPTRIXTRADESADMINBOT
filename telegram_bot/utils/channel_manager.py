"""Channel management utilities for OPTRIXTRADES Telegram Bot"""

import logging
from typing import Optional

from telegram import Bot
from telegram.error import TelegramError, BadRequest, Forbidden

from config import BotConfig
from telegram_bot.utils.error_handler import error_handler_decorator

logger = logging.getLogger(__name__)

@error_handler_decorator
async def add_user_to_channel(bot: Bot, user_id: int, channel_id: str = None) -> bool:
    """
    Automatically add a user to the premium channel
    
    Args:
        bot: Telegram Bot instance
        user_id: User's Telegram ID
        channel_id: Channel ID to add user to (defaults to PREMIUM_CHANNEL_ID)
    
    Returns:
        bool: True if user was successfully added, False otherwise
    """
    if not channel_id:
        channel_id = BotConfig.PREMIUM_CHANNEL_ID
    
    if not channel_id:
        logger.error("No channel ID configured for automatic user addition")
        return False
    
    try:
        # Add user to the channel
        await bot.add_chat_member(chat_id=channel_id, user_id=user_id)
        logger.info(f"Successfully added user {user_id} to channel {channel_id}")
        return True
        
    except Forbidden as e:
        logger.warning(f"Bot lacks permission to add user {user_id} to channel {channel_id}: {e}")
        return False
        
    except BadRequest as e:
        if "user is already a participant" in str(e).lower():
            logger.info(f"User {user_id} is already a member of channel {channel_id}")
            return True
        elif "user not found" in str(e).lower():
            logger.warning(f"User {user_id} not found when trying to add to channel")
            return False
        elif "chat not found" in str(e).lower():
            logger.error(f"Channel {channel_id} not found")
            return False
        else:
            logger.error(f"BadRequest error adding user {user_id} to channel {channel_id}: {e}")
            return False
            
    except TelegramError as e:
        logger.error(f"Telegram error adding user {user_id} to channel {channel_id}: {e}")
        return False
        
    except Exception as e:
        logger.error(f"Unexpected error adding user {user_id} to channel {channel_id}: {e}")
        return False

@error_handler_decorator
async def add_user_to_multiple_channels(bot: Bot, user_id: int, channel_ids: list) -> dict:
    """
    Add a user to multiple channels
    
    Args:
        bot: Telegram Bot instance
        user_id: User's Telegram ID
        channel_ids: List of channel IDs to add user to
    
    Returns:
        dict: Results for each channel {channel_id: success_bool}
    """
    results = {}
    
    for channel_id in channel_ids:
        success = await add_user_to_channel(bot, user_id, channel_id)
        results[channel_id] = success
        
    return results

@error_handler_decorator
async def check_user_channel_membership(bot: Bot, user_id: int, channel_id: str = None) -> bool:
    """
    Check if a user is already a member of the channel
    
    Args:
        bot: Telegram Bot instance
        user_id: User's Telegram ID
        channel_id: Channel ID to check (defaults to PREMIUM_CHANNEL_ID)
    
    Returns:
        bool: True if user is a member, False otherwise
    """
    if not channel_id:
        channel_id = BotConfig.PREMIUM_CHANNEL_ID
    
    if not channel_id:
        logger.error("No channel ID configured for membership check")
        return False
    
    try:
        # Get chat member info
        member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
        
        # Check if user is a member (not kicked or left)
        if member.status in ['member', 'administrator', 'creator']:
            logger.info(f"User {user_id} is already a member of channel {channel_id}")
            return True
        else:
            logger.info(f"User {user_id} is not a member of channel {channel_id} (status: {member.status})")
            return False
            
    except BadRequest as e:
        if "user not found" in str(e).lower():
            logger.info(f"User {user_id} not found in channel {channel_id}")
            return False
        else:
            logger.error(f"BadRequest error checking membership for user {user_id} in channel {channel_id}: {e}")
            return False
            
    except TelegramError as e:
        logger.error(f"Telegram error checking membership for user {user_id} in channel {channel_id}: {e}")
        return False
        
    except Exception as e:
        logger.error(f"Unexpected error checking membership for user {user_id} in channel {channel_id}: {e}")
        return False