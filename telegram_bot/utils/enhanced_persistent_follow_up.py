"""Enhanced Persistent follow-up system for OPTRIXTRADES Telegram Bot

This module implements a robust messaging system that sends exactly 3 follow-up messages
every 24 hours with 8-hour intervals between each message. The sequence operates in a
continuous loop until the user's status is set to "verified" or "blocked as a bot."
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import pytz

from telegram import Bot
from telegram.error import Forbidden, BadRequest
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.executors.asyncio import AsyncIOExecutor

from config import BotConfig
from telegram_bot.utils.error_handler import error_handler_decorator
from telegram_bot.utils.follow_up_handlers import FollowUpHandlers

logger = logging.getLogger(__name__)

class EnhancedPersistentFollowUpScheduler:
    """Enhanced scheduler for persistent follow-up messages - 3 messages every 24 hours"""
    
    def __init__(self, bot: Bot):
        """Initialize the enhanced persistent scheduler"""
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
            'max_instances': 15
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
        
        logger.info("Enhanced persistent follow-up scheduler initialized")
    
    async def start_enhanced_persistent_follow_up(self, user_id: int, user_data: Dict[str, Any]) -> None:
        """Start enhanced persistent follow-up messages for a user (3 messages every 24 hours)"""
        # Stop any existing persistent follow-up for this user
        await self.stop_enhanced_persistent_follow_up(user_id)
        
        # Store user data
        self.active_users[user_id] = {
            'user_data': user_data,
            'start_time': datetime.now(pytz.UTC),
            'daily_cycle': 1,  # Track which 24-hour cycle we're in
            'messages_sent_today': 0  # Track messages sent in current cycle
        }
        
        # Schedule the first set of 3 messages for today
        await self._schedule_daily_message_cycle(user_id)
        
        logger.info(f"Started enhanced persistent follow-up for user {user_id}")
    
    async def stop_enhanced_persistent_follow_up(self, user_id: int) -> None:
        """Stop enhanced persistent follow-up messages for a user"""
        # Remove from active users
        if user_id in self.active_users:
            del self.active_users[user_id]
        
        # Remove all scheduled jobs for this user
        job_ids = [
            f"enhanced_followup_{user_id}_msg1",
            f"enhanced_followup_{user_id}_msg2", 
            f"enhanced_followup_{user_id}_msg3",
            f"enhanced_followup_{user_id}_cycle"
        ]
        
        for job_id in job_ids:
            try:
                self.scheduler.remove_job(job_id)
            except Exception as e:
                logger.debug(f"No job {job_id} to remove for user {user_id}: {e}")
        
        logger.info(f"Stopped enhanced persistent follow-up for user {user_id}")
    
    async def _schedule_daily_message_cycle(self, user_id: int) -> None:
        """Schedule 3 messages for the current 24-hour cycle"""
        if user_id not in self.active_users:
            return
        
        current_time = datetime.now(pytz.UTC)
        
        # Schedule 3 messages with 8-hour intervals
        message_times = [
            current_time + timedelta(hours=0),    # First message immediately
            current_time + timedelta(hours=8),    # Second message after 8 hours
            current_time + timedelta(hours=16)    # Third message after 16 hours
        ]
        
        # Schedule each message
        for i, run_time in enumerate(message_times, 1):
            job_id = f"enhanced_followup_{user_id}_msg{i}"
            
            try:
                self.scheduler.add_job(
                    self._send_enhanced_persistent_message,
                    'date',
                    run_date=run_time,
                    args=[user_id, i],
                    id=job_id,
                    replace_existing=True
                )
                logger.debug(f"Scheduled message {i} for user {user_id} at {run_time}")
            except Exception as e:
                logger.error(f"Failed to schedule message {i} for user {user_id}: {e}")
        
        # Schedule the next cycle to start in 24 hours
        next_cycle_time = current_time + timedelta(hours=24)
        cycle_job_id = f"enhanced_followup_{user_id}_cycle"
        
        try:
            self.scheduler.add_job(
                self._start_next_cycle,
                'date',
                run_date=next_cycle_time,
                args=[user_id],
                id=cycle_job_id,
                replace_existing=True
            )
            logger.debug(f"Scheduled next cycle for user {user_id} at {next_cycle_time}")
        except Exception as e:
            logger.error(f"Failed to schedule next cycle for user {user_id}: {e}")
    
    async def _start_next_cycle(self, user_id: int) -> None:
        """Start the next 24-hour cycle of messages"""
        if user_id not in self.active_users:
            return
        
        # Check if user should continue receiving messages
        should_continue = await self._should_continue_follow_up(user_id)
        if not should_continue:
            await self.stop_enhanced_persistent_follow_up(user_id)
            return
        
        # Increment cycle counter and reset daily message count
        self.active_users[user_id]['daily_cycle'] += 1
        self.active_users[user_id]['messages_sent_today'] = 0
        
        # Schedule next cycle of 3 messages
        await self._schedule_daily_message_cycle(user_id)
        
        logger.info(f"Started cycle {self.active_users[user_id]['daily_cycle']} for user {user_id}")
    
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
            new_sequence = current_sequence + 1
            
            # If we've gone through all 24 messages, restart from 1
            if new_sequence > 24:
                new_sequence = 1
            
            await update_user_data(user_id, follow_up_sequence=new_sequence)
        except Exception as e:
            logger.error(f"Error incrementing sequence number for user {user_id}: {e}")
    
    async def _should_continue_follow_up(self, user_id: int) -> bool:
        """Check if follow-up should continue for a user"""
        try:
            from database.connection import get_user_data
            current_user_data = await get_user_data(user_id)
            
            if not current_user_data:
                logger.warning(f"No user data found for {user_id}")
                return False
            
            # Stop if user is blocked or inactive
            if current_user_data.get('blocked_bot', False) or not current_user_data.get('is_active', True):
                logger.info(f"User {user_id} is blocked or inactive")
                return False
            
            # Stop if user has completed verification
            verification_status = current_user_data.get('registration_status', 'not_started')
            if verification_status == 'approved':
                logger.info(f"User {user_id} has completed verification")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking if follow-up should continue for user {user_id}: {e}")
            return False
    
    @error_handler_decorator
    async def _send_enhanced_persistent_message(self, user_id: int, message_number: int) -> None:
        """Send an enhanced persistent follow-up message"""
        try:
            # Check if user is still in active list
            if user_id not in self.active_users:
                logger.debug(f"User {user_id} no longer in active enhanced follow-up list")
                return
            
            # Check if user should continue receiving messages
            should_continue = await self._should_continue_follow_up(user_id)
            if not should_continue:
                await self.stop_enhanced_persistent_follow_up(user_id)
                return
            
            # Get user's current sequence number
            current_sequence = await self.get_user_sequence_number(user_id)
            
            # Get the appropriate handler for this sequence
            handler_func = self.follow_up_handlers.get(current_sequence)
            
            if not handler_func:
                logger.error(f"No handler found for sequence {current_sequence}")
                return
            
            # Get message content from handler
            message_data = handler_func()
            
            # Get current user data for personalization
            from database.connection import get_user_data
            current_user_data = await get_user_data(user_id)
            
            # Personalize message if first name is available
            message_text = message_data['text']
            first_name = current_user_data.get('first_name', '') if current_user_data else ''
            if first_name:
                message_text = f"Hi {first_name}! 👋\n\n" + message_text
            
            # Add message number indicator for clarity
            cycle_info = f"📅 Message {message_number}/3 today\n\n"
            message_text = cycle_info + message_text
            
            # Send message
            await self.bot.send_message(
                chat_id=user_id,
                text=message_text,
                reply_markup=message_data.get('reply_markup'),
                parse_mode='Markdown'
            )
            
            # Update user's sequence number for next message
            await self.increment_user_sequence(user_id)
            
            # Update message count for today
            if user_id in self.active_users:
                self.active_users[user_id]['messages_sent_today'] += 1
            
            logger.info(f"Sent enhanced persistent message {message_number}/3 (sequence {current_sequence}) to user {user_id}")
            
        except Forbidden as e:
            # User has blocked the bot
            logger.warning(f"User {user_id} has blocked the bot. Stopping enhanced follow-up.")
            await self.stop_enhanced_persistent_follow_up(user_id)
            
            # Mark user as blocked in database
            try:
                from database.connection import update_user_data
                await update_user_data(user_id, is_active=False, blocked_bot=True)
                logger.info(f"Marked user {user_id} as blocked in database")
            except Exception as db_error:
                logger.error(f"Failed to update user {user_id} blocked status in database: {db_error}")
                
        except BadRequest as e:
            logger.error(f"Bad request when sending enhanced message to user {user_id}: {e}")
            # Continue with follow-up despite bad request
            
        except Exception as e:
            logger.error(f"Unexpected error sending enhanced message to user {user_id}: {e}")
    
    def get_active_users_count(self) -> int:
        """Get count of users with active enhanced persistent follow-ups"""
        return len(self.active_users)
    
    def get_user_info(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get enhanced persistent follow-up info for a specific user"""
        return self.active_users.get(user_id)
    
    def get_all_active_users(self) -> Dict[int, Dict[str, Any]]:
        """Get all users with active enhanced persistent follow-ups"""
        return self.active_users.copy()
    
    async def cleanup_inactive_users(self) -> None:
        """Clean up users who are no longer active or have been blocked"""
        users_to_remove = []
        
        for user_id in self.active_users:
            should_continue = await self._should_continue_follow_up(user_id)
            if not should_continue:
                users_to_remove.append(user_id)
        
        for user_id in users_to_remove:
            await self.stop_enhanced_persistent_follow_up(user_id)
            logger.info(f"Cleaned up inactive enhanced follow-up for user {user_id}")
        
        if users_to_remove:
            logger.info(f"Cleaned up {len(users_to_remove)} inactive enhanced follow-ups")


# Global instance
enhanced_persistent_follow_up_scheduler = None

def init_enhanced_persistent_follow_up_scheduler(bot: Bot) -> EnhancedPersistentFollowUpScheduler:
    """Initialize the enhanced persistent follow-up scheduler"""
    global enhanced_persistent_follow_up_scheduler
    if enhanced_persistent_follow_up_scheduler is None:
        enhanced_persistent_follow_up_scheduler = EnhancedPersistentFollowUpScheduler(bot)
    return enhanced_persistent_follow_up_scheduler

def get_enhanced_persistent_follow_up_scheduler() -> Optional[EnhancedPersistentFollowUpScheduler]:
    """Get the enhanced persistent follow-up scheduler instance"""
    return enhanced_persistent_follow_up_scheduler