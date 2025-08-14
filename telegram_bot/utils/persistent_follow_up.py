"""Persistent follow-up system for OPTRIXTRADES Telegram Bot

This module implements a persistent messaging system that sends predefined messages
every 8 hours indefinitely until the user blocks the bot or completes verification.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import pytz

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import Forbidden, BadRequest
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.executors.asyncio import AsyncIOExecutor

from config import BotConfig
from telegram_bot.utils.error_handler import error_handler_decorator
from telegram_bot.utils.follow_up_handlers import FollowUpHandlers

logger = logging.getLogger(__name__)

class PersistentFollowUpScheduler:
    """Scheduler for persistent follow-up messages every 8 hours"""
    
    def __init__(self, bot: Bot):
        """Initialize the persistent scheduler"""
        self.bot = bot
        self.active_users = {}  # Track users with active persistent follow-ups
        
        # Initialize APScheduler
        jobstores = {
            'default': MemoryJobStore()
        }
        executors = {
            'default': AsyncIOExecutor()
        }
        job_defaults = {
            'coalesce': False,
            'max_instances': 10
        }
        
        self.scheduler = AsyncIOScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone=pytz.UTC
        )
        self.scheduler.start()
        
        # Initialize follow-up handlers to get all 24 message templates
        self.handlers = FollowUpHandlers(bot)
        
        # Create mapping of all 24 follow-up handlers
        self.follow_up_handlers = {
            1: self.handlers.get_sequence1_handler,
            2: self.handlers.get_sequence2_handler,
            3: self.handlers.get_sequence3_handler,
            4: self.handlers.get_sequence4_handler,
            5: self.handlers.get_sequence5_handler,
            6: self.handlers.get_sequence6_handler,
            7: self.handlers.get_sequence7_handler,
            8: self.handlers.get_sequence8_handler,
            9: self.handlers.get_sequence9_handler,
            10: self.handlers.get_sequence10_handler,
            11: self.handlers.get_sequence11_handler,
            12: self.handlers.get_sequence12_handler,
            13: self.handlers.get_sequence13_handler,
            14: self.handlers.get_sequence14_handler,
            15: self.handlers.get_sequence15_handler,
            16: self.handlers.get_sequence16_handler,
            17: self.handlers.get_sequence17_handler,
            18: self.handlers.get_sequence18_handler,
            19: self.handlers.get_sequence19_handler,
            20: self.handlers.get_sequence20_handler,
            21: self.handlers.get_sequence21_handler,
            22: self.handlers.get_sequence22_handler,
            23: self.handlers.get_sequence23_handler,
            24: self.handlers.get_sequence24_handler,
        }
        
        logger.info("Persistent follow-up scheduler initialized")
    
    async def start_persistent_follow_up(self, user_id: int, user_data: Dict[str, Any]) -> None:
        """Start persistent follow-up messages for a user"""
        # Stop any existing persistent follow-up for this user
        await self.stop_persistent_follow_up(user_id)
        
        # Store user data
        self.active_users[user_id] = {
            'user_data': user_data,
            'start_time': datetime.now(pytz.UTC),
            'message_count': 0
        }
        
        # Schedule the first message in 8 hours
        await self._schedule_next_message(user_id)
        
        logger.info(f"Started persistent follow-up for user {user_id}")
    
    async def stop_persistent_follow_up(self, user_id: int) -> None:
        """Stop persistent follow-up messages for a user"""
        # Remove from active users
        if user_id in self.active_users:
            del self.active_users[user_id]
        
        # Remove scheduled job
        job_id = f"persistent_followup_{user_id}"
        try:
            self.scheduler.remove_job(job_id)
            logger.info(f"Stopped persistent follow-up for user {user_id}")
        except Exception as e:
            logger.debug(f"No persistent follow-up job to remove for user {user_id}: {e}")
    
    async def _schedule_next_message(self, user_id: int) -> None:
        """Schedule the next persistent follow-up message"""
        if user_id not in self.active_users:
            return
        
        # Schedule next message in exactly 8 hours
        run_time = datetime.now(pytz.UTC) + timedelta(hours=8)
        
        job_id = f"persistent_followup_{user_id}"
        
        try:
            self.scheduler.add_job(
                self._send_persistent_message,
                'date',
                run_date=run_time,
                args=[user_id],
                id=job_id,
                replace_existing=True
            )
            logger.debug(f"Scheduled next persistent message for user {user_id} at {run_time}")
        except Exception as e:
            logger.error(f"Failed to schedule persistent message for user {user_id}: {e}")
    
    @error_handler_decorator
    async def get_user_sequence_number(self, user_id: int) -> int:
        """Get the current sequence number for a user"""
        try:
            from database.connection import get_user_data
            user_data = await get_user_data(user_id)
            return user_data.get('follow_up_sequence', 1) if user_data else 1
        except Exception as e:
            logger.error(f"Error getting sequence number for user {user_id}: {e}")
            return 1
    
    async def increment_user_sequence(self, user_id: int):
        """Increment the sequence number for a user"""
        try:
            from database.connection import update_user_data
            current_sequence = await self.get_user_sequence_number(user_id)
            await update_user_data(user_id, follow_up_sequence=current_sequence + 1)
        except Exception as e:
            logger.error(f"Error incrementing sequence number for user {user_id}: {e}")
    
    async def reset_user_sequence(self, user_id: int):
        """Reset the sequence number for a user back to 1"""
        try:
            from database.connection import update_user_data
            await update_user_data(user_id, follow_up_sequence=1)
        except Exception as e:
            logger.error(f"Error resetting sequence number for user {user_id}: {e}")

    @error_handler_decorator
    async def _send_persistent_message(self, user_id: int) -> None:
        """Send a persistent follow-up message"""
        try:
            # Check if user is still in active list
            if user_id not in self.active_users:
                logger.debug(f"User {user_id} no longer in active persistent follow-up list")
                return
            
            # Check user status from database
            from database.connection import get_user_data
            current_user_data = await get_user_data(user_id)
            
            if not current_user_data:
                logger.warning(f"No user data found for {user_id}, stopping persistent follow-up")
                await self.stop_persistent_follow_up(user_id)
                return
            
            # Check if user is blocked or inactive
            if current_user_data.get('blocked_bot', False) or not current_user_data.get('is_active', True):
                logger.info(f"User {user_id} is blocked or inactive, stopping persistent follow-up")
                await self.stop_persistent_follow_up(user_id)
                return
            
            # Check if user has completed verification
            verification_status = current_user_data.get('registration_status', 'not_started')
            if verification_status == 'approved':
                logger.info(f"User {user_id} has completed verification, stopping persistent follow-up")
                await self.stop_persistent_follow_up(user_id)
                return
            
            # Get user's current sequence number (track progress through messages)
            current_sequence = await self.get_user_sequence_number(user_id)
            
            # If user has gone through all 24 messages, restart from sequence 1
            if current_sequence > 24:
                current_sequence = 1
                await self.reset_user_sequence(user_id)
            
            # Get the appropriate handler for this sequence
            handler_func = self.follow_up_handlers.get(current_sequence)
            
            if not handler_func:
                logger.error(f"No handler found for sequence {current_sequence}")
                return
            
            # Get message content from handler
            message_data = handler_func()
            
            # Personalize message if first name is available
            message_text = message_data['text']
            first_name = current_user_data.get('first_name', '')
            if first_name:
                message_text = f"Hi {first_name}! 👋\n\n" + message_text
            
            # Send message
            await self.bot.send_message(
                chat_id=user_id,
                text=message_text,
                reply_markup=message_data.get('reply_markup'),
                parse_mode='Markdown'
            )
            
            # Update user's sequence number for next message
            await self.increment_user_sequence(user_id)
            
            # Schedule next message
            await self._schedule_next_message(user_id)
            
            logger.info(f"Sent persistent follow-up message (sequence {current_sequence}) to user {user_id}")
            
        except Forbidden as e:
            # User has blocked the bot
            logger.warning(f"User {user_id} has blocked the bot. Stopping persistent follow-up.")
            await self.stop_persistent_follow_up(user_id)
            
            # Mark user as blocked in database
            try:
                from database.connection import update_user_data
                await update_user_data(user_id, is_active=False, blocked_bot=True)
                logger.info(f"Marked user {user_id} as blocked in database")
            except Exception as db_error:
                logger.error(f"Failed to update user {user_id} blocked status in database: {db_error}")
                
        except BadRequest as e:
            logger.error(f"Bad request when sending persistent message to user {user_id}: {e}")
            # Don't stop follow-up for bad requests, might be temporary
            await self._schedule_next_message(user_id)
            
        except Exception as e:
            logger.error(f"Unexpected error sending persistent message to user {user_id}: {e}")
            # Continue with next message despite error
            await self._schedule_next_message(user_id)
    
    def get_active_users_count(self) -> int:
        """Get count of users with active persistent follow-ups"""
        return len(self.active_users)
    
    def get_user_info(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get persistent follow-up info for a specific user"""
        return self.active_users.get(user_id)
    
    async def cleanup_inactive_users(self) -> None:
        """Clean up users who are no longer active or have been blocked"""
        users_to_remove = []
        
        for user_id in self.active_users:
            try:
                from database.connection import get_user_data
                user_data = await get_user_data(user_id)
                
                if not user_data or user_data.get('blocked_bot', False) or not user_data.get('is_active', True):
                    users_to_remove.append(user_id)
                elif user_data.get('registration_status') == 'approved':
                    users_to_remove.append(user_id)
                    
            except Exception as e:
                logger.error(f"Error checking user {user_id} status during cleanup: {e}")
        
        for user_id in users_to_remove:
            await self.stop_persistent_follow_up(user_id)
            logger.info(f"Cleaned up inactive persistent follow-up for user {user_id}")
        
        if users_to_remove:
            logger.info(f"Cleaned up {len(users_to_remove)} inactive persistent follow-ups")


# Global instance
persistent_follow_up_scheduler = None

def init_persistent_follow_up_scheduler(bot: Bot) -> PersistentFollowUpScheduler:
    """Initialize the persistent follow-up scheduler"""
    global persistent_follow_up_scheduler
    if persistent_follow_up_scheduler is None:
        persistent_follow_up_scheduler = PersistentFollowUpScheduler(bot)
    return persistent_follow_up_scheduler

def get_persistent_follow_up_scheduler() -> Optional[PersistentFollowUpScheduler]:
    """Get the persistent follow-up scheduler instance"""
    return persistent_follow_up_scheduler