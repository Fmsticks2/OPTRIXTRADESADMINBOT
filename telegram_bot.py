import logging
import os
import asyncio
import re
import traceback
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    TypeHandler
)
from telegram.error import TelegramError, RetryAfter
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import gettext
from pathlib import Path

# Import database manager
from database import db_manager, get_user_data, update_user_data, create_user, log_interaction
from config import config

# Configure internationalization
LOCALE_DIR = Path(__file__).parent / "locales"
gettext.bindtextdomain('tradingbot', LOCALE_DIR)
gettext.textdomain('tradingbot')
_ = gettext.gettext

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=getattr(logging, config.LOG_LEVEL),
    handlers=[
        logging.FileHandler(config.LOG_FILE_PATH),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class TradingBot:
    def __init__(self):
        self.premium_channel_link = f"https://t.me/c/{config.PREMIUM_CHANNEL_ID.replace('-100', '')}"
        self.user_activity: Dict[int, Dict[str, datetime]] = {}  # For rate limiting
        self.supported_languages = ['en', 'es', 'fr', 'de']  # Supported languages
        
        # Initialize error handler
        self.error_handler = self.telegram_error_handler
        
        # Keyboards initialization
        self._init_keyboards()

    def _init_keyboards(self):
        """Initialize all inline keyboards"""
        self.admin_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(_("📊 Statistics"), callback_data="admin_stats"),
             InlineKeyboardButton(_("👥 Verification Queue"), callback_data="admin_queue")],
            [InlineKeyboardButton(_("📢 Post Signal"), callback_data="post_signal"),
             InlineKeyboardButton(_("📝 Edit Last Signal"), callback_data="edit_signal")],
            [InlineKeyboardButton(_("⚙️ Bot Settings"), callback_data="bot_settings")]
        ])
        
        self.user_main_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(_("💎 VIP Access"), callback_data="get_vip_access")],
            [InlineKeyboardButton(_("📱 My Account"), callback_data="my_account"),
             InlineKeyboardButton(_("ℹ️ Help"), callback_data="help_menu")],
            [InlineKeyboardButton(_("🌐 Language"), callback_data="language_menu"),
             InlineKeyboardButton(_("📞 Support"), callback_data="contact_support")]
        ])
        
        self.help_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(_("📝 Registration Help"), callback_data="help_signup"),
             InlineKeyboardButton(_("💳 Deposit Help"), callback_data="help_deposit")],
            [InlineKeyboardButton(_("❓ FAQ"), callback_data="faq"),
             InlineKeyboardButton(_("📞 Contact Support"), callback_data="contact_support")],
            [InlineKeyboardButton(_("🔙 Back to Main Menu"), callback_data="main_menu")]
        ])
        
        self.account_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(_("📊 My Status"), callback_data="account_status"),
             InlineKeyboardButton(_("⭐️ Upgrade Account"), callback_data="upgrade_account")],
            [InlineKeyboardButton(_("🔔 Notification Settings"), callback_data="notification_settings"),
             InlineKeyboardButton(_("🌐 Language Settings"), callback_data="language_menu")],
            [InlineKeyboardButton(_("🔙 Back to Main Menu"), callback_data="main_menu")]
        ])

        # Language selection keyboard
        self.language_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("English 🇬🇧", callback_data="set_lang_en")],
            [InlineKeyboardButton("Español 🇪🇸", callback_data="set_lang_es")],
            [InlineKeyboardButton("Français 🇫🇷", callback_data="set_lang_fr")],
            [InlineKeyboardButton("Deutsch 🇩🇪", callback_data="set_lang_de")],
            [InlineKeyboardButton(_("🔙 Back"), callback_data="main_menu")]
        ])

    def set_user_language(self, user_id: int, language: str):
        """Set language preference for a user"""
        if language in self.supported_languages:
            self.user_languages[user_id] = language
            return True
        return False

    def get_user_language(self, user_id: int) -> str:
        """Get user's language preference"""
        return self.user_languages.get(user_id, 'en')

    async def check_rate_limit(self, user_id: int, action: str) -> bool:
        """
        Check if user is rate limited for a specific action.
        Returns True if allowed, False if rate limited.
        """
        now = datetime.now()
        user_actions = self.user_activity.setdefault(user_id, {})
        
        last_action_time = user_actions.get(action)
        if last_action_time:
            time_diff = now - last_action_time
            if time_diff < timedelta(seconds=config.RATE_LIMITS.get(action, 1)):
                return False
        
        user_actions[action] = now
        return True

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(Exception),
        reraise=True
    )
    async def retry_db_operation(self, func, *args, **kwargs):
        """Retry a database operation with exponential backoff"""
        return await func(*args, **kwargs)

    async def telegram_error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle all Telegram bot errors"""
        logger.error(msg="Exception while handling Telegram update:", exc_info=context.error)
        
        # Handle rate limiting errors
        if isinstance(context.error, RetryAfter):
            retry_after = context.error.retry_after
            logger.warning(f"Rate limited, retrying after {retry_after} seconds")
            await asyncio.sleep(retry_after)
            return
        
        # Log error to database
        try:
            user_id = update.effective_user.id if update and update.effective_user else None
            
            error_data = {
                'error_type': type(context.error).__name__,
                'error_message': str(context.error),
                'stack_trace': ''.join(traceback.format_exception(
                    type(context.error), context.error, context.error.__traceback__)),
                'context': 'telegram_update',
                'user_id': user_id,
                'extra_data': str(update.to_dict()) if hasattr(update, 'to_dict') else None
            }
            
            await self.retry_db_operation(
                db_manager.execute_query,
                """
                INSERT INTO error_logs (
                    error_type, error_message, stack_trace, 
                    context, user_id, extra_data
                ) VALUES ($1, $2, $3, $4, $5, $6)
                """ if db_manager.db_type == 'postgresql' else """
                INSERT INTO error_logs (
                    error_type, error_message, stack_trace,
                    context, user_id, extra_data
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                tuple(error_data.values())
            )
        except Exception as db_error:
            logger.error(f"Failed to log error to database: {db_error}")

        # Try to notify the user about the error
        try:
            if update and update.effective_user:
                await context.bot.send_message(
                    chat_id=update.effective_user.id,
                    text=_("⚠️ An error occurred. Our team has been notified.")
                )
        except Exception as notify_error:
            logger.error(f"Failed to notify user: {notify_error}")

        # Notify admin about critical errors
        try:
            error_trace = ''.join(traceback.format_exception(
                type(context.error), context.error, context.error.__traceback__))
            await context.bot.send_message(
                chat_id=config.ADMIN_USER_ID,
                text=_("🚨 BOT ERROR\n\n{error_type}: {error_message}\n\n{error_trace}").format(
                    error_type=type(context.error).__name__,
                    error_message=str(context.error),
                    error_trace=error_trace[:3000]
                )
            )
        except Exception as admin_error:
            logger.error(f"Failed to notify admin: {admin_error}")

    async def initialize(self):
        """Initialize database connection with retry logic"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                await db_manager.initialize()
                logger.info("Database initialized successfully")
                return
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.critical("Failed to initialize database after retries", exc_info=True)
                    raise
                wait_time = 2 ** (attempt + 1)
                logger.warning(f"Database initialization failed (attempt {attempt + 1}), retrying in {wait_time} seconds...")
                await asyncio.sleep(wait_time)

    def validate_uid(self, uid: str) -> Tuple[bool, str]:
        """Validate UID format for auto-verification"""
        try:
            if not uid or len(uid) < config.MIN_UID_LENGTH or len(uid) > config.MAX_UID_LENGTH:
                return False, _("UID length invalid")
            
            if not re.match(r'^[a-zA-Z0-9]+$', uid):
                return False, _("UID contains invalid characters")
            
            if uid.lower() in ['test', 'demo', '123456', 'sample']:
                return False, _("UID appears to be a test/demo account")
            
            return True, _("UID format valid")
        except Exception as e:
            logger.error(f"Error validating UID {uid}: {e}")
            return False, _("UID validation error")

    async def auto_verify_user(self, user_id: int, uid: str, screenshot_file_id: str) -> Tuple[bool, str]:
        """Auto-verify user based on criteria with retry logic"""
        try:
            uid_valid, uid_message = self.validate_uid(uid)
            
            if not uid_valid:
                logger.info(f"Auto-verification failed for user {user_id}: {uid_message}")
                return False, uid_message
            
            if config.AUTO_VERIFY_ENABLED:
                success = await self.retry_db_operation(
                    update_user_data,
                    user_id,
                    deposit_confirmed=True,
                    current_flow='completed',
                    verification_status='approved',
                    verification_method='auto',
                    verified_by='system',
                    verification_date=datetime.now(),
                    screenshot_file_id=screenshot_file_id
                )
                
                if success:
                    await self.add_to_verification_queue(user_id, uid, screenshot_file_id, auto_verified=True)
                    logger.info(f"User {user_id} auto-verified successfully")
                    return True, _("Auto-verification successful")
                return False, _("Database update failed")
            
            await self.add_to_verification_queue(user_id, uid, screenshot_file_id, auto_verified=False)
            return False, _("Manual verification required")
        except Exception as e:
            logger.error(f"Error in auto-verification for user {user_id}: {e}")
            return False, _("Auto-verification error")

    async def add_to_verification_queue(self, user_id: int, uid: str, screenshot_file_id: str, auto_verified: bool = False):
        """Add user to verification queue with retry logic"""
        try:
            query = """
                INSERT INTO verification_queue (user_id, uid, screenshot_file_id, auto_verified)
                VALUES ($1, $2, $3, $4)
            """ if db_manager.db_type == 'postgresql' else """
                INSERT INTO verification_queue (user_id, uid, screenshot_file_id, auto_verified)
                VALUES (?, ?, ?, ?)
            """
            
            await self.retry_db_operation(
                db_manager.execute_query,
                query,
                (user_id, uid, screenshot_file_id, auto_verified)
            )
            
            if not auto_verified:
                asyncio.create_task(self.notify_admin_verification_needed(user_id, uid))
        except Exception as e:
            logger.error(f"Error adding to verification queue: {e}")

    async def notify_admin_verification_needed(self, user_id: int, uid: str):
        """Notify admin that manual verification is needed"""
        try:
            user_data = await self.retry_db_operation(get_user_data, user_id)
            if user_data:
                first_name = user_data.get('first_name', _('Unknown'))
                username = user_data.get('username') or _("No username")
                
                admin_message = _("""🔍 MANUAL VERIFICATION NEEDED

👤 User: {first_name} (@{username})
🆔 User ID: {user_id}
🔑 UID: {uid}

Use /verify {user_id} to approve
Use /reject {user_id} to reject
Use /queue to see all pending verifications""").format(
                    first_name=first_name,
                    username=username,
                    user_id=user_id,
                    uid=uid
                )

                from telegram import Bot
                bot = Bot(token=config.BOT_TOKEN)
                await bot.send_message(chat_id=config.ADMIN_USER_ID, text=admin_message)
        except Exception as e:
            logger.error(f"Error notifying admin: {e}")

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command with rate limiting"""
        try:
            if not await self.check_rate_limit(update.effective_user.id, 'start'):
                await update.message.reply_text(_("Please wait a moment before trying again."))
                return
            
            user = update.effective_user
            user_id = user.id
            username = user.username or ""
            first_name = user.first_name or _("there")
            
            await self.retry_db_operation(create_user, user_id, username, first_name)
            await log_interaction(user_id, "start_command")
            
            # Check admin status
            is_admin = str(user_id) == config.ADMIN_USER_ID
            
            if is_admin:
                await update.message.reply_text(
                    _("👑 ADMIN MODE ACTIVATED\n\nYou now have access to all admin commands."),
                    reply_markup=self.admin_keyboard
                )
                return
            
            welcome_text = _("""Heyy {first_name}! 👋

Welcome to OPTRIXTRADES

You're one step away from unlocking high-accuracy trading signals, expert strategies, and real trader bonuses, completely free.

Here's what you get as a member:

✅ Daily VIP trading signals
✅ Strategy sessions from 6-figure traders  
✅ Access to our private trader community
✅ Exclusive signup bonuses (up to $500)
✅ Automated trading bot - trade while you sleep

Tap below to activate your free VIP access and get started.""").format(first_name=first_name)

            keyboard = [[InlineKeyboardButton(_("➡️ Get Free VIP Access"), callback_data="get_vip_access")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(welcome_text, reply_markup=reply_markup)
        except Exception as e:
            logger.error(f"Error in start_command: {e}")
            await update.message.reply_text(_("Sorry, something went wrong. Please try again later."))

    async def activation_instructions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle activation instructions with rate limiting"""
        try:
            query = update.callback_query
            await query.answer()
            
            if not await self.check_rate_limit(query.from_user.id, 'activation'):
                await query.edit_message_text(_("Please wait a moment before trying again."))
                return
            
            user_id = query.from_user.id
            await self.retry_db_operation(update_user_data, user_id, current_flow='activation')
            await log_interaction(user_id, "activation_instructions")
            
            activation_text = _("""To activate your free access and join our VIP Signal Channel, follow these steps:

1️⃣ Click the link below to register with our official broker partner
{broker_link}

2️⃣ Deposit $20 or more

3️⃣ Send your proof of deposit

Once your proof has been confirmed, your access will be unlocked immediately.

The more you deposit, the more powerful your AI access:

✅ $100+ → Full access to OPTRIX Web AI Portal, Live Signals & AI tools

✅ $500+ → Includes:
- All available signal alert options
- VIP telegram group  
- Access to private sessions and risk management blueprint
- OPTRIX AI Auto-Trading (trades for you automatically)""").format(broker_link=config.BROKER_LINK)

            keyboard = [
                [InlineKeyboardButton(_("➡️ I've Registered"), callback_data="registered")],
                [InlineKeyboardButton(_("➡️ Need help signing up"), callback_data="help_signup")],
                [InlineKeyboardButton(_("➡️ Need support making a deposit"), callback_data="help_deposit")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(activation_text, reply_markup=reply_markup)
            
            second_part = _("""Why is it free?

We earn a small commission from the broker through your trading volume, not your money. So we are more focused on your success - the more you win, the better for both of us. ✅

Want to unlock even higher-tier bonuses or full bot access?
Send "UPGRADE" """)

            await context.bot.send_message(chat_id=query.from_user.id, text=second_part)
        except Exception as e:
            logger.error(f"Error in activation_instructions: {e}")

    async def registration_confirmation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle registration confirmation with rate limiting"""
        try:
            query = update.callback_query
            await query.answer()
            
            if not await self.check_rate_limit(query.from_user.id, 'registration'):
                await query.edit_message_text(_("Please wait a moment before trying again."))
                return
            
            user_id = query.from_user.id
            await self.retry_db_operation(
                update_user_data,
                user_id,
                current_flow='confirmation',
                registration_status='registered'
            )
            await log_interaction(user_id, "registration_confirmation")
            
            verification_status = _("🤖 Auto-verification enabled") if config.AUTO_VERIFY_ENABLED else _("👨‍💼 Manual verification required")
            
            confirmation_text = _("""Send in your UID and deposit screenshot to gain access to OPTRIXTRADES premium signal channel.

{verification_status}

BONUS: We're hosting a live session soon with exclusive insights. Stay tuned. Get early access now into our premium channel - only limited slots are available! 🚀""").format(verification_status=verification_status)

            await query.edit_message_text(confirmation_text)
            await context.bot.send_message(
                chat_id=user_id, 
                text=_("Please send your UID first, then your deposit screenshot as separate messages.")
            )
        except Exception as e:
            logger.error(f"Error in registration_confirmation: {e}")

    async def handle_text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages with rate limiting"""
        try:
            user_id = update.effective_user.id
            
            if not await self.check_rate_limit(user_id, 'text_message'):
                await update.message.reply_text(_("Please wait a moment before sending another message."))
                return
            
            text = update.message.text
            
            # Check admin status
            is_admin = str(user_id) == config.ADMIN_USER_ID
            
            # Admin commands
            if is_admin:
                if text.startswith('/verify '):
                    await self.admin_verify_user(update, context)
                    return
                elif text.startswith('/reject '):
                    await self.admin_reject_user(update, context)
                    return
                elif text == '/queue':
                    await self.show_verification_queue(update, context)
                    return
                elif text == '/stats':
                    await self.show_admin_stats(update, context)
                    return
                elif text.startswith('/signal '):
                    await self.post_signal(update, context)
                    return
            
            user_data = await self.retry_db_operation(get_user_data, user_id)
            if not user_data:
                await self.start_command(update, context)
                return
            
            await log_interaction(user_id, "text_message", text)
            
            if text.upper() == "UPGRADE":
                await self.handle_upgrade_request(update, context)
            elif user_data.get('current_flow') == 'confirmation':
                await self.retry_db_operation(update_user_data, user_id, uid=text)
                await update.message.reply_text(_("✅ UID received! Now please send your deposit screenshot."))
        except Exception as e:
            logger.error(f"Error handling text message: {e}")

    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle photo messages (deposit screenshots) with rate limiting"""
        try:
            user_id = update.effective_user.id
            
            if not await self.check_rate_limit(user_id, 'photo_upload'):
                await update.message.reply_text(_("Please wait a moment before sending another photo."))
                return
            
            user_data = await self.retry_db_operation(get_user_data, user_id)
            
            if not user_data:
                await update.message.reply_text(_("Please start with /start first."))
                return
            
            await log_interaction(user_id, "photo_upload", "deposit_screenshot")
            
            if user_data.get('current_flow') == 'confirmation':
                uid = user_data.get('uid')
                
                if not uid:
                    await update.message.reply_text(_("Please send your UID first before uploading the screenshot."))
                    return
                
                photo = update.message.photo[-1]
                screenshot_file_id = photo.file_id
                
                await self.retry_db_operation(update_user_data, user_id, screenshot_file_id=screenshot_file_id)
                
                auto_verified, message = await self.auto_verify_user(user_id, uid, screenshot_file_id)
                
                if auto_verified:
                    success_text = _("""🎉 Congratulations! Your deposit has been automatically verified.

Welcome to OPTRIXTRADES Premium! 

You now have access to:
✅ Daily VIP trading signals
✅ Premium trading strategies  
✅ Live trading sessions
✅ AI trading bot access

Join our premium channel: {premium_channel_link}

Your trading journey starts now! 🚀

Note: Your verification has been logged for admin review.""").format(premium_channel_link=self.premium_channel_link)
                    await update.message.reply_text(success_text)
                else:
                    pending_text = _("""📋 Thank you for submitting your verification documents!

🔍 Status: Under Review
⏱️ Processing Time: Usually within 24 hours

Your submission includes:
✅ UID: {uid}
✅ Deposit Screenshot: Received

Our team will review your documents and grant access once verified.

You'll receive a notification when your access is approved.

Need urgent assistance? Contact @{admin_username}""").format(
                        uid=uid,
                        admin_username=config.ADMIN_USERNAME
                    )
                    await update.message.reply_text(pending_text)
            else:
                await update.message.reply_text(_("Please complete the registration process first by using /start"))
        except Exception as e:
            logger.error(f"Error handling photo: {e}")

    async def admin_verify_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Admin command to manually verify a user with retry logic"""
        try:
            command_parts = update.message.text.split()
            if len(command_parts) != 2:
                await update.message.reply_text(_("Usage: /verify <user_id>"))
                return
            
            target_user_id = int(command_parts[1])
            user_data = await self.retry_db_operation(get_user_data, target_user_id)
            
            if not user_data:
                await update.message.reply_text(_("User not found."))
                return
            
            success = await self.retry_db_operation(
                update_user_data,
                target_user_id,
                deposit_confirmed=True,
                current_flow='completed',
                verification_status='approved',
                verification_method='manual',
                verified_by=f"admin_{update.effective_user.id}",
                verification_date=datetime.now()
            )
            
            if success:
                query = """
                    UPDATE verification_queue 
                    SET admin_reviewed = TRUE, reviewed_at = CURRENT_TIMESTAMP 
                    WHERE user_id = $1
                """ if db_manager.db_type == 'postgresql' else """
                    UPDATE verification_queue 
                    SET admin_reviewed = TRUE, reviewed_at = CURRENT_TIMESTAMP 
                    WHERE user_id = ?
                """
                
                await self.retry_db_operation(db_manager.execute_query, query, (target_user_id,))
                
                success_text = _("""🎉 VERIFICATION APPROVED!

Welcome to OPTRIXTRADES Premium! 

You now have access to:
✅ Daily VIP trading signals
✅ Premium trading strategies  
✅ Live trading sessions
✅ AI trading bot access

Join our premium channel: {premium_channel_link}

Your trading journey starts now! 🚀""").format(premium_channel_link=self.premium_channel_link)

                await context.bot.send_message(chat_id=target_user_id, text=success_text)
                
                first_name = user_data.get('first_name', _('Unknown'))
                await update.message.reply_text(
                    _("✅ User {first_name} (ID: {user_id}) has been manually verified and granted access.").format(
                        first_name=first_name,
                        user_id=target_user_id
                    )
                )
            else:
                await update.message.reply_text(_("❌ Failed to update user verification status."))
        except ValueError:
            await update.message.reply_text(_("❌ Invalid user ID format."))
        except Exception as e:
            logger.error(f"Error in admin verify: {e}")
            await update.message.reply_text(_("❌ Error processing verification command."))

    async def admin_reject_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Admin command to reject a user verification with retry logic"""
        try:
            command_parts = update.message.text.split()
            if len(command_parts) != 2:
                await update.message.reply_text(_("Usage: /reject <user_id>"))
                return
            
            target_user_id = int(command_parts[1])
            user_data = await self.retry_db_operation(get_user_data, target_user_id)
            
            if not user_data:
                await update.message.reply_text(_("User not found."))
                return
            
            success = await self.retry_db_operation(
                update_user_data,
                target_user_id,
                verification_status='rejected',
                verification_method='manual',
                verified_by=f"admin_{update.effective_user.id}",
                verification_date=datetime.now()
            )
            
            if success:
                query = """
                    UPDATE verification_queue 
                    SET admin_reviewed = TRUE, reviewed_at = CURRENT_TIMESTAMP 
                    WHERE user_id = $1
                """ if db_manager.db_type == 'postgresql' else """
                    UPDATE verification_queue 
                    SET admin_reviewed = TRUE, reviewed_at = CURRENT_TIMESTAMP 
                    WHERE user_id = ?
                """
                
                await self.retry_db_operation(db_manager.execute_query, query, (target_user_id,))
                
                rejection_text = _("""❌ VERIFICATION REJECTED

Unfortunately, we couldn't verify your deposit information. This could be due to:

• Invalid or unclear screenshot
• Incorrect UID format
• Insufficient deposit amount
• Account verification issues

Please try again with:
1. Clear, high-quality screenshot
2. Correct UID from your broker account
3. Minimum $20 deposit confirmation

Need help? Contact @{admin_username}""").format(admin_username=config.ADMIN_USERNAME)

                await context.bot.send_message(chat_id=target_user_id, text=rejection_text)
                
                first_name = user_data.get('first_name', _('Unknown'))
                await update.message.reply_text(
                    _("❌ User {first_name} (ID: {user_id}) verification has been rejected.").format(
                        first_name=first_name,
                        user_id=target_user_id
                    )
                )
            else:
                await update.message.reply_text(_("❌ Failed to update user verification status."))
        except ValueError:
            await update.message.reply_text(_("❌ Invalid user ID format."))
        except Exception as e:
            logger.error(f"Error in admin reject: {e}")
            await update.message.reply_text(_("❌ Error processing rejection command."))

    async def show_verification_queue(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show pending verifications to admin with retry logic"""
        try:
            query = """
                SELECT vq.user_id, vq.uid, vq.auto_verified, vq.created_at, u.first_name, u.username
                FROM verification_queue vq
                JOIN users u ON vq.user_id = u.user_id
                WHERE vq.admin_reviewed = FALSE
                ORDER BY vq.created_at DESC
                LIMIT 10
            """
            
            pending = await self.retry_db_operation(db_manager.execute_query, query, fetch='all')
            
            if not pending:
                await update.message.reply_text(_("✅ No pending verifications!"))
                return
            
            queue_text = _("🔍 VERIFICATION QUEUE\n\n")
            
            for item in pending:
                user_id = item['user_id']
                uid = item['uid']
                auto_verified = item['auto_verified']
                created_at = item['created_at']
                first_name = item['first_name']
                username = item['username']
                
                status = _("🤖 Auto-verified") if auto_verified else _("⏳ Pending")
                username_display = f"@{username}" if username else _("No username")
                
                if isinstance(created_at, str):
                    created_at = created_at[:16]
                else:
                    created_at = created_at.strftime('%Y-%m-%d %H:%M')
                
                queue_text += _("""👤 {first_name} ({username_display})
🆔 ID: {user_id}
🔑 UID: {uid}
📊 Status: {status}
📅 Submitted: {created_at}

Commands:
/verify {user_id} - Approve
/reject {user_id} - Reject

---

""").format(
                    first_name=first_name,
                    username_display=username_display,
                    user_id=user_id,
                    uid=uid,
                    status=status,
                    created_at=created_at
                )
            
            await update.message.reply_text(queue_text)
        except Exception as e:
            logger.error(f"Error showing queue: {e}")
            await update.message.reply_text(_("❌ Error retrieving verification queue."))

    async def show_admin_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show admin statistics with retry logic"""
        try:
            stats_queries = [
                ("total_users", "SELECT COUNT(*) as count FROM users"),
                ("verified_users", "SELECT COUNT(*) as count FROM users WHERE deposit_confirmed = TRUE"),
                ("auto_verified", "SELECT COUNT(*) as count FROM users WHERE verification_method = 'auto'"),
                ("manual_verified", "SELECT COUNT(*) as count FROM users WHERE verification_method = 'manual'"),
                ("pending_queue", "SELECT COUNT(*) as count FROM verification_queue WHERE admin_reviewed = FALSE"),
                ("today_signups", "SELECT COUNT(*) as count FROM users WHERE DATE(join_date) = CURRENT_DATE" if db_manager.db_type == 'postgresql' else "SELECT COUNT(*) as count FROM users WHERE DATE(join_date) = DATE('now')")
            ]
            
            stats = {}
            for stat_name, query in stats_queries:
                result = await self.retry_db_operation(db_manager.execute_query, query, fetch='one')
                stats[stat_name] = result['count'] if result else 0
            
            stats_text = _("""📊 OPTRIXTRADES BOT STATISTICS

👥 Total Users: {total_users}
✅ Verified Users: {verified_users}
🤖 Auto-Verified: {auto_verified}
👨‍💼 Manual Verified: {manual_verified}
⏳ Pending Queue: {pending_queue}
📅 Today's Signups: {today_signups}

🔧 Settings:
Auto-Verification: {auto_verify_status}
Min UID Length: {min_uid_length}
Max UID Length: {max_uid_length}
Database: {database_type}

Commands:
/queue - View pending verifications
/verify <user_id> - Approve user
/reject <user_id> - Reject user""").format(
                total_users=stats['total_users'],
                verified_users=stats['verified_users'],
                auto_verified=stats['auto_verified'],
                manual_verified=stats['manual_verified'],
                pending_queue=stats['pending_queue'],
                today_signups=stats['today_signups'],
                auto_verify_status=_('✅ Enabled') if config.AUTO_VERIFY_ENABLED else _('❌ Disabled'),
                min_uid_length=config.MIN_UID_LENGTH,
                max_uid_length=config.MAX_UID_LENGTH,
                database_type=db_manager.db_type.upper()
            )

            await update.message.reply_text(stats_text)
        except Exception as e:
            logger.error(f"Error showing stats: {e}")
            await update.message.reply_text(_("❌ Error retrieving statistics."))

    async def post_signal(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle signal posting by admin"""
        try:
            if str(update.effective_user.id) != config.ADMIN_USER_ID:
                await update.message.reply_text(_("❌ Only admins can post signals."))
                return
            
            signal_text = update.message.text.replace('/signal ', '').strip()
            if not signal_text:
                await update.message.reply_text(_("Usage: /signal <signal_details>"))
                return
            
            # Save signal to database
            query = """
                INSERT INTO signals (user_id, signal_details, created_at)
                VALUES ($1, $2, CURRENT_TIMESTAMP)
            """ if db_manager.db_type == 'postgresql' else """
                INSERT INTO signals (user_id, signal_details, created_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            """
            
            await self.retry_db_operation(
                db_manager.execute_query,
                query,
                (update.effective_user.id, signal_text)
            )
            
            # Get all verified users
            verified_users = await self.retry_db_operation(
                db_manager.execute_query,
                "SELECT user_id FROM users WHERE deposit_confirmed = TRUE",
                fetch='all'
            )
            
            # Send signal to all verified users
            success_count = 0
            for user in verified_users:
                try:
                    await context.bot.send_message(
                        chat_id=user['user_id'],
                        text=_("🚀 NEW TRADING SIGNAL\n\n{signal_text}\n\nHappy trading!").format(signal_text=signal_text)
                    )
                    success_count += 1
                except Exception as e:
                    logger.error(f"Failed to send signal to user {user['user_id']}: {e}")
            
            await update.message.reply_text(
                _("✅ Signal posted successfully to {success_count}/{total_users} users.").format(
                    success_count=success_count,
                    total_users=len(verified_users)
                )
            )
        except Exception as e:
            logger.error(f"Error posting signal: {e}")
            await update.message.reply_text(_("❌ Error posting signal."))

    async def handle_upgrade_request(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle upgrade requests with rate limiting"""
        try:
            user_id = update.effective_user.id
            
            if not await self.check_rate_limit(user_id, 'upgrade'):
                await update.message.reply_text(_("Please wait a moment before making another request."))
                return
            
            await log_interaction(user_id, "upgrade_request")
            
            upgrade_text = _("""🔥 UPGRADE REQUEST RECEIVED

For premium upgrade options and full bot access, please contact our support team directly.

Our team will help you unlock:
🚀 Advanced AI trading algorithms
💎 VIP-only trading signals  
📈 Personal trading mentor
💰 Higher deposit bonuses

Contact: @{admin_username}""").format(admin_username=config.ADMIN_USERNAME)

            await update.message.reply_text(upgrade_text)
        except Exception as e:
            logger.error(f"Error handling upgrade request: {e}")

    async def help_signup(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle signup help with rate limiting"""
        try:
            query = update.callback_query
            await query.answer()
            
            if not await self.check_rate_limit(query.from_user.id, 'help'):
                await query.edit_message_text(_("Please wait a moment before trying again."))
                return
            
            await log_interaction(query.from_user.id, "help_signup")
            
            help_text = _("""📹 SIGNUP HELP

Step-by-step registration guide:

1. Click this link: {broker_link}
2. Fill in your personal details
3. Verify your email address
4. Complete account verification
5. Make your first deposit ($20 minimum)

Need personal assistance? Contact @{admin_username}

[Video tutorial coming soon]""").format(
                broker_link=config.BROKER_LINK,
                admin_username=config.ADMIN_USERNAME
            )

            await query.edit_message_text(help_text)
        except Exception as e:
            logger.error(f"Error in help_signup: {e}")

    async def help_deposit(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle deposit help with rate limiting"""
        try:
            query = update.callback_query
            await query.answer()
            
            if not await self.check_rate_limit(query.from_user.id, 'help'):
                await query.edit_message_text(_("Please wait a moment before trying again."))
                return
            
            await log_interaction(query.from_user.id, "help_deposit")
            
            help_text = _("""💳 DEPOSIT HELP

How to make your first deposit:

1. Log into your broker account
2. Go to "Deposit" section
3. Choose your payment method
4. Enter amount ($20 minimum)
5. Complete the transaction
6. Take a screenshot of confirmation

Need help? Contact @{admin_username}

[Video tutorial coming soon]""").format(admin_username=config.ADMIN_USERNAME)

            await query.edit_message_text(help_text)
        except Exception as e:
            logger.error(f"Error in help_deposit: {e}")

    async def handle_not_interested(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle not interested callback with rate limiting"""
        try:
            query = update.callback_query
            await query.answer()
            
            if not await self.check_rate_limit(query.from_user.id, 'not_interested'):
                await query.edit_message_text(_("Please wait a moment before trying again."))
                return
            
            user_id = query.from_user.id
            await self.retry_db_operation(update_user_data, user_id, is_active=False)
            await log_interaction(user_id, "not_interested")
            
            farewell_text = _("""Alright, no problem! 👋

Feel free to reach us at any time @{admin_username} if you change your mind.

We'll be here when you're ready to start your trading journey! 🚀""").format(admin_username=config.ADMIN_USERNAME)

            await query.edit_message_text(farewell_text)
        except Exception as e:
            logger.error(f"Error handling not interested: {e}")

    async def handle_language_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle language selection"""
        try:
            query = update.callback_query
            await query.answer()
            
            lang_code = query.data.replace('set_lang_', '')
            user_id = query.from_user.id
            
            if lang_code in self.supported_languages:
                await self.retry_db_operation(update_user_data, user_id, language=lang_code)
                await log_interaction(user_id, "language_change", lang_code)
                
                # Update user's language preference in context
                context.user_data['language'] = lang_code
                
                await query.edit_message_text(
                    _("🌐 Language set to {language}").format(language=lang_code),
                    reply_markup=self.user_main_keyboard
                )
            else:
                await query.edit_message_text(
                    _("❌ Invalid language selection"),
                    reply_markup=self.user_main_keyboard
                )
        except Exception as e:
            logger.error(f"Error in language selection: {e}")

    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks with rate limiting"""
        try:
            query = update.callback_query
            await query.answer()
            
            data = query.data
            user_id = query.from_user.id
            
            if not await self.check_rate_limit(user_id, 'button_callback'):
                await query.edit_message_text(_("Please wait a moment before trying again."))
                return
            
            is_admin = str(user_id) == config.ADMIN_USER_ID
            
            # Maintain user context between actions
            context.user_data['last_action'] = data
            
            if data == "main_menu":
                await self.handle_main_menu(update, context)
            elif data == "my_account":
                await self.handle_account_menu(update, context)
            elif data == "help_menu":
                await self.handle_help_menu(update, context)
            elif data == "get_vip_access":
                await self.activation_instructions(update, context)
            elif data == "registered":
                await self.registration_confirmation(update, context)
            elif data == "help_signup":
                await self.help_signup(update, context)
            elif data == "help_deposit":
                await self.help_deposit(update, context)
            elif data == "not_interested":
                await self.handle_not_interested(update, context)
            elif data == "contact_support":
                await query.answer()
                await query.edit_message_text(_("Please contact our support team: @{admin_username}").format(admin_username=config.ADMIN_USERNAME))
            elif data == "account_status":
                await self.handle_account_status(update, context)
            elif data == "upgrade_account":
                await self.handle_upgrade_request(update, context)
            elif data == "notification_settings":
                await self.handle_notification_settings(update, context)
            elif data == "language_menu":
                await query.edit_message_text(_("🌐 Select your language:"), reply_markup=self.language_keyboard)
            elif data.startswith("set_lang_"):
                await self.handle_language_selection(update, context)
            elif data.startswith("signal_"):
                await self.handle_signal_type(update, context)
            elif data == "admin_stats" and is_admin:
                await self.show_admin_stats(update, context)
            elif data == "admin_queue" and is_admin:
                await self.show_verification_queue(update, context)
            elif data == "post_signal" and is_admin:
                await query.edit_message_text(_("Please use /signal <signal_details> to post a new signal."))
            elif data == "edit_signal" and is_admin:
                last_signal = await self.get_last_signal(user_id)
                if last_signal:
                    await query.edit_message_text(
                        _("Edit Last Signal:\n{signal}\n\nSend new signal details").format(signal=last_signal),
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton(_("Cancel"), callback_data="cancel_signal")]
                        ])
                    )
                    context.user_data['editing_signal'] = True
                else:
                    await query.edit_message_text(_("No recent signals found to edit."))
            elif data == "cancel_signal":
                context.user_data.clear()
                await query.edit_message_text(_("Action cancelled."), reply_markup=self.admin_keyboard if is_admin else self.user_main_keyboard)
            
            # Return to appropriate menu after action
            if not data.startswith('cancel_'):
                if is_admin and data in ['admin_stats', 'admin_queue', 'edit_signal']:
                    await self.handle_admin_menu(update, context)
                else:
                    await self.handle_main_menu(update, context)
                    
        except Exception as e:
            logger.error(f"Error in button callback: {e}")

    async def handle_main_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show main menu"""
        try:
            query = update.callback_query
            await query.answer()
            
            welcome_text = _("Welcome to OPTRIXTRADES! 👋\n\nWhat would you like to do?")
            
            await query.edit_message_text(
                welcome_text,
                reply_markup=self.user_main_keyboard
            )
        except Exception as e:
            logger.error(f"Error in main menu: {e}")

    async def handle_account_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show account menu"""
        try:
            query = update.callback_query
            await query.answer()
            
            user_id = query.from_user.id
            user_data = await self.retry_db_operation(get_user_data, user_id)
            
            if user_data:
                status = _("✅ Verified") if user_data.get('deposit_confirmed') else _("⏳ Pending")
                join_date = user_data.get('join_date', _('Unknown'))
                
                account_text = _("""📱 My Account

Status: {status}
Member since: {join_date}

Select an option below:""").format(
                    status=status,
                    join_date=join_date
                )
                
                await query.edit_message_text(
                    account_text,
                    reply_markup=self.account_keyboard
                )
            else:
                await query.edit_message_text(
                    _("⚠️ Account not found. Please start over with /start")
                )
        except Exception as e:
            logger.error(f"Error in account menu: {e}")

    async def handle_help_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show help menu with available commands"""
        try:
            query = update.callback_query
            await query.answer()
            
            user_id = query.from_user.id
            is_admin = str(user_id) == config.ADMIN_USER_ID
            
            help_text = _("ℹ️ Available Commands\n\n")
            
            # User commands
            help_text += _("👤 User Commands:\n")
            help_text += "/start - Begin using the bot\n"
            help_text += "/menu - Show main menu\n"
            help_text += "UPGRADE - Request premium upgrade\n"
            help_text += _("Send UID + screenshot - Complete verification\n\n")
            
            # Admin commands
            if is_admin:
                help_text += _("👨‍💼 Admin Commands:\n")
                help_text += "/admin - Admin dashboard\n"
                help_text += "/verify <user_id> - Approve user\n"
                help_text += "/reject <user_id> - Reject user\n"
                help_text += "/queue - View verification queue\n"
                help_text += "/stats - View bot statistics\n"
                help_text += "/signal <details> - Post trading signal\n"
            
            help_text += _("\nNeed more help? Contact @{admin_username}").format(admin_username=config.ADMIN_USERNAME)
            
            await query.edit_message_text(
                help_text,
                reply_markup=self.help_keyboard
            )
        except Exception as e:
            logger.error(f"Error in help menu: {e}")

    async def handle_account_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show account status"""
        try:
            query = update.callback_query
            await query.answer()
            
            user_id = query.from_user.id
            user_data = await self.retry_db_operation(get_user_data, user_id)
            
            if user_data:
                status = _("✅ Verified") if user_data.get('deposit_confirmed') else _("⏳ Pending Verification")
                join_date = user_data.get('join_date', _('Unknown'))
                verification_method = user_data.get('verification_method', _('Not verified'))
                
                status_text = _("""📊 ACCOUNT STATUS

🔹 Status: {status}
🔹 Verification Method: {verification_method}
🔹 Member Since: {join_date}""").format(
                    status=status,
                    verification_method=verification_method,
                    join_date=join_date
                )

                keyboard = [[InlineKeyboardButton(_("🔙 Back"), callback_data="my_account")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    status_text,
                    reply_markup=reply_markup
                )
            else:
                await query.edit_message_text(
                    _("⚠️ Account not found. Please start over with /start")
                )
        except Exception as e:
            logger.error(f"Error in account status: {e}")

    async def handle_notification_settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show notification settings"""
        try:
            query = update.callback_query
            await query.answer()
            
            user_id = query.from_user.id
            user_data = await self.retry_db_operation(get_user_data, user_id)
            
            if user_data:
                notifications = user_data.get('notifications_enabled', True)
                status = _("✅ Enabled") if notifications else _("❌ Disabled")
                
                settings_text = _("""🔔 NOTIFICATION SETTINGS

Current status: {status}

Would you like to receive trading signals and updates?""").format(status=status)

                keyboard = [
                    [
                        InlineKeyboardButton(_("✅ Enable"), callback_data="enable_notifications"),
                        InlineKeyboardButton(_("❌ Disable"), callback_data="disable_notifications")
                    ],
                    [InlineKeyboardButton(_("🔙 Back"), callback_data="my_account")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    settings_text,
                    reply_markup=reply_markup
                )
            else:
                await query.edit_message_text(
                    _("⚠️ Account not found. Please start over with /start")
                )
        except Exception as e:
            logger.error(f"Error in notification settings: {e}")

    async def get_last_signal(self, user_id: int) -> Optional[str]:
        """Get the last signal posted by admin with retry logic"""
        try:
            query = """
                SELECT signal_details FROM signals 
                WHERE user_id = $1 
                ORDER BY created_at DESC 
                LIMIT 1
            """ if db_manager.db_type == 'postgresql' else """
                SELECT signal_details FROM signals 
                WHERE user_id = ? 
                ORDER BY created_at DESC 
                LIMIT 1
            """
            
            result = await self.retry_db_operation(
                db_manager.execute_query,
                query,
                (user_id,),
                fetch='one'
            )
            return result['signal_details'] if result else None
        except Exception as e:
            logger.error(f"Error getting last signal: {e}")
            return None

    async def run(self):
        """Run the bot with all handlers"""
        try:
            await self.initialize()
            
            app = Application.builder().token(config.BOT_TOKEN).build()
            
            # Register handlers
            app.add_handler(CommandHandler("start", self.start_command))
            app.add_handler(CommandHandler("admin", self.handle_admin_menu))
            app.add_handler(CommandHandler("signal", self.post_signal))
            app.add_handler(CallbackQueryHandler(self.button_callback))
            app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text_message))
            app.add_handler(MessageHandler(filters.PHOTO, self.handle_photo))
            
            # Register error handler
            app.add_error_handler(self.error_handler)
            
            # Add rate limiting handler
            app.add_handler(TypeHandler(Update, self.check_rate_limit), group=-1)
            
            # Start the bot
            logger.info("Starting bot...")
            await app.run_polling()
        except asyncio.CancelledError:
            logger.info("Bot shutdown requested")
        except Exception as e:
            logger.critical("Fatal error in bot main loop", exc_info=True)
            raise

def main():
    """Entry point with error handling"""
    try:
        bot = TradingBot()
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.critical("Bot crashed", exc_info=True)
        raise

if __name__ == "__main__":
    # Load translations
    gettext.install('tradingbot')
    
    # Create locales directory if it doesn't exist
    if not LOCALE_DIR.exists():
        LOCALE_DIR.mkdir(parents=True)
        logger.info(f"Created locales directory at {LOCALE_DIR}")
    
    main()