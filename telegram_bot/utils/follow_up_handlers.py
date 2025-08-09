"""Follow-up message handlers based on newfollowup.txt content"""

import logging
from typing import Callable, Any, Coroutine
from telegram.ext import ContextTypes
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from config import BotConfig
from telegram_bot.utils.error_handler import error_handler_decorator

logger = logging.getLogger(__name__)

class FollowUpHandlers:
    """Collection of follow-up message handlers"""
    
    def __init__(self, bot):
        self.bot = bot
    
    def get_sequence1_handler(self) -> Callable[[Any, ContextTypes.DEFAULT_TYPE], Coroutine[Any, Any, None]]:
        """Get handler for sequence 1 follow-up"""
        @error_handler_decorator
        async def followup_sequence1(update: Any, context: ContextTypes.DEFAULT_TYPE) -> None:
            user = update.effective_user
            user_name = user.first_name or "there"
            
            followup_text = f"Hey {user_name} 👋\n\n"
            followup_text += "just checking in…\n"
            followup_text += "You haven't completed your free VIP access setup yet. If you still want:\n"
            followup_text += "✅ Daily signals\n"
            followup_text += "✅ Auto trading bot\n"
            followup_text += "✅ Bonus deposit rewards\n"
            followup_text += "…then don't miss out. Traders are already making serious moves this week.\n"
            followup_text += "Tap below to continue your registration. You're just one step away 👇"
            
            keyboard = [
                [InlineKeyboardButton("➡️ Claim Free Access Now", callback_data="activation_instructions")],
                [InlineKeyboardButton("➡️ Contact support team", url=f"https://t.me/{BotConfig.ADMIN_USERNAME}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await self.bot.send_message(
                chat_id=user.id,
                text=followup_text,
                reply_markup=reply_markup
            )
        
        return followup_sequence1
    
    def get_sequence2_handler(self) -> Callable[[Any, ContextTypes.DEFAULT_TYPE], Coroutine[Any, Any, None]]:
        """Get handler for sequence 2 follow-up"""
        @error_handler_decorator
        async def followup_sequence2(update: Any, context: ContextTypes.DEFAULT_TYPE) -> None:
            user = update.effective_user
            user_name = user.first_name or "there"
            
            followup_text = f"⌛ Still thinking, {user_name}?\n\n"
            followup_text += "This could be the shift you've been waiting for. The sooner you move, the better for you.\n"
            followup_text += "Free slot won't be open forever."
            
            keyboard = [
                [InlineKeyboardButton("➡️ Claim Free Access Now", callback_data="activation_instructions")],
                [InlineKeyboardButton("➡️ Contact support team", url=f"https://t.me/{BotConfig.ADMIN_USERNAME}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await self.bot.send_message(
                chat_id=user.id,
                text=followup_text,
                reply_markup=reply_markup
            )
        
        return followup_sequence2
    
    def get_sequence3_handler(self) -> Callable[[Any, ContextTypes.DEFAULT_TYPE], Coroutine[Any, Any, None]]:
        """Get handler for sequence 3 follow-up"""
        @error_handler_decorator
        async def followup_sequence3(update: Any, context: ContextTypes.DEFAULT_TYPE) -> None:
            user = update.effective_user
            
            followup_text = "👋 Just checking in... You haven't taken the next step yet. Are you having any issues?\n\n"
            followup_text += "Let's fix that and get you in before it's too late."
            
            keyboard = [
                [InlineKeyboardButton("➡️ Claim Free Access Now", callback_data="activation_instructions")],
                [InlineKeyboardButton("➡️ Contact support team", url=f"https://t.me/{BotConfig.ADMIN_USERNAME}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await self.bot.send_message(
                chat_id=user.id,
                text=followup_text,
                reply_markup=reply_markup
            )
        
        return followup_sequence3
    
    def get_sequence4_handler(self) -> Callable[[Any, ContextTypes.DEFAULT_TYPE], Coroutine[Any, Any, None]]:
        """Get handler for sequence 4 follow-up"""
        @error_handler_decorator
        async def followup_sequence4(update: Any, context: ContextTypes.DEFAULT_TYPE) -> None:
            user = update.effective_user
            
            followup_text = "👋 Just an update…\n\n"
            followup_text += "We've already had many traders activate their access this week and most of them are already "
            followup_text += "using the free bot + signals to start profiting.\n\n"
            followup_text += "You're still eligible but access may close soon once we hit this week's quota.\n\n"
            followup_text += "Don't miss your shot."
            
            keyboard = [
                [InlineKeyboardButton("➡️ Complete My Free access.", callback_data="activation_instructions")],
                [InlineKeyboardButton("➡️ Contact support team", url=f"https://t.me/{BotConfig.ADMIN_USERNAME}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await self.bot.send_message(
                chat_id=user.id,
                text=followup_text,
                reply_markup=reply_markup
            )
        
        return followup_sequence4
    
    def get_sequence5_handler(self) -> Callable[[Any, ContextTypes.DEFAULT_TYPE], Coroutine[Any, Any, None]]:
        """Get handler for sequence 5 follow-up"""
        @error_handler_decorator
        async def followup_sequence5(update: Any, context: ContextTypes.DEFAULT_TYPE) -> None:
            user = update.effective_user
            user_name = user.first_name or "there"
            
            followup_text = f"👋 You've come this far. Why stop now, {user_name}?\n\n"
            followup_text += "Everything you need to be a successful trader is on our premium channel\n\n"
            followup_text += "Tap the button and let's make it real."
            
            keyboard = [
                [InlineKeyboardButton("➡️ Claim Free Access Now", callback_data="activation_instructions")],
                [InlineKeyboardButton("➡️ Contact support team", url=f"https://t.me/{BotConfig.ADMIN_USERNAME}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await self.bot.send_message(
                chat_id=user.id,
                text=followup_text,
                reply_markup=reply_markup
            )
        
        return followup_sequence5
    
    def get_sequence6_handler(self) -> Callable[[Any, ContextTypes.DEFAULT_TYPE], Coroutine[Any, Any, None]]:
        """Get handler for sequence 6 follow-up"""
        @error_handler_decorator
        async def followup_sequence6(update: Any, context: ContextTypes.DEFAULT_TYPE) -> None:
            user = update.effective_user
            user_name = user.first_name or "there"
            
            followup_text = "⏰ Opportunities don't wait.\n\n"
            followup_text += "Every minute you delay, someone else is stepping up.\n\n"
            followup_text += f"Don't get left behind, {user_name}."
            
            keyboard = [
                [InlineKeyboardButton("➡️ Claim Free Access Now", callback_data="activation_instructions")],
                [InlineKeyboardButton("➡️ Contact support team", url=f"https://t.me/{BotConfig.ADMIN_USERNAME}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await self.bot.send_message(
                chat_id=user.id,
                text=followup_text,
                reply_markup=reply_markup
            )
        
        return followup_sequence6
    
    def get_sequence7_handler(self) -> Callable[[Any, ContextTypes.DEFAULT_TYPE], Coroutine[Any, Any, None]]:
        """Get handler for sequence 7 follow-up"""
        @error_handler_decorator
        async def followup_sequence7(update: Any, context: ContextTypes.DEFAULT_TYPE) -> None:
            user = update.effective_user
            
            followup_text = "Hey! Just wanted to remind you of everything you get for free once you sign up:\n\n"
            followup_text += "✅ Daily VIP signals\n"
            followup_text += "✅ Auto-trading bot\n"
            followup_text += "✅ Strategy sessions\n"
            followup_text += "✅ Private trader group\n"
            followup_text += "✅ Up to $500 in deposit bonuses\n\n"
            followup_text += "And yes, it's still 100% free when you use our broker link 👇"
            
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
        
        return followup_sequence7
    
    def get_sequence8_handler(self) -> Callable[[Any, ContextTypes.DEFAULT_TYPE], Coroutine[Any, Any, None]]:
        """Get handler for sequence 8 follow-up"""
        @error_handler_decorator
        async def followup_sequence8(update: Any, context: ContextTypes.DEFAULT_TYPE) -> None:
            user = update.effective_user
            user_name = user.first_name or "there"
            
            followup_text = f"👋 {user_name}, just a gentle nudge.\n\n"
            followup_text += "Success rewards action, don't let procrastination steal this from you."
            
            keyboard = [
                [InlineKeyboardButton("➡️ Claim Free Access Now", callback_data="activation_instructions")],
                [InlineKeyboardButton("➡️ Contact support team", url=f"https://t.me/{BotConfig.ADMIN_USERNAME}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await self.bot.send_message(
                chat_id=user.id,
                text=followup_text,
                reply_markup=reply_markup
            )
        
        return followup_sequence8
    
    def get_sequence9_handler(self) -> Callable[[Any, ContextTypes.DEFAULT_TYPE], Coroutine[Any, Any, None]]:
        """Get handler for sequence 9 follow-up"""
        @error_handler_decorator
        async def followup_sequence9(update: Any, context: ContextTypes.DEFAULT_TYPE) -> None:
            user = update.effective_user
            user_name = user.first_name or "there"
            
            followup_text = "You saw the message, but didn't move.\n\n"
            followup_text += "That's okay, but nothing changes until you do.\n\n"
            followup_text += f"Make today count, {user_name}"
            
            keyboard = [
                [InlineKeyboardButton("➡️ Claim Free Access Now", callback_data="activation_instructions")],
                [InlineKeyboardButton("➡️ Contact support team", url=f"https://t.me/{BotConfig.ADMIN_USERNAME}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await self.bot.send_message(
                chat_id=user.id,
                text=followup_text,
                reply_markup=reply_markup
            )
        
        return followup_sequence9
    
    def get_sequence10_handler(self) -> Callable[[Any, ContextTypes.DEFAULT_TYPE], Coroutine[Any, Any, None]]:
        """Get handler for sequence 10 follow-up"""
        @error_handler_decorator
        async def followup_sequence10(update: Any, context: ContextTypes.DEFAULT_TYPE) -> None:
            user = update.effective_user
            user_name = user.first_name or "there"
            
            followup_text = f"⚡ Quick one, {user_name}.\n\n"
            followup_text += "If you're still interested, act now, thie free spot won't be open forever"
            
            keyboard = [
                [InlineKeyboardButton("➡️ Claim Free Access Now", callback_data="activation_instructions")],
                [InlineKeyboardButton("➡️ Contact support team", url=f"https://t.me/{BotConfig.ADMIN_USERNAME}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await self.bot.send_message(
                chat_id=user.id,
                text=followup_text,
                reply_markup=reply_markup
            )
        
        return followup_sequence10
    
    def get_sequence11_handler(self) -> Callable[[Any, ContextTypes.DEFAULT_TYPE], Coroutine[Any, Any, None]]:
        """Get handler for sequence 11 follow-up"""
        @error_handler_decorator
        async def followup_sequence11(update: Any, context: ContextTypes.DEFAULT_TYPE) -> None:
            user = update.effective_user
            
            followup_text = "👋 You've been on our early access list for a few days…\n\n"
            followup_text += "If you're still interested but something's holding you back, reply to this message and let's help "
            followup_text += "you sort it out.\n\n"
            followup_text += "Even if you don't have a big budget right now, we'll guide you to start small and smart."
            
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
        
        return followup_sequence11
    
    def get_sequence12_handler(self) -> Callable[[Any, ContextTypes.DEFAULT_TYPE], Coroutine[Any, Any, None]]:
        """Get handler for sequence 12 follow-up"""
        @error_handler_decorator
        async def followup_sequence12(update: Any, context: ContextTypes.DEFAULT_TYPE) -> None:
            user = update.effective_user
            user_name = user.first_name or "there"
            
            followup_text = f"👋 We don't want you to miss out, {user_name}.\n\n"
            followup_text += "So here's your friendly reminder. Click below and lock in your access."
            
            keyboard = [
                [InlineKeyboardButton("➡️ Claim Free Access Now", callback_data="activation_instructions")],
                [InlineKeyboardButton("➡️ Contact support team", url=f"https://t.me/{BotConfig.ADMIN_USERNAME}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await self.bot.send_message(
                chat_id=user.id,
                text=followup_text,
                reply_markup=reply_markup
            )
        
        return followup_sequence12
    
    def get_sequence13_handler(self) -> Callable[[Any, ContextTypes.DEFAULT_TYPE], Coroutine[Any, Any, None]]:
        """Get handler for sequence 13 follow-up"""
        @error_handler_decorator
        async def followup_sequence13(update: Any, context: ContextTypes.DEFAULT_TYPE) -> None:
            user = update.effective_user
            user_name = user.first_name or "there"
            
            followup_text = f"👋 Still on the fence, {user_name}?\n\n"
            followup_text += "What's stopping you? Let's break through that together.\n\n"
            followup_text += "One click is all it takes."
            
            keyboard = [
                [InlineKeyboardButton("➡️ Claim Free Access Now", callback_data="activation_instructions")],
                [InlineKeyboardButton("➡️ Contact support team", url=f"https://t.me/{BotConfig.ADMIN_USERNAME}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await self.bot.send_message(
                chat_id=user.id,
                text=followup_text,
                reply_markup=reply_markup
            )
        
        return followup_sequence13
    
    def get_sequence14_handler(self) -> Callable[[Any, ContextTypes.DEFAULT_TYPE], Coroutine[Any, Any, None]]:
        """Get handler for sequence 14 follow-up"""
        @error_handler_decorator
        async def followup_sequence14(update: Any, context: ContextTypes.DEFAULT_TYPE) -> None:
            user = update.effective_user
            
            followup_text = "👋 FINAL REMINDER\n\n"
            followup_text += "We're closing registrations today for this round of free VIP access. No promises it'll open again, "
            followup_text += "especially not at this level of access.\n\n"
            followup_text += "If you want in, this is it."
            
            keyboard = [
                [InlineKeyboardButton("➡️✅ Count Me In", callback_data="activation_instructions")],
                [InlineKeyboardButton("➡️❌ Remove Me From This List", callback_data="remove_from_list")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await self.bot.send_message(
                chat_id=user.id,
                text=followup_text,
                reply_markup=reply_markup
            )
        
        return followup_sequence14
    
    def get_sequence15_handler(self) -> Callable[[Any, ContextTypes.DEFAULT_TYPE], Coroutine[Any, Any, None]]:
        """Get handler for sequence 15 follow-up"""
        @error_handler_decorator
        async def followup_sequence15(update: Any, context: ContextTypes.DEFAULT_TYPE) -> None:
            user = update.effective_user
            user_name = user.first_name or "there"
            
            followup_text = f"👋 Your wake-up call, {user_name}.\n\n"
            followup_text += "Every hour, someone else makes a move.\n\n"
            followup_text += "Be one of them."
            
            keyboard = [
                [InlineKeyboardButton("➡️ Claim Free Access Now", callback_data="activation_instructions")],
                [InlineKeyboardButton("➡️ Contact support team", url=f"https://t.me/{BotConfig.ADMIN_USERNAME}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await self.bot.send_message(
                chat_id=user.id,
                text=followup_text,
                reply_markup=reply_markup
            )
        
        return followup_sequence15
    
    def get_sequence16_handler(self) -> Callable[[Any, ContextTypes.DEFAULT_TYPE], Coroutine[Any, Any, None]]:
        """Get handler for sequence 16 follow-up"""
        @error_handler_decorator
        async def followup_sequence16(update: Any, context: ContextTypes.DEFAULT_TYPE) -> None:
            user = update.effective_user
            user_name = user.first_name or "there"
            
            followup_text = f"This is for you, {user_name}.\n\n"
            followup_text += "Not just anyone.\n\n"
            followup_text += "You joined for a reason, honor that reason."
            
            keyboard = [
                [InlineKeyboardButton("➡️ Claim Free Access Now", callback_data="activation_instructions")],
                [InlineKeyboardButton("➡️ Contact support team", url=f"https://t.me/{BotConfig.ADMIN_USERNAME}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await self.bot.send_message(
                chat_id=user.id,
                text=followup_text,
                reply_markup=reply_markup
            )
        
        return followup_sequence16
    
    def get_sequence17_handler(self) -> Callable[[Any, ContextTypes.DEFAULT_TYPE], Coroutine[Any, Any, None]]:
        """Get handler for sequence 17 follow-up"""
        @error_handler_decorator
        async def followup_sequence17(update: Any, context: ContextTypes.DEFAULT_TYPE) -> None:
            user = update.effective_user
            
            followup_text = "Wondering if OPTRIXTRADES is legit?\n\n"
            followup_text += "We totally get it. That's why we host free sessions, give access to our AI, and don't charge "
            followup_text += "upfront.\n\n"
            followup_text += "✅ Real traders use us.\n"
            followup_text += "✅ Real results.\n"
            followup_text += "✅ Real support, 24/7.\n\n"
            followup_text += "We only earn a small % when you win. That's why we want to help you trade smarter.\n\n"
            followup_text += "Want to test us out with just $20?"
            
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
        
        return followup_sequence17
    
    def get_sequence18_handler(self) -> Callable[[Any, ContextTypes.DEFAULT_TYPE], Coroutine[Any, Any, None]]:
        """Get handler for sequence 18 follow-up"""
        @error_handler_decorator
        async def followup_sequence18(update: Any, context: ContextTypes.DEFAULT_TYPE) -> None:
            user = update.effective_user
            user_name = user.first_name or "there"
            
            followup_text = f"You deserve better. {user_name}.\n\n"
            followup_text += "And this is the first step.\n\n"
            followup_text += "Don't delay the version of you that's waiting to become a profitable trader!"
            
            keyboard = [
                [InlineKeyboardButton("➡️ Claim Free Access Now", callback_data="activation_instructions")],
                [InlineKeyboardButton("➡️ Contact support team", url=f"https://t.me/{BotConfig.ADMIN_USERNAME}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await self.bot.send_message(
                chat_id=user.id,
                text=followup_text,
                reply_markup=reply_markup
            )
        
        return followup_sequence18
    
    def get_sequence19_handler(self) -> Callable[[Any, ContextTypes.DEFAULT_TYPE], Coroutine[Any, Any, None]]:
        """Get handler for sequence 19 follow-up"""
        @error_handler_decorator
        async def followup_sequence19(update: Any, context: ContextTypes.DEFAULT_TYPE) -> None:
            user = update.effective_user
            user_name = user.first_name or "there"
            
            followup_text = f"Quick reminder, {user_name}.\n\n"
            followup_text += "You haven't taken action. We're holding space, but not for long."
            
            keyboard = [
                [InlineKeyboardButton("➡️ Claim Free Access Now", callback_data="activation_instructions")],
                [InlineKeyboardButton("➡️ Contact support team", url=f"https://t.me/{BotConfig.ADMIN_USERNAME}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await self.bot.send_message(
                chat_id=user.id,
                text=followup_text,
                reply_markup=reply_markup
            )
        
        return followup_sequence19
    
    def get_sequence20_handler(self) -> Callable[[Any, ContextTypes.DEFAULT_TYPE], Coroutine[Any, Any, None]]:
        """Get handler for sequence 20 follow-up"""
        @error_handler_decorator
        async def followup_sequence20(update: Any, context: ContextTypes.DEFAULT_TYPE) -> None:
            user = update.effective_user
            
            followup_text = "Okay… we're starting to think you're ghosting us 😂\n\n"
            followup_text += "But seriously, if you've been busy, no stress. Just pick up where you left off and grab your free "
            followup_text += "access before this week closes.\n\n"
            followup_text += "The AI bot is still available for new traders using our link."
            
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
        
        return followup_sequence20
    
    def get_sequence21_handler(self) -> Callable[[Any, ContextTypes.DEFAULT_TYPE], Coroutine[Any, Any, None]]:
        """Get handler for sequence 21 follow-up"""
        @error_handler_decorator
        async def followup_sequence21(update: Any, context: ContextTypes.DEFAULT_TYPE) -> None:
            user = update.effective_user
            user_name = user.first_name or "there"
            
            followup_text = f"We're still waiting on you, {user_name}.\n\n"
            followup_text += "But not forever. Tap in before the window closes."
            
            keyboard = [
                [InlineKeyboardButton("➡️ Claim Free Access Now", callback_data="activation_instructions")],
                [InlineKeyboardButton("➡️ Contact support team", url=f"https://t.me/{BotConfig.ADMIN_USERNAME}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await self.bot.send_message(
                chat_id=user.id,
                text=followup_text,
                reply_markup=reply_markup
            )
        
        return followup_sequence21
    
    def get_sequence22_handler(self) -> Callable[[Any, ContextTypes.DEFAULT_TYPE], Coroutine[Any, Any, None]]:
        """Get handler for sequence 22 follow-up"""
        @error_handler_decorator
        async def followup_sequence22(update: Any, context: ContextTypes.DEFAULT_TYPE) -> None:
            user = update.effective_user
            
            followup_text = "Don't look back with regret.\n\n"
            followup_text += "Moments like this seem small... until they're gone. Act now."
            
            keyboard = [
                [InlineKeyboardButton("➡️ Claim Free Access Now", callback_data="activation_instructions")],
                [InlineKeyboardButton("➡️ Contact support team", url=f"https://t.me/{BotConfig.ADMIN_USERNAME}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await self.bot.send_message(
                chat_id=user.id,
                text=followup_text,
                reply_markup=reply_markup
            )
        
        return followup_sequence22
    
    def get_sequence23_handler(self) -> Callable[[Any, ContextTypes.DEFAULT_TYPE], Coroutine[Any, Any, None]]:
        """Get handler for sequence 23 follow-up"""
        @error_handler_decorator
        async def followup_sequence23(update: Any, context: ContextTypes.DEFAULT_TYPE) -> None:
            user = update.effective_user
            
            followup_text = "Another trader just flipped a $100 deposit into $390 using our AI bot + signal combo in 4 days.\n\n"
            followup_text += "We can't guarantee profits, but the tools work when used right.\n\n"
            followup_text += "If you missed your shot last time, you're still eligible now 👇"
            
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
        
        return followup_sequence23
    
    def get_sequence24_handler(self) -> Callable[[Any, ContextTypes.DEFAULT_TYPE], Coroutine[Any, Any, None]]:
        """Get handler for sequence 24 follow-up"""
        @error_handler_decorator
        async def followup_sequence24(update: Any, context: ContextTypes.DEFAULT_TYPE) -> None:
            user = update.effective_user
            
            followup_text = "👋 Still on the fence?\n\n"
            followup_text += "What if you start small with $20, get access to our signals, and scale up when you're ready?\n\n"
            followup_text += "No pressure. We've helped hundreds of new traders start from scratch and grow step by step.\n\n"
            followup_text += "Ready to test it out?"
            
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
        
        return followup_sequence24