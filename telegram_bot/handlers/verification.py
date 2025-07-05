"""Verification flow handlers for OPTRIXTRADES Telegram Bot"""

import logging
from typing import Dict, Any, Optional, List, Union

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from config import BotConfig
from telegram_bot.utils.error_handler import error_handler
from telegram_bot.utils.monitoring import measure_time
from telegram_bot.utils.decorators import rate_limit

logger = logging.getLogger(__name__)

# Conversation states
REGISTER_UID = 0
UPLOAD_SCREENSHOT = 1

# Flow tracking in user_data
FLOW_KEY = "verification_flow"
FLOW_WELCOME = "welcome"
FLOW_ACTIVATION = "activation"
FLOW_CONFIRMATION = "confirmation"
FLOW_FOLLOWUP = "followup"

@error_handler
@measure_time
@rate_limit(5, 60)  # 5 requests per minute
async def start_verification(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the verification process with welcome message"""
    # Handle both command and callback query
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        message = query.message
        user = query.from_user
    else:
        message = update.message
        user = update.effective_user
    
    # Store flow state
    if not context.user_data.get(FLOW_KEY):
        context.user_data[FLOW_KEY] = FLOW_WELCOME
        
        # Schedule follow-ups for this user
        from telegram_bot.bot import TradingBot
        if isinstance(context.application.bot_data.get('bot_instance'), TradingBot):
            bot_instance = context.application.bot_data.get('bot_instance')
            await bot_instance.schedule_follow_ups(user.id, context)
    
    # Get user's first name or username
    user_name = user.first_name or user.username or "there"
    
    # Welcome message (Flow 1)
    welcome_text = f"Heyy {user_name}\n"
    welcome_text += "Welcome to OPTRIXTRADES\n"
    welcome_text += "you're one step away from unlocking high-accuracy trading signals, expert strategies, and real\n"
    welcome_text += "trader bonuses, completely free.\n"
    welcome_text += "Here's what you get as a member:\n"
    welcome_text += "✅ Daily VIP trading signals\n"
    welcome_text += "✅ Strategy sessions from 6-figure traders\n"
    welcome_text += "✅ Access to our private trader community\n"
    welcome_text += "✅ Exclusive signup bonuses (up to $500)\n"
    welcome_text += "✅ Automated trading bot – trade while you sleep\n"
    welcome_text += "👇 Tap below to activate your free VIP access and get started."
    
    # Create keyboard with activation button
    keyboard = [
        [InlineKeyboardButton("➡️ Get Free VIP Access", callback_data="activation_instructions")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Send welcome message
    if update.callback_query:
        await message.edit_text(welcome_text, reply_markup=reply_markup)
    else:
        await message.reply_text(welcome_text, reply_markup=reply_markup)
    
    return ConversationHandler.END

@error_handler
@measure_time
async def activation_instructions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show activation instructions (Flow 2)"""
    query = update.callback_query
    await query.answer()
    
    # Update flow state
    context.user_data[FLOW_KEY] = FLOW_ACTIVATION
    
    # Activation instructions text
    activation_text = "To activate your free access and join our VIP Signal Channel, follow these steps:\n"
    activation_text += "1️⃣Click the link below to register with our official broker partner\n"
    activation_text += f"[{BotConfig.BROKER_LINK}]\n"
    activation_text += "2️⃣Deposit $20 or more\n"
    activation_text += "3️⃣Send your proof of deposit\n"
    activation_text += "once your proof have been confirmed your access will be unlocked immediately\n\n"
    activation_text += "The more you deposit, the more powerful your AI access:\n"
    activation_text += "✅ $100+ → Full access to OPTRIX Web AI Portal, Live Signals & AI tools.\n"
    activation_text += "✅ $500+ → Includes:\n"
    activation_text += "— All available signal alert options\n"
    activation_text += "— VIP telegram group\n"
    activation_text += "— Access to private sessions and risk management blueprint\n"
    activation_text += "— OPTRIX AI Auto-Trading (trades for you automatically)"
    
    # Create keyboard with registration buttons
    keyboard = [
        [InlineKeyboardButton("➡️ I've Registered", callback_data="registered")],
        [InlineKeyboardButton("➡️ Need help signing up", callback_data="signup_help")],
        [InlineKeyboardButton("➡️ Need support making a deposit", callback_data="deposit_help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Send activation instructions
    await query.message.edit_text(activation_text, reply_markup=reply_markup)
    
    # Send follow-up message about why it's free
    why_free_text = "Why is it free?\n"
    why_free_text += "We earn a small commission from the broker through your trading volume, not your money. So\n"
    why_free_text += "we are more focused on your success, the more you win, the better for both of us. ✅\n\n"
    why_free_text += "Want to unlock even higher-tier bonuses or full bot access?\n"
    why_free_text += "Send \"UPGRADE\""
    
    # Send as a separate message
    await query.message.reply_text(why_free_text)
    
    return ConversationHandler.END

@error_handler
@measure_time
async def registered_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle user confirmation of registration (Flow 3)"""
    query = update.callback_query
    await query.answer()
    
    # Update flow state
    context.user_data[FLOW_KEY] = FLOW_CONFIRMATION
    
    # Confirmation text
    confirmation_text = "Send in your uid and deposit screenshot to gain access optrixtrades trades premium signal channel.\n\n"
    confirmation_text += "BONUS: We're hosting a live session soon with exclusive insights. Stay tuned. Get an early\n"
    confirmation_text += "access now into our premium channel only limited slots are available."
    
    # Send confirmation message
    await query.message.edit_text(confirmation_text)
    
    # Set state for conversation handler
    return REGISTER_UID

@error_handler
@measure_time
async def handle_uid_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process the UID sent by the user"""
    # Store the UID in context
    context.user_data['uid'] = update.message.text.strip()
    
    # Ask for screenshot
    await update.message.reply_text(
        "Great! Now please send a screenshot of your deposit as proof."
    )
    
    return UPLOAD_SCREENSHOT

@error_handler
@measure_time
async def handle_screenshot_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process the screenshot uploaded by the user"""
    user = update.effective_user
    user_id = user.id
    uid = context.user_data.get('uid', 'Unknown')
    
    # Get the photo file_id
    if update.message.photo:
        file_id = update.message.photo[-1].file_id
    else:  # Document
        file_id = update.message.document.file_id
    
    # Store verification data
    context.user_data['screenshot_file_id'] = file_id
    
    # TODO: Implement actual verification request creation in database
    # await create_verification_request(user_id, uid, file_id)
    
    # Notify user
    await update.message.reply_text(
        "✅ Thank you! Your verification information has been submitted.\n\n"
        "Our team will review your submission and grant you access to the premium channel shortly.\n\n"
        "Please wait for confirmation."
    )
    
    # Notify admin (placeholder)
    admin_message = (
        f"🔔 New verification request:\n"
        f"User: {user.first_name} {user.last_name if user.last_name else ''}\n"
        f"Username: @{user.username if user.username else 'None'}\n"
        f"User ID: {user_id}\n"
        f"UID: {uid}\n"
    )
    
    # TODO: Send notification to admin
    # if BotConfig.ADMIN_USER_ID:
    #     await context.bot.send_message(chat_id=BotConfig.ADMIN_USER_ID, text=admin_message)
    #     await context.bot.send_photo(chat_id=BotConfig.ADMIN_USER_ID, photo=file_id)
    
    # Cancel any scheduled follow-ups since verification is complete
    from telegram_bot.utils.follow_up_scheduler import get_follow_up_scheduler
    scheduler = get_follow_up_scheduler()
    if scheduler:
        await scheduler.cancel_follow_ups(user_id)
        logger.info(f"Cancelled follow-ups for user {user_id} as verification is complete")
    
    return ConversationHandler.END

@error_handler
async def signup_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Provide help with signing up"""
    query = update.callback_query
    await query.answer()
    
    # TODO: Replace with actual video or instructions
    await query.message.reply_text(
        "Here's how to sign up with our broker partner:\n\n"
        "1. Click the registration link\n"
        "2. Enter your details\n"
        "3. Verify your email\n"
        "4. Complete your profile\n\n"
        "A detailed video guide will be available soon."
    )

@error_handler
async def deposit_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Provide help with making a deposit"""
    query = update.callback_query
    await query.answer()
    
    # TODO: Replace with actual video or instructions
    await query.message.reply_text(
        "Here's how to make a deposit with our broker partner:\n\n"
        "1. Log in to your account\n"
        "2. Navigate to the Deposit section\n"
        "3. Choose your preferred payment method\n"
        "4. Follow the instructions to complete your deposit\n\n"
        "A detailed video guide will be available soon."
    )

@error_handler
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the verification process"""
    if update.message:
        await update.message.reply_text(
            "❌ Verification process cancelled. You can restart anytime with /verify."
        )
    else:
        query = update.callback_query
        await query.answer()
        await query.message.reply_text(
            "❌ Verification process cancelled. You can restart anytime with /verify."
        )
    
    return ConversationHandler.END

# Follow-up message handlers for leads who stop interacting
@error_handler
async def followup_day1(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send follow-up message for day 1"""
    user = update.effective_user
    user_name = user.first_name or user.username or "there"
    
    followup_text = f"Hey {user_name} 👋 just checking in…\n"
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
    
    await context.bot.send_message(
        chat_id=user.id,
        text=followup_text,
        reply_markup=reply_markup
    )

@error_handler
async def followup_day2(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send follow-up message for day 2 (scarcity + social proof)"""
    user = update.effective_user
    
    followup_text = "🔥 Just an update…\n"
    followup_text += "We've already had 42 traders activate their access this week and most of them are already\n"
    followup_text += "using the free bot + signals to start profiting.\n"
    followup_text += "You're still eligible but access may close soon once we hit this week's quota.\n"
    followup_text += "Don't miss your shot."
    
    keyboard = [
        [InlineKeyboardButton("➡️ Complete My Free access", callback_data="activation_instructions")],
        [InlineKeyboardButton("➡️ Contact support team", url=f"https://t.me/{BotConfig.ADMIN_USERNAME}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=user.id,
        text=followup_text,
        reply_markup=reply_markup
    )

@error_handler
async def followup_day3(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send follow-up message for day 3 (value recap)"""
    user = update.effective_user
    
    followup_text = "Hey! Just wanted to remind you of everything you get for free once you sign up:\n"
    followup_text += "✅ Daily VIP signals\n"
    followup_text += "✅ Auto-trading bot\n"
    followup_text += "✅ Strategy sessions\n"
    followup_text += "✅ Private trader group\n"
    followup_text += "✅ Up to $500 in deposit bonuses\n"
    followup_text += "And yes, it's still 100% free when you use our broker link 👇"
    
    keyboard = [
        [InlineKeyboardButton("➡️ I'm Ready to Activate", callback_data="activation_instructions")],
        [InlineKeyboardButton("➡️ Contact support team", url=f"https://t.me/{BotConfig.ADMIN_USERNAME}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=user.id,
        text=followup_text,
        reply_markup=reply_markup
    )

@error_handler
async def followup_day4(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send follow-up message for day 4 (personal + soft CTA)"""
    user = update.effective_user
    
    followup_text = "👀 You've been on our early access list for a few days…\n"
    followup_text += "If you're still interested but something's holding you back, reply to this message and let's help\n"
    followup_text += "you sort it out.\n"
    followup_text += "Even if you don't have a big budget right now, we'll guide you to start small and smart."
    
    keyboard = [
        [InlineKeyboardButton("➡️ I Have a Question", url=f"https://t.me/{BotConfig.ADMIN_USERNAME}")],
        [InlineKeyboardButton("➡️ Continue Activation", callback_data="activation_instructions")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=user.id,
        text=followup_text,
        reply_markup=reply_markup
    )

@error_handler
async def followup_day5(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send follow-up message for day 5 (last chance + exit option)"""
    user = update.effective_user
    
    followup_text = "📌 Last call to claim your free access to OPTRIXTRADES.\n"
    followup_text += "This week's onboarding closes in a few hours. After that, you'll need to wait for the next batch,\n"
    followup_text += "no guarantees it'll still be free.\n"
    followup_text += "Want in?"
    
    keyboard = [
        [InlineKeyboardButton("✅ Yes, Activate Me Now", callback_data="activation_instructions")],
        [InlineKeyboardButton("❌ Not Interested", callback_data="not_interested")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=user.id,
        text=followup_text,
        reply_markup=reply_markup
    )

@error_handler
async def followup_day6(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
    
    keyboard = [
        [InlineKeyboardButton("➡️ Try With $20 I'm Curious", callback_data="activation_instructions")],
        [InlineKeyboardButton("➡️ Contact support team", url=f"https://t.me/{BotConfig.ADMIN_USERNAME}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=user.id,
        text=followup_text,
        reply_markup=reply_markup
    )

@error_handler
async def followup_day7(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send follow-up message for day 7 (light humor + re-activation)"""
    user = update.effective_user
    
    followup_text = "Okay… we're starting to think you're ghosting us 😂\n"
    followup_text += "But seriously, if you've been busy, no stress. Just pick up where you left off and grab your free\n"
    followup_text += "access before this week closes.\n"
    followup_text += "The AI bot is still available for new traders using our link."
    
    keyboard = [
        [InlineKeyboardButton("➡️ Okay, Let's Do This", callback_data="activation_instructions")],
        [InlineKeyboardButton("➡️ Contact support team", url=f"https://t.me/{BotConfig.ADMIN_USERNAME}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=user.id,
        text=followup_text,
        reply_markup=reply_markup
    )

@error_handler
async def followup_day8(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send follow-up message for day 8 (FOMO + new success update)"""
    user = update.effective_user
    
    followup_text = "Another trader just flipped a $100 deposit into $390 using our AI bot + signal combo in 4 days.\n"
    followup_text += "We can't guarantee profits, but the tools work when used right.\n"
    followup_text += "If you missed your shot last time, you're still eligible now 👇"
    
    keyboard = [
        [InlineKeyboardButton("➡️ Activate My Tools Now", callback_data="activation_instructions")],
        [InlineKeyboardButton("➡️ Contact support team", url=f"https://t.me/{BotConfig.ADMIN_USERNAME}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=user.id,
        text=followup_text,
        reply_markup=reply_markup
    )

@error_handler
async def followup_day9(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send follow-up message for day 9 (let's help you start small offer)"""
    user = update.effective_user
    
    followup_text = "💡 Still on the fence?\n"
    followup_text += "What if you start small with $20, get access to our signals, and scale up when you're ready?\n"
    followup_text += "No pressure. We've helped hundreds of new traders start from scratch and grow step by step.\n"
    followup_text += "Ready to test it out?"
    
    keyboard = [
        [InlineKeyboardButton("➡️ Start Small, Grow Fast", callback_data="activation_instructions")],
        [InlineKeyboardButton("➡️ Contact support team", url=f"https://t.me/{BotConfig.ADMIN_USERNAME}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=user.id,
        text=followup_text,
        reply_markup=reply_markup
    )

@error_handler
async def followup_day10(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send follow-up message for day 10 (hard close)"""
    user = update.effective_user
    
    followup_text = "⏳ FINAL REMINDER\n"
    followup_text += "We're closing registrations today for this round of free VIP access. No promises it'll open again,\n"
    followup_text += "especially not at this level of access.\n"
    followup_text += "If you want in, this is it."
    
    keyboard = [
        [InlineKeyboardButton("➡️ ✅ Count Me In", callback_data="activation_instructions")],
        [InlineKeyboardButton("➡️ ❌ Remove Me From This List", callback_data="remove_from_list")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=user.id,
        text=followup_text,
        reply_markup=reply_markup
    )

@error_handler
async def handle_not_interested(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle when user indicates they are not interested"""
    query = update.callback_query
    await query.answer()
    
    await query.message.edit_text(
        "We understand. Thanks for considering OPTRIXTRADES.\n\n"
        "If you change your mind, you can always restart with /start.\n\n"
        "Have a great day!"
    )
    
    # Cancel any scheduled follow-ups
    from telegram_bot.utils.follow_up_scheduler import get_follow_up_scheduler
    scheduler = get_follow_up_scheduler()
    if scheduler:
        await scheduler.cancel_follow_ups(query.from_user.id)

@error_handler
async def handle_remove_from_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle when user wants to be removed from follow-up list"""
    query = update.callback_query
    await query.answer()
    
    await query.message.edit_text(
        "You've been removed from our follow-up list.\n\n"
        "If you change your mind in the future, you can always restart with /start.\n\n"
        "Thanks for your time!"
    )
    
    # Cancel any scheduled follow-ups
    from telegram_bot.utils.follow_up_scheduler import get_follow_up_scheduler
    scheduler = get_follow_up_scheduler()
    if scheduler:
        await scheduler.cancel_follow_ups(query.from_user.id)