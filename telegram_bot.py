import logging
import os
import asyncio
import re
import traceback
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes
)
from telegram.error import TelegramError

# Import database manager
from database import db_manager, get_user_data, update_user_data, create_user, log_interaction
from config import config

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
        
        # Initialize error handler
        self.error_handler = self.telegram_error_handler
        
        # Keyboards initialization
        self._init_keyboards()

    def _init_keyboards(self):
        """Initialize all inline keyboards"""
        self.admin_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 Statistics", callback_data="admin_stats"),
             InlineKeyboardButton("👥 Verification Queue", callback_data="admin_queue")],
            [InlineKeyboardButton("📢 Post Signal", callback_data="post_signal"),
             InlineKeyboardButton("📝 Edit Last Signal", callback_data="edit_signal")]
        ])
        
        self.user_main_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("💎 VIP Access", callback_data="get_vip_access")],
            [InlineKeyboardButton("📱 My Account", callback_data="my_account"),
             InlineKeyboardButton("ℹ️ Help", callback_data="help_menu")],
            [InlineKeyboardButton("📞 Support", callback_data="contact_support")]
        ])
        
        self.help_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📝 Registration Help", callback_data="help_signup"),
             InlineKeyboardButton("💳 Deposit Help", callback_data="help_deposit")],
            [InlineKeyboardButton("❓ FAQ", callback_data="faq"),
             InlineKeyboardButton("📞 Contact Support", callback_data="contact_support")],
            [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu")]
        ])
        
        self.account_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 My Status", callback_data="account_status"),
             InlineKeyboardButton("⭐️ Upgrade Account", callback_data="upgrade_account")],
            [InlineKeyboardButton("🔔 Notification Settings", callback_data="notification_settings")],
            [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu")]
        ])

    async def telegram_error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle all Telegram bot errors"""
        logger.error(msg="Exception while handling Telegram update:", exc_info=context.error)
        
        # Log error to database
        try:
            user_id = update.effective_user.id if update and update.effective_user else None
            
            if db_manager.db_type == 'postgresql':
                query = """
                    INSERT INTO error_logs (
                        error_type, 
                        error_message, 
                        stack_trace, 
                        context, 
                        user_id, 
                        extra_data
                    ) VALUES ($1, $2, $3, $4, $5, $6)
                """
            else:
                query = """
                    INSERT INTO error_logs (
                        error_type,
                        error_message,
                        stack_trace,
                        context,
                        user_id,
                        extra_data
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """
            
            await db_manager.execute_query(
                query,
                (
                    type(context.error).__name__,
                    str(context.error),
                    ''.join(traceback.format_exception(type(context.error), context.error, context.error.__traceback__)),
                    'telegram_update',
                    user_id,
                    str(update.to_dict()) if update else None
                )
            )
        except Exception as db_error:
            logger.error(f"Failed to log error to database: {db_error}")

        # Try to notify the user about the error
        try:
            if update and update.effective_user:
                await context.bot.send_message(
                    chat_id=update.effective_user.id,
                    text="⚠️ An error occurred. Our team has been notified."
                )
        except Exception as notify_error:
            logger.error(f"Failed to notify user: {notify_error}")

        # Notify admin about critical errors
        try:
            error_trace = ''.join(traceback.format_exception(type(context.error), context.error, context.error.__traceback__))
            await context.bot.send_message(
                chat_id=config.ADMIN_USER_ID,
                text=f"🚨 BOT ERROR\n\n{type(context.error).__name__}: {str(context.error)}\n\n{error_trace[:3000]}"
            )
        except Exception as admin_error:
            logger.error(f"Failed to notify admin: {admin_error}")

    async def initialize(self):
        """Initialize database connection"""
        try:
            await db_manager.initialize()
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.critical("Failed to initialize database", exc_info=True)
            raise

    def validate_uid(self, uid):
        """Validate UID format for auto-verification"""
        try:
            if not uid or len(uid) < config.MIN_UID_LENGTH or len(uid) > config.MAX_UID_LENGTH:
                return False, "UID length invalid"
            
            if not re.match(r'^[a-zA-Z0-9]+$', uid):
                return False, "UID contains invalid characters"
            
            if uid.lower() in ['test', 'demo', '123456', 'sample']:
                return False, "UID appears to be a test/demo account"
            
            return True, "UID format valid"
        except Exception as e:
            logger.error(f"Error validating UID {uid}: {e}")
            return False, "UID validation error"

    async def auto_verify_user(self, user_id, uid, screenshot_file_id):
        """Auto-verify user based on criteria"""
        try:
            uid_valid, uid_message = self.validate_uid(uid)
            
            if not uid_valid:
                logger.info(f"Auto-verification failed for user {user_id}: {uid_message}")
                return False, uid_message
            
            if config.AUTO_VERIFY_ENABLED:
                success = await update_user_data(
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
                    return True, "Auto-verification successful"
                return False, "Database update failed"
            
            await self.add_to_verification_queue(user_id, uid, screenshot_file_id, auto_verified=False)
            return False, "Manual verification required"
        except Exception as e:
            logger.error(f"Error in auto-verification for user {user_id}: {e}")
            return False, "Auto-verification error"

    async def add_to_verification_queue(self, user_id, uid, screenshot_file_id, auto_verified=False):
        """Add user to verification queue"""
        try:
            if db_manager.db_type == 'postgresql':
                query = """
                    INSERT INTO verification_queue (user_id, uid, screenshot_file_id, auto_verified)
                    VALUES ($1, $2, $3, $4)
                """
            else:
                query = """
                    INSERT INTO verification_queue (user_id, uid, screenshot_file_id, auto_verified)
                    VALUES (?, ?, ?, ?)
                """
            
            await db_manager.execute_query(query, (user_id, uid, screenshot_file_id, auto_verified))
            
            if not auto_verified:
                asyncio.create_task(self.notify_admin_verification_needed(user_id, uid))
        except Exception as e:
            logger.error(f"Error adding to verification queue: {e}")

    async def notify_admin_verification_needed(self, user_id, uid):
        """Notify admin that manual verification is needed"""
        try:
            user_data = await get_user_data(user_id)
            if user_data:
                first_name = user_data.get('first_name', 'Unknown')
                username = user_data.get('username') or "No username"
                
                admin_message = f"""🔍 MANUAL VERIFICATION NEEDED

👤 User: {first_name} (@{username})
🆔 User ID: {user_id}
🔑 UID: {uid}

Use /verify {user_id} to approve
Use /reject {user_id} to reject
Use /queue to see all pending verifications"""

                from telegram import Bot
                bot = Bot(token=config.BOT_TOKEN)
                await bot.send_message(chat_id=config.ADMIN_USER_ID, text=admin_message)
        except Exception as e:
            logger.error(f"Error notifying admin: {e}")

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        try:
            user = update.effective_user
            user_id = user.id
            username = user.username or ""
            first_name = user.first_name or "there"
            
            await create_user(user_id, username, first_name)
            await log_interaction(user_id, "start_command")
            
            # Check admin status
            is_admin = str(user_id) == config.ADMIN_USER_ID
            
            if is_admin:
                await update.message.reply_text(
                    "👑 ADMIN MODE ACTIVATED\n\nYou now have access to all admin commands.",
                    reply_markup=self.admin_keyboard
                )
                return
            
            welcome_text = f"""Heyy {first_name}! 👋

Welcome to OPTRIXTRADES

You're one step away from unlocking high-accuracy trading signals, expert strategies, and real trader bonuses, completely free.

Here's what you get as a member:

✅ Daily VIP trading signals
✅ Strategy sessions from 6-figure traders  
✅ Access to our private trader community
✅ Exclusive signup bonuses (up to $500)
✅ Automated trading bot - trade while you sleep

Tap below to activate your free VIP access and get started."""

            keyboard = [[InlineKeyboardButton("➡️ Get Free VIP Access", callback_data="get_vip_access")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(welcome_text, reply_markup=reply_markup)
        except Exception as e:
            logger.error(f"Error in start_command: {e}")
            await update.message.reply_text("Sorry, something went wrong. Please try again later.")

    async def activation_instructions(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle activation instructions"""
        try:
            query = update.callback_query
            await query.answer()
            
            user_id = query.from_user.id
            await update_user_data(user_id, current_flow='activation')
            await log_interaction(user_id, "activation_instructions")
            
            activation_text = f"""To activate your free access and join our VIP Signal Channel, follow these steps:

1️⃣ Click the link below to register with our official broker partner
{config.BROKER_LINK}

2️⃣ Deposit $20 or more

3️⃣ Send your proof of deposit

Once your proof has been confirmed, your access will be unlocked immediately.

The more you deposit, the more powerful your AI access:

✅ $100+ → Full access to OPTRIX Web AI Portal, Live Signals & AI tools

✅ $500+ → Includes:
- All available signal alert options
- VIP telegram group  
- Access to private sessions and risk management blueprint
- OPTRIX AI Auto-Trading (trades for you automatically)"""

            keyboard = [
                [InlineKeyboardButton("➡️ I've Registered", callback_data="registered")],
                [InlineKeyboardButton("➡️ Need help signing up", callback_data="help_signup")],
                [InlineKeyboardButton("➡️ Need support making a deposit", callback_data="help_deposit")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(activation_text, reply_markup=reply_markup)
            
            second_part = """Why is it free?

We earn a small commission from the broker through your trading volume, not your money. So we are more focused on your success - the more you win, the better for both of us. ✅

Want to unlock even higher-tier bonuses or full bot access?
Send "UPGRADE" """

            await context.bot.send_message(chat_id=query.from_user.id, text=second_part)
        except Exception as e:
            logger.error(f"Error in activation_instructions: {e}")

    async def registration_confirmation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle registration confirmation"""
        try:
            query = update.callback_query
            await query.answer()
            
            user_id = query.from_user.id
            await update_user_data(user_id, current_flow='confirmation', registration_status='registered')
            await log_interaction(user_id, "registration_confirmation")
            
            verification_status = "🤖 Auto-verification enabled" if config.AUTO_VERIFY_ENABLED else "👨‍💼 Manual verification required"
            
            confirmation_text = f"""Send in your UID and deposit screenshot to gain access to OPTRIXTRADES premium signal channel.

{verification_status}

BONUS: We're hosting a live session soon with exclusive insights. Stay tuned. Get early access now into our premium channel - only limited slots are available! 🚀"""

            await query.edit_message_text(confirmation_text)
            await context.bot.send_message(
                chat_id=user_id, 
                text="Please send your UID first, then your deposit screenshot as separate messages."
            )
        except Exception as e:
            logger.error(f"Error in registration_confirmation: {e}")

    async def handle_text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages"""
        try:
            user_id = update.effective_user.id
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
            
            user_data = await get_user_data(user_id)
            if not user_data:
                await self.start_command(update, context)
                return
            
            await log_interaction(user_id, "text_message", text)
            
            if text.upper() == "UPGRADE":
                await self.handle_upgrade_request(update, context)
            elif user_data.get('current_flow') == 'confirmation':
                await update_user_data(user_id, uid=text)
                await update.message.reply_text("✅ UID received! Now please send your deposit screenshot.")
        except Exception as e:
            logger.error(f"Error handling text message: {e}")

    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle photo messages (deposit screenshots)"""
        try:
            user_id = update.effective_user.id
            user_data = await get_user_data(user_id)
            
            if not user_data:
                await update.message.reply_text("Please start with /start first.")
                return
            
            await log_interaction(user_id, "photo_upload", "deposit_screenshot")
            
            if user_data.get('current_flow') == 'confirmation':
                uid = user_data.get('uid')
                
                if not uid:
                    await update.message.reply_text("Please send your UID first before uploading the screenshot.")
                    return
                
                photo = update.message.photo[-1]
                screenshot_file_id = photo.file_id
                
                await update_user_data(user_id, screenshot_file_id=screenshot_file_id)
                
                auto_verified, message = await self.auto_verify_user(user_id, uid, screenshot_file_id)
                
                if auto_verified:
                    success_text = f"""🎉 Congratulations! Your deposit has been automatically verified.

Welcome to OPTRIXTRADES Premium! 

You now have access to:
✅ Daily VIP trading signals
✅ Premium trading strategies  
✅ Live trading sessions
✅ AI trading bot access

Join our premium channel: {self.premium_channel_link}

Your trading journey starts now! 🚀

Note: Your verification has been logged for admin review."""
                    await update.message.reply_text(success_text)
                else:
                    pending_text = f"""📋 Thank you for submitting your verification documents!

🔍 Status: Under Review
⏱️ Processing Time: Usually within 24 hours

Your submission includes:
✅ UID: {uid}
✅ Deposit Screenshot: Received

Our team will review your documents and grant access once verified.

You'll receive a notification when your access is approved.

Need urgent assistance? Contact @{config.ADMIN_USERNAME}"""
                    await update.message.reply_text(pending_text)
            else:
                await update.message.reply_text("Please complete the registration process first by using /start")
        except Exception as e:
            logger.error(f"Error handling photo: {e}")

    async def admin_verify_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Admin command to manually verify a user"""
        try:
            command_parts = update.message.text.split()
            if len(command_parts) != 2:
                await update.message.reply_text("Usage: /verify <user_id>")
                return
            
            target_user_id = int(command_parts[1])
            user_data = await get_user_data(target_user_id)
            
            if not user_data:
                await update.message.reply_text("User not found.")
                return
            
            success = await update_user_data(
                target_user_id,
                deposit_confirmed=True,
                current_flow='completed',
                verification_status='approved',
                verification_method='manual',
                verified_by=f"admin_{update.effective_user.id}",
                verification_date=datetime.now()
            )
            
            if success:
                if db_manager.db_type == 'postgresql':
                    query = 'UPDATE verification_queue SET admin_reviewed = TRUE, reviewed_at = CURRENT_TIMESTAMP WHERE user_id = $1'
                else:
                    query = 'UPDATE verification_queue SET admin_reviewed = TRUE, reviewed_at = CURRENT_TIMESTAMP WHERE user_id = ?'
                
                await db_manager.execute_query(query, (target_user_id,))
                
                success_text = f"""🎉 VERIFICATION APPROVED!

Welcome to OPTRIXTRADES Premium! 

You now have access to:
✅ Daily VIP trading signals
✅ Premium trading strategies  
✅ Live trading sessions
✅ AI trading bot access

Join our premium channel: {self.premium_channel_link}

Your trading journey starts now! 🚀"""

                await context.bot.send_message(chat_id=target_user_id, text=success_text)
                
                first_name = user_data.get('first_name', 'Unknown')
                await update.message.reply_text(f"✅ User {first_name} (ID: {target_user_id}) has been manually verified and granted access.")
            else:
                await update.message.reply_text("❌ Failed to update user verification status.")
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID format.")
        except Exception as e:
            logger.error(f"Error in admin verify: {e}")
            await update.message.reply_text("❌ Error processing verification command.")

    async def admin_reject_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Admin command to reject a user verification"""
        try:
            command_parts = update.message.text.split()
            if len(command_parts) != 2:
                await update.message.reply_text("Usage: /reject <user_id>")
                return
            
            target_user_id = int(command_parts[1])
            user_data = await get_user_data(target_user_id)
            
            if not user_data:
                await update.message.reply_text("User not found.")
                return
            
            success = await update_user_data(
                target_user_id,
                verification_status='rejected',
                verification_method='manual',
                verified_by=f"admin_{update.effective_user.id}",
                verification_date=datetime.now()
            )
            
            if success:
                if db_manager.db_type == 'postgresql':
                    query = 'UPDATE verification_queue SET admin_reviewed = TRUE, reviewed_at = CURRENT_TIMESTAMP WHERE user_id = $1'
                else:
                    query = 'UPDATE verification_queue SET admin_reviewed = TRUE, reviewed_at = CURRENT_TIMESTAMP WHERE user_id = ?'
                
                await db_manager.execute_query(query, (target_user_id,))
                
                rejection_text = f"""❌ VERIFICATION REJECTED

Unfortunately, we couldn't verify your deposit information. This could be due to:

• Invalid or unclear screenshot
• Incorrect UID format
• Insufficient deposit amount
• Account verification issues

Please try again with:
1. Clear, high-quality screenshot
2. Correct UID from your broker account
3. Minimum $20 deposit confirmation

Need help? Contact @{config.ADMIN_USERNAME}"""

                await context.bot.send_message(chat_id=target_user_id, text=rejection_text)
                
                first_name = user_data.get('first_name', 'Unknown')
                await update.message.reply_text(f"❌ User {first_name} (ID: {target_user_id}) verification has been rejected.")
            else:
                await update.message.reply_text("❌ Failed to update user verification status.")
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID format.")
        except Exception as e:
            logger.error(f"Error in admin reject: {e}")
            await update.message.reply_text("❌ Error processing rejection command.")

    async def show_verification_queue(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show pending verifications to admin"""
        try:
            if db_manager.db_type == 'postgresql':
                query = """
                    SELECT vq.user_id, vq.uid, vq.auto_verified, vq.created_at, u.first_name, u.username
                    FROM verification_queue vq
                    JOIN users u ON vq.user_id = u.user_id
                    WHERE vq.admin_reviewed = FALSE
                    ORDER BY vq.created_at DESC
                    LIMIT 10
                """
            else:
                query = """
                    SELECT vq.user_id, vq.uid, vq.auto_verified, vq.created_at, u.first_name, u.username
                    FROM verification_queue vq
                    JOIN users u ON vq.user_id = u.user_id
                    WHERE vq.admin_reviewed = FALSE
                    ORDER BY vq.created_at DESC
                    LIMIT 10
                """
            
            pending = await db_manager.execute_query(query, fetch='all')
            
            if not pending:
                await update.message.reply_text("✅ No pending verifications!")
                return
            
            queue_text = "🔍 VERIFICATION QUEUE\n\n"
            
            for item in pending:
                user_id = item['user_id']
                uid = item['uid']
                auto_verified = item['auto_verified']
                created_at = item['created_at']
                first_name = item['first_name']
                username = item['username']
                
                status = "🤖 Auto-verified" if auto_verified else "⏳ Pending"
                username_display = f"@{username}" if username else "No username"
                
                if isinstance(created_at, str):
                    created_at = created_at[:16]
                else:
                    created_at = created_at.strftime('%Y-%m-%d %H:%M')
                
                queue_text += f"""👤 {first_name} ({username_display})
🆔 ID: {user_id}
🔑 UID: {uid}
📊 Status: {status}
📅 Submitted: {created_at}

Commands:
/verify {user_id} - Approve
/reject {user_id} - Reject

---

"""
            
            await update.message.reply_text(queue_text)
        except Exception as e:
            logger.error(f"Error showing queue: {e}")
            await update.message.reply_text("❌ Error retrieving verification queue.")

    async def show_admin_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show admin statistics"""
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
                result = await db_manager.execute_query(query, fetch='one')
                stats[stat_name] = result['count'] if result else 0
            
            stats_text = f"""📊 OPTRIXTRADES BOT STATISTICS

👥 Total Users: {stats['total_users']}
✅ Verified Users: {stats['verified_users']}
🤖 Auto-Verified: {stats['auto_verified']}
👨‍💼 Manual Verified: {stats['manual_verified']}
⏳ Pending Queue: {stats['pending_queue']}
📅 Today's Signups: {stats['today_signups']}

🔧 Settings:
Auto-Verification: {'✅ Enabled' if config.AUTO_VERIFY_ENABLED else '❌ Disabled'}
Min UID Length: {config.MIN_UID_LENGTH}
Max UID Length: {config.MAX_UID_LENGTH}
Database: {db_manager.db_type.upper()}

Commands:
/queue - View pending verifications
/verify <user_id> - Approve user
/reject <user_id> - Reject user"""

            await update.message.reply_text(stats_text)
        except Exception as e:
            logger.error(f"Error showing stats: {e}")
            await update.message.reply_text("❌ Error retrieving statistics.")

    async def handle_upgrade_request(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle upgrade requests"""
        try:
            user_id = update.effective_user.id
            await log_interaction(user_id, "upgrade_request")
            
            upgrade_text = f"""🔥 UPGRADE REQUEST RECEIVED

For premium upgrade options and full bot access, please contact our support team directly.

Our team will help you unlock:
🚀 Advanced AI trading algorithms
💎 VIP-only trading signals  
📈 Personal trading mentor
💰 Higher deposit bonuses

Contact: @{config.ADMIN_USERNAME}"""

            await update.message.reply_text(upgrade_text)
        except Exception as e:
            logger.error(f"Error handling upgrade request: {e}")

    async def help_signup(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle signup help"""
        try:
            query = update.callback_query
            await query.answer()
            
            await log_interaction(query.from_user.id, "help_signup")
            
            help_text = f"""📹 SIGNUP HELP

Step-by-step registration guide:

1. Click this link: {config.BROKER_LINK}
2. Fill in your personal details
3. Verify your email address
4. Complete account verification
5. Make your first deposit ($20 minimum)

Need personal assistance? Contact @{config.ADMIN_USERNAME}

[Video tutorial coming soon]"""

            await query.edit_message_text(help_text)
        except Exception as e:
            logger.error(f"Error in help_signup: {e}")

    async def help_deposit(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle deposit help"""
        try:
            query = update.callback_query
            await query.answer()
            
            await log_interaction(query.from_user.id, "help_deposit")
            
            help_text = f"""💳 DEPOSIT HELP

How to make your first deposit:

1. Log into your broker account
2. Go to "Deposit" section
3. Choose your payment method
4. Enter amount ($20 minimum)
5. Complete the transaction
6. Take a screenshot of confirmation

Need help? Contact @{config.ADMIN_USERNAME}

[Video tutorial coming soon]"""

            await query.edit_message_text(help_text)
        except Exception as e:
            logger.error(f"Error in help_deposit: {e}")

    async def handle_not_interested(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle not interested callback"""
        try:
            query = update.callback_query
            await query.answer()
            
            user_id = query.from_user.id
            await update_user_data(user_id, is_active=False)
            await log_interaction(user_id, "not_interested")
            
            farewell_text = f"""Alright, no problem! 👋

Feel free to reach us at any time @{config.ADMIN_USERNAME} if you change your mind.

We'll be here when you're ready to start your trading journey! 🚀"""

            await query.edit_message_text(farewell_text)
        except Exception as e:
            logger.error(f"Error handling not interested: {e}")

    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks"""
        try:
            query = update.callback_query
            data = query.data
            
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
                await query.edit_message_text(f"Please contact our support team: @{config.ADMIN_USERNAME}")
            elif data == "account_status":
                await self.handle_account_status(update, context)
            elif data == "upgrade_account":
                await self.handle_upgrade_request(update, context)
            elif data == "notification_settings":
                await self.handle_notification_settings(update, context)
            elif data.startswith("signal_"):
                await self.handle_signal_type(update, context)
            elif data == "admin_stats":
                await self.show_admin_stats(update, context)
            elif data == "admin_queue":
                await self.show_verification_queue(update, context)
            elif data == "edit_signal":
                await self.handle_edit_signal(update, context)
            elif data == "cancel_signal":
                context.user_data.clear()
                await query.edit_message_text("Signal posting cancelled.")
        except Exception as e:
            logger.error(f"Error in button callback: {e}")

    async def handle_main_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show main menu"""
        try:
            query = update.callback_query
            await query.answer()
            
            welcome_text = f"Welcome to OPTRIXTRADES! 👋\n\nWhat would you like to do?"
            
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
            user_data = await get_user_data(user_id)
            
            if user_data:
                status = "✅ Verified" if user_data.get('deposit_confirmed') else "⏳ Pending"
                join_date = user_data.get('join_date', 'Unknown')
                
                account_text = f"📱 My Account\n\n"\
                    f"Status: {status}\n"\
                    f"Member since: {join_date}\n\n"\
                    f"Select an option below:"
                
                await query.edit_message_text(
                    account_text,
                    reply_markup=self.account_keyboard
                )
            else:
                await query.edit_message_text(
                    "⚠️ Account not found. Please start over with /start"
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
            
            help_text = "ℹ️ Available Commands\n\n"
            
            # User commands
            help_text += "👤 User Commands:\n"
            help_text += "/start - Begin using the bot\n"
            help_text += "/menu - Show main menu\n"
            help_text += "UPGRADE - Request premium upgrade\n"
            help_text += "Send UID + screenshot - Complete verification\n\n"
            
            # Admin commands
            if is_admin:
                help_text += "👨‍💼 Admin Commands:\n"
                help_text += "/admin - Admin dashboard\n"
                help_text += "/verify <user_id> - Approve user\n"
                help_text += "/reject <user_id> - Reject user\n"
                help_text += "/queue - View verification queue\n"
                help_text += "/stats - View bot statistics\n"
            
            help_text += "\nNeed more help? Contact @{config.ADMIN_USERNAME}"
            
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
            user_data = await get_user_data(user_id)
            
            if user_data:
                status = "✅ Verified" if user_data.get('deposit_confirmed') else "⏳ Pending Verification"
                join_date = user_data.get('join_date', 'Unknown')
                verification_method = user_data.get('verification_method', 'Not verified')
                
                status_text = f"""📊 ACCOUNT STATUS

🔹 Status: {status}
🔹 Verification Method: {verification_method}
🔹 Member Since: {join_date}"""

                keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="my_account")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    status_text,
                    reply_markup=reply_markup
                )
            else:
                await query.edit_message_text(
                    "⚠️ Account not found. Please start over with /start"
                )
        except Exception as e:
            logger.error(f"Error in account status: {e}")

    async def handle_notification_settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show notification settings"""
        try:
            query = update.callback_query
            await query.answer()
            
            user_id = query.from_user.id
            user_data = await get_user_data(user_id)
            
            if user_data:
                notifications = user_data.get('notifications_enabled', True)
                status = "✅ Enabled" if notifications else "❌ Disabled"
                
                settings_text = f"""🔔 NOTIFICATION SETTINGS

Current status: {status}

Would you like to receive trading signals and updates?"""

                keyboard = [
                    [
                        InlineKeyboardButton("✅ Enable", callback_data="enable_notifications"),
                        InlineKeyboardButton("❌ Disable", callback_data="disable_notifications")
                    ],
                    [InlineKeyboardButton("🔙 Back", callback_data="my_account")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    settings_text,
                    reply_markup=reply_markup
                )
            else:
                await query.edit_message_text(
                    "⚠️ Account not found. Please start over with /start"
                )
        except Exception as e:
            logger.error(f"Error in notification settings: {e}")

    async def handle_edit_signal(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle edit signal request"""
        try:
            query = update.callback_query
            if str(query.from_user.id) != config.ADMIN_USER_ID:
                return
            
            await query.answer()
            await query.edit_message_text(
                "Edit signal functionality coming soon!"
            )
        except Exception as e:
            logger.error(f"Error in edit signal: {e}")

    async def run(self):
        """Run the bot with all handlers"""
        try:
            await self.initialize()
            
            app = Application.builder().token(config.BOT_TOKEN).build()
            
            # Register handlers
            app.add_handler(CommandHandler("start", self.start_command))
            app.add_handler(CommandHandler("admin", self.handle_admin_menu))
            app.add_handler(CallbackQueryHandler(self.button_callback))
            app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text_message))
            app.add_handler(MessageHandler(filters.PHOTO, self.handle_photo))
            
            # Register error handler
            app.add_error_handler(self.error_handler)
            
            # Start the bot
            logger.info("Starting bot...")
            await app.run_polling()
        except asyncio.CancelledError:
            logger.info("Bot shutdown requested")
        except Exception as e:
            logger.critical("Fatal error in bot main loop", exc_info=True)
            raise

def main():
    """Entry point"""
    try:
        bot = TradingBot()
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.critical("Bot crashed", exc_info=True)
        raise

if __name__ == "__main__":
    main()