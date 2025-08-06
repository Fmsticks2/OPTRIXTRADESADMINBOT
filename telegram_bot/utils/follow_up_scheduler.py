"""Follow-up scheduler for OPTRIXTRADES Telegram Bot"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable, Coroutine

from telegram import Bot
from telegram.ext import ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.executors.asyncio import AsyncIOExecutor

from config import BotConfig
from telegram_bot.utils.error_handler import error_handler
from telegram_bot.utils.follow_up_handlers import FollowUpHandlers

logger = logging.getLogger(__name__)

class FollowUpScheduler:
    """Scheduler for follow-up messages to users who stop interacting"""
    
    def __init__(self, bot: Bot):
        """Initialize the scheduler"""
        self.bot = bot
        self.scheduled_tasks = {}
        
        # Initialize APScheduler
        jobstores = {
            'default': MemoryJobStore()
        }
        executors = {
            'default': AsyncIOExecutor()
        }
        job_defaults = {
            'coalesce': False,
            'max_instances': 3
        }
        
        self.scheduler = AsyncIOScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults
        )
        self.scheduler.start()
        
        self.handlers = FollowUpHandlers(bot)
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
        logger.info("Follow-up scheduler initialized with APScheduler")
    
    async def schedule_follow_ups(self, user_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Schedule follow-up messages for a user"""
        # Cancel any existing follow-ups for this user
        await self.cancel_follow_ups(user_id)
        
        # Store user context data for later use
        user_data = {
            'first_name': context.user_data.get('first_name', ''),
            'username': context.user_data.get('username', ''),
            'verified': context.user_data.get('verified', False)
        }
        
        # Schedule new follow-ups
        self.scheduled_tasks[user_id] = []
        
        # Schedule follow-ups with 7.5-8 hour intervals
        for sequence in range(1, 25):  # Extended to 24 sequences based on newfollowup.txt
            # Calculate delay based on sequence (7.5-8 hours between each)
            delay_hours = sequence * 8  # 8 hours between each follow-up
            
            # Calculate run time
            run_time = datetime.now() + timedelta(hours=delay_hours)
            
            # Schedule job with APScheduler
            job = self.scheduler.add_job(
                self._send_follow_up,
                'date',
                run_date=run_time,
                args=[user_id, sequence, user_data],
                id=f"followup_{user_id}_{sequence}",
                replace_existing=True
            )
            
            self.scheduled_tasks[user_id].append(job.id)
            
        logger.info(f"Scheduled {len(self.scheduled_tasks[user_id])} follow-ups for user {user_id}")
    
    async def cancel_follow_ups(self, user_id: int) -> None:
        """Cancel all scheduled follow-ups for a user"""
        if user_id in self.scheduled_tasks:
            for job_id in self.scheduled_tasks[user_id]:
                try:
                    self.scheduler.remove_job(job_id)
                except Exception as e:
                    logger.warning(f"Could not remove job {job_id}: {e}")
            del self.scheduled_tasks[user_id]
            logger.info(f"Cancelled follow-ups for user {user_id}")
    
    async def _send_follow_up(self, user_id: int, sequence: int, user_data: Dict[str, Any]) -> None:
        """Send a follow-up message for a specific sequence"""
        try:
            # Check if user has completed verification
            is_verified = user_data.get('verified', False)
            
            if not is_verified:
                # Get the appropriate handler for this sequence
                handler = self.follow_up_handlers.get(sequence)
                if handler:
                    # Create a fake update object with the user_id
                    class FakeUpdate:
                        def __init__(self, user_id, user_data):
                            self.effective_user = FakeUser(user_id, user_data)
                    
                    class FakeUser:
                        def __init__(self, user_id, user_data):
                            self.id = user_id
                            self.first_name = user_data.get('first_name', '')
                            self.username = user_data.get('username', '')
                    
                    fake_update = FakeUpdate(user_id, user_data)
                    
                    # Create a minimal context for the handler
                    from telegram.ext import ApplicationBuilder
                    application = ApplicationBuilder().token(self.bot.token).build()
                    context = ContextTypes.DEFAULT_TYPE(application=application)
                    context.user_data = user_data
                    
                    # Call the handler
                    await handler()(fake_update, context)
                    logger.info(f"Sent sequence {sequence} follow-up to user {user_id}")
                else:
                    logger.warning(f"No handler found for sequence {sequence} follow-up")
            else:
                logger.info(f"User {user_id} is verified, skipping sequence {sequence} follow-up")
                
        except Exception as e:
            logger.error(f"Error sending sequence {sequence} follow-up to user {user_id}: {e}")
            
        # Remove this job from scheduled tasks
        if user_id in self.scheduled_tasks:
            job_id = f"followup_{user_id}_{sequence}"
            if job_id in self.scheduled_tasks[user_id]:
                self.scheduled_tasks[user_id].remove(job_id)
    


# Singleton instance
follow_up_scheduler = None

def init_follow_up_scheduler(bot: Bot) -> FollowUpScheduler:
    """Initialize the follow-up scheduler"""
    global follow_up_scheduler
    if follow_up_scheduler is None:
        follow_up_scheduler = FollowUpScheduler(bot)
    return follow_up_scheduler

def get_follow_up_scheduler() -> Optional[FollowUpScheduler]:
    """Get the follow-up scheduler instance"""
    return follow_up_scheduler