import logging
import os
import asyncio
import re
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram.error import TelegramError

# Import database manager
from database import db_manager, get_user_data, update_user_data, create_user, log_interaction
from config import config
from utils.error_handler import error_handler, ErrorHandler

# Configure logging for production
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=getattr(logging, config.LOG_LEVEL),
    handlers=[
        logging.FileHandler(config.LOG_FILE_PATH),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize error handler
error_handler_instance = ErrorHandler()

class TradingBot:
    def __init__(self):
        self.premium_channel_link = f"https://t.me/c/{config.PREMIUM_CHANNEL_ID.replace('-100', '')}"
        
        # Admin keyboards
        self.admin_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 Statistics", callback_data="admin_stats"),
             InlineKeyboardButton("👥 Verification Queue", callback_data="admin_queue")],
            [InlineKeyboardButton("📢 Post Signal", callback_data="post_signal"),
             InlineKeyboardButton("📝 Edit Last Signal", callback_data="edit_signal")]
        ])
        
        # User main menu keyboard
        self.user_main_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("💎 VIP Access", callback_data="get_vip_access")],
            [InlineKeyboardButton("📱 My Account", callback_data="my_account"),
             InlineKeyboardButton("ℹ️ Help", callback_data="help_menu")],
            [InlineKeyboardButton("📞 Support", callback_data="contact_support")]
        ])
        
        # Help menu keyboard
        self.help_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📝 Registration Help", callback_data="help_signup"),
             InlineKeyboardButton("💳 Deposit Help", callback_data="help_deposit")],
            [InlineKeyboardButton("❓ FAQ", callback_data="faq"),
             InlineKeyboardButton("📞 Contact Support", callback_data="contact_support")],
            [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu")]
        ])
        
        # Account menu keyboard
        self.account_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 My Status", callback_data="account_status"),
             InlineKeyboardButton("⭐️ Upgrade Account", callback_data="upgrade_account")],
            [InlineKeyboardButton("🔔 Notification Settings", callback_data="notification_settings")],
            [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu")]
        ])

    async def initialize(self):
        """Initialize bot and database"""
        try:
            logger.info("Initializing OPTRIXTRADES bot...")
            await db_manager.initialize()
            logger.info("Bot initialization completed successfully")
        except Exception as e:
            logger.error(f"Bot initialization failed: {e}")
            raise

    @error_handler("validate_uid")
    def validate_uid(self, uid):
        """Validate UID format for auto-verification"""
        try:
            # Basic validation rules
            if not uid or len(uid) < config.MIN_UID_LENGTH or len(uid) > config.MAX_UID_LENGTH:
                return False, "UID length invalid"
            
            # Check if UID contains only alphanumeric characters
            if not re.match(r'^[a-zA-Z0-9]+$', uid):
                return False, "UID contains invalid characters"
            
            # Check for common patterns (you can customize these)
            if uid.lower() in ['test', 'demo', '123456', 'sample']:
                return False, "UID appears to be a test/demo account"
            
            return True, "UID format valid"
            
        except Exception as e:
            logger.error(f"Error validating UID {uid}: {e}")
            return False, "UID validation error"

    @error_handler("auto_verify_user")
    async def auto_verify_user(self, user_id, uid, screenshot_file_id):
        """Auto-verify user based on criteria"""
        try:
            # Validate UID
            uid_valid, uid_message = self.validate_uid(uid)
            
            if not uid_valid:
                logger.info(f"Auto-verification failed for user {user_id}: {uid_message}")
                return False, uid_message
            
            # Additional checks can be added here:
            # - Image format validation
            # - File size checks
            # - Pattern recognition in screenshots
            # - Time-based verification
            
            # For now, if UID is valid, auto-approve
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
                    # Add to verification queue for admin review
                    await self.add_to_verification_queue(user_id, uid, screenshot_file_id, auto_verified=True)
                    
                    logger.info(f"User {user_id} auto-verified successfully")
                    return True, "Auto-verification successful"
                else:
                    return False, "Database update failed"
            else:
                # Add to manual verification queue
                await self.add_to_verification_queue(user_id, uid, screenshot_file_id, auto_verified=False)
                return False, "Manual verification required"
                
        except Exception as e:
            logger.error(f"Error in auto-verification for user {user_id}: {e}")
            return False, "Auto-verification error"

    @error_handler("add_to_verification_queue")
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
            
            # Notify admin if manual verification needed
            if not auto_verified:
                asyncio.create_task(self.notify_admin_verification_needed(user_id, uid))
                
        except Exception as e:
            logger.error(f"Error adding to verification queue: {e}")

    @error_handler("notify_admin_verification_needed")
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

                # Send to admin
                from telegram import Bot
                bot = Bot(token=config.BOT_TOKEN)
                await bot.send_message(chat_id=config.ADMIN_USER_ID, text=admin_message)
                
        except Exception as e:
            logger.error(f"Error notifying admin: {e}")

    @error_handler("start_command")
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        try:
            user = update.effective_user
            user_id = user.id
            username = user.username or ""
            first_name = user.first_name or "there"
            
            await create_user(user_id, username, first_name)
            await log_interaction(user_id, "start_command")
            
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

    @error_handler("activation_instructions")
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

    @error_handler("registration_confirmation")
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

    @error_handler("handle_text_message")
    async def handle_text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages"""
        try:
            user_id = update.effective_user.id
            text = update.message.text
            
            # Admin commands
            if str(user_id) == config.ADMIN_USER_ID:
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
                # This is a UID
                await update_user_data(user_id, uid=text)
                await update.message.reply_text(
                    "✅ UID received! Now please send your deposit screenshot."
                )
                
        except Exception as e:
            logger.error(f"Error handling text message: {e}")

    @error_handler("handle_photo")
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
                
                # Get the largest photo
                photo = update.message.photo[-1]
                screenshot_file_id = photo.file_id
                
                # Store screenshot file ID
                await update_user_data(user_id, screenshot_file_id=screenshot_file_id)
                
                # Attempt auto-verification
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

Your trading journey starts now! �

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

    @error_handler("admin_verify_user")
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
            
            # Update user verification status
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
                # Mark as admin reviewed in queue
                if db_manager.db_type == 'postgresql':
                    query = 'UPDATE verification_queue SET admin_reviewed = TRUE, reviewed_at = CURRENT_TIMESTAMP WHERE user_id = $1'
                else:
                    query = 'UPDATE verification_queue SET admin_reviewed = TRUE, reviewed_at = CURRENT_TIMESTAMP WHERE user_id = ?'
                
                await db_manager.execute_query(query, (target_user_id,))
                
                # Notify user
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
                
                # Confirm to admin
                first_name = user_data.get('first_name', 'Unknown')
                await update.message.reply_text(f"✅ User {first_name} (ID: {target_user_id}) has been manually verified and granted access.")
            else:
                await update.message.reply_text("❌ Failed to update user verification status.")
            
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID format.")
        except Exception as e:
            logger.error(f"Error in admin verify: {e}")
            await update.message.reply_text("❌ Error processing verification command.")

    @error_handler("admin_reject_user")
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
            
            # Update user verification status
            success = await update_user_data(
                target_user_id,
                verification_status='rejected',
                verification_method='manual',
                verified_by=f"admin_{update.effective_user.id}",
                verification_date=datetime.now()
            )
            
            if success:
                # Mark as admin reviewed in queue
                if db_manager.db_type == 'postgresql':
                    query = 'UPDATE verification_queue SET admin_reviewed = TRUE, reviewed_at = CURRENT_TIMESTAMP WHERE user_id = $1'
                else:
                    query = 'UPDATE verification_queue SET admin_reviewed = TRUE, reviewed_at = CURRENT_TIMESTAMP WHERE user_id = ?'
                
                await db_manager.execute_query(query, (target_user_id,))
                
                # Notify user
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
                
                # Confirm to admin
                first_name = user_data.get('first_name', 'Unknown')
                await update.message.reply_text(f"❌ User {first_name} (ID: {target_user_id}) verification has been rejected.")
            else:
                await update.message.reply_text("❌ Failed to update user verification status.")
            
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID format.")
        except Exception as e:
            logger.error(f"Error in admin reject: {e}")
            await update.message.reply_text("❌ Error processing rejection command.")

    @error_handler("show_verification_queue")
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
                
                # Format datetime
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

    @error_handler("show_admin_stats")
    async def show_admin_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show admin statistics"""
        try:
            # Get various stats
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

    @error_handler("handle_upgrade_request")
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

    @error_handler("help_signup")
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

    @error_handler("help_deposit")
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

    @error_handler("handle_not_interested")
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

    @error_handler("button_callback")
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks"""
        try:
            query = update.callback_query
            data = query.data
            
            # Main menu options
            if data == "main_menu":
                await self.handle_main_menu(update, context)
            elif data == "my_account":
                await self.handle_account_menu(update, context)
            elif data == "help_menu":
                await self.handle_help_menu(update, context)
            
            # VIP access flow
            elif data == "get_vip_access":
                await self.activation_instructions(update, context)
            elif data == "registered":
                await self.registration_confirmation(update, context)
                
            # Help options
            elif data == "help_signup":
                await self.help_signup(update, context)
            elif data == "help_deposit":
                await self.help_deposit(update, context)
            elif data == "not_interested":
                await self.handle_not_interested(update, context)
            elif data == "contact_support":
                await query.answer()
                await query.edit_message_text(f"Please contact our support team: @{config.ADMIN_USERNAME}")
            
            # Account options
            elif data == "account_status":
                await self.handle_account_status(update, context)
            elif data == "upgrade_account":
                await self.handle_upgrade_request(update, context)
            elif data == "notification_settings":
                await self.handle_notification_settings(update, context)
            
            # Admin options
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

    @error_handler("handle_main_menu")
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

    @error_handler("handle_account_menu")
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

    @error_handler("handle_help_menu")
    async def handle_help_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show help menu"""
        try:
            query = update.callback_query
            await query.answer()
            
            help_text = f"ℹ️ Help Center\n\n"\
                f"How can we assist you today?\n\n"\
                f"Select a topic below or contact our support team."
            
            await query.edit_message_text(
                help_text,
                reply_markup=self.help_keyboard
            )
            
        except Exception as e:
            logger.error(f"Error in help menu: {e}")

    @error_handler("handle_account_status")
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

    @error_handler("handle_notification_settings")
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

    @error_handler("handle_edit_signal")
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
            
            application = Application.builder().token(config.BOT_TOKEN).build()
            
            # Add command handlers
            application.add_handler(CommandHandler("start", self.start_command))
            application.add_handler(CommandHandler("admin", self.handle_admin_menu))
            
            # Add callback query handlers
            application.add_handler(CallbackQueryHandler(self.button_callback))
            
            # Add message handlers
            application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text_message))
            application.add_handler(MessageHandler(filters.PHOTO, self.handle_photo))
            
            # Add error handler
            application.add_error_handler(self.error_handler)
            
            # Start polling
            await application.run_polling()
            
        except Exception as e:
            logger.error(f"Error in run: {e}")
            raise

def main():
    """Main function"""
    try:
        bot = TradingBot()
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot crashed: {e}")
        raise

if __name__ == '__main__':
    main()