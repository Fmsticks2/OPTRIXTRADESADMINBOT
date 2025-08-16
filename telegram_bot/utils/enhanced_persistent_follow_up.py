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
        
        # Note: Using direct message content instead of handlers for enhanced persistent follow-ups
        
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
            
            # Get message content for this sequence
            message_data = await self._get_message_content_for_sequence(current_sequence)
            
            if not message_data:
                logger.error(f"No message content found for sequence {current_sequence}")
                return
            
            # Get current user data for personalization
            from database.connection import get_user_data
            current_user_data = await get_user_data(user_id)
            
            # Personalize message with first name
            message_text = message_data['text']
            first_name = current_user_data.get('first_name', '') if current_user_data else ''
            
            # Replace {first_name} placeholder in the message text
            if '{first_name}' in message_text:
                if first_name:
                    message_text = message_text.replace('{first_name}', first_name)
                else:
                    message_text = message_text.replace('{first_name}', 'there')
            elif first_name and not message_text.startswith('Hey'):
                # Add greeting only if message doesn't already have one and first name is available
                message_text = f"Hi {first_name}! 👋\n\n" + message_text
            
            # No message number indicator needed
            
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
    
    async def _get_message_content_for_sequence(self, sequence: int) -> Optional[Dict[str, Any]]:
        """Get message content for a specific sequence number"""
        try:
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            
            # Define all 24 follow-up messages from newfollowup.txt
            messages = {
                1: {
                    'text': "Hey {first_name} 👋\n\njust checking in…\nYou haven't completed your free VIP access setup yet. If you still want:\n✅ Daily signals\n✅ Auto trading bot\n✅ Bonus deposit rewards\n…then don't miss out. Traders are already making serious moves this week.\nTap below to continue your registration. You're just one step away 👇",
                    'reply_markup': InlineKeyboardMarkup([
                        [InlineKeyboardButton("➡️ Claim Free Access Now", callback_data="activation_instructions")],
                        [InlineKeyboardButton("➡️ Contact support team", url=f"https://t.me/{BotConfig.ADMIN_USERNAME}")]
                    ])
                },
                2: {
                    'text': "⌛ Still thinking, {first_name}?\nThis could be the shift you've been waiting for. The sooner you move, the better you for you.\nFree slot won't be open forever.",
                    'reply_markup': InlineKeyboardMarkup([
                        [InlineKeyboardButton("➡️ Claim Free Access Now", callback_data="activation_instructions")],
                        [InlineKeyboardButton("➡️ Contact support team", url=f"https://t.me/{BotConfig.ADMIN_USERNAME}")]
                    ])
                },
                3: {
                    'text': "👋 Just checking in... You haven't taken the next step yet. Are you having any issues?\nLet's fix that and get you in before it's too late.",
                    'reply_markup': InlineKeyboardMarkup([
                        [InlineKeyboardButton("➡️ Claim Free Access Now", callback_data="activation_instructions")],
                        [InlineKeyboardButton("➡️ Contact support team", url=f"https://t.me/{BotConfig.ADMIN_USERNAME}")]
                    ])
                },
                4: {
                    'text': "📈 Just an update…\nWe've already had many traders activate their access this week and most of them are already using the free bot + signals to start profiting.\nYou're still eligible but access may close soon once we hit this week's quota.\nDon't miss your shot.",
                    'reply_markup': InlineKeyboardMarkup([
                        [InlineKeyboardButton("➡️ Complete My Free access", callback_data="activation_instructions")],
                        [InlineKeyboardButton("➡️ Contact support team", url=f"https://t.me/{BotConfig.ADMIN_USERNAME}")]
                    ])
                },
                5: {
                    'text': "💪 You've come this far. Why stop now, {first_name}?\nEverything you need to be a successful trader is on our premium channel\nTap the button and let's make it real.",
                    'reply_markup': InlineKeyboardMarkup([
                        [InlineKeyboardButton("➡️ Claim Free Access Now", callback_data="activation_instructions")],
                        [InlineKeyboardButton("➡️ Contact support team", url=f"https://t.me/{BotConfig.ADMIN_USERNAME}")]
                    ])
                },
                6: {
                    'text': "⏰ Opportunities don't wait.\nEvery minute you delay, someone else is stepping up.\nDon't get left behind, {first_name}.",
                    'reply_markup': InlineKeyboardMarkup([
                        [InlineKeyboardButton("➡️ Claim Free Access Now", callback_data="activation_instructions")],
                        [InlineKeyboardButton("➡️ Contact support team", url=f"https://t.me/{BotConfig.ADMIN_USERNAME}")]
                    ])
                },
                7: {
                    'text': "Hey! Just wanted to remind you of everything you get for free once you sign up:\n✅ Daily VIP signals\n✅ Auto-trading bot\n✅ Strategy sessions\n✅ Private trader group\n✅ Up to $500 in deposit bonuses\nAnd yes, it's still 100% free when you use our broker link 🔥",
                    'reply_markup': InlineKeyboardMarkup([
                        [InlineKeyboardButton("➡️ I'm Ready to Activate", callback_data="activation_instructions")],
                        [InlineKeyboardButton("➡️ Contact support team", url=f"https://t.me/{BotConfig.ADMIN_USERNAME}")]
                    ])
                },
                8: {
                    'text': "💪 {first_name}, just a gentle nudge.\nSuccess rewards action, don't let procrastination steal this from you.",
                    'reply_markup': InlineKeyboardMarkup([
                        [InlineKeyboardButton("➡️ Claim Free Access Now", callback_data="activation_instructions")],
                        [InlineKeyboardButton("➡️ Contact support team", url=f"https://t.me/{BotConfig.ADMIN_USERNAME}")]
                    ])
                },
                9: {
                    'text': "You saw the message, but didn't move.\nThat's okay, but nothing changes until you do.\nMake today count, {first_name}",
                    'reply_markup': InlineKeyboardMarkup([
                        [InlineKeyboardButton("➡️ Claim Free Access Now", callback_data="activation_instructions")],
                        [InlineKeyboardButton("➡️ Contact support team", url=f"https://t.me/{BotConfig.ADMIN_USERNAME}")]
                    ])
                },
                10: {
                    'text': "⚡ Quick one, {first_name}.\nIf you're still interested, act now, this free spot won't be open forever",
                    'reply_markup': InlineKeyboardMarkup([
                        [InlineKeyboardButton("➡️ Claim Free Access Now", callback_data="activation_instructions")],
                        [InlineKeyboardButton("➡️ Contact support team", url=f"https://t.me/{BotConfig.ADMIN_USERNAME}")]
                    ])
                },
                11: {
                    'text': "💭 You've been on our early access list for a few days…\nIf you're still interested but something's holding you back, reply to this message and let's help you sort it out.\nEven if you don't have a big budget right now, we'll guide you to start small and smart.",
                    'reply_markup': InlineKeyboardMarkup([
                        [InlineKeyboardButton("➡️ I Have a Question", url=f"https://t.me/{BotConfig.ADMIN_USERNAME}")],
                        [InlineKeyboardButton("➡️ Continue Activation", callback_data="activation_instructions")]
                    ])
                },
                12: {
                    'text': "💎 We don't want you to miss out, {first_name}.\nSo here's your friendly reminder. Click below and lock in your access.",
                    'reply_markup': InlineKeyboardMarkup([
                        [InlineKeyboardButton("➡️ Claim Free Access Now", callback_data="activation_instructions")],
                        [InlineKeyboardButton("➡️ Contact support team", url=f"https://t.me/{BotConfig.ADMIN_USERNAME}")]
                    ])
                },
                13: {
                    'text': "🤔 Still on the fence, {first_name}?\nWhat's stopping you? Let's break through that together.\nOne click is all it takes.",
                    'reply_markup': InlineKeyboardMarkup([
                        [InlineKeyboardButton("➡️ Claim Free Access Now", callback_data="activation_instructions")],
                        [InlineKeyboardButton("➡️ Contact support team", url=f"https://t.me/{BotConfig.ADMIN_USERNAME}")]
                    ])
                },
                14: {
                    'text': "🚨 Last call to claim your free access to OPTRIXTRADES.\nThis week's onboarding closes in a few hours. After that, you'll need to wait for the next batch, no guarantees it'll still be free.\nWant in?",
                    'reply_markup': InlineKeyboardMarkup([
                        [InlineKeyboardButton("✅ Yes, Activate Me Now", callback_data="activation_instructions")],
                        [InlineKeyboardButton("❌ Not Interested", callback_data="not_interested")]
                    ])
                },
                15: {
                    'text': "⏰ Your wake-up call, {first_name}.\nEvery hour, someone else makes a move.\nBe one of them.",
                    'reply_markup': InlineKeyboardMarkup([
                        [InlineKeyboardButton("➡️ Claim Free Access Now", callback_data="activation_instructions")],
                        [InlineKeyboardButton("➡️ Contact support team", url=f"https://t.me/{BotConfig.ADMIN_USERNAME}")]
                    ])
                },
                16: {
                    'text': "This is for you, {first_name}.\nNot just anyone.\nYou joined for a reason, honor that reason.",
                    'reply_markup': InlineKeyboardMarkup([
                        [InlineKeyboardButton("➡️ Claim Free Access Now", callback_data="activation_instructions")],
                        [InlineKeyboardButton("➡️ Contact support team", url=f"https://t.me/{BotConfig.ADMIN_USERNAME}")]
                    ])
                },
                17: {
                    'text': "Wondering if OPTRIXTRADES is legit?\nWe totally get it. That's why we host free sessions, give access to our AI, and don't charge upfront.\n✅ Real traders use us.\n✅ Real results.\n✅ Real support, 24/7.\nWe only earn a small % when you win. That's why we want to help you trade smarter.\nWant to test us out with just $20?",
                    'reply_markup': InlineKeyboardMarkup([
                        [InlineKeyboardButton("➡️ Try With $20 I'm Curious", callback_data="activation_instructions")],
                        [InlineKeyboardButton("➡️ Contact support team", url=f"https://t.me/{BotConfig.ADMIN_USERNAME}")]
                    ])
                },
                18: {
                    'text': "You deserve better, {first_name}.\nAnd this is the first step.\nDon't delay the version of you that's waiting to become a profitable trader!",
                    'reply_markup': InlineKeyboardMarkup([
                        [InlineKeyboardButton("➡️ Claim Free Access Now", callback_data="activation_instructions")],
                        [InlineKeyboardButton("➡️ Contact support team", url=f"https://t.me/{BotConfig.ADMIN_USERNAME}")]
                    ])
                },
                19: {
                    'text': "Quick reminder, {first_name}.\nYou haven't taken action. We're holding space, but not for long.",
                    'reply_markup': InlineKeyboardMarkup([
                        [InlineKeyboardButton("➡️ Claim Free Access Now", callback_data="activation_instructions")],
                        [InlineKeyboardButton("➡️ Contact support team", url=f"https://t.me/{BotConfig.ADMIN_USERNAME}")]
                    ])
                },
                20: {
                    'text': "Okay… we're starting to think you're ghosting us 😅\n\nBut seriously, if you've been busy, no stress. Just pick up where you left off and grab your free access before this week closes.\nThe AI bot is still available for new traders using our link.",
                    'reply_markup': InlineKeyboardMarkup([
                        [InlineKeyboardButton("➡️ Okay, Let's Do This", callback_data="activation_instructions")],
                        [InlineKeyboardButton("➡️ Contact support team", url=f"https://t.me/{BotConfig.ADMIN_USERNAME}")]
                    ])
                },
                21: {
                    'text': "We're still waiting on you, {first_name}.\nBut not forever. Tap in before the window closes.",
                    'reply_markup': InlineKeyboardMarkup([
                        [InlineKeyboardButton("➡️ Claim Free Access Now", callback_data="activation_instructions")],
                        [InlineKeyboardButton("➡️ Contact support team", url=f"https://t.me/{BotConfig.ADMIN_USERNAME}")]
                    ])
                },
                22: {
                    'text': "Don't look back with regret.\nMoments like this seem small... until they're gone. Act now.",
                    'reply_markup': InlineKeyboardMarkup([
                        [InlineKeyboardButton("➡️ Claim Free Access Now", callback_data="activation_instructions")],
                        [InlineKeyboardButton("➡️ Contact support team", url=f"https://t.me/{BotConfig.ADMIN_USERNAME}")]
                    ])
                },
                23: {
                    'text': "Another trader just flipped a $100 deposit into $390 using our AI bot + signal combo in 4 days.\nWe can't guarantee profits, but the tools work when used right.\nIf you missed your shot last time, you're still eligible now 🔥",
                    'reply_markup': InlineKeyboardMarkup([
                        [InlineKeyboardButton("➡️ Activate My Tools Now", callback_data="activation_instructions")],
                        [InlineKeyboardButton("➡️ Contact support team", url=f"https://t.me/{BotConfig.ADMIN_USERNAME}")]
                    ])
                },
                24: {
                    'text': "⏳ FINAL REMINDER\nWe're closing registrations today for this round of free VIP access. No promises it'll open again, especially not at this level of access.\nIf you want in, this is it.",
                    'reply_markup': InlineKeyboardMarkup([
                        [InlineKeyboardButton("➡️✅ Count Me In", callback_data="activation_instructions")],
                        [InlineKeyboardButton("➡️❌ Remove Me From This List", callback_data="remove_from_list")]
                    ])
                }
            }
            
            return messages.get(sequence)
            
        except Exception as e:
            logger.error(f"Error getting message content for sequence {sequence}: {e}")
            return None
    
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