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

# Configuration imports
from config import BotConfig

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

# Constants from BotConfig
PREMIUM_CHANNEL_LINK = f"https://t.me/c/{BotConfig.PREMIUM_CHANNEL_ID.replace('-100', '')}"
PREMIUM_GROUP_LINK = "https://t.me/+LTnKwBO54DRiOTNk"  # Premium group link

# States for conversation
REGISTER_UID, UPLOAD_SCREENSHOT, BROADCAST_MESSAGE, USER_LOOKUP = range(4)

# Helper functions
def validate_uid(uid):
    """Validate UID format and length"""
    if not uid or not isinstance(uid, str):
        return False, "UID must be a valid string"
    
    # Remove whitespace
    uid = uid.strip()
    
    if len(uid) < BotConfig.MIN_UID_LENGTH:
        return False, f"UID too short (minimum {BotConfig.MIN_UID_LENGTH} characters)"
    
    if len(uid) > BotConfig.MAX_UID_LENGTH:
        return False, f"UID too long (maximum {BotConfig.MAX_UID_LENGTH} characters)"
    
    # Check for alphanumeric characters only
    if not uid.isalnum():
        return False, "UID must contain only letters and numbers"
    
    return True, "Valid UID"

def should_auto_verify(user_id, uid):
    """Determine if user should be auto-verified based on criteria"""
    if not BotConfig.AUTO_VERIFY_ENABLED:
        return False, "Auto-verification is disabled"
    
    # Validate UID format
    is_valid, reason = validate_uid(uid)
    if not is_valid:
        return False, reason
    
    # Check business hours if required
    if BotConfig.AUTO_VERIFY_BUSINESS_HOURS_ONLY:
        current_hour = datetime.now().hour
        if not (BotConfig.BUSINESS_HOURS_START <= current_hour < BotConfig.BUSINESS_HOURS_END):
            return False, "Auto-verification only available during business hours"
    
    # Check daily auto-approval limit
    today = datetime.now().date()
    if BotConfig.DATABASE_TYPE == 'postgresql':
        query = '''
            SELECT COUNT(*) as count FROM verification_requests 
            WHERE status = %s AND auto_verified = %s 
            AND DATE(created_at) = %s
        '''
    else:
        query = '''
            SELECT COUNT(*) as count FROM verification_requests 
            WHERE status = ? AND auto_verified = ? 
            AND DATE(created_at) = ?
        '''
    
    result = db_manager.execute_query(query, ('approved', True, today), fetch=True)
    daily_count = result[0]['count'] if result else 0
    
    if daily_count >= BotConfig.DAILY_AUTO_APPROVAL_LIMIT:
        return False, f"Daily auto-approval limit reached ({BotConfig.DAILY_AUTO_APPROVAL_LIMIT})"
    
    return True, "All auto-verification criteria met"

async def auto_verify_user(user_id, uid, file_id, context):
    """Auto-verify a user and update their status"""
    try:
        # Insert verification request with approved status
        if BotConfig.DATABASE_TYPE == 'postgresql':
            query = '''
                INSERT INTO verification_requests (user_id, uid, screenshot_file_id, status, auto_verified, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
            '''
        else:
            query = '''
                INSERT INTO verification_requests (user_id, uid, screenshot_file_id, status, auto_verified, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            '''
        
        db_manager.execute_query(query, (
            user_id, uid, file_id, 'approved', True, datetime.now()
        ))
        
        # Update user data
        await update_user_data(user_id, {
            'deposit_confirmed': True,
            'verification_status': 'approved'
        })
        
        # Send success message to user
        success_message = f"""🎉 **Verification Successful!**

✅ Your account has been **automatically verified**!
✅ UID: `{uid}`
✅ Status: **Approved**

🚀 **You now have access to:**
• Premium Signals: {PREMIUM_GROUP_LINK}
• VIP Trading Group: {PREMIUM_GROUP_LINK}
• Exclusive market insights
• Priority support

💡 **Next Steps:**
1. Join our premium channels
2. Start receiving VIP signals
3. Begin your trading journey

📈 **Happy Trading!**"""
        
        keyboard = [
            [InlineKeyboardButton("🚀 Start Trading", url=BotConfig.BROKER_LINK)],
            [InlineKeyboardButton("💬 Contact Support", callback_data="support")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
        ]
        
        await context.bot.send_message(
            chat_id=user_id,
            text=success_message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        
        logger.info(f"Auto-verified user {user_id} with UID {uid}")
        return True
        
    except Exception as e:
        logger.error(f"Error auto-verifying user {user_id}: {e}")
        return False

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
                welcome_text = f"""Heyy {user.first_name or "there"}
Welcome to OPTRIXTRADES
you're one step away from unlocking high-accuracy trading signals, expert strategies, and real trader bonuses, completely free.

Here's what you get as a member:
✅ Daily VIP trading signals
✅ Strategy sessions from 6-figure traders
✅ Access to our private trader community
✅ Exclusive signup bonuses (up to $500)
✅ Automated trading bot – trade while you sleep

👇 Tap below to activate your free VIP access and get started."""
                reply_markup = InlineKeyboardMarkup([
                    [InlineKeyboardButton("➡️ Get Free VIP Access", callback_data="get_vip_access")],
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
                follow_up = """"""
                
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
                text = f"""To activate your free access and join our VIP Signal Channel, follow these steps:

1️⃣Click the link below to register with our official broker partner
[{self.broker_link}]
2️⃣Deposit $20 or more
3️⃣Send your proof of deposit

once your proof have been confirmed your access will be unlocked immediately

The more you deposit, the more powerful your AI access:
✅ $100+ → Full access to OPTRIX Web AI Portal, Live Signals & AI tools.
✅ $500+ → Includes:
— All available signal alert options
— VIP telegram group
— Access to private sessions and risk management blueprint
— OPTRIX AI Auto-Trading (trades for you automatically)

Why is it free?
We earn a small commission from the broker through your trading volume, not your money. So we are more focused on your success, the more you win, the better for both of us. ✅

Want to unlock even higher-tier bonuses or full bot access?
Send \"UPGRADE\""""
                keyboard = [
                    [InlineKeyboardButton("➡️ I've Registered", callback_data="get_vip_access")],
                    [InlineKeyboardButton("➡️ Need help signing up", callback_data="help_signup")],
                    [InlineKeyboardButton("➡️ Need support making a deposit", callback_data="help_deposit")],
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
            
            text = """Send in your uid and deposit screenshot to gain access optrixtrades trades premium signal channel.

BONUS: We're hosting a live session soon with exclusive insights. Stay tuned. Get an early access now into our premium channel only limited slots are available."""
            
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
            
            # Get user data to retrieve UID
            user_data = await get_user_data(user_id)
            uid = user_data.get('uid', 'Not provided') if user_data else 'Not provided'
            
            # Store photo file_id for verification
            await update_user_data(user_id, {
                "screenshot_id": photo.file_id,
                "verification_pending": True,
                "verification_date": datetime.now(pytz.utc).isoformat()
            })
            
            # Check if user should be auto-verified
            can_auto_verify, auto_verify_reason = should_auto_verify(user_id, uid)
            
            if can_auto_verify:
                # Attempt auto-verification
                try:
                    success = await auto_verify_user(user_id, uid, photo.file_id, context)
                    if success:
                        # Auto-verification completed successfully
                        return ConversationHandler.END
                    else:
                        logger.error(f"Auto-verification failed for user {user_id}, falling back to manual review")
                except Exception as e:
                    logger.error(f"Auto-verification error for user {user_id}: {e}")
            
            # Manual verification process
            # Notify admin
            if self.admin_user_id:
                try:
                    admin_notification = f"""🔔 **NEW VERIFICATION REQUEST**

👤 **User:** {update.effective_user.first_name}
🆔 **User ID:** {user_id}
💳 **UID:** {uid}
📸 **Screenshot:** Uploaded
⏰ **Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Use /verify {user_id} to approve or /reject {user_id} to reject."""
                    
                    await context.bot.send_photo(
                        chat_id=self.admin_user_id,
                        photo=photo.file_id,
                        caption=admin_notification,
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"Couldn't notify admin: {e}")
            
            # Send confirmation to user with appropriate buttons
            if can_auto_verify:
                confirmation_text = f"""✅ **Screenshot Received Successfully!**

📋 **Verification Details:**
• UID: {uid}
• Screenshot: Uploaded
• Status: Under Review (Manual)
• Reason: Auto-verification temporarily unavailable

⏳ Your verification request has been submitted to our admin team. You'll receive a notification once your deposit is verified.

🕐 **Processing Time:** Usually within 2-4 hours

Thank you for your patience! 🙏"""
            else:
                confirmation_text = f"""✅ **Screenshot Received Successfully!**

📋 **Verification Details:**
• UID: {uid}
• Screenshot: Uploaded
• Status: Under Review (Manual)
• Reason: {auto_verify_reason}

⏳ Your verification request has been submitted to our admin team. You'll receive a notification once your deposit is verified.

🕐 **Processing Time:** Usually within 2-4 hours

Thank you for your patience! 🙏"""
            
            # Add appropriate buttons
            keyboard = [
                [InlineKeyboardButton("📊 My Account", callback_data="my_account")],
                [InlineKeyboardButton("⬅️ Main Menu", callback_data="main_menu")]
            ]
            
            await self._send_persistent_message(
                chat_id=user_id,
                text=confirmation_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
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

A human support will be needed here for higher-tier bonuses or full bot access.

Our team will help you unlock:
🚀 Advanced AI trading algorithms
💎 VIP-only trading signals  
📈 Personal trading mentor
💰 Higher deposit bonuses

Contact: @{self.admin_username}

You will be contacted shortly by our support team."""
            
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
                await self.main_menu_callback(update, context)
            elif data == "menu":
                await self.menu_command(update, context)
            elif data == "account_menu":
                await self.account_menu_callback(update, context)
            elif data == "help_menu":
                await self.help_menu_callback(update, context)
            elif data == "notification_settings":
                await self.notification_settings_callback(update, context)
            elif data == "start_trading":
                await self.start_trading_callback(update, context)
            elif data == "contact_support":
                await self.contact_support(update, context)
            elif data == "verification_help":
                await self.verification_help(update, context)
            elif data == "help_signup":
                await self.help_signup(update, context)
            elif data == "help_deposit":
                await self.help_deposit(update, context)
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
                # Valid UID format - Fixed function call
                await update_user_data(user_id, uid=uid)
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
            
            # Check if user has UID
            uid = user_data.get('uid') if isinstance(user_data, dict) else (user_data[6] if len(user_data) > 6 and user_data[6] else None)
            
            if uid:
                # User has UID, process as verification screenshot
                await self.handle_screenshot_upload(update, context)
            else:
                # User doesn't have UID, prompt them to provide it first
                await update.message.reply_text(
                    "📸 Photo received! To proceed with verification, please provide your Broker UID first.",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔓 Start Verification", callback_data="start_verification")],
                        [InlineKeyboardButton("📋 Main Menu", callback_data="main_menu")]
                    ])
                )
            
        except Exception as e:
            logger.error(f"Error in handle_photo: {e}")

    async def admin_verify_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Admin command to verify a user"""
        try:
            user_id = update.effective_user.id
            
            if not await self._is_admin(user_id):
                await update.message.reply_text("⛔ Unauthorized")
                return
            
            if not context.args:
                await update.message.reply_text("Usage: /verify <user_id>")
                return
            
            target_user_id = int(context.args[0])
            
            # Update user verification status
            await update_user_data(target_user_id, {
                'verified': True,
                'verification_status': 'approved',
                'verification_date': datetime.now().isoformat()
            })
            
            # Update verification request status
            if BotConfig.DATABASE_TYPE == 'postgresql':
                query = "UPDATE verification_requests SET status = %s WHERE user_id = %s"
            else:
                query = "UPDATE verification_requests SET status = ? WHERE user_id = ?"
            
            db_manager.execute_query(query, ('approved', target_user_id))
            
            # Notify user of approval
            success_message = f"""🎉 **Verification Approved!**

✅ Your account has been **manually verified** by our admin team!
✅ Status: **Approved**

🚀 **You now have access to:**
• Premium Signals: {PREMIUM_GROUP_LINK}
• VIP Trading Group: {PREMIUM_GROUP_LINK}
• Exclusive market insights
• Priority support

💡 **Next Steps:**
1. Join our premium channels
2. Start receiving VIP signals
3. Begin your trading journey

📈 **Happy Trading!**"""
            
            keyboard = [
                [InlineKeyboardButton("🚀 Join Premium Group", url=PREMIUM_GROUP_LINK)],
                [InlineKeyboardButton("💬 Contact Support", callback_data="support")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
            ]
            
            await context.bot.send_message(
                chat_id=target_user_id,
                text=success_message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            
            await update.message.reply_text(f"✅ User {target_user_id} has been verified and notified.")
            
            # Log the action
            await log_interaction(user_id, "admin_verify", f"Verified user {target_user_id}")
            
        except Exception as e:
            logger.error(f"Error in admin_verify_command: {e}")
            await update.message.reply_text("❌ Error verifying user.")
    
    async def admin_reject_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Admin command to reject a user verification"""
        try:
            user_id = update.effective_user.id
            
            if not await self._is_admin(user_id):
                await update.message.reply_text("⛔ Unauthorized")
                return
            
            if not context.args:
                await update.message.reply_text("Usage: /reject <user_id> [reason]")
                return
            
            target_user_id = int(context.args[0])
            reason = " ".join(context.args[1:]) if len(context.args) > 1 else "Verification requirements not met"
            
            # Update verification request status
            if BotConfig.DATABASE_TYPE == 'postgresql':
                query = "UPDATE verification_requests SET status = %s WHERE user_id = %s"
            else:
                query = "UPDATE verification_requests SET status = ? WHERE user_id = ?"
            
            db_manager.execute_query(query, ('rejected', target_user_id))
            
            # Notify user of rejection
            rejection_message = f"""❌ **Verification Rejected**

📋 **Reason:** {reason}

🔄 **What you can do:**
• Review our verification requirements
• Ensure your deposit meets minimum amount
• Submit a clear screenshot of your deposit
• Contact support if you need help

💡 **Need assistance?** Our support team is here to help!"""
            
            keyboard = [
                [InlineKeyboardButton("🔄 Try Again", callback_data="get_vip_access")],
                [InlineKeyboardButton("💬 Contact Support", callback_data="support")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
            ]
            
            await context.bot.send_message(
                chat_id=target_user_id,
                text=rejection_message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            
            await update.message.reply_text(f"❌ User {target_user_id} verification has been rejected and user notified.")
            
            # Log the action
            await log_interaction(user_id, "admin_reject", f"Rejected user {target_user_id}: {reason}")
            
        except Exception as e:
            logger.error(f"Error in admin_reject_command: {e}")
            await update.message.reply_text("❌ Error rejecting user verification.")

    async def admin_queue_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Admin command to view pending verification queue"""
        try:
            user_id = update.effective_user.id
            
            if not await self._is_admin(user_id):
                await update.message.reply_text("⛔ Unauthorized")
                return
            
            # Get pending verification requests
            pending_requests = await get_pending_verifications()
            
            if not pending_requests:
                await update.message.reply_text("✅ No pending verification requests.")
                return
            
            queue_text = "📋 **Pending Verification Queue**\n\n"
            
            for i, request in enumerate(pending_requests[:10], 1):  # Limit to 10 requests
                user_data = await get_user_data(request['user_id'])
                username = user_data.get('username', 'N/A') if user_data else 'N/A'
                first_name = user_data.get('first_name', 'Unknown') if user_data else 'Unknown'
                
                queue_text += f"""{i}. **{first_name}** (@{username})
   • User ID: `{request['user_id']}`
   • UID: `{request.get('uid', 'N/A')}`
   • Submitted: {request.get('created_at', 'Unknown')}
   • Commands: `/verify {request['user_id']}` | `/reject {request['user_id']}`

"""
            
            if len(pending_requests) > 10:
                queue_text += f"\n... and {len(pending_requests) - 10} more requests."
            
            await update.message.reply_text(queue_text, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error in admin_queue_command: {e}")
            await update.message.reply_text("❌ Error retrieving verification queue.")

    async def admin_broadcast_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Admin command to broadcast message to all users"""
        try:
            user_id = update.effective_user.id
            
            if not await self._is_admin(user_id):
                await update.message.reply_text("⛔ Unauthorized")
                return
            
            if not context.args:
                await update.message.reply_text("Usage: /broadcast <message>")
                return
            
            broadcast_message = " ".join(context.args)
            
            # Get all users
            all_users = await get_all_users()
            
            if not all_users:
                await update.message.reply_text("❌ No users found to broadcast to.")
                return
            
            # Create broadcast record
            broadcast_id = f"broadcast_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # Send broadcast message to all users
            successful_sends = 0
            failed_sends = 0
            
            for user in all_users:
                try:
                    target_user_id = user.get('user_id') if isinstance(user, dict) else user[0]
                    
                    await context.bot.send_message(
                        chat_id=target_user_id,
                        text=f"📢 **Admin Broadcast**\n\n{broadcast_message}",
                        parse_mode='Markdown'
                    )
                    successful_sends += 1
                    
                except Exception as send_error:
                    logger.error(f"Failed to send broadcast to user {target_user_id}: {send_error}")
                    failed_sends += 1
            
            # Send delivery confirmation to admin
            confirmation_text = f"""📢 **Broadcast Complete**

✅ Successfully sent: {successful_sends}
❌ Failed to send: {failed_sends}
📊 Total users: {len(all_users)}

📝 **Message:** {broadcast_message[:100]}{'...' if len(broadcast_message) > 100 else ''}"""
            
            await update.message.reply_text(confirmation_text, parse_mode='Markdown')
            
            # Log the broadcast
            await log_interaction(user_id, "admin_broadcast", f"Broadcast to {successful_sends} users")
            
        except Exception as e:
            logger.error(f"Error in admin_broadcast_command: {e}")
            await update.message.reply_text("❌ Error sending broadcast message.")

    async def menu_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /menu command"""
        try:
            user_id = update.effective_user.id
            await log_interaction(user_id, "menu_command")
            
            user_data = await get_user_data(user_id)
            is_verified = user_data.get('verified', False) if user_data else False
            
            menu_text = "🏠 **Main Menu**\n\nChoose an option below:"
            
            if is_verified:
                keyboard = [
                    [InlineKeyboardButton("📊 Account Status", callback_data="account_menu")],
                    [InlineKeyboardButton("🚀 Start Trading", callback_data="start_trading")],
                    [InlineKeyboardButton("❓ Help", callback_data="help_menu")],
                    [InlineKeyboardButton("🔔 Notifications", callback_data="notification_settings")],
                    [InlineKeyboardButton("💬 Contact Support", callback_data="contact_support")]
                ]
            else:
                keyboard = [
                    [InlineKeyboardButton("📊 Account Status", callback_data="account_menu")],
                    [InlineKeyboardButton("🔓 Get Verified", callback_data="get_vip_access")],
                    [InlineKeyboardButton("❓ Help", callback_data="help_menu")],
                    [InlineKeyboardButton("🔔 Notifications", callback_data="notification_settings")],
                    [InlineKeyboardButton("💬 Contact Support", callback_data="contact_support")]
                ]
            
            await self._send_persistent_message(
                chat_id=user_id,
                text=menu_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Error in menu_command: {e}")

    async def main_menu_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle main menu callback"""
        try:
            query = update.callback_query
            await query.answer()
            
            user_id = query.from_user.id
            await log_interaction(user_id, "main_menu_callback")
            
            user_data = await get_user_data(user_id)
            is_verified = user_data.get('verified', False) if user_data else False
            
            menu_text = "🏠 **Main Menu**\n\nChoose an option below:"
            
            if is_verified:
                keyboard = [
                    [InlineKeyboardButton("📊 Account Status", callback_data="account_menu")],
                    [InlineKeyboardButton("🚀 Start Trading", callback_data="start_trading")],
                    [InlineKeyboardButton("🚀 Join Premium Group", url=PREMIUM_GROUP_LINK)],
                    [InlineKeyboardButton("❓ Help", callback_data="help_menu")],
                    [InlineKeyboardButton("🔔 Notifications", callback_data="notification_settings")],
                    [InlineKeyboardButton("💬 Contact Support", callback_data="contact_support")]
                ]
            else:
                keyboard = [
                    [InlineKeyboardButton("📊 Account Status", callback_data="account_menu")],
                    [InlineKeyboardButton("🔓 Get Verified", callback_data="get_vip_access")],
                    [InlineKeyboardButton("❓ Help", callback_data="help_menu")],
                    [InlineKeyboardButton("🔔 Notifications", callback_data="notification_settings")],
                    [InlineKeyboardButton("💬 Contact Support", callback_data="contact_support")]
                ]
            
            await self._send_persistent_message(
                chat_id=user_id,
                text=menu_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Error in main_menu_callback: {e}")

    async def account_menu_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle account menu callback"""
        try:
            query = update.callback_query
            await query.answer()
            
            user_id = query.from_user.id
            await log_interaction(user_id, "account_menu_callback")
            
            user_data = await get_user_data(user_id)
            
            if user_data:
                name = user_data.get('first_name', 'Unknown')
                username = user_data.get('username', 'Not set')
                uid = user_data.get('uid', 'Not provided')
                is_verified = user_data.get('verified', False)
                status = "✅ Verified" if is_verified else "❌ Not Verified"
                current_flow = user_data.get('current_flow', 'main_menu')
                
                account_text = f"""📊 **Account Information**

👤 **Name:** {name}
🏷️ **Username:** @{username}
🆔 **User ID:** `{user_id}`
💳 **UID:** `{uid}`
🔒 **Status:** {status}
📍 **Current Flow:** {current_flow}

💼 **Broker Link:** [Click Here]({self.broker_link})"""
            else:
                account_text = "❌ **No account information found**\n\nPlease complete registration to create your account."
            
            keyboard = [
                [InlineKeyboardButton("🔄 Refresh Status", callback_data="account_menu")]
            ]
            
            # Add verification button if not verified
            if not user_data or not user_data.get('verified', False):
                keyboard.append([InlineKeyboardButton("🔓 Complete Verification", callback_data="get_vip_access")])
            
            keyboard.append([InlineKeyboardButton("⬅️ Back to Menu", callback_data="main_menu")])
            
            await self._send_persistent_message(
                chat_id=user_id,
                text=account_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown',
                disable_web_page_preview=True
            )
            
        except Exception as e:
            logger.error(f"Error in account_menu_callback: {e}")

    async def help_menu_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle help menu callback"""
        try:
            query = update.callback_query
            await query.answer()
            
            user_id = query.from_user.id
            await log_interaction(user_id, "help_menu_callback")
            
            help_text = """❓ **Help & Support**

Choose a topic for assistance:"""
            
            keyboard = [
                [InlineKeyboardButton("🔍 Verification Help", callback_data="verification_help")],
                [InlineKeyboardButton("💰 Deposit Guide", callback_data="help_deposit")],
                [InlineKeyboardButton("📝 Registration Guide", callback_data="help_signup")],
                [InlineKeyboardButton("💬 Contact Support", callback_data="contact_support")],
                [InlineKeyboardButton("⬅️ Back to Menu", callback_data="main_menu")]
            ]
            
            await self._send_persistent_message(
                chat_id=user_id,
                text=help_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Error in help_menu_callback: {e}")

    async def notification_settings_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle notification settings callback"""
        try:
            query = update.callback_query
            await query.answer()
            
            user_id = query.from_user.id
            await log_interaction(user_id, "notification_settings_callback")
            
            settings_text = """🔔 **Notification Settings**

📊 **Current Settings:**
• Trading Signals: ✅ Enabled
• Account Updates: ✅ Enabled
• Admin Messages: ✅ Enabled
• System Alerts: ✅ Enabled

⚙️ **Note:** Notification customization is under development. All notifications are currently enabled by default."""
            
            keyboard = [
                [InlineKeyboardButton("⬅️ Back to Menu", callback_data="main_menu")]
            ]
            
            await self._send_persistent_message(
                chat_id=user_id,
                text=settings_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Error in notification_settings_callback: {e}")

    async def start_trading_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle start trading callback"""
        try:
            query = update.callback_query
            await query.answer()
            
            user_id = query.from_user.id
            await log_interaction(user_id, "start_trading_callback")
            
            user_data = await get_user_data(user_id)
            is_verified = user_data.get('verified', False) if user_data else False
            
            if is_verified:
                trading_text = f"""🚀 **Start Trading**

🎯 **Ready to Trade?**
You're all set to start your trading journey!

📈 **Access Your Tools:**
• Join our Premium Group for live signals
• Use our recommended broker platform
• Follow our expert analysis

💡 **Trading Tips:**
• Start with small amounts
• Follow risk management rules
• Stay updated with market news

🔗 **Quick Links:**"""
                
                keyboard = [
                    [InlineKeyboardButton("🚀 Join Premium Group", url=PREMIUM_GROUP_LINK)],
                    [InlineKeyboardButton("💼 Open Broker Account", url=self.broker_link)],
                    [InlineKeyboardButton("📊 Account Status", callback_data="account_menu")],
                    [InlineKeyboardButton("⬅️ Back to Menu", callback_data="main_menu")]
                ]
            else:
                trading_text = """🔒 **Verification Required**

To start trading, you need to complete verification first.

✅ **Complete these steps:**
1. Get verified with your broker UID
2. Upload deposit screenshot
3. Wait for admin approval
4. Access premium trading features"""
                
                keyboard = [
                    [InlineKeyboardButton("🔓 Get Verified", callback_data="get_vip_access")],
                    [InlineKeyboardButton("❓ How It Works", callback_data="how_it_works")],
                    [InlineKeyboardButton("⬅️ Back to Menu", callback_data="main_menu")]
                ]
            
            await self._send_persistent_message(
                chat_id=user_id,
                text=trading_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown',
                disable_web_page_preview=True
            )
            
        except Exception as e:
            logger.error(f"Error in start_trading_callback: {e}")

    async def contact_support(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle contact support callback"""
        try:
            if update.callback_query:
                query = update.callback_query
                await query.answer()
                user_id = query.from_user.id
            else:
                user_id = update.effective_user.id
            
            await log_interaction(user_id, "contact_support")
            
            support_text = f"""💬 **Contact Support**

🆘 **Need Help?**
Our support team is here to assist you!

📞 **Contact Information:**
👤 **Admin:** @{self.admin_username}
⏰ **Hours:** 24/7 Support Available
📧 **Response Time:** Usually within 1-2 hours

❓ **Common Issues:**
• Verification problems
• Account access issues
• Trading questions
• Technical support

💡 **Tip:** Please include your User ID (`{user_id}`) when contacting support for faster assistance."""
            
            keyboard = [
                [InlineKeyboardButton("💬 Message Admin", url=f"https://t.me/{self.admin_username}")],
                [InlineKeyboardButton("❓ Help Menu", callback_data="help_menu")],
                [InlineKeyboardButton("⬅️ Back to Menu", callback_data="main_menu")]
            ]
            
            await self._send_persistent_message(
                chat_id=user_id,
                text=support_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Error in contact_support: {e}")

    async def verification_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle verification help callback"""
        try:
            query = update.callback_query
            await query.answer()
            
            user_id = query.from_user.id
            await log_interaction(user_id, "verification_help")
            
            help_text = """🔍 **Verification Help**

❓ **Frequently Asked Questions:**

**Q: What is UID?**
A: UID is your unique broker account identifier (8-20 characters)

**Q: Where do I find my UID?**
A: In your broker account → Profile → Account ID/UID

**Q: What screenshot do I need?**
A: A clear image of your deposit confirmation showing amount and date

**Q: How long does verification take?**
A: Usually 2-4 hours during business hours

**Q: What's the minimum deposit?**
A: $20 minimum (recommended $100+ for full access)

💡 **Tips for Faster Verification:**
• Use clear, high-quality screenshots
• Ensure UID is clearly visible
• Include deposit amount and date
• Contact support if you have issues"""
            
            keyboard = [
                [InlineKeyboardButton("🔓 Start Verification", callback_data="get_vip_access")],
                [InlineKeyboardButton("💬 Contact Support", callback_data="contact_support")],
                [InlineKeyboardButton("⬅️ Back to Help", callback_data="help_menu")]
            ]
            
            await self._send_persistent_message(
                chat_id=user_id,
                text=help_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Error in verification_help: {e}")

    async def help_signup(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle signup help callback"""
        try:
            query = update.callback_query
            await query.answer()
            
            user_id = query.from_user.id
            await log_interaction(user_id, "help_signup")
            
            signup_text = f"""📝 **Registration Guide**

🎯 **Step-by-Step Registration:**

**Step 1: Create Broker Account**
• Click: [Register Here]({self.broker_link})
• Fill in your personal details
• Verify your email address
• Complete account setup

**Step 2: Make Initial Deposit**
• Minimum: $20 (recommended $100+)
• Choose your preferred payment method
• Complete the deposit process
• Save the confirmation screenshot

**Step 3: Get Your UID**
• Login to your broker account
• Go to Profile/Account Settings
• Find your Account ID/UID
• Copy the alphanumeric code

**Step 4: Verify with Bot**
• Send your UID to this bot
• Upload deposit screenshot
• Wait for admin approval

✅ **You're all set!**"""
            
            keyboard = [
                [InlineKeyboardButton("💼 Register Now", url=self.broker_link)],
                [InlineKeyboardButton("🔓 Start Verification", callback_data="get_vip_access")],
                [InlineKeyboardButton("⬅️ Back to Help", callback_data="help_menu")]
            ]
            
            await self._send_persistent_message(
                chat_id=user_id,
                text=signup_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown',
                disable_web_page_preview=True
            )
            
        except Exception as e:
            logger.error(f"Error in help_signup: {e}")

    async def help_deposit(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle deposit help callback"""
        try:
            query = update.callback_query
            await query.answer()
            
            user_id = query.from_user.id
            await log_interaction(user_id, "help_deposit")
            
            deposit_text = """💰 **Deposit Guide**

💳 **How to Make a Deposit:**

**Step 1: Login to Broker**
• Access your broker account
• Navigate to 'Deposit' or 'Fund Account'

**Step 2: Choose Payment Method**
• Credit/Debit Card
• Bank Transfer
• E-wallets (Skrill, Neteller)
• Cryptocurrency

**Step 3: Enter Amount**
• Minimum: $20
• Recommended: $100+ for full access
• Check for any bonus offers

**Step 4: Complete Payment**
• Follow payment instructions
• Wait for confirmation
• Take screenshot of confirmation

**Step 5: Verify Deposit**
• Send screenshot to this bot
• Include your UID
• Wait for verification

⚠️ **Important Notes:**
• Keep all transaction records
• Use the same name as your account
• Contact support if deposit fails"""
            
            keyboard = [
                [InlineKeyboardButton("💼 Access Broker", url=self.broker_link)],
                [InlineKeyboardButton("🔓 Verify Deposit", callback_data="get_vip_access")],
                [InlineKeyboardButton("⬅️ Back to Help", callback_data="help_menu")]
            ]
            
            await self._send_persistent_message(
                chat_id=user_id,
                text=deposit_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown',
                disable_web_page_preview=True
            )
            
        except Exception as e:
            logger.error(f"Error in help_deposit: {e}")

    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle document uploads from users"""
        try:
            user_id = update.effective_user.id
            document = update.message.document
            
            # Check if user exists
            user_data = await get_user_data(user_id)
            if not user_data:
                await update.message.reply_text("Please start with /start first.")
                return
            
            await log_interaction(user_id, "document_upload", f"File: {document.file_name}")
            
            # Check file type
            allowed_types = ['pdf', 'jpg', 'jpeg', 'png']
            file_extension = document.file_name.lower().split('.')[-1] if '.' in document.file_name else ''
            
            if file_extension not in allowed_types:
                await update.message.reply_text(
                    "❌ **Invalid file type**\n\nPlease upload:\n• PDF documents\n• Image files (JPG, PNG)\n• Screenshots of your deposit",
                    parse_mode='Markdown'
                )
                return
            
            # Check if user has UID
            uid = user_data.get('uid') if isinstance(user_data, dict) else (user_data[6] if len(user_data) > 6 and user_data[6] else None)
            
            if not uid:
                await update.message.reply_text(
                    "📄 Document received! But I need your UID first.\n\nPlease provide your broker UID, then upload your document again.",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔓 Start Verification", callback_data="start_verification")]
                    ])
                )
                return
            
            # Process as verification document
            try:
                from database.connection import create_verification_request
                await create_verification_request(user_id, uid, document.file_id)
                
                confirmation_text = f"""✅ **Document Received Successfully!**

📋 **Verification Details:**
• UID: {uid}
• Document: {document.file_name}
• File Type: {file_extension.upper()}
• Status: Under Review

⏳ Your verification request has been submitted to our admin team. You'll receive a notification once your deposit is verified.

🕐 **Processing Time:** Usually within 2-4 hours

📊 **What's Next?**
• Our team will review your document
• You'll get notified of the decision
• Once approved, you'll have full access

Thank you for your patience! 🙏"""
                
                keyboard = [
                    [InlineKeyboardButton("📊 Check Status", callback_data="account_menu")],
                    [InlineKeyboardButton("💬 Contact Support", callback_data="contact_support")],
                    [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
                ]
                
                await update.message.reply_text(
                    confirmation_text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode='Markdown'
                )
                
                # Notify admin
                if self.admin_user_id:
                    admin_notification = f"""📄 **New Document Verification Request**

👤 **User:** {update.effective_user.first_name or 'Unknown'}
🆔 **User ID:** {user_id}
🔑 **UID:** {uid}
📄 **Document:** {document.file_name}
📁 **Type:** {file_extension.upper()}

**Admin Actions:**
• /verify {user_id} - Approve
• /reject {user_id} - Reject
• /queue - View all pending"""
                    
                    try:
                        await context.bot.send_document(
                            chat_id=self.admin_user_id,
                            document=document.file_id,
                            caption=admin_notification,
                            parse_mode='Markdown'
                        )
                    except Exception as admin_error:
                        logger.error(f"Failed to notify admin about document: {admin_error}")
                        
            except Exception as db_error:
                logger.error(f"Database error in document verification: {db_error}")
                await update.message.reply_text(
                    "❌ There was an error processing your document. Please try again or contact support."
                )
                
        except Exception as e:
            logger.error(f"Error in handle_document: {e}")
            await update.message.reply_text(
                "❌ There was an error processing your document. Please try again."
            )

    async def help_signup(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle help signup callback"""
        try:
            query = update.callback_query
            await query.answer()
            
            user_id = query.from_user.id
            await log_interaction(user_id, "help_signup")
            
            help_text = f"""📹 **SIGNUP HELP**

Step-by-step registration guide:

1️⃣ Click this link: {BotConfig.BROKER_LINK}
2️⃣ Fill in your personal details
3️⃣ Verify your email address
4️⃣ Complete account verification
5️⃣ Make your first deposit ($20 minimum)

📝 **Important Notes:**
• Use real information for verification
• Keep your login details safe
• Contact support if you need help

💡 **Need more help?** Contact our support team!"""
            
            keyboard = [
                [InlineKeyboardButton("🔗 Register Now", url=BotConfig.BROKER_LINK)],
                [InlineKeyboardButton("💬 Contact Support", callback_data="contact_support")],
                [InlineKeyboardButton("🔙 Back", callback_data="get_vip_access")]
            ]
            
            await query.edit_message_text(
                text=help_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Error in help_signup: {e}")
    
    async def help_deposit(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle help deposit callback"""
        try:
            query = update.callback_query
            await query.answer()
            
            user_id = query.from_user.id
            await log_interaction(user_id, "help_deposit")
            
            help_text = f"""💳 **DEPOSIT HELP**

How to make your first deposit:

1️⃣ Log into your broker account
2️⃣ Go to "Deposit" section
3️⃣ Choose your payment method
4️⃣ Enter deposit amount ($20 minimum)
5️⃣ Complete the payment
6️⃣ Take a screenshot of confirmation

📱 **Payment Methods:**
• Credit/Debit Cards
• Bank Transfer
• E-wallets
• Crypto (if available)

⚠️ **Important:** Always take a screenshot of your deposit confirmation!

💡 **Need assistance?** Our support team is here to help!"""
            
            keyboard = [
                [InlineKeyboardButton("🔗 Go to Broker", url=BotConfig.BROKER_LINK)],
                [InlineKeyboardButton("💬 Contact Support", callback_data="contact_support")],
                [InlineKeyboardButton("🔙 Back", callback_data="get_vip_access")]
            ]
            
            await query.edit_message_text(
                text=help_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"Error in help_deposit: {e}")

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
        
        # User commands
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("vipsignals", self.vip_signals_command))
        self.application.add_handler(CommandHandler("myaccount", self.my_account_command))
        self.application.add_handler(CommandHandler("support", self.support_command))
        self.application.add_handler(CommandHandler("stats", self.stats_command))
        self.application.add_handler(CommandHandler("howitworks", self.how_it_works))
        self.application.add_handler(CommandHandler("menu", self.menu_command))
        
        # Admin commands
        self.application.add_handler(CommandHandler("admin_verify", self.admin_verify_command))
        self.application.add_handler(CommandHandler("admin_reject", self.admin_reject_command))
        self.application.add_handler(CommandHandler("admin_queue", self.admin_queue_command))
        self.application.add_handler(CommandHandler("admin_broadcast", self.admin_broadcast_command))
        self.application.add_handler(CommandHandler("broadcast", self.handle_broadcast))
        self.application.add_handler(CommandHandler("lookup", self.handle_user_lookup))
        
        self.application.add_handler(CallbackQueryHandler(self.button_callback))
        self.application.add_handler(verification_conv)
        
        # Add text, photo, and document handlers
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text_message))
        self.application.add_handler(MessageHandler(filters.PHOTO, self.handle_photo))
        self.application.add_handler(MessageHandler(filters.Document.ALL, self.handle_document))
        
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