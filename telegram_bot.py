import logging
import os
from typing import Dict, Optional, Any
from datetime import datetime, timedelta
import pytz
import re
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
    ConversationHandler,
)
from telegram.error import TelegramError

# Database imports
from database import (
    initialize_db,
    get_user_data,
    update_user_data,
    create_user,
    log_interaction,
    get_pending_verifications,
    get_all_users,
    delete_user,
    db_manager
)

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# States for conversation
REGISTER_UID, UPLOAD_SCREENSHOT, BROADCAST_MESSAGE, USER_LOOKUP = range(4)

class TradingBot:
    def __init__(self):
        # Load configuration from environment
        self.bot_token = os.getenv('BOT_TOKEN')
        self.broker_link = os.getenv('BROKER_LINK')
        self.premium_channel_id = os.getenv('PREMIUM_CHANNEL_ID')
        self.admin_username = os.getenv('ADMIN_USERNAME')
        self.admin_user_id = int(os.getenv('ADMIN_USER_ID', '0'))
        
        # Bot configuration
        self.webhook_url = os.getenv('WEBHOOK_URL', '')
        self.webhook_port = int(os.getenv('WEBHOOK_PORT', '8000'))
        self.webhook_path = os.getenv('WEBHOOK_PATH', '/webhook')
        
        # Application instance (will be set during initialize)
        self.application = None
    
    def set_application(self, application):
        """Set the application instance for the bot"""
        self.application = application
        
        # Admin keyboard - only shown to admin users
        self.admin_keyboard = [
            [InlineKeyboardButton("📊 Stats", callback_data="stats")],
            [InlineKeyboardButton("📢 Broadcast", callback_data="broadcast")],
            [InlineKeyboardButton("🔍 User Lookup", callback_data="user_lookup")],
        ]
        
        # Verified user keyboard - shown after successful verification
        self.verified_user_keyboard = [
            [InlineKeyboardButton("💎 VIP Signals", callback_data="vip_signals")],
            [InlineKeyboardButton("📈 My Account", callback_data="my_account")],
            [InlineKeyboardButton("🆘 Support", callback_data="support")],
        ]
        
        # Unverified user keyboard - shown to new users
        self.unverified_user_keyboard = [
            [InlineKeyboardButton("🔓 Get Verified", callback_data="get_vip_access")],
            [InlineKeyboardButton("❓ How It Works", callback_data="how_it_works")],
            [InlineKeyboardButton("🆘 Support", callback_data="support")],
        ]
        
        self.message_history = {}  # Track message history per user
        self.user_states = {}  # Track user verification states

    async def _is_admin(self, user_id: int) -> bool:
        """Check if user is admin"""
        return user_id == self.admin_user_id

    async def _is_verified(self, user_id: int) -> bool:
        """Check if user is verified"""
        if user_id in self.user_states:
            return self.user_states[user_id]
        
        user_data = await get_user_data(user_id)
        is_verified = user_data.get("verified", False) if user_data else False
        self.user_states[user_id] = is_verified
        return is_verified

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(Exception)
    )
    async def _send_persistent_message(self, chat_id: int, text: str, reply_markup=None, parse_mode=None, disable_web_page_preview=False):
        """Send a new message while maintaining chat history"""
        try:
            # Always send a new message to preserve chat history
            new_message = await self.application.bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
                disable_web_page_preview=disable_web_page_preview
            )
            self.message_history[chat_id] = new_message.message_id
            return new_message.message_id
        except Exception as e:
            logger.error(f"Error in _send_persistent_message: {e}")
            raise

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command with proper user state management"""
        try:
            user = update.effective_user
            user_id = user.id
            
            # Log interaction
            await log_interaction(user_id, "start_command")
            
            # Check admin status
            if await self._is_admin(user_id):
                await self._send_persistent_message(
                    chat_id=user_id,
                    text="👑 *ADMIN MODE ACTIVATED*\n\nYou now have access to all admin commands.",
                    reply_markup=InlineKeyboardMarkup(self.admin_keyboard),
                    parse_mode="Markdown"
                )
                return
            
            # Check verification status
            is_verified = await self._is_verified(user_id)
            
            if is_verified:
                welcome_text = f"""👋 *Welcome back {user.first_name or "Trader"}!*

You have full access to our VIP trading signals and features."""
                reply_markup = InlineKeyboardMarkup(self.verified_user_keyboard)
            else:
                welcome_text = f"""👋 *Hey {user.first_name or "there"}!* Welcome to *OPTRIXTRADES*

Unlock VIP trading signals by completing our quick verification process."""
                reply_markup = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔓 Get Verified", callback_data="get_vip_access")],
                    [InlineKeyboardButton("❓ How It Works", callback_data="how_it_works")]
                ])
            
            await self._send_persistent_message(
                chat_id=user_id,
                text=welcome_text,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
            
            # Send follow-up based on user state
            if is_verified:
                follow_up = "Use the menu below to access your VIP features:"
            else:
                follow_up = """*Here's what you get when verified:*
✅ Daily VIP trading signals
✅ Expert trading strategies
✅ Private community access"""
                
            await context.bot.send_message(
                chat_id=user_id,
                text=follow_up,
                parse_mode="Markdown",
                reply_to_message_id=self.message_history.get(user_id)
            )
            
            # Create user in database if not exists
            if not await get_user_data(user_id):
                await create_user(user_id, user.first_name, user.username)
                
        except Exception as e:
            logger.error(f"Error in start_command: {e}")

    async def how_it_works(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Detailed explanation of the verification process"""
        try:
            query = update.callback_query
            await query.answer()
            
            user_id = query.from_user.id
            is_verified = await self._is_verified(user_id)
            
            if is_verified:
                text = """✅ *You're already verified!*

You have full access to all VIP features."""
                keyboard = self.verified_user_keyboard
            else:
                text = f"""📝 *How It Works:*

1️⃣ *Register* at our broker: [Click Here]({self.broker_link})
2️⃣ *Deposit* $20+ (recommended $100+ for full access)
3️⃣ *Verify* by sending your UID and deposit proof
4️⃣ *Get Access* to VIP signals within minutes

*Why we verify:*
🔒 Prevent signal abuse
🛡️ Ensure serious traders only
💎 Maintain signal quality"""
                keyboard = [
                    [InlineKeyboardButton("🔓 Start Verification", callback_data="get_vip_access")],
                    [InlineKeyboardButton("⬅️ Back", callback_data="main_menu")]
                ]
            
            await self._send_persistent_message(
                chat_id=user_id,
                text=text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown",
                disable_web_page_preview=True
            )
        except Exception as e:
            logger.error(f"Error in how_it_works: {e}")

    async def get_vip_access(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start verification process"""
        try:
            query = update.callback_query
            await query.answer()
            
            user_id = query.from_user.id
            is_verified = await self._is_verified(user_id)
            
            if is_verified:
                await self._send_persistent_message(
                    chat_id=user_id,
                    text="✅ *You're already verified!*",
                    reply_markup=InlineKeyboardMarkup(self.verified_user_keyboard),
                    parse_mode="Markdown"
                )
                return
            
            text = """🔓 *Get VIP Access*

To verify your account:

1️⃣ Open your broker account
2️⃣ Copy your *Unique ID* (UID)
3️⃣ Take screenshot of your deposit
4️⃣ Send both to this bot

*Minimum deposit:* $20 (recommended $100+)"""
            
            await self._send_persistent_message(
                chat_id=user_id,
                text=text,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📝 Start Verification", callback_data="start_verification")],
                    [InlineKeyboardButton("❓ Where to find UID?", callback_data="uid_help")]
                ]),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Error in get_vip_access: {e}")

    async def start_verification(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Begin verification process"""
        try:
            query = update.callback_query
            await query.answer()
            
            user_id = query.from_user.id
            
            await self._send_persistent_message(
                chat_id=user_id,
                text="📝 *Verification Step 1/2*\n\nPlease send your *Broker UID* (8-20 characters, alphanumeric):",
                parse_mode="Markdown"
            )
            
            return REGISTER_UID
        except Exception as e:
            logger.error(f"Error in start_verification: {e}")
            return ConversationHandler.END

    async def handle_uid_confirmation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Process UID input"""
        try:
            user_id = update.message.from_user.id
            uid = update.message.text.strip()
            
            if not re.match(r"^[A-Za-z0-9]{8,20}$", uid):
                await update.message.reply_text(
                    "❌ *Invalid UID format*\n\nPlease enter a valid UID (8-20 alphanumeric characters).\nExample: ABC123XYZ456",
                    parse_mode="Markdown"
                )
                return REGISTER_UID
            
            await update_user_data(user_id, {"uid": uid})
            
            await self._send_persistent_message(
                chat_id=user_id,
                text="✅ *UID Received!*\n\n📸 *Verification Step 2/2*\n\nNow please send your *deposit screenshot* as a photo:",
                parse_mode="Markdown"
            )
            
            return UPLOAD_SCREENSHOT
        except Exception as e:
            logger.error(f"Error in handle_uid_confirmation: {e}")
            return ConversationHandler.END

    async def handle_screenshot_upload(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Process screenshot upload"""
        try:
            user_id = update.message.from_user.id
            photo = update.message.photo[-1]
            
            # Store photo file_id for verification
            await update_user_data(user_id, {
                "screenshot_id": photo.file_id,
                "verification_pending": True,
                "verification_date": datetime.now(pytz.utc).isoformat()
            })
            
            # Notify admin
            if self.admin_user_id:
                try:
                    user_data = await get_user_data(user_id)
                    uid = user_data.get('uid', 'Not provided') if user_data else 'Not provided'
                    await context.bot.send_message(
                        chat_id=self.admin_user_id,
                        text=f"🔄 New verification request from user {user_id}\n\nUID: {uid}"
                    )
                    await context.bot.send_photo(
                        chat_id=self.admin_user_id,
                        photo=photo.file_id
                    )
                except Exception as e:
                    logger.error(f"Couldn't notify admin: {e}")
            
            await self._send_persistent_message(
                chat_id=user_id,
                text="🔍 *Verification in Progress...*\n\nWe're reviewing your information. This usually takes 1-2 hours.",
                parse_mode="Markdown"
            )
            
            return ConversationHandler.END
        except Exception as e:
            logger.error(f"Error in handle_screenshot_upload: {e}")
            return ConversationHandler.END

    async def vip_signals_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /vipsignals command"""
        try:
            user_id = update.effective_user.id
            is_verified = await self._is_verified(user_id)
            
            if is_verified:
                text = """📈 *Today's VIP Signals* 🚀

*EUR/USD*  
🟢 BUY @ 1.0850  
🎯 TP: 1.0900  
⛔ SL: 1.0820  
📊 Confidence: High  

*GBP/USD*  
🔴 SELL @ 1.2650  
🎯 TP: 1.2600  
⛔ SL: 1.2680  
📊 Confidence: Medium  

*BTC/USD*  
🟢 BUY @ 42000  
🎯 TP: 43000  
⛔ SL: 41500  
📊 Confidence: High  

💡 *Risk Management Tip*  
Only risk 1-2% of your capital per trade"""
            else:
                text = "🔒 *VIP Signals are for verified members only*\n\nComplete verification to access our premium signals."
            
            reply_markup = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔓 Get Verified", callback_data="get_vip_access")],
                [InlineKeyboardButton("⬅️ Main Menu", callback_data="main_menu")]
            ]) if not is_verified else InlineKeyboardMarkup(self.verified_user_keyboard)
            
            await self._send_persistent_message(
                chat_id=user_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Error in vip_signals_command: {e}")

    async def my_account_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /myaccount command"""
        try:
            user_id = update.effective_user.id
            user_data = await get_user_data(user_id)
            
            if user_data:
                status = "✅ Verified" if user_data.get("verified") else "❌ Not Verified"
                uid = user_data.get("uid", "Not provided")
                join_date = user_data.get("join_date", "Unknown")
                deposit_amount = user_data.get("deposit_amount", "Not specified")
                
                text = f"""📊 *Your Account Details*

🆔 *UID:* `{uid}`  
🔒 *Status:* {status}  
💰 *Deposit:* ${deposit_amount}  
📅 *Member Since:* {join_date}  

💼 *Broker Link:* [Click Here]({self.broker_link})"""
            else:
                text = "❌ *No account information found*\n\nPlease complete registration to create your account."
            
            reply_markup = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Refresh", callback_data="my_account")],
                [InlineKeyboardButton("⬅️ Main Menu", callback_data="main_menu")]
            ])
            
            await self._send_persistent_message(
                chat_id=user_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode="Markdown",
                disable_web_page_preview=True
            )
        except Exception as e:
            logger.error(f"Error in my_account_command: {e}")

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stats command (admin only)"""
        try:
            user_id = update.effective_user.id
            
            if not await self._is_admin(user_id):
                await update.message.reply_text("⛔ *Unauthorized*", parse_mode="Markdown")
                return
            
            users = await get_all_users()
            total_users = len(users)
            verified_users = len([u for u in users if u.get("verified")])
            pending_verification = len([u for u in users if u.get("verification_pending")])
            
            text = f"""📊 *Bot Statistics*

👥 *Total Users:* {total_users}  
✅ *Verified Users:* {verified_users}  
🔄 *Pending Verification:* {pending_verification}  
📈 *Verification Rate:* {round((verified_users/total_users)*100 if total_users > 0 else 0, 2)}%  

⏳ *Last Updated:* {datetime.now(pytz.utc).strftime('%Y-%m-%d %H:%M UTC')}"""
            
            await self._send_persistent_message(
                chat_id=user_id,
                text=text,
                reply_markup=InlineKeyboardMarkup(self.admin_keyboard),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Error in stats_command: {e}")

    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Central button callback handler"""
        try:
            query = update.callback_query
            await query.answer()
            
            data = query.data
            user_id = query.from_user.id
            
            # Route to appropriate handler
            if data == "get_vip_access":
                await self.get_vip_access(update, context)
            elif data == "how_it_works":
                await self.how_it_works(update, context)
            elif data == "start_verification":
                await self.start_verification(update, context)
            elif data == "vip_signals":
                await self.vip_signals_command(update, context)
            elif data == "my_account":
                await self.my_account_command(update, context)
            elif data == "support":
                await self.support_command(update, context)
            elif data == "stats":
                await self.stats_command(update, context)
            elif data == "broadcast":
                await self.handle_broadcast(update, context)
            elif data == "user_lookup":
                await self.handle_user_lookup(update, context)
            elif data == "main_menu":
                await self.handle_main_menu(update, context)
            elif data == "uid_help":
                await self.uid_help(update, context)
            else:
                await query.answer("Feature coming soon!")
        except Exception as e:
            logger.error(f"Error in button callback: {e}")

    async def handle_text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages from users"""
        try:
            user_id = update.effective_user.id
            message_text = update.message.text.strip()
            text = message_text.upper()
            
            user_data = await get_user_data(user_id)
            if not user_data:
                await self.start_command(update, context)
                return
            
            await log_interaction(user_id, "text_message", update.message.text)
            
            # Handle UID submission
            uid = message_text.replace("UID:", "").strip()
            
            # Check if this looks like a UID (6-20 alphanumeric characters)
            if len(uid) >= 6 and len(uid) <= 20 and uid.isalnum():
                # Update user with UID
                await update_user_data(user_id, uid=uid)
                
                response_text = f"""✅ **UID Received: {uid}**

📸 **Next Step:** Send your deposit screenshot to complete verification

⚡ **What happens next:**
• Upload your deposit screenshot
• Our system will process your verification
• You'll get instant access once approved

🎯 **Ready for screenshot upload!**"""
                
                await update.message.reply_text(response_text, parse_mode='Markdown')
                return  # Exit early for valid UID
            
            # Check if user tried to send a UID but it's invalid format
            elif len(message_text) >= 3 and any(c.isalnum() for c in message_text):
                error_response = f"""❌ **Invalid UID Format**

📋 **UID Requirements:**
• Length: 6-20 characters
• Format: Letters and numbers only

💡 **Examples of valid UIDs:**
• ABC123456
• USER789012
• TRADER456789

🔄 **Please send a valid UID to continue.**"""
                
                await update.message.reply_text(error_response, parse_mode='Markdown')
                return  # Exit early for invalid UID
                    
            elif text == "UPGRADE":
                await self._handle_upgrade_request(update, context)
            else:
                # Default response for unrecognized text
                await update.message.reply_text(
                    "I received your message. Use the menu buttons to navigate or type /start to see options."
                )
                
        except Exception as e:
            logger.error(f"Error in handle_text_message: {e}")

    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle photo uploads from users"""
        try:
            user_id = update.effective_user.id
            user_data = await get_user_data(user_id)
            
            if not user_data:
                await update.message.reply_text("Please start with /start first.")
                return
            
            await log_interaction(user_id, "photo_upload", "deposit_screenshot")
            
            # Check if user has provided UID
            uid = user_data[6] if len(user_data) > 6 and user_data[6] else None
            
            if uid:
                screenshot_file_id = update.message.photo[-1].file_id
                
                # Create verification request
                try:
                    from database.connection import create_verification_request
                    await create_verification_request(user_id, uid, screenshot_file_id)
                    
                    confirmation_text = f"""✅ **Screenshot Received Successfully!**

📋 **Verification Details:**
• UID: {uid}
• Screenshot: Uploaded
• Status: Under Review

⏳ Your verification request has been submitted to our admin team. You'll receive a notification once your deposit is verified.

🕐 **Processing Time:** Usually within 2-4 hours

Thank you for your patience! 🙏"""
                    
                    await update.message.reply_text(confirmation_text, parse_mode='Markdown')
                    
                    # Notify admin
                    if self.admin_user_id:
                        admin_notification = f"""🔔 **New Verification Request**

👤 **User:** {update.effective_user.first_name or 'Unknown'}
🆔 **User ID:** {user_id}
🔑 **UID:** {uid}
📸 **Screenshot:** Uploaded

**Admin Actions:**
• /verify {user_id} - Approve
• /reject {user_id} - Reject
• /queue - View all pending"""
                        
                        try:
                            await context.bot.send_message(
                                chat_id=self.admin_user_id,
                                text=admin_notification,
                                parse_mode='Markdown'
                            )
                        except Exception as admin_error:
                            logger.error(f"Failed to notify admin: {admin_error}")
                            
                except Exception as db_error:
                    logger.error(f"Database error in verification: {db_error}")
                    await update.message.reply_text(
                        "❌ There was an error processing your verification. Please try again or contact support."
                    )
            else:
                await update.message.reply_text(
                    "📸 Screenshot received! But I need your UID first.\n\nPlease send your broker UID, then upload your screenshot again."
                )
                
        except Exception as e:
            logger.error(f"Error in handle_photo: {e}")
            await update.message.reply_text(
                "❌ There was an error processing your photo. Please try again."
            )

    async def _handle_upgrade_request(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle upgrade requests from users"""
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

Contact: @{self.admin_username}"""
            
            await update.message.reply_text(upgrade_text)
            
        except Exception as e:
            logger.error(f"Error in _handle_upgrade_request: {e}")

    async def _track_messages(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Track messages for persistent messaging"""
        try:
            if update.message and update.message.chat.type == 'private':
                chat_id = update.message.chat_id
                self.message_history[chat_id] = update.message.message_id
        except Exception as e:
            logger.error(f"Error tracking message: {e}")

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel current conversation"""
        try:
            await update.message.reply_text(
                "❌ Operation cancelled. Type /start to begin again.",
                reply_markup=ReplyKeyboardRemove()
            )
            return ConversationHandler.END
        except Exception as e:
            logger.error(f"Error in cancel: {e}")
            return ConversationHandler.END

    async def support_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle support requests"""
        try:
            user_id = update.effective_user.id if update.effective_user else None
            
            if update.callback_query:
                await update.callback_query.answer()
                user_id = update.callback_query.from_user.id
            
            support_text = f"""🆘 *Support & Help*

📞 *Contact our support team:*
👤 Admin: @{self.admin_username}

❓ *Common Questions:*
• How to verify my account?
• Where to find my UID?
• Minimum deposit amount?
• How long does verification take?

💬 *Live Chat:* Available 24/7"""
            
            keyboard = [
                [InlineKeyboardButton("💬 Contact Admin", url=f"https://t.me/{self.admin_username}")],
                [InlineKeyboardButton("⬅️ Back to Menu", callback_data="main_menu")]
            ]
            
            await self._send_persistent_message(
                chat_id=user_id,
                text=support_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Error in support_command: {e}")

    async def handle_broadcast(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle broadcast functionality (admin only)"""
        try:
            user_id = update.effective_user.id if update.effective_user else update.callback_query.from_user.id
            
            if not await self._is_admin(user_id):
                await update.callback_query.answer("⛔ Unauthorized")
                return
            
            await self._send_persistent_message(
                chat_id=user_id,
                text="📢 *Broadcast Message*\n\nPlease send the message you want to broadcast to all users:",
                parse_mode="Markdown"
            )
            
            return BROADCAST_MESSAGE
        except Exception as e:
            logger.error(f"Error in handle_broadcast: {e}")

    async def handle_user_lookup(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle user lookup functionality (admin only)"""
        try:
            user_id = update.effective_user.id if update.effective_user else update.callback_query.from_user.id
            
            if not await self._is_admin(user_id):
                await update.callback_query.answer("⛔ Unauthorized")
                return
            
            await self._send_persistent_message(
                chat_id=user_id,
                text="🔍 *User Lookup*\n\nPlease send the User ID you want to look up:",
                parse_mode="Markdown"
            )
            
            return USER_LOOKUP
        except Exception as e:
            logger.error(f"Error in handle_user_lookup: {e}")

    async def handle_main_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle main menu navigation"""
        try:
            user_id = update.callback_query.from_user.id if update.callback_query else update.effective_user.id
            
            if await self._is_admin(user_id):
                keyboard = self.admin_keyboard
                text = "👑 *Admin Panel*\n\nSelect an option:"
            elif await self._is_verified(user_id):
                keyboard = self.verified_user_keyboard
                text = "💎 *VIP Member Dashboard*\n\nWelcome back! Choose an option:"
            else:
                keyboard = self.unverified_user_keyboard
                text = "🔓 *Get Started*\n\nComplete verification to unlock VIP features:"
            
            await self._send_persistent_message(
                chat_id=user_id,
                text=text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Error in handle_main_menu: {e}")

    async def uid_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show UID help information"""
        try:
            query = update.callback_query
            await query.answer()
            
            user_id = query.from_user.id
            
            help_text = f"""❓ *Where to find your UID?*

1️⃣ Open your broker account
2️⃣ Go to 'Profile' or 'Account Settings'
3️⃣ Look for 'User ID', 'Account ID', or 'UID'
4️⃣ Copy the alphanumeric code (8-20 characters)

*Example UIDs:*
• ABC123XYZ456
• USER789012
• ID1234567890

*Need help?* Contact @{self.admin_username}"""
            
            keyboard = [
                [InlineKeyboardButton("📝 Start Verification", callback_data="start_verification")],
                [InlineKeyboardButton("⬅️ Back", callback_data="get_vip_access")]
            ]
            
            await self._send_persistent_message(
                chat_id=user_id,
                text=help_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Error in uid_help: {e}")

    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks"""
        try:
            query = update.callback_query
            await query.answer()
            
            user_id = query.from_user.id
            data = query.data
            
            # Route to appropriate handler based on callback data
            if data == "get_vip_access":
                await self.get_vip_access(update, context)
            elif data == "how_it_works":
                await self.how_it_works(update, context)
            elif data == "start_verification":
                await self.start_verification(update, context)
            elif data == "uid_help":
                await self.uid_help(update, context)
            elif data == "vip_signals":
                await self.vip_signals_command(update, context)
            elif data == "my_account":
                await self.my_account_command(update, context)
            elif data == "support":
                await self.support_command(update, context)
            elif data == "stats":
                await self.stats_command(update, context)
            elif data == "broadcast":
                await self.handle_broadcast(update, context)
            elif data == "user_lookup":
                await self.handle_user_lookup(update, context)
            elif data == "main_menu":
                await self.handle_main_menu(update, context)
            else:
                await query.answer("Unknown action")
                
        except Exception as e:
            logger.error(f"Error in button_callback: {e}")

    async def handle_text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages"""
        try:
            user_id = update.effective_user.id
            message_text = update.message.text.strip()
            text = message_text.upper()
            
            # Log interaction
            await log_interaction(user_id, "text_message", message_text)
            
            # Check if user exists, if not create them
            user_data = await get_user_data(user_id)
            if not user_data:
                await self.start_command(update, context)
                return
            
            # Handle UID submission
            uid = message_text.replace("UID:", "").strip()
            
            # Check if this looks like a UID (6-20 alphanumeric characters)
            if len(uid) >= 6 and len(uid) <= 20 and uid.isalnum():
                # Valid UID format
                await update_user_data(user_id, {"uid": uid})
                await update.message.reply_text(
                    f"✅ UID Received: {uid}\n\nNow please upload your deposit screenshot to complete verification.",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("📋 Main Menu", callback_data="main_menu")]
                    ])
                )
                return
            
            # Handle UPGRADE command
            if text == "UPGRADE":
                await update.message.reply_text(
                    "🔓 *VIP Access Verification*\n\nTo get VIP access, you need to:\n\n1️⃣ Provide your Broker UID\n2️⃣ Upload deposit screenshot\n\nClick below to start:",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔓 Start Verification", callback_data="get_vip_access")]
                    ])
                )
                return
            
            # Default response for unrecognized text
            await update.message.reply_text(
                "I received your message. Use the menu buttons to navigate or type /start to see options.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📋 Main Menu", callback_data="main_menu")]
                ])
            )
            
        except Exception as e:
            logger.error(f"Error in handle_text_message: {e}")

    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle photo uploads"""
        try:
            user_id = update.effective_user.id
            
            # Log interaction
            await log_interaction(user_id, "photo_upload", "screenshot")
            
            # Check if user exists
            user_data = await get_user_data(user_id)
            if not user_data:
                await update.message.reply_text("Please start with /start first.")
                return
            
            # Handle photo upload (could be verification screenshot)
            photo = update.message.photo[-1]  # Get highest resolution
            
            # For now, acknowledge receipt
            await update.message.reply_text(
                "📸 Photo received! If this is a verification screenshot, please make sure you've also provided your UID.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔓 Start Verification", callback_data="get_vip_access")],
                    [InlineKeyboardButton("📋 Main Menu", callback_data="main_menu")]
                ])
            )
            
        except Exception as e:
            logger.error(f"Error in handle_photo: {e}")

    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Log errors caused by updates."""
        logger.error("Exception while handling an update:", exc_info=context.error)
        
        # Notify admin of critical errors
        if self.admin_user_id:
            try:
                await context.bot.send_message(
                    chat_id=self.admin_user_id,
                    text=f"🚨 Bot Error: {str(context.error)[:500]}"
                )
            except Exception as e:
                logger.error(f"Failed to send error notification: {e}")

    async def initialize(self):
        """Initialize the bot"""
        await initialize_db()
        logger.info("Database initialized")

    def _setup_handlers(self):
        """Setup all bot handlers"""
        # Add handler to track message history
        self.application.add_handler(MessageHandler(filters.ALL, self._track_messages), group=-1)
        
        # Conversation handler for verification flow
        verification_conv = ConversationHandler(
            entry_points=[
                CallbackQueryHandler(self.start_verification, pattern="^start_verification$"),
                CommandHandler("verify", self.start_verification)
            ],
            states={
                REGISTER_UID: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_uid_confirmation)],
                UPLOAD_SCREENSHOT: [MessageHandler(filters.PHOTO, self.handle_screenshot_upload)],
            },
            fallbacks=[CommandHandler("cancel", self.cancel)],
        )
        
        # Add all handlers
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("vipsignals", self.vip_signals_command))
        self.application.add_handler(CommandHandler("myaccount", self.my_account_command))
        self.application.add_handler(CommandHandler("support", self.support_command))
        self.application.add_handler(CommandHandler("stats", self.stats_command))
        self.application.add_handler(CommandHandler("howitworks", self.how_it_works))
        
        self.application.add_handler(CallbackQueryHandler(self.button_callback))
        self.application.add_handler(verification_conv)
        
        # Add text and photo handlers
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text_message))
        self.application.add_handler(MessageHandler(filters.PHOTO, self.handle_photo))
        
        self.application.add_error_handler(self.error_handler)

    async def start_polling(self):
        """Start bot in polling mode"""
        logger.info("🔄 Starting bot in polling mode...")
        await self.application.run_polling(allowed_updates=Update.ALL_TYPES)

    async def start_webhook(self):
        """Start bot in webhook mode"""
        logger.info("🔄 Starting bot in webhook mode...")
        await self.application.run_webhook(
            listen="0.0.0.0",
            port=self.webhook_port,
            url_path=self.webhook_path,
            webhook_url=self.webhook_url + self.webhook_path
        )

    async def run(self):
        """Run the bot with all handlers"""
        try:
            await self.initialize()
            
            # Create application
            self.application = Application.builder().token(self.bot_token).build()
            self._setup_handlers()
            
            # Start the bot
            logger.info("Bot is running...")
            if self.webhook_url:
                await self.start_webhook()
            else:
                await self.start_polling()
        except Exception as e:
            logger.error(f"Error in bot run: {e}")
            raise

if __name__ == "__main__":
    bot = TradingBot()
    asyncio.run(bot.run())