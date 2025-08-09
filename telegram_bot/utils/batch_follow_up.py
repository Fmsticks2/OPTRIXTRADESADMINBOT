import asyncio
import logging
from typing import List, Dict, Any
from collections import defaultdict
from telegram import Bot
from telegram.ext import ContextTypes, ApplicationBuilder

from database.connection import get_user_data
from telegram_bot.utils.follow_up_scheduler import get_follow_up_scheduler
from config import BotConfig

logger = logging.getLogger(__name__)

class BatchFollowUpManager:
    """Manager for batch processing follow-ups for existing unverified users"""
    
    def __init__(self, bot: Bot, db_manager):
        self.bot = bot
        self.db_manager = db_manager
        self.follow_up_scheduler = get_follow_up_scheduler()
    
    async def get_unverified_users(self) -> List[Dict[str, Any]]:
        """Get all users who are not verified from the database"""
        try:
            query = """
        SELECT user_id, username, first_name, registration_status, created_at
        FROM users
        WHERE registration_status = 'not_started'
           AND is_active = TRUE
        ORDER BY created_at DESC
        """
            
            results = await self.db_manager.execute(query, fetch='all')
            logger.info(f"Found {len(results)} unverified users")
            return results
            
        except Exception as e:
            logger.error(f"Error getting unverified users: {e}")
            return []
    
    async def start_follow_ups_for_unverified_users(self, limit: int = None) -> Dict[str, int]:
        """Start follow-up sequences for all unverified users
        
        Args:
            limit: Maximum number of users to process (None for all)
            
        Returns:
            Dict with counts of processed, scheduled, and failed users
        """
        stats = {
            'processed': 0,
            'scheduled': 0,
            'failed': 0,
            'already_scheduled': 0
        }
        
        try:
            # Get unverified users
            unverified_users = await self.get_unverified_users()
            
            if limit:
                unverified_users = unverified_users[:limit]
            
            logger.info(f"Starting follow-ups for {len(unverified_users)} unverified users")
            
            for user in unverified_users:
                user_id = user['user_id']
                stats['processed'] += 1
                
                try:
                    # Check if user already has scheduled follow-ups
                    if self.follow_up_scheduler and user_id in self.follow_up_scheduler.scheduled_tasks:
                        logger.info(f"User {user_id} already has scheduled follow-ups, skipping")
                        stats['already_scheduled'] += 1
                        continue
                    
                    # Create a minimal context for the user
                    context = await self._create_user_context(user)
                    
                    # Schedule follow-ups
                    if self.follow_up_scheduler:
                        await self.follow_up_scheduler.schedule_follow_ups(user_id, context)
                        stats['scheduled'] += 1
                        logger.info(f"Scheduled follow-ups for user {user_id} ({user.get('first_name', 'Unknown')})")
                    else:
                        logger.error("Follow-up scheduler not available")
                        stats['failed'] += 1
                        
                except Exception as e:
                    logger.error(f"Failed to schedule follow-ups for user {user_id}: {e}")
                    stats['failed'] += 1
                    
                # Add small delay to avoid overwhelming the system
                await asyncio.sleep(0.1)
            
            logger.info(f"Batch follow-up processing completed: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Error in batch follow-up processing: {e}")
            return stats
    
    async def _create_user_context(self, user: Dict[str, Any]) -> ContextTypes.DEFAULT_TYPE:
        """Create a minimal context object for a user"""
        # Create a minimal application for context
        application = ApplicationBuilder().token(BotConfig.BOT_TOKEN).build()
        context = ContextTypes.DEFAULT_TYPE(application=application)
        
        # Initialize user_data properly
        context._user_data = defaultdict(dict)
        context._user_data[user['user_id']] = {
            'first_name': user.get('first_name', ''),
            'username': user.get('username', ''),
            'verified': False
        }
        context._user_id = user['user_id']
        
        return context
    
    async def cancel_all_follow_ups(self) -> int:
        """Cancel all scheduled follow-ups (emergency stop)
        
        Returns:
            Number of users whose follow-ups were cancelled
        """
        cancelled_count = 0
        
        if not self.follow_up_scheduler:
            logger.error("Follow-up scheduler not available")
            return 0
        
        try:
            # Get all users with scheduled tasks
            scheduled_users = list(self.follow_up_scheduler.scheduled_tasks.keys())
            
            for user_id in scheduled_users:
                await self.follow_up_scheduler.cancel_follow_ups(user_id)
                cancelled_count += 1
                logger.info(f"Cancelled follow-ups for user {user_id}")
            
            logger.info(f"Cancelled follow-ups for {cancelled_count} users")
            return cancelled_count
            
        except Exception as e:
            logger.error(f"Error cancelling follow-ups: {e}")
            return cancelled_count
    
    async def get_follow_up_stats(self) -> Dict[str, Any]:
        """Get statistics about current follow-up schedules
        
        Returns:
            Dict with follow-up statistics
        """
        stats = {
            'total_users_with_follow_ups': 0,
            'total_scheduled_tasks': 0,
            'users_by_sequence_count': {},
            'scheduler_status': 'unknown'
        }
        
        try:
            if not self.follow_up_scheduler:
                stats['scheduler_status'] = 'not_available'
                return stats
            
            stats['scheduler_status'] = 'available'
            scheduled_tasks = self.follow_up_scheduler.scheduled_tasks
            stats['total_users_with_follow_ups'] = len(scheduled_tasks)
            
            total_tasks = 0
            sequence_counts = {}
            
            for user_id, tasks in scheduled_tasks.items():
                task_count = len(tasks)
                total_tasks += task_count
                
                if task_count not in sequence_counts:
                    sequence_counts[task_count] = 0
                sequence_counts[task_count] += 1
            
            stats['total_scheduled_tasks'] = total_tasks
            stats['users_by_sequence_count'] = sequence_counts
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting follow-up stats: {e}")
            return stats


async def start_batch_follow_ups(db_manager, bot: Bot, limit: int = None) -> Dict[str, int]:
    """Convenience function to start follow-ups for unverified users
    
    Args:
        db_manager: Database manager instance
        bot: Bot instance
        limit: Maximum number of users to process
        
    Returns:
        Dict with processing statistics
    """
    manager = BatchFollowUpManager(bot, db_manager)
    return await manager.start_follow_ups_for_unverified_users(limit)


async def get_batch_follow_up_stats(db_manager, bot: Bot) -> Dict[str, Any]:
    """Convenience function to get follow-up statistics
    
    Args:
        db_manager: Database manager instance
        bot: Bot instance
        
    Returns:
        Dict with follow-up statistics
    """
    manager = BatchFollowUpManager(bot, db_manager)
    return await manager.get_follow_up_stats()