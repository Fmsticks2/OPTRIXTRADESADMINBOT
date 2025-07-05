"""Follow-up scheduler for OPTRIXTRADES Telegram Bot"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable, Coroutine

from telegram import Bot
from telegram.ext import ContextTypes

from config import BotConfig
from telegram_bot.utils.error_handler import error_handler

logger = logging.getLogger(__name__)

class FollowUpScheduler:
    """Scheduler for follow-up messages to users who stop interacting"""
    
    def __init__(self, bot: Bot):
        """Initialize the scheduler"""
        self.bot = bot
        self.scheduled_tasks = {}
        self.follow_up_handlers = {
            1: self._get_day1_handler,
            2: self._get_day2_handler,
            3: self._get_day3_handler,
            4: self._get_day4_handler,
            5: self._get_day5_handler,
            6: self._get_day6_handler,
            7: self._get_day7_handler,
            8: self._get_day8_handler,
            9: self._get_day9_handler,
            10: self._get_day10_handler
        }
        logger.info("Follow-up scheduler initialized")
    
    async def schedule_follow_ups(self, user_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Schedule follow-up messages for a user"""
        # Cancel any existing follow-ups for this user
        await self.cancel_follow_ups(user_id)
        
        # Schedule new follow-ups
        self.scheduled_tasks[user_id] = []
        
        # Schedule follow-ups for days 1-10
        for day in range(1, 11):
            # Schedule task
            task = asyncio.create_task(
                self._schedule_follow_up(user_id, day, context)
            )
            self.scheduled_tasks[user_id].append(task)
        
        logger.info(f"Scheduled follow-ups for user {user_id}")
    
    async def cancel_follow_ups(self, user_id: int) -> None:
        """Cancel all scheduled follow-ups for a user"""
        if user_id in self.scheduled_tasks:
            for task in self.scheduled_tasks[user_id]:
                if not task.done():
                    task.cancel()
            del self.scheduled_tasks[user_id]
            logger.info(f"Cancelled follow-ups for user {user_id}")
    
    async def _schedule_follow_up(self, user_id: int, day: int, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Schedule a follow-up message for a specific day"""
        # Calculate delay based on day (hours)
        if day == 1:
            delay_hours = 4  # First follow-up after 4 hours
        else:
            delay_hours = (day - 1) * 23  # Subsequent follow-ups approximately daily
        
        # Sleep until it's time to send the follow-up
        await asyncio.sleep(delay_hours * 3600)  # Convert hours to seconds
        
        # Check if user has completed verification
        # This would need to be implemented based on your verification tracking
        is_verified = context.user_data.get('verified', False)
        
        if not is_verified:
            # Get the appropriate handler for this day
            handler = self.follow_up_handlers.get(day)
            if handler:
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
                    
                    # Call the handler
                    await handler()(fake_update, context)
                    logger.info(f"Sent day {day} follow-up to user {user_id}")
                except Exception as e:
                    logger.error(f"Error sending follow-up to user {user_id}: {e}")
    
    def _get_day1_handler(self) -> Callable[[Any, ContextTypes.DEFAULT_TYPE], Coroutine[Any, Any, None]]:
        """Get handler for day 1 follow-up"""
        from telegram_bot.handlers.verification import followup_day1
        return followup_day1
    
    def _get_day2_handler(self) -> Callable[[Any, ContextTypes.DEFAULT_TYPE], Coroutine[Any, Any, None]]:
        """Get handler for day 2 follow-up"""
        from telegram_bot.handlers.verification import followup_day2
        return followup_day2
    
    def _get_day3_handler(self) -> Callable[[Any, ContextTypes.DEFAULT_TYPE], Coroutine[Any, Any, None]]:
        """Get handler for day 3 follow-up"""
        # This would be implemented in verification.py
        @error_handler
        async def followup_day3(update: Any, context: ContextTypes.DEFAULT_TYPE) -> None:
            """Send follow-up message for day 3 (value recap)"""
            user = update.effective_user
            
            followup_text = "Hey! Just wanted to remind you of everything you get for free once you sign up:\n"
            followup_text += "✅ Daily VIP signals\n"
            followup_text += "✅ Auto-trading bot\n"
            followup_text += "✅ Strategy sessions\n"
            followup_text += "✅ Private trader group\n"
            followup_text += "✅ Up to $500 in deposit bonuses\n"
            followup_text += "And yes, it's still 100% free when you use our broker link 👇"
            
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            keyboard = [
                [InlineKeyboardButton("➡️ I'm Ready to Activate", callback_data="activation_instructions")],
                [InlineKeyboardButton("➡️ Contact support team", url=f"https://t.me/{BotConfig.ADMIN_USERNAME}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await self.bot.send_message(
                chat_id=user.id,
                text=followup_text,
                reply_markup=reply_markup
            )
        
        return followup_day3
    
    def _get_day4_handler(self) -> Callable[[Any, ContextTypes.DEFAULT_TYPE], Coroutine[Any, Any, None]]:
        """Get handler for day 4 follow-up"""
        # This would be implemented in verification.py
        @error_handler
        async def followup_day4(update: Any, context: ContextTypes.DEFAULT_TYPE) -> None:
            """Send follow-up message for day 4 (personal + soft CTA)"""
            user = update.effective_user
            
            followup_text = "👀 You've been on our early access list for a few days…\n"
            followup_text += "If you're still interested but something's holding you back, reply to this message and let's help\n"
            followup_text += "you sort it out.\n"
            followup_text += "Even if you don't have a big budget right now, we'll guide you to start small and smart."
            
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            keyboard = [
                [InlineKeyboardButton("➡️ I Have a Question", url=f"https://t.me/{BotConfig.ADMIN_USERNAME}")],
                [InlineKeyboardButton("➡️ Continue Activation", callback_data="activation_instructions")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await self.bot.send_message(
                chat_id=user.id,
                text=followup_text,
                reply_markup=reply_markup
            )
        
        return followup_day4
    
    def _get_day5_handler(self) -> Callable[[Any, ContextTypes.DEFAULT_TYPE], Coroutine[Any, Any, None]]:
        """Get handler for day 5 follow-up"""
        # This would be implemented in verification.py
        @error_handler
        async def followup_day5(update: Any, context: ContextTypes.DEFAULT_TYPE) -> None:
            """Send follow-up message for day 5 (last chance + exit option)"""
            user = update.effective_user
            
            followup_text = "📌 Last call to claim your free access to OPTRIXTRADES.\n"
            followup_text += "This week's onboarding closes in a few hours. After that, you'll need to wait for the next batch,\n"
            followup_text += "no guarantees it'll still be free.\n"
            followup_text += "Want in?"
            
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            keyboard = [
                [InlineKeyboardButton("✅ Yes, Activate Me Now", callback_data="activation_instructions")],
                [InlineKeyboardButton("❌ Not Interested", callback_data="not_interested")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await self.bot.send_message(
                chat_id=user.id,
                text=followup_text,
                reply_markup=reply_markup
            )
        
        return followup_day5
    
    # Implement the remaining handlers similarly
    def _get_day6_handler(self) -> Callable[[Any, ContextTypes.DEFAULT_TYPE], Coroutine[Any, Any, None]]:
        """Get handler for day 6 follow-up"""
        @error_handler
        async def followup_day6(update: Any, context: ContextTypes.DEFAULT_TYPE) -> None:
            """Send follow-up message for day 6 (education + trust-building)"""
            user = update.effective_user
            
            followup_text = "Wondering if OPTRIXTRADES is legit?\n"
            followup_text += "We totally get it. That's why we host free sessions, give access to our AI, and don't charge\n"
            followup_text += "upfront.\n"
            followup_text += "✅ Real traders use us.\n"
            followup_text += "✅ Real results.\n"
            followup_text += "✅ Real support, 24/7.\n"
            followup_text += "We only earn a small % when you win. That's why we want to help you trade smarter.\n"
            followup_text += "Want to test us out with just $20?"
            
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            keyboard = [
                [InlineKeyboardButton("➡️ Try With $20 I'm Curious", callback_data="activation_instructions")],
                [InlineKeyboardButton("➡️ Contact support team", url=f"https://t.me/{BotConfig.ADMIN_USERNAME}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await self.bot.send_message(
                chat_id=user.id,
                text=followup_text,
                reply_markup=reply_markup
            )
        
        return followup_day6
    
    def _get_day7_handler(self) -> Callable[[Any, ContextTypes.DEFAULT_TYPE], Coroutine[Any, Any, None]]:
        """Get handler for day 7 follow-up"""
        @error_handler
        async def followup_day7(update: Any, context: ContextTypes.DEFAULT_TYPE) -> None:
            """Send follow-up message for day 7 (light humor + re-activation)"""
            user = update.effective_user
            
            followup_text = "Okay… we're starting to think you're ghosting us 😂\n"
            followup_text += "But seriously, if you've been busy, no stress. Just pick up where you left off and grab your free\n"
            followup_text += "access before this week closes.\n"
            followup_text += "The AI bot is still available for new traders using our link."
            
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            keyboard = [
                [InlineKeyboardButton("➡️ Okay, Let's Do This", callback_data="activation_instructions")],
                [InlineKeyboardButton("➡️ Contact support team", url=f"https://t.me/{BotConfig.ADMIN_USERNAME}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await self.bot.send_message(
                chat_id=user.id,
                text=followup_text,
                reply_markup=reply_markup
            )
        
        return followup_day7
    
    def _get_day8_handler(self) -> Callable[[Any, ContextTypes.DEFAULT_TYPE], Coroutine[Any, Any, None]]:
        """Get handler for day 8 follow-up"""
        @error_handler
        async def followup_day8(update: Any, context: ContextTypes.DEFAULT_TYPE) -> None:
            """Send follow-up message for day 8 (FOMO + new success update)"""
            user = update.effective_user
            
            followup_text = "Another trader just flipped a $100 deposit into $390 using our AI bot + signal combo in 4 days.\n"
            followup_text += "We can't guarantee profits, but the tools work when used right.\n"
            followup_text += "If you missed your shot last time, you're still eligible now 👇"
            
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            keyboard = [
                [InlineKeyboardButton("➡️ Activate My Tools Now", callback_data="activation_instructions")],
                [InlineKeyboardButton("➡️ Contact support team", url=f"https://t.me/{BotConfig.ADMIN_USERNAME}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await self.bot.send_message(
                chat_id=user.id,
                text=followup_text,
                reply_markup=reply_markup
            )
        
        return followup_day8
    
    def _get_day9_handler(self) -> Callable[[Any, ContextTypes.DEFAULT_TYPE], Coroutine[Any, Any, None]]:
        """Get handler for day 9 follow-up"""
        @error_handler
        async def followup_day9(update: Any, context: ContextTypes.DEFAULT_TYPE) -> None:
            """Send follow-up message for day 9 (let's help you start small offer)"""
            user = update.effective_user
            
            followup_text = "💡 Still on the fence?\n"
            followup_text += "What if you start small with $20, get access to our signals, and scale up when you're ready?\n"
            followup_text += "No pressure. We've helped hundreds of new traders start from scratch and grow step by step.\n"
            followup_text += "Ready to test it out?"
            
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            keyboard = [
                [InlineKeyboardButton("➡️ Start Small, Grow Fast", callback_data="activation_instructions")],
                [InlineKeyboardButton("➡️ Contact support team", url=f"https://t.me/{BotConfig.ADMIN_USERNAME}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await self.bot.send_message(
                chat_id=user.id,
                text=followup_text,
                reply_markup=reply_markup
            )
        
        return followup_day9
    
    def _get_day10_handler(self) -> Callable[[Any, ContextTypes.DEFAULT_TYPE], Coroutine[Any, Any, None]]:
        """Get handler for day 10 follow-up"""
        @error_handler
        async def followup_day10(update: Any, context: ContextTypes.DEFAULT_TYPE) -> None:
            """Send follow-up message for day 10 (hard close)"""
            user = update.effective_user
            
            followup_text = "⏳ FINAL REMINDER\n"
            followup_text += "We're closing registrations today for this round of free VIP access. No promises it'll open again,\n"
            followup_text += "especially not at this level of access.\n"
            followup_text += "If you want in, this is it."
            
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            keyboard = [
                [InlineKeyboardButton("➡️ ✅ Count Me In", callback_data="activation_instructions")],
                [InlineKeyboardButton("➡️ ❌ Remove Me From This List", callback_data="remove_from_list")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await self.bot.send_message(
                chat_id=user.id,
                text=followup_text,
                reply_markup=reply_markup
            )
        
        return followup_day10

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