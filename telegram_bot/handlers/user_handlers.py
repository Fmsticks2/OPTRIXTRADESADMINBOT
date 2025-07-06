"""User command handlers for OPTRIXTRADES Telegram Bot"""

import logging
from typing import Dict, Any, Optional, List

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import BotConfig
from database.connection import log_interaction

logger = logging.getLogger(__name__)

# Placeholder functions that will need to be implemented with actual logic
# These would be extracted from the original telegram_bot.py file

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /start command"""
    user_id = update.effective_user.id
    
    # Log user interaction
    await log_interaction(user_id, 'start_command', 'User started bot')
    
    # Check if user is admin first
    if str(user_id) == BotConfig.ADMIN_USER_ID:
        # Show admin dashboard for admin users
        from telegram_bot.handlers.admin_handlers import admin_command
        return await admin_command(update, context)
    else:
        # Redirect to the verification flow for regular users
        from telegram_bot.handlers.verification import start_verification
        return await start_verification(update, context)

async def vip_signals_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /vipsignals command"""
    user_id = update.effective_user.id
    await log_interaction(user_id, 'vip_signals_command', 'User accessed VIP signals')
    
    # Placeholder
    await update.message.reply_text(
        "🔒 VIP Signals are available to verified users only."
    )

async def my_account_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /myaccount command"""
    # Placeholder
    await update.message.reply_text(
        "👤 Your account information will be displayed here."
    )

async def support_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /support command"""
    user_id = update.effective_user.id
    await log_interaction(user_id, 'support_command', 'User requested support')
    
    # Placeholder
    keyboard = [
        [InlineKeyboardButton("Contact Support", callback_data="contact_support")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "📞 Need help? Our support team is here for you.",
        reply_markup=reply_markup
    )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /status command - Show user verification status"""
    user = update.effective_user
    user_id = user.id
    
    # Log user interaction
    await log_interaction(user_id, 'stats_command', 'User checked account status')
    
    try:
        # Import database utilities
        from telegram_bot.utils.database_utils import get_user_data
        from database.connection import db_manager
        
        # Get user data from database
        user_data = await get_user_data(user_id)
        
        if not user_data:
            # User not found in database
            status_text = "📊 **Account Status**\n\n"
            status_text += "❌ **Status:** Not Registered\n"
            status_text += "📝 **Action Required:** Please use /start to begin registration\n\n"
            status_text += "💡 **Next Steps:**\n"
            status_text += "• Complete account registration\n"
            status_text += "• Provide your trading UID\n"
            status_text += "• Submit verification documents"
        else:
            # Check verification status
            verification_status = user_data.get('verification_status', 'not_verified')
            registration_status = user_data.get('registration_status', 'incomplete')
            
            status_text = "📊 **Account Status**\n\n"
            status_text += f"👤 **Name:** {user.first_name}\n"
            status_text += f"🆔 **User ID:** {user_id}\n"
            
            # Show verification status with appropriate emoji and message
            if verification_status == 'approved' or verification_status == 'verified':
                status_text += "✅ **Verification Status:** Verified\n"
                status_text += "🎉 **Access Level:** Premium Member\n\n"
                status_text += "🚀 **Available Features:**\n"
                status_text += "• VIP Trading Signals\n"
                status_text += "• Premium Community Access\n"
                status_text += "• Advanced Trading Tools\n"
                status_text += "• Priority Support"
            elif verification_status == 'pending':
                status_text += "⏳ **Verification Status:** Pending Review\n"
                status_text += "🔍 **Access Level:** Under Review\n\n"
                status_text += "📋 **What's Next:**\n"
                status_text += "• Our team is reviewing your submission\n"
                status_text += "• Expected review time: 2-24 hours\n"
                status_text += "• You'll be notified once approved\n"
                status_text += f"• Need help? Contact @{BotConfig.ADMIN_USERNAME}"
            elif verification_status == 'rejected':
                status_text += "❌ **Verification Status:** Rejected\n"
                status_text += "🔄 **Access Level:** Resubmission Required\n\n"
                status_text += "📝 **Action Required:**\n"
                status_text += "• Review rejection reason\n"
                status_text += "• Submit new verification documents\n"
                status_text += "• Ensure all requirements are met\n"
                status_text += f"• Contact support: @{BotConfig.ADMIN_USERNAME}"
            else:
                status_text += "❌ **Verification Status:** Not Verified\n"
                status_text += "📝 **Access Level:** Basic User\n\n"
                status_text += "🎯 **To Get Verified:**\n"
                status_text += "• Use /start to begin verification\n"
                status_text += "• Provide your trading account UID\n"
                status_text += "• Submit deposit screenshot\n"
                status_text += "• Wait for admin approval"
        
        # Add helpful buttons
        keyboard = []
        if not user_data or user_data.get('verification_status') not in ['approved', 'verified']:
            if user_data and user_data.get('verification_status') == 'rejected':
                keyboard.append([InlineKeyboardButton("🔄 Retry Verification", callback_data="start_verification")])
            else:
                keyboard.append([InlineKeyboardButton("🚀 Start Verification", callback_data="start_verification")])
            
            # Add admin contact options for unverified users
            keyboard.append([
                InlineKeyboardButton("💬 Message Admin", url=f"https://t.me/{BotConfig.ADMIN_USERNAME}"),
                InlineKeyboardButton("📞 Contact Support", callback_data="contact_support")
            ])
        else:
            # For verified users, show support option
            keyboard.append([InlineKeyboardButton("💬 Contact Support", url=f"https://t.me/{BotConfig.ADMIN_USERNAME}")])
        
        keyboard.append([InlineKeyboardButton("🔙 Main Menu", callback_data="start_verification")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            status_text,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        
    except Exception as e:
        logger.error(f"Error in stats_command: {e}")
        await update.message.reply_text(
            "❌ **Error**\n\n"
            "Unable to retrieve your account status at the moment.\n"
            f"Please try again later or contact support: @{BotConfig.ADMIN_USERNAME}",
            parse_mode='Markdown'
        )

async def how_it_works(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /howitworks command"""
    # Placeholder
    await update.message.reply_text(
        "ℹ️ Information about how the bot works will be displayed here."
    )

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /menu command"""
    user_id = update.effective_user.id
    await log_interaction(user_id, 'menu_command', 'User accessed menu')
    
    # Placeholder
    await update.message.reply_text(
        "📋 Menu options will be displayed here."
    )

async def get_my_id_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /getmyid command"""
    user_id = update.effective_user.id
    await update.message.reply_text(f"Your Telegram ID is: {user_id}")

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text messages with proper UID detection, UPGRADE command, and admin recognition"""
    user = update.effective_user
    user_id = str(user.id)
    message_text = update.message.text.strip()
    
    # Log user interaction
    await log_interaction(int(user_id), 'text_message', f'User sent: {message_text[:50]}...')
    
    # Check if user is admin first - only handle specific admin commands outside conversation
    if str(user_id) == BotConfig.ADMIN_USER_ID:
        # Let conversation handler process admin messages when in conversation states
        # Only handle standalone admin commands here
        from telegram_bot.handlers.admin_handlers import handle_text_message_admin_standalone
        await handle_text_message_admin_standalone(update, context)
        return
    
    # Handle UPGRADE command
    if message_text.upper() == "UPGRADE":
        upgrade_text = "🚀 **PREMIUM UPGRADE AVAILABLE**\n\n"
        upgrade_text += "Ready to unlock the full power of OPTRIXTRADES?\n\n"
        upgrade_text += "**Premium Features Include:**\n"
        upgrade_text += "✅ Advanced AI Trading Bot (Auto-trades for you)\n"
        upgrade_text += "✅ VIP Signal Alerts (SMS + Email + Push)\n"
        upgrade_text += "✅ Private 1-on-1 Strategy Sessions\n"
        upgrade_text += "✅ Risk Management Blueprint\n"
        upgrade_text += "✅ Priority Support (24/7)\n"
        upgrade_text += "✅ Exclusive Market Analysis\n\n"
        upgrade_text += f"Contact our team for upgrade: @{BotConfig.ADMIN_USERNAME}"
        
        keyboard = [
            [InlineKeyboardButton("💬 Contact Support", url=f"https://t.me/{BotConfig.ADMIN_USERNAME}")],
            [InlineKeyboardButton("🌟 Join VIP Group", callback_data="vip_verification_requirements")],
            [InlineKeyboardButton("🔙 Back to Menu", callback_data="start_verification")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(upgrade_text, reply_markup=reply_markup, parse_mode='Markdown')
        return
    
    # Check if message looks like a UID (6-20 alphanumeric characters)
    if is_valid_uid(message_text):
        # This looks like a UID - start verification flow
        context.user_data['uid'] = message_text
        await update.message.reply_text(
            f"✅ UID received: {message_text}\n\n"
            "Great! Now please send a screenshot of your deposit as proof to complete verification."
        )
        return
    
    # Default response for other text messages
    await update.message.reply_text(
        "I've received your message. How can I help you?\n\n"
        "💡 **Quick Actions:**\n"
        "• Send your UID to start verification\n"
        "• Type 'UPGRADE' for premium features\n"
        "• Use /start to see the main menu"
    )

def is_valid_uid(text: str) -> bool:
    """Check if text looks like a valid UID"""
    if not text:
        return False
    
    # Remove any whitespace
    text = text.strip()
    
    # Check length
    if len(text) < BotConfig.MIN_UID_LENGTH or len(text) > BotConfig.MAX_UID_LENGTH:
        return False
    
    # Check if alphanumeric (letters and numbers only)
    if not text.isalnum():
        return False
    
    # Additional validation: should contain at least one number or letter
    has_letter = any(c.isalpha() for c in text)
    has_number = any(c.isdigit() for c in text)
    
    return has_letter or has_number

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle photo messages for verification"""
    user = update.effective_user
    user_id = user.id
    
    # Check if user has provided UID and is in verification process
    uid = context.user_data.get('uid')
    
    if uid:
        # User has UID, this photo is likely a deposit screenshot
        file_id = update.message.photo[-1].file_id
        context.user_data['screenshot_file_id'] = file_id
        
        # Notify user
        await update.message.reply_text(
            "✅ **Verification Submitted Successfully!**\n\n"
            f"**Your Details:**\n"
            f"• UID: {uid}\n"
            f"• Screenshot: Received\n\n"
            "🔍 Our team will review your submission and grant you access to the premium channel shortly.\n\n"
            "⏰ **Expected Review Time:** 2-24 hours\n"
            "📞 **Need Help?** Contact @" + BotConfig.ADMIN_USERNAME,
            parse_mode='Markdown'
        )
        
        # Notify admin if configured
        if BotConfig.ADMIN_USER_ID:
            admin_message = (
                f"🔔 **New Verification Request**\n\n"
                f"**User Details:**\n"
                f"• Name: {user.first_name} {user.last_name if user.last_name else ''}\n"
                f"• Username: @{user.username if user.username else 'None'}\n"
                f"• User ID: {user_id}\n"
                f"• UID: {uid}\n\n"
                f"**Actions:**\n"
                f"/verify {user_id} - Approve verification\n"
                f"/reject {user_id} - Reject verification"
            )
            
            try:
                await context.bot.send_message(
                    chat_id=BotConfig.ADMIN_USER_ID, 
                    text=admin_message,
                    parse_mode='Markdown'
                )
                await context.bot.send_photo(
                    chat_id=BotConfig.ADMIN_USER_ID, 
                    photo=file_id,
                    caption=f"Deposit screenshot from {user.first_name} (UID: {uid})"
                )
            except Exception as e:
                logger.error(f"Failed to notify admin: {e}")
        
        # Clear the UID from context since verification is submitted
        context.user_data.pop('uid', None)
        
    else:
        # User sent photo without UID
        await update.message.reply_text(
            "📸 I received your photo!\n\n"
            "To complete verification, please:\n"
            "1️⃣ Send your UID first\n"
            "2️⃣ Then send your deposit screenshot\n\n"
            "💡 **Tip:** Send your UID as a text message, then upload your screenshot."
        )

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle document messages"""
    # Placeholder
    await update.message.reply_text(
        "I've received your document. How can I help you?"
    )

async def contact_support(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle contact_support callback"""
    # Placeholder
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        f"Please contact our support team at @{BotConfig.ADMIN_USERNAME}"
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button callbacks"""
    # Placeholder
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "Button callback received."
    )