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

# Standalone utility functions
def init_database():
    """Initialize database using the database manager"""
    from database.db_manager import db_manager
    db_manager.init_database()

def is_admin(user_id):
    """Check if user is admin"""
    return str(user_id) == str(BotConfig.ADMIN_USER_ID)

async def get_my_id_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    username = user.username or "No username"
    first_name = user.first_name or "Unknown"
    
    id_info_text = f"""🆔 **Your Telegram Information:**

👤 **Name:** {first_name}
📱 **Username:** @{username}
🔢 **User ID:** `{user_id}`

**To set yourself as admin:**
1. Copy your User ID: `{user_id}`
2. Update the .env file: `ADMIN_USER_ID={user_id}`
3. Restart the bot

**Current Admin Status:** {'✅ You are admin' if is_admin(user_id) else '❌ Not admin'}"""
    
    await update.message.reply_text(id_info_text, parse_mode='Markdown')
    
    # Log the ID request
    from database.db_manager import db_manager
    await db_manager.log_chat_message(user_id, "command", "/getmyid", {
        "username": username,
        "first_name": first_name,
        "current_admin_status": is_admin(user_id)
    })
    
    await db_manager.log_chat_message(user_id, "bot_response", id_info_text, {
        "action": "user_id_info",
        "user_id_revealed": user_id
    })

async def admin_chat_history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command to view chat history for a specific user"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ You don't have permission to use this command.")
        return
    
    # Get target user ID
    if not context.args:
        await update.message.reply_text(
            "Usage: /chathistory <user_id> [limit]\n\n"
            "Example: /chathistory 123456789 50"
        )
        return
    
    try:
        target_user_id = int(context.args[0])
        limit = int(context.args[1]) if len(context.args) > 1 else 20
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID or limit. Please use numbers only.")
        return
    
    # Get chat history
    from database.db_manager import db_manager
    chat_history = await db_manager.get_chat_history(target_user_id, limit)
    
    if not chat_history:
        await update.message.reply_text(f"No chat history found for user {target_user_id}.")
        return
    
    # Format chat history
    history_text = f"📋 Chat History for User {target_user_id}\n"
    history_text += f"📊 Showing last {len(chat_history)} messages\n\n"
    
    for entry in chat_history:
        timestamp = entry[2]  # created_at
        message_type = entry[3]  # message_type
        content = entry[4]  # content
        
        if message_type == "user_message":
            history_text += f"👤 {timestamp}: {content}\n"
        elif message_type == "bot_response":
            history_text += f"🤖 {timestamp}: {content}\n"
        elif message_type == "command":
            history_text += f"⚡ {timestamp}: {content}\n"
        elif message_type == "user_action":
            history_text += f"🔘 {timestamp}: {content}\n"
        elif message_type == "broadcast":
            history_text += f"📢 {timestamp}: {content}\n"
        else:
            history_text += f"📝 {timestamp}: {content}\n"
        
        history_text += "\n"
    
    # Split long messages
    if len(history_text) > 4000:
        chunks = [history_text[i:i+4000] for i in range(0, len(history_text), 4000)]
        for i, chunk in enumerate(chunks):
            if i == 0:
                await update.message.reply_text(chunk)
            else:
                await update.message.reply_text(f"📋 Chat History (Part {i+1})\n\n{chunk}")
    else:
        await update.message.reply_text(history_text)

async def get_all_active_users():
    """Get all active users for broadcasting"""
    if BotConfig.DATABASE_TYPE == 'postgresql':
        query = '''
            SELECT user_id, first_name FROM users 
            WHERE is_active = %s
        '''
    else:
        query = '''
            SELECT user_id, first_name FROM users 
            WHERE is_active = ?
        '''
    
    result = await db_manager.execute_query(query, (True,), fetch=True)
    return [(user['user_id'], user['first_name']) for user in result] if result else []

async def create_verification_request(user_id, uid, screenshot_file_id):
    """Create a new verification request"""
    if BotConfig.DATABASE_TYPE == 'postgresql':
        query = '''
            INSERT INTO verification_requests (user_id, uid, screenshot_file_id)
            VALUES (%s, %s, %s) RETURNING id
        '''
        result = await db_manager.execute_query(query, (user_id, uid, screenshot_file_id), fetch=True)
        return result[0]['id'] if result else None
    else:
        query = '''
            INSERT INTO verification_requests (user_id, uid, screenshot_file_id)
            VALUES (?, ?, ?)
        '''
        await db_manager.execute_query(query, (user_id, uid, screenshot_file_id))
        return None

async def update_verification_status(request_id, status, admin_response=""):
    """Update verification request status"""
    if BotConfig.DATABASE_TYPE == 'postgresql':
        query = '''
            UPDATE verification_requests 
            SET status = %s, admin_response = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        '''
    else:
        query = '''
            UPDATE verification_requests 
            SET status = ?, admin_response = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        '''
    
    await db_manager.execute_query(query, (status, admin_response, request_id))

def validate_uid(uid):
    """Validate UID format and patterns for auto-verification"""
    if not uid or not isinstance(uid, str):
        return False, "UID is required"
    
    uid = uid.strip()
    
    # Check length requirements
    if len(uid) < BotConfig.MIN_UID_LENGTH:
        return False, f"UID too short (minimum {BotConfig.MIN_UID_LENGTH} characters)"
    
    if len(uid) > BotConfig.MAX_UID_LENGTH:
        return False, f"UID too long (maximum {BotConfig.MAX_UID_LENGTH} characters)"
    
    # Check for alphanumeric characters only
    if not re.match(r'^[a-zA-Z0-9]+$', uid):
        return False, "UID must contain only letters and numbers"
    
    # Check for suspicious patterns (test/demo accounts)
    suspicious_patterns = [
        r'test', r'demo', r'sample', r'example', r'fake', r'trial', r'temp',
        r'123456', r'000000', r'111111', r'999999',
        # Sequential patterns
        r'012345', r'123457', r'234567', r'345678', r'456789', r'567890',
        r'098765', r'987654',
        # Repeated patterns
        r'222222', r'333333', r'444444', r'555555', r'666666', r'777777',
        r'888888', r'aaaaaa', r'bbbbbb',
        # Common test/placeholder text
        r'lorem', r'ipsum', r'placeholder', r'dummy', r'mock', r'stub',
        r'testing', r'debug', r'dev', r'sandbox',
        # Default/admin patterns
        r'admin', r'default', r'guest', r'user', r'anonymous', r'null',
        r'undefined', r'empty', r'blank',
        # Keyboard patterns
        r'qwerty', r'asdfgh', r'zxcvbn', r'qaz', r'wsx', r'edc',
        # Email patterns
        r'test@', r'demo@', r'sample@', r'example@', r'fake@', r'noreply@',
        r'donotreply@',
        # Development/testing environments
        r'localhost', r'127\.0\.0\.1', r'dev\..*', r'test\..*',
        r'staging\..*', r'beta\..*', r'alpha\..*'
    ]
    
    uid_lower = uid.lower()
    for pattern in suspicious_patterns:
        if re.search(pattern, uid_lower):
            return False, f"UID appears to be a test/demo account"
    
    # Check for repeated characters (more than 4 in a row)
    if re.search(r'(.)\1{4,}', uid):
        return False, "UID contains too many repeated characters"
    
    return True, "UID format is valid"

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

async def auto_verify_user(user_id, uid, screenshot_file_id, context):
    """Automatically verify user and update their status"""
    try:
        # Create verification request with auto_verified flag
        if BotConfig.DATABASE_TYPE == 'postgresql':
            query = '''
                INSERT INTO verification_requests (user_id, uid, screenshot_file_id, status, auto_verified, admin_response)
                VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
            '''
            result = await db_manager.execute_query(query, (
                user_id, uid, screenshot_file_id, 'approved', True, 'Auto-verified by system'
            ), fetch=True)
            request_id = result[0]['id'] if result else None
        else:
            query = '''
                INSERT INTO verification_requests (user_id, uid, screenshot_file_id, status, auto_verified, admin_response)
                VALUES (?, ?, ?, ?, ?, ?)
            '''
            await db_manager.execute_query(query, (
                user_id, uid, screenshot_file_id, 'approved', True, 'Auto-verified by system'
            ))
            request_id = None
        
        # Update user status
        await update_user_data(user_id, 
            deposit_confirmed=True, 
            current_flow='completed',
            verification_status='approved'
        )
        
        # Log the auto-verification
        await log_interaction(user_id, "auto_verified", f"UID: {uid}")
        
        # Send success message to user
        success_message = f"""🎉 **AUTO-VERIFICATION SUCCESSFUL!**

✅ **Your account has been instantly verified!**
🆔 **UID:** `{uid}`
⚡ **Status:** Automatically Approved
🕐 **Verified at:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

🚀 **PREMIUM ACCESS UNLOCKED:**
• 💎 VIP Signals Channel: {PREMIUM_GROUP_LINK}
• 📈 Premium Trading Group: {PREMIUM_GROUP_LINK}
• 🎯 Exclusive Market Analysis
• ⚡ Priority Customer Support
• 📊 Advanced Trading Tools

💡 **NEXT STEPS:**
1. 🔗 Join our premium channels above
2. 📱 Start receiving VIP signals immediately
3. 💰 Begin your profitable trading journey
4. 📞 Contact support for any questions

🎊 **Welcome to the VIP community!**
📈 **Happy Trading & Profit Making!**"""
        
        keyboard = [
            [InlineKeyboardButton("🚀 Start Trading Now", url=BotConfig.BROKER_LINK)],
            [InlineKeyboardButton("💎 Join VIP Signals", url=PREMIUM_GROUP_LINK)],
            [InlineKeyboardButton("💬 Contact Support", callback_data="support")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
        ]
        
        await context.bot.send_message(
            chat_id=user_id,
            text=success_message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        
        # Log chat history
        await db_manager.log_chat_message(user_id, "bot_response", success_message, {
            "verification_type": "auto_verified",
            "uid": uid,
            "request_id": request_id,
            "status": "approved"
        })
        
        logger.info(f"Auto-verified user {user_id} with UID {uid}")
        return True, request_id
        
    except Exception as e:
        logger.error(f"Error in auto_verify_user: {e}")
        return False, None

# Standalone callback functions (from scripts version)
async def activation_instructions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    await update_user_data(user_id, current_flow='activation')
    await log_interaction(user_id, "activation_instructions")
    
    # Log chat history
    await db_manager.log_chat_message(user_id, "user_action", "Clicked Get Free VIP Access", {
        "action_type": "button_click",
        "button_data": "get_vip_access"
    })
    
    activation_text = f"""✅ Activation Instructions

To activate your free access and join our VIP Signal Channel, follow these steps:

1️⃣Click the link below to register with our official broker partner
{BotConfig.BROKER_LINK}

2️⃣Deposit $20 or more

3️⃣Send your proof of deposit

once your proof have been confirmed your access will be unlocked immediately

The more you deposit, the more powerful your AI access:

✅ $100+ → Full access to OPTRIX Web AI Portal, Live Signals & AI tools.

✅ $500+ → Includes:
— All available signal alert options
— VIP telegram group
— Access to private sessions and risk management blueprint
— OPTRIX AI Auto-Trading (trades for you automatically)"""

    keyboard = [
        [InlineKeyboardButton("➡️ I've Registered", callback_data="registered")],
        [InlineKeyboardButton("➡️ Need help signing up", callback_data="help_signup")],
        [InlineKeyboardButton("➡️ Need support making a deposit", callback_data="help_deposit")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Send new message instead of editing to preserve chat history
    await context.bot.send_message(
        chat_id=user_id,
        text=activation_text,
        reply_markup=reply_markup
    )
    
    # Log bot response
    await db_manager.log_chat_message(user_id, "bot_response", activation_text, {
        "buttons": ["I've Registered", "Need help signing up", "Need support making a deposit"]
    })
    
    # Send second part of message
    second_part = """Why is it free?

We earn a small commission from the broker through your trading volume, not your money. So we are more focused on your success, the more you win, the better for both of us. ✅

Want to unlock even higher-tier bonuses or full bot access?
Send "UPGRADE"""

    await context.bot.send_message(chat_id=query.from_user.id, text=second_part)
    
    # Log second part
    await db_manager.log_chat_message(user_id, "bot_response", second_part)

async def registration_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    await update_user_data(user_id, current_flow='confirmation', registration_status='registered')
    await log_interaction(user_id, "registration_confirmation")
    
    # Log chat history
    await db_manager.log_chat_message(user_id, "user_action", "Clicked I've Registered", {
        "action_type": "button_click",
        "button_data": "registered"
    })
    
    confirmation_text = """✅ Confirmation

Send in your uid and deposit screenshot to gain access optrixtrades trades premium signal channel.

BONUS: We're hosting a live session soon with exclusive insights. Stay tuned. Get an early access now into our premium channel only limited slots are available."""

    # Send new message instead of editing to preserve chat history
    await context.bot.send_message(
        chat_id=user_id,
        text=confirmation_text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📝 Start Verification", callback_data="start_verification")],
            [InlineKeyboardButton("❓ Where to find UID?", callback_data="uid_help")]
        ])
    )
    
    # Log bot response
    await db_manager.log_chat_message(user_id, "bot_response", confirmation_text)

async def help_signup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    await log_interaction(user_id, "help_signup")
    
    # Log chat history
    await db_manager.log_chat_message(user_id, "user_action", "Requested signup help", {
        "action_type": "button_click",
        "button_data": "help_signup"
    })
    
    help_text = f"""📹 SIGNUP HELP

Step-by-step registration guide:

1. Click this link: {BotConfig.BROKER_LINK}
2. Fill in your personal details
3. Verify your email address
4. Complete account verification
5. Make your first deposit ($20 minimum)

Need personal assistance? Contact @{BotConfig.ADMIN_USERNAME}"""

    # Send new message instead of editing to preserve chat history
    await context.bot.send_message(
        chat_id=user_id,
        text=help_text
    )
    
    # Log bot response
    await db_manager.log_chat_message(user_id, "bot_response", help_text, {
        "action": "signup_help"
    })

async def help_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    await log_interaction(user_id, "help_deposit")
    
    # Log chat history
    await db_manager.log_chat_message(user_id, "user_action", "Requested deposit help", {
        "action_type": "button_click",
        "button_data": "help_deposit"
    })
    
    help_text = f"""💳 DEPOSIT HELP

How to make your first deposit:

1. Log into your broker account
2. Go to "Deposit" section
3. Choose your payment method
4. Enter amount ($20 minimum)
5. Complete the transaction
6. Take a screenshot of confirmation

Need help? Contact @{BotConfig.ADMIN_USERNAME}"""

    # Send new message instead of editing to preserve chat history
    await context.bot.send_message(
        chat_id=user_id,
        text=help_text
    )
    
    # Log bot response
    await db_manager.log_chat_message(user_id, "bot_response", help_text, {
        "action": "deposit_help"
    })

async def handle_not_interested(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    await update_user_data(user_id, is_active=False)
    await log_interaction(user_id, "not_interested")
    
    # Log chat history
    await db_manager.log_chat_message(user_id, "user_action", "Clicked not interested", {
        "action_type": "button_click",
        "button_data": "not_interested"
    })
    
    farewell_text = """Alright, no problem! 👋

Feel free to reach us at any time @Optrixtradesadmin if you change your mind.

We'll be here when you're ready to start your trading journey! 🚀"""

    # Send new message instead of editing to preserve chat history
    await context.bot.send_message(
        chat_id=user_id,
        text=farewell_text
    )
    
    # Log bot response
    await db_manager.log_chat_message(user_id, "bot_response", farewell_text, {
        "action": "not_interested_farewell"
    })

async def handle_group_access_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    first_name = query.from_user.first_name or "there"
    username = query.from_user.username or ""
    
    await log_interaction(user_id, "group_access_request")
    
    # Log chat history
    await db_manager.log_chat_message(user_id, "user_action", "Requested premium group access", {
        "action_type": "group_access_request",
        "username": username,
        "first_name": first_name
    })
    
    # Check if user is verified before allowing premium access
    user_data = await get_user_data(user_id)
    is_verified = user_data and user_data[4] == 1  # deposit_confirmed field
    
    # Also check verification requests table
    if not is_verified:
        if BotConfig.DATABASE_TYPE == 'postgresql':
            query = '''
                SELECT status FROM verification_requests 
                WHERE user_id = %s AND status = 'approved'
                ORDER BY created_at DESC LIMIT 1
            '''
        else:
            query = '''
                SELECT status FROM verification_requests 
                WHERE user_id = ? AND status = 'approved'
                ORDER BY created_at DESC LIMIT 1
            '''
        result = await db_manager.execute_query(query, (user_id,), fetch=True)
        is_verified = result is not None and len(result) > 0
    
    if not is_verified:
        # User is not verified - show verification required message
        verification_required_text = f"""🔒 **Verification Required**

Hi {first_name}! To access our premium group, you need to complete verification first.

**Current Status:** ❌ Not Verified

📋 **To get verified:**
1. Register with our broker: {BotConfig.BROKER_LINK[:50]}...
2. Make a minimum deposit of $20
3. Upload your deposit screenshot
4. Wait for admin approval (2-4 hours)

⏳ **Have you already submitted verification?**
Please wait for admin approval. You'll be notified automatically.

💡 **Need help with verification?**
Click the button below for detailed guidance."""
        
        keyboard = [
            [InlineKeyboardButton("❓ Verification Help", callback_data="verification_help")],
            [InlineKeyboardButton("📞 Contact Support", callback_data="contact_support")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(
            chat_id=user_id,
            text=verification_required_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
        # Log verification required response
        await db_manager.log_chat_message(user_id, "bot_response", verification_required_text, {
            "action": "verification_required_for_premium",
            "verification_status": "not_verified",
            "buttons": ["Verification Help", "Contact Support"]
        })
        
        return
    
    # User is verified - provide group access
    join_text = f"""🎯 **Join OPTRIXTRADES Premium Group**

Hi {first_name}! ✅ **You are verified!** Click the link below to join our premium trading group:

🔗 **Group Link:** {PREMIUM_GROUP_LINK}

✅ **What you'll get:**
• Real-time trading signals
• Market analysis and insights
• Direct access to our trading experts
• Exclusive trading strategies
• Community support

📱 **After joining the group, click the button below to confirm your membership and continue your trading journey!**"""
    
    keyboard = [[InlineKeyboardButton("✅ I've Joined the Group", callback_data="confirm_group_joined")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Send new message instead of editing to preserve chat history
    await context.bot.send_message(
        chat_id=user_id,
        text=join_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    # Log bot response
    await db_manager.log_chat_message(user_id, "bot_response", join_text, {
        "action": "premium_group_join_instructions",
        "group_link": PREMIUM_GROUP_LINK,
        "verification_status": "verified",
        "buttons": ["I've Joined the Group"]
    })
    
    # Update user status to indicate they're in the process of joining
    await update_user_data(user_id, current_flow='joining_group')

async def handle_group_join_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    first_name = query.from_user.first_name or "there"
    username = query.from_user.username or ""
    
    await log_interaction(user_id, "group_join_confirmed")
    
    # Log chat history
    await db_manager.log_chat_message(user_id, "user_action", "Confirmed group membership", {
        "action_type": "group_join_confirmation",
        "username": username,
        "first_name": first_name
    })
    
    # Send welcome confirmation message
    welcome_text = f"""🎉 **Welcome to OPTRIXTRADES Premium Group!**

Hi {first_name}! Thank you for joining our premium trading group.

🚀 **You now have access to:**
• Real-time trading signals
• Market analysis and insights
• Direct access to our trading experts
• Exclusive trading strategies
• Community support

✨ **Ready to start your trading journey?**"""
    
    keyboard = [[InlineKeyboardButton("🚀 Start Trading Journey", callback_data="start_trading")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Send new message instead of editing to preserve chat history
    await context.bot.send_message(
        chat_id=user_id,
        text=welcome_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    # Log bot response
    await db_manager.log_chat_message(user_id, "bot_response", welcome_text, {
        "action": "premium_group_welcome_confirmation",
        "buttons": ["Start Trading Journey"]
    })
    
    # Update user status to group member
    await update_user_data(user_id, current_flow='group_member')

async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    await log_interaction(user_id, "main_menu")
    
    # Log chat history
    await db_manager.log_chat_message(user_id, "user_action", "Clicked Main Menu", {
        "action_type": "button_click",
        "button_data": "main_menu"
    })
    
    # Get user data to determine status
    user_data = await get_user_data(user_id)
    is_verified = user_data and user_data[4] == 1  # deposit_confirmed field
    
    # Also check verification requests table
    if not is_verified:
        if BotConfig.DATABASE_TYPE == 'postgresql':
            query_sql = '''
                SELECT status FROM verification_requests 
                WHERE user_id = %s AND status = 'approved'
                ORDER BY created_at DESC LIMIT 1
            '''
        else:
            query_sql = '''
                SELECT status FROM verification_requests 
                WHERE user_id = ? AND status = 'approved'
                ORDER BY created_at DESC LIMIT 1
            '''
        result = await db_manager.execute_query(query_sql, (user_id,), fetch=True)
        is_verified = result is not None and len(result) > 0
    
    first_name = query.from_user.first_name or "there"
    
    if is_verified:
        status_text = "✅ Verified Member"
        menu_text = f"""🏠 **Main Menu**

Welcome back, {first_name}! {status_text}

Choose an option below:"""
        
        keyboard = [
            [InlineKeyboardButton("👤 My Account", callback_data="account_menu")],
            [InlineKeyboardButton("🚀 Start Trading", callback_data="start_trading")],
            [InlineKeyboardButton("🎯 Premium Group Access", callback_data="request_group_access")],
            [InlineKeyboardButton("❓ Help & Support", callback_data="help_menu")],
            [InlineKeyboardButton("🔔 Notification Settings", callback_data="notification_settings")]
        ]
    else:
        status_text = "⏳ Pending Verification"
        menu_text = f"""🏠 **Main Menu**

Welcome, {first_name}! {status_text}

Choose an option below:"""
        
        keyboard = [
            [InlineKeyboardButton("👤 My Account", callback_data="account_menu")],
            [InlineKeyboardButton("🎯 Get VIP Access", callback_data="get_vip_access")],
            [InlineKeyboardButton("❓ Help & Support", callback_data="help_menu")],
            [InlineKeyboardButton("🔔 Notification Settings", callback_data="notification_settings")]
        ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Send new message instead of editing to preserve chat history
    await context.bot.send_message(
        chat_id=user_id,
        text=menu_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    # Log bot response
    await db_manager.log_chat_message(user_id, "bot_response", menu_text, {
        "action": "main_menu_display",
        "verification_status": "verified" if is_verified else "pending",
        "buttons": [btn[0].text for btn in keyboard]
    })

async def account_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    await log_interaction(user_id, "account_menu")
    
    # Log chat history
    await db_manager.log_chat_message(user_id, "user_action", "Clicked My Account", {
        "action_type": "button_click",
        "button_data": "account_menu"
    })
    
    # Get user data
    user_data = await get_user_data(user_id)
    first_name = query.from_user.first_name or "User"
    username = query.from_user.username or "Not set"
    
    if user_data:
        uid = user_data[2] or "Not provided"
        is_verified = user_data[4] == 1
        created_at = user_data[5]
        
        # Format creation date
        if created_at:
            if isinstance(created_at, str):
                from datetime import datetime
                try:
                    created_date = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    formatted_date = created_date.strftime("%B %d, %Y")
                except:
                    formatted_date = created_at
            else:
                formatted_date = created_at.strftime("%B %d, %Y")
        else:
            formatted_date = "Unknown"
        
        verification_status = "✅ Verified" if is_verified else "⏳ Pending Verification"
        
        account_text = f"""👤 **My Account**

**Name:** {first_name}
**Username:** @{username}
**User ID:** `{user_id}`
**UID:** {uid}
**Status:** {verification_status}
**Member Since:** {formatted_date}

💡 **Need to update your information?**
Contact support for assistance."""
    else:
        account_text = f"""👤 **My Account**

**Name:** {first_name}
**Username:** @{username}
**User ID:** `{user_id}`
**Status:** ❌ Not Registered

💡 **Get started by clicking 'Get VIP Access' from the main menu.**"""
    
    keyboard = [
        [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")],
        [InlineKeyboardButton("📞 Contact Support", callback_data="contact_support")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Send new message instead of editing to preserve chat history
    await context.bot.send_message(
        chat_id=user_id,
        text=account_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    # Log bot response
    await db_manager.log_chat_message(user_id, "bot_response", account_text, {
        "action": "account_menu_display",
        "user_data_available": user_data is not None,
        "buttons": ["Main Menu", "Contact Support"]
    })

async def help_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    await log_interaction(user_id, "help_menu")
    
    # Log chat history
    await db_manager.log_chat_message(user_id, "user_action", "Clicked Help & Support", {
        "action_type": "button_click",
        "button_data": "help_menu"
    })
    
    help_text = f"""❓ **Help & Support**

Choose the type of help you need:

🔍 **Common Questions:**
• How to verify my account
• Deposit requirements
• Group access issues

📞 **Direct Support:**
Contact our admin for personalized assistance."""
    
    keyboard = [
        [InlineKeyboardButton("❓ Verification Help", callback_data="verification_help")],
        [InlineKeyboardButton("📝 Signup Help", callback_data="help_signup")],
        [InlineKeyboardButton("💳 Deposit Help", callback_data="help_deposit")],
        [InlineKeyboardButton("📞 Contact Support", callback_data="contact_support")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Send new message instead of editing to preserve chat history
    await context.bot.send_message(
        chat_id=user_id,
        text=help_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    # Log bot response
    await db_manager.log_chat_message(user_id, "bot_response", help_text, {
        "action": "help_menu_display",
        "buttons": ["Verification Help", "Signup Help", "Deposit Help", "Contact Support", "Main Menu"]
    })

async def start_trading_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    first_name = query.from_user.first_name or "there"
    await log_interaction(user_id, "start_trading")
    
    # Log chat history
    await db_manager.log_chat_message(user_id, "user_action", "Clicked Start Trading", {
        "action_type": "button_click",
        "button_data": "start_trading"
    })
    
    trading_text = f"""🚀 **Start Your Trading Journey**

Hi {first_name}! Ready to begin trading? Here's your roadmap:

📈 **Step 1: Access Premium Signals**
Join our premium group for real-time trading signals

📊 **Step 2: Learn the Basics**
Familiarize yourself with our trading strategies

💰 **Step 3: Start Small**
Begin with small trades to build confidence

🎯 **Step 4: Follow Signals**
Implement our expert signals in your trades

📚 **Resources Available:**
• Live trading signals
• Market analysis
• Risk management tips
• Community support

✨ **Ready to access premium features?**"""
    
    keyboard = [
        [InlineKeyboardButton("🎯 Join Premium Group", callback_data="request_group_access")],
        [InlineKeyboardButton("📚 Trading Resources", url=BotConfig.BROKER_LINK)],
        [InlineKeyboardButton("📞 Get Personal Guidance", callback_data="contact_support")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Send new message instead of editing to preserve chat history
    await context.bot.send_message(
        chat_id=user_id,
        text=trading_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    # Log bot response
    await db_manager.log_chat_message(user_id, "bot_response", trading_text, {
        "action": "start_trading_guidance",
        "buttons": ["Join Premium Group", "Trading Resources", "Get Personal Guidance", "Main Menu"]
    })

async def notification_settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    await log_interaction(user_id, "notification_settings")
    
    # Log chat history
    await db_manager.log_chat_message(user_id, "user_action", "Clicked Notification Settings", {
        "action_type": "button_click",
        "button_data": "notification_settings"
    })
    
    settings_text = f"""🔔 **Notification Settings**

**Current Settings:**
✅ Trading Signals: Enabled
✅ Account Updates: Enabled
✅ Group Notifications: Enabled
✅ Admin Messages: Enabled

💡 **Note:** All notifications are currently enabled to ensure you don't miss important trading opportunities and account updates.

📞 **Want to customize your notifications?**
Contact support for personalized notification preferences."""
    
    keyboard = [
        [InlineKeyboardButton("📞 Contact Support", callback_data="contact_support")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Send new message instead of editing to preserve chat history
    await context.bot.send_message(
        chat_id=user_id,
        text=settings_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    # Log bot response
    await db_manager.log_chat_message(user_id, "bot_response", settings_text, {
        "action": "notification_settings_display",
        "buttons": ["Contact Support", "Main Menu"]
    })

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    first_name = update.effective_user.first_name or "there"
    
    await log_interaction(user_id, "menu_command")
    
    # Log chat history
    await db_manager.log_chat_message(user_id, "user_action", "Used /menu command", {
        "action_type": "command",
        "command": "/menu"
    })
    
    # Get user data to determine status
    user_data = await get_user_data(user_id)
    is_verified = user_data and user_data[4] == 1  # deposit_confirmed field
    
    # Also check verification requests table
    if not is_verified:
        if BotConfig.DATABASE_TYPE == 'postgresql':
            query = '''
                SELECT status FROM verification_requests 
                WHERE user_id = %s AND status = 'approved'
                ORDER BY created_at DESC LIMIT 1
            '''
        else:
            query = '''
                SELECT status FROM verification_requests 
                WHERE user_id = ? AND status = 'approved'
                ORDER BY created_at DESC LIMIT 1
            '''
        result = await db_manager.execute_query(query, (user_id,), fetch=True)
        is_verified = result is not None and len(result) > 0
    
    if is_verified:
        status_text = "✅ Verified Member"
        menu_text = f"""🏠 **Main Menu**

Welcome back, {first_name}! {status_text}

Choose an option below:"""
        
        keyboard = [
            [InlineKeyboardButton("👤 My Account", callback_data="account_menu")],
            [InlineKeyboardButton("🚀 Start Trading", callback_data="start_trading")],
            [InlineKeyboardButton("🎯 Premium Group Access", callback_data="request_group_access")],
            [InlineKeyboardButton("❓ Help & Support", callback_data="help_menu")],
            [InlineKeyboardButton("🔔 Notification Settings", callback_data="notification_settings")]
        ]
    else:
        status_text = "⏳ Pending Verification"
        menu_text = f"""🏠 **Main Menu**

Welcome, {first_name}! {status_text}

Choose an option below:"""
        
        keyboard = [
            [InlineKeyboardButton("👤 My Account", callback_data="account_menu")],
            [InlineKeyboardButton("🎯 Get VIP Access", callback_data="get_vip_access")],
            [InlineKeyboardButton("❓ Help & Support", callback_data="help_menu")],
            [InlineKeyboardButton("🔔 Notification Settings", callback_data="notification_settings")]
        ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        text=menu_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    # Log bot response
    await db_manager.log_chat_message(user_id, "bot_response", menu_text, {
        "action": "menu_command_response",
        "verification_status": "verified" if is_verified else "pending",
        "buttons": [btn[0].text for btn in keyboard]
    })


async def handle_admin_queue_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin queue callback with verification action buttons"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if not is_admin(user_id):
        await context.bot.send_message(chat_id=query.message.chat_id, text="❌ You don't have permission to use this command.")
        return
    
    pending_requests = await get_pending_verifications()
    
    if not pending_requests:
        queue_text = "✅ No pending verification requests."
        keyboard = [
            [InlineKeyboardButton("🔄 Refresh", callback_data="admin_queue")],
            [InlineKeyboardButton("⬅️ Back", callback_data="admin_dashboard")]
        ]
    else:
        queue_text = "📋 **Pending Verification Queue:**\n\n"
        keyboard = []
        
        for i, req in enumerate(pending_requests[:5], 1):  # Limit to 5 for button space
            req_id, user_id_req, first_name, username, uid, created_at = req
            username_display = f"@{username}" if username else "No username"
            queue_text += f"**{i}.** {first_name} ({username_display})\n"
            queue_text += f"🆔 ID: `{user_id_req}` | 💳 UID: `{uid}`\n"
            queue_text += f"⏰ {created_at}\n\n"
            
            # Add approve/reject buttons for each user
            keyboard.append([
                InlineKeyboardButton(f"✅ Approve #{i}", callback_data=f"verify_{user_id_req}"),
                InlineKeyboardButton(f"❌ Reject #{i}", callback_data=f"reject_{user_id_req}")
            ])
        
        if len(pending_requests) > 5:
            queue_text += f"\n... and {len(pending_requests) - 5} more requests.\n"
            queue_text += "💡 Use `/queue` command to see all requests."
        
        # Add navigation buttons
        keyboard.extend([
            [InlineKeyboardButton("🔄 Refresh", callback_data="admin_queue")],
            [InlineKeyboardButton("⬅️ Back", callback_data="admin_dashboard")]
        ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.edit_message_text(
        chat_id=query.message.chat_id,
        message_id=query.message.message_id,
        text=queue_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def handle_admin_activity_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin activity callback"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if not is_admin(user_id):
        await context.bot.send_message(chat_id=query.message.chat_id, text="❌ You don't have permission to use this command.")
        return
    
    # Get recent activity from chat history
    if BotConfig.DATABASE_TYPE == 'postgresql':
        activity_query = '''
            SELECT ch.user_id, u.first_name, ch.message_type, ch.message_content, ch.created_at
            FROM chat_history ch
            JOIN users u ON ch.user_id = u.user_id
            ORDER BY ch.created_at DESC
            LIMIT %s
        '''
    else:
        activity_query = '''
            SELECT ch.user_id, u.first_name, ch.message_type, ch.message_content, ch.created_at
            FROM chat_history ch
            JOIN users u ON ch.user_id = u.user_id
            ORDER BY ch.created_at DESC
            LIMIT ?
        '''
    
    try:
        recent_activity = await db_manager.execute_query(activity_query, (10,))
        
        if not recent_activity:
            activity_text = "📊 No recent activity found."
        else:
            activity_text = "📊 **Recent Activity (Last 10):**\n\n"
            
            for entry in recent_activity:
                user_id_entry, first_name, message_type, content, timestamp = entry
                timestamp_str = str(timestamp)[:16] if timestamp else "Unknown"
                content_preview = content[:30] + "..." if len(str(content)) > 30 else str(content)
                
                activity_text += f"👤 {first_name} (ID: {user_id_entry}) | {timestamp_str}\n"
                activity_text += f"📝 {message_type}: {content_preview}\n\n"
    except Exception as e:
        logger.error(f"Error fetching recent activity: {e}")
        activity_text = "❌ Error fetching recent activity."
    
    keyboard = [
        [InlineKeyboardButton("🔄 Refresh", callback_data="admin_activity")],
        [InlineKeyboardButton("⬅️ Back", callback_data="admin_dashboard")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=activity_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )


async def handle_admin_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin-specific callback queries"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if not is_admin(user_id):
        await context.bot.send_message(chat_id=query.message.chat_id, text="❌ You don't have permission to use this feature.")
        return
    
    callback_data = query.data
    
    if callback_data == "admin_queue":
        await handle_admin_queue_callback(update, context)
    elif callback_data == "admin_activity":
        await handle_admin_activity_callback(update, context)
    elif callback_data == "admin_dashboard":
        first_name = query.from_user.first_name or "Admin"
        
        admin_welcome_text = f"""🔧 **Admin Panel - Welcome {first_name}!**

**Bot Status:** ✅ Running | **Database:** ✅ Connected
**Broker Link:** {BotConfig.BROKER_LINK[:50]}...
**Premium Group:** {BotConfig.PREMIUM_GROUP_LINK}

🎯 **Admin Dashboard:**"""
        
        keyboard = [
            [InlineKeyboardButton("📋 Pending Queue", callback_data="admin_queue"),
             InlineKeyboardButton("📊 User Activity", callback_data="admin_activity")],
            [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"),
             InlineKeyboardButton("👥 All Users", callback_data="admin_users")],
            [InlineKeyboardButton("📈 Bot Stats", callback_data="admin_stats")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=admin_welcome_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    else:
        await query.answer("Feature coming soon!")


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
            
            await update_user_data(user_id, uid=uid)
            
            await self._send_persistent_message(
                chat_id=user_id,
                text="✅ *UID Received!*\n\nYour UID has been recorded.\n\n📸 *Verification Step 2/2*\n\nNow please send your *deposit screenshot* as a photo. If you have any issues, you can contact support using the button below:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📞 Contact Support", callback_data="contact_support")],
                    [InlineKeyboardButton("⬅️ Main Menu", callback_data="main_menu")]
                ]),
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
                await activation_instructions(update, context)
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
                await main_menu_callback(update, context)
            elif data == "uid_help":
                await self.uid_help(update, context)
            elif data == "registered":
                await registration_confirmation(update, context)
            elif data == "help_signup":
                await help_signup(update, context)
            elif data == "help_deposit":
                await help_deposit(update, context)
            elif data == "not_interested":
                await handle_not_interested(update, context)
            elif data == "request_group_access":
                await handle_group_access_request(update, context)
            elif data == "confirm_group_joined":
                await handle_group_join_confirmation(update, context)
            elif data == "account_menu":
                await account_menu_callback(update, context)
            elif data == "help_menu":
                await help_menu_callback(update, context)
            elif data == "start_trading":
                await start_trading_callback(update, context)
            elif data == "notification_settings":
                await notification_settings_callback(update, context)
            elif data == "contact_support":
                await self.handle_contact_support(update, context)
            elif data == "verification_help":
                await self.handle_verification_help(update, context)
            elif data in ["admin_queue", "admin_activity", "admin_dashboard", "admin_broadcast", "admin_users", "admin_stats"]:
                await handle_admin_callbacks(update, context)
            else:
                await query.answer("Feature coming soon!")
        except Exception as e:
            logger.error(f"Error in button callback: {e}")

    # Removed duplicate handle_text_message method - using the one at line 2492 instead

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
    

    
    async def handle_verification_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle verification help callback"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        await log_interaction(user_id, "verification_help")
        
        # Log chat history
        await db_manager.log_chat_message(user_id, "user_action", "Requested verification help", {
            "action_type": "button_click",
            "button_data": "verification_help"
        })
        
        help_text = f"""❓ **Verification Help & FAQ**

**What happens during verification?**
• Our admin team reviews your deposit screenshot
• We verify the transaction details and amount
• You get instant access once approved

**How long does verification take?**
• Usually 2-4 hours during business hours
• Auto-verification: Instant (when available)
• Manual review: Up to 24 hours maximum

**What should my screenshot include?**
• Clear deposit confirmation
• Visible transaction amount
• Your broker UID/account number
• Transaction date and time

**Common issues:**
• Blurry or unclear screenshots
• Missing transaction details
• Incorrect UID format
• Demo/test account UIDs

**Need more help?**
Contact support: @{BotConfig.ADMIN_USERNAME}"""
        
        keyboard = [
            [InlineKeyboardButton("📞 Contact Support", callback_data="contact_support")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
        ]
        
        await context.bot.send_message(
            chat_id=user_id,
            text=help_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        
        # Log bot response
        await db_manager.log_chat_message(user_id, "bot_response", help_text, {
            "help_type": "verification_help",
            "buttons": ["Contact Support", "Main Menu"]
        })
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
    
    async def handle_broadcast_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle broadcast message input from admin"""
        try:
            user_id = update.effective_user.id
            
            if not await self._is_admin(user_id):
                await update.message.reply_text("⛔ Unauthorized")
                return ConversationHandler.END
            
            broadcast_message = update.message.text.strip()
            
            if not broadcast_message:
                await update.message.reply_text("❌ Please provide a valid message to broadcast.")
                return BROADCAST_MESSAGE
            
            # Get all users
            all_users = await get_all_users()
            
            if not all_users:
                await update.message.reply_text("❌ No users found to broadcast to.")
                return ConversationHandler.END
            
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
            
            return ConversationHandler.END
            
        except Exception as e:
            logger.error(f"Error in handle_broadcast_message: {e}")
            await update.message.reply_text("❌ Error sending broadcast message.")
            return ConversationHandler.END
    
    async def handle_lookup_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle user lookup input from admin"""
        try:
            user_id = update.effective_user.id
            
            if not await self._is_admin(user_id):
                await update.message.reply_text("⛔ Unauthorized")
                return ConversationHandler.END
            
            lookup_user_id = update.message.text.strip()
            
            # Validate user ID format
            if not lookup_user_id.isdigit():
                await update.message.reply_text("❌ Please provide a valid numeric User ID.")
                return USER_LOOKUP
            
            lookup_user_id = int(lookup_user_id)
            
            # Get user data
            user_data = await get_user_data(lookup_user_id)
            
            if not user_data:
                await update.message.reply_text(f"❌ No user found with ID: {lookup_user_id}")
                return ConversationHandler.END
            
            # Format user information
            if isinstance(user_data, dict):
                name = user_data.get('first_name', 'Unknown')
                username = user_data.get('username', 'Not set')
                uid = user_data.get('uid', 'Not provided')
                is_verified = user_data.get('verified', False)
                is_active = user_data.get('is_active', False)
                created_at = user_data.get('created_at', 'Unknown')
            else:
                # Handle tuple format
                name = user_data[2] if len(user_data) > 2 else 'Unknown'
                username = user_data[3] if len(user_data) > 3 else 'Not set'
                uid = user_data[6] if len(user_data) > 6 else 'Not provided'
                is_verified = bool(user_data[4]) if len(user_data) > 4 else False
                is_active = bool(user_data[5]) if len(user_data) > 5 else False
                created_at = user_data[7] if len(user_data) > 7 else 'Unknown'
            
            status = "✅ Verified" if is_verified else "❌ Not Verified"
            active_status = "🟢 Active" if is_active else "🔴 Inactive"
            
            user_info_text = f"""👤 **User Lookup Results**

🆔 **User ID:** `{lookup_user_id}`
👤 **Name:** {name}
🏷️ **Username:** @{username if username != 'Not set' else 'Not set'}
💳 **UID:** `{uid}`
🔒 **Status:** {status}
📊 **Activity:** {active_status}
📅 **Joined:** {created_at}

**Admin Actions:**
• /admin_verify {lookup_user_id} - Verify user
• /admin_reject {lookup_user_id} - Reject user
• /chathistory {lookup_user_id} - View chat history"""
            
            await update.message.reply_text(user_info_text, parse_mode='Markdown')
            
            # Log the lookup
            await log_interaction(user_id, "admin_user_lookup", f"Looked up user {lookup_user_id}")
            
            return ConversationHandler.END
            
        except Exception as e:
            logger.error(f"Error in handle_lookup_user: {e}")
            await update.message.reply_text("❌ Error looking up user.")
            return ConversationHandler.END

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
            elif data == "admin_queue":
                await handle_admin_queue_callback(update, context)
            elif data == "admin_activity":
                await handle_admin_activity_callback(update, context)
            elif data == "admin_dashboard":
                await handle_admin_callbacks(update, context)
            elif data.startswith("verify_"):
                await self.handle_verify_callback(update, context)
            elif data.startswith("reject_"):
                await self.handle_reject_callback(update, context)
            else:
                await query.answer("Unknown action")
                
        except Exception as e:
            logger.error(f"Error in button_callback: {e}")

    async def handle_text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages with comprehensive auto-verification logic"""
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
            
            # Log chat history
            await db_manager.log_chat_message(user_id, "user_message", message_text)
            
            # Handle UID submission
            if text.startswith("UID:") or message_text.isdigit():
                uid = message_text.replace("UID:", "").strip()
                
                # Validate UID format
                is_valid, validation_message = validate_uid(uid)
                
                if is_valid:
                    # Update user with UID
                    await update_user_data(user_id, uid=uid)
                    
                    # Check if auto-verification is possible
                    can_auto_verify, auto_verify_reason = should_auto_verify(user_id, uid)
                    
                    if can_auto_verify:
                        response_text = f"""✅ **UID Received: {uid}**

🤖 **Auto-Verification Status:** Ready for instant approval!
📸 **Next Step:** Send your deposit screenshot to get automatically verified

⚡ **Benefits of Auto-Verification:**
• Instant approval (no waiting)
• Immediate premium access
• Automated processing

📋 **Your UID meets all criteria:**
• Length: ✅ Valid ({len(uid)} characters)
• Format: ✅ Alphanumeric
• Pattern: ✅ No suspicious patterns detected

🎯 **Ready for screenshot upload!**"""
                    else:
                        response_text = f"""✅ **UID Received: {uid}**

📋 **Verification Status:** Manual review required
📝 **Reason:** {auto_verify_reason}
📸 **Next Step:** Send your deposit screenshot for admin review

⏳ **Processing Time:** Usually 2-4 hours
🔍 **Review Process:** Admin will verify your deposit manually

📋 **Your UID status:**
• Length: {'✅' if BotConfig.MIN_UID_LENGTH <= len(uid) <= BotConfig.MAX_UID_LENGTH else '❌'} ({len(uid)} characters)
• Format: {'✅' if re.match(r'^[a-zA-Z0-9]+$', uid) else '❌'} Alphanumeric check

🎯 **Ready for screenshot upload!**"""
                    
                    await update.message.reply_text(response_text, parse_mode='Markdown')
                    
                    # Log bot response
                    await db_manager.log_chat_message(user_id, "bot_response", response_text, {
                        "uid": uid,
                        "validation_status": "valid",
                        "auto_verify_eligible": can_auto_verify,
                        "auto_verify_reason": auto_verify_reason
                    })
                else:
                    # UID validation failed
                    error_response = f"""❌ **Invalid UID Format**

🔍 **Issue:** {validation_message}

📋 **UID Requirements:**
• Length: {BotConfig.MIN_UID_LENGTH}-{BotConfig.MAX_UID_LENGTH} characters
• Format: Letters and numbers only
• No test/demo account patterns
• No excessive repeated characters

💡 **Examples of valid UIDs:**
• ABC123456
• USER789012
• TRADER456789

🔄 **Please send a valid UID to continue.**"""
                    
                    await update.message.reply_text(error_response, parse_mode='Markdown')
                    
                    # Log validation failure
                    await db_manager.log_chat_message(user_id, "bot_response", error_response, {
                        "uid_attempted": uid,
                        "validation_status": "failed",
                        "validation_error": validation_message
                    })
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
            keyboard = [
                [InlineKeyboardButton("📞 Contact Support", callback_data="contact_support")],
                [InlineKeyboardButton("❓ Get Help", callback_data="verification_help")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            response_text = "I didn't understand that. How can I help you?"
            await update.message.reply_text(response_text, reply_markup=reply_markup)
            
            # Log bot response
            await db_manager.log_chat_message(user_id, "bot_response", response_text, {
                "buttons": ["Contact Support", "Get Help"]
            })
            
        except Exception as e:
            logger.error(f"Error in handle_text_message: {e}")

    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle photo uploads with auto-verification logic"""
        try:
            user_id = update.effective_user.id
            
            # Check if user is admin first
            if await self._is_admin(user_id):
                admin_photo_text = f"""🔧 **Admin Photo Upload Detected**

📸 **Photo received from admin:** {update.effective_user.first_name}
🆔 **Admin User ID:** {user_id}
⏰ **Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

**Admin Actions Available:**
• Use /verify <user_id> to approve users
• Use /queue to see pending verifications
• Use /activity to see recent activity

**Note:** This photo was uploaded by an admin account."""
                
                await update.message.reply_text(admin_photo_text, parse_mode='Markdown')
                
                # Log admin photo upload
                await db_manager.log_chat_message(user_id, "admin_action", "Admin uploaded photo", {
                    "action_type": "admin_photo_upload",
                    "file_id": update.message.photo[-1].file_id
                })
                return
            
            # Log interaction
            await log_interaction(user_id, "photo_upload", "deposit_screenshot")
            
            # Check if user exists
            user_data = await get_user_data(user_id)
            if not user_data:
                await update.message.reply_text("Please start with /start first.")
                return
            
            # Get the user's UID from database
            uid = user_data.get('uid') if isinstance(user_data, dict) else (user_data[6] if len(user_data) > 6 and user_data[6] else None)
            
            if not uid:
                # User doesn't have UID, prompt them to provide it first
                await update.message.reply_text(
                    "📸 Photo received! To proceed with verification, please provide your Broker UID first.",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔓 Start Verification", callback_data="start_verification")],
                        [InlineKeyboardButton("📋 Main Menu", callback_data="main_menu")]
                    ])
                )
                return
            
            screenshot_file_id = update.message.photo[-1].file_id
            
            # Check if user should be auto-verified
            can_auto_verify, auto_verify_reason = should_auto_verify(user_id, uid)
            
            if can_auto_verify:
                # Auto-verify the user
                success, request_id = await auto_verify_user(user_id, uid, screenshot_file_id, context)
                
                if success:
                    # Auto-verification completed, function handles all messaging and logging
                    return
                else:
                    logger.error(f"Auto-verification failed for user {user_id}, falling back to manual review")
            
            # Manual verification process (fallback)
            # Create verification request
            from database import create_verification_request
            await create_verification_request(user_id, uid, screenshot_file_id)
            
            # Send confirmation to user with auto-verification status
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
• Status: Manual Review Required
• Reason: {auto_verify_reason}

⏳ Your verification request has been submitted to our admin team. You'll receive a notification once your deposit is verified.

🕐 **Processing Time:** Usually within 2-4 hours

Thank you for your patience! 🙏"""
            
            keyboard = [
                [InlineKeyboardButton("📞 Contact Support", callback_data="contact_support")],
                [InlineKeyboardButton("❓ Verification Help", callback_data="verification_help")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
            ]
            
            await update.message.reply_text(
                confirmation_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            
            # Log chat history
            await db_manager.log_chat_message(user_id, "bot_response", confirmation_text, {
                "uid": uid,
                "screenshot_file_id": screenshot_file_id,
                "auto_verify_eligible": can_auto_verify,
                "auto_verify_reason": auto_verify_reason,
                "verification_type": "manual_review"
            })
            
        except Exception as e:
            logger.error(f"Error in handle_photo: {e}")

    async def admin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Main admin dashboard command"""
        try:
            user_id = update.effective_user.id
            
            if not await self._is_admin(user_id):
                await update.message.reply_text("❌ You don't have permission to use this command.")
                return
            
            first_name = update.effective_user.first_name or "Admin"
            
            # Get pending verifications count
            pending_requests = await get_pending_verifications()
            pending_count = len(pending_requests) if pending_requests else 0
            
            # Get total users count
            all_users = await get_all_users()
            total_users = len(all_users) if all_users else 0
            
            admin_text = f"""👑 **Admin Dashboard**

Welcome back, {first_name}!

📊 **Quick Stats:**
• Total Users: {total_users}
• Pending Verifications: {pending_count}

🛠️ **Admin Tools:**
• View verification queue
• Send broadcast messages
• Look up user information
• Manage user verifications

💡 **Quick Commands:**
• `/queue` - View pending verifications
• `/verify <user_id>` - Approve verification
• `/reject <user_id>` - Reject verification
• `/broadcast` - Send broadcast message
• `/lookup` - Look up user info"""
            
            keyboard = [
                [InlineKeyboardButton("📋 Verification Queue", callback_data="admin_queue")],
                [InlineKeyboardButton("📢 Broadcast Message", callback_data="broadcast"),
                 InlineKeyboardButton("🔍 User Lookup", callback_data="user_lookup")],
                [InlineKeyboardButton("📊 Recent Activity", callback_data="admin_activity")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
            ]
            
            await self._send_persistent_message(
                chat_id=user_id,
                text=admin_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            
            # Log the action
            await log_interaction(user_id, "admin_dashboard", "Accessed admin dashboard")
            
        except Exception as e:
            logger.error(f"Error in admin_command: {e}")
            await update.message.reply_text("❌ Error accessing admin dashboard.")

    async def handle_verify_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle verification approval callback"""
        try:
            query = update.callback_query
            await query.answer()
            
            user_id = query.from_user.id
            if not await self._is_admin(user_id):
                await context.bot.send_message(chat_id=query.message.chat_id, text="❌ You don't have permission to use this feature.")
                return
            
            # Extract user ID from callback data (format: verify_123456789)
            target_user_id = int(query.data.split("_")[1])
            
            # Update user verification status
            await update_user_data(target_user_id, {
                'verified': True,
                'verification_status': 'approved',
                'verification_date': datetime.now().isoformat()
            })
            
            # Update verification request status
            if BotConfig.DATABASE_TYPE == 'postgresql':
                query_sql = "UPDATE verification_requests SET status = %s WHERE user_id = %s"
            else:
                query_sql = "UPDATE verification_requests SET status = ? WHERE user_id = ?"
            
            await db_manager.execute_query(query_sql, ('approved', target_user_id))
            
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
            
            # Update admin with confirmation
            await context.bot.edit_message_text(
                chat_id=query.message.chat_id,
                message_id=query.message.message_id,
                text=f"✅ User {target_user_id} has been verified and notified.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📋 Back to Queue", callback_data="admin_queue")],
                    [InlineKeyboardButton("🏠 Admin Dashboard", callback_data="admin_dashboard")]
                ])
            )
            
            # Log the action
            await log_interaction(user_id, "admin_verify", f"Verified user {target_user_id}")
            
        except Exception as e:
            logger.error(f"Error in handle_verify_callback: {e}")
            await query.answer("❌ Error verifying user.")

    async def handle_reject_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle verification rejection callback"""
        try:
            query = update.callback_query
            await query.answer()
            
            user_id = query.from_user.id
            if not await self._is_admin(user_id):
                await context.bot.send_message(chat_id=query.message.chat_id, text="❌ You don't have permission to use this feature.")
                return
            
            # Extract user ID from callback data (format: reject_123456789)
            target_user_id = int(query.data.split("_")[1])
            
            # Update verification request status
            if BotConfig.DATABASE_TYPE == 'postgresql':
                query_sql = "UPDATE verification_requests SET status = %s WHERE user_id = %s"
            else:
                query_sql = "UPDATE verification_requests SET status = ? WHERE user_id = ?"
            
            await db_manager.execute_query(query_sql, ('rejected', target_user_id))
            
            # Notify user of rejection
            rejection_message = f"""❌ **Verification Rejected**

📋 **Reason:** Verification requirements not met

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
            
            # Update admin with confirmation
            await context.bot.edit_message_text(
                chat_id=query.message.chat_id,
                message_id=query.message.message_id,
                text=f"❌ User {target_user_id} verification has been rejected and user notified.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📋 Back to Queue", callback_data="admin_queue")],
                    [InlineKeyboardButton("🏠 Admin Dashboard", callback_data="admin_dashboard")]
                ])
            )
            
            # Log the action
            await log_interaction(user_id, "admin_reject", f"Rejected user {target_user_id}")
            
        except Exception as e:
            logger.error(f"Error in handle_reject_callback: {e}")
            await query.answer("❌ Error rejecting user verification.")

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
                # Import the create_verification_request function
                from database import create_verification_request
                
                # Create verification request using the existing function
                request_id = await create_verification_request(user_id, uid, document.file_id)
                
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

    async def admin_recent_activity_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Admin command to view recent activity across all users"""
        try:
            user_id = update.effective_user.id
            
            if not await self._is_admin(user_id):
                await update.message.reply_text("❌ You don't have permission to use this command.")
                return
            
            limit = int(context.args[0]) if context.args else 30
            
            # Get recent activity
            recent_activity = await db_manager.get_recent_activity(limit)
            
            if not recent_activity:
                await update.message.reply_text("No recent activity found.")
                return
            
            # Format recent activity
            activity_text = f"📊 Recent Activity (Last {len(recent_activity)} messages)\n\n"
            
            for entry in recent_activity:
                user_id_entry = entry[1]  # user_id
                timestamp = entry[2]  # created_at
                message_type = entry[3]  # message_type
                content = entry[4][:50] + "..." if len(entry[4]) > 50 else entry[4]  # truncated content
                
                activity_text += f"👤 User {user_id_entry} | {timestamp}\n"
                activity_text += f"📝 {message_type}: {content}\n\n"
            
            # Split long messages
            if len(activity_text) > 4000:
                chunks = [activity_text[i:i+4000] for i in range(0, len(activity_text), 4000)]
                for i, chunk in enumerate(chunks):
                    if i == 0:
                        await update.message.reply_text(chunk)
                    else:
                        await update.message.reply_text(f"📊 Recent Activity (Part {i+1})\n\n{chunk}")
            else:
                await update.message.reply_text(activity_text)
                
        except Exception as e:
            logger.error(f"Error in admin_recent_activity_command: {e}")
            await update.message.reply_text("❌ Error retrieving recent activity.")

    async def admin_search_user_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Admin command to search for users"""
        try:
            user_id = update.effective_user.id
            
            if not await self._is_admin(user_id):
                await update.message.reply_text("❌ You don't have permission to use this command.")
                return
            
            if not context.args:
                await update.message.reply_text(
                    "🔍 **Search User Usage:**\n\n"
                    "**Search by username:**\n"
                    "`/searchuser @username`\n\n"
                    "**Search by user ID:**\n"
                    "`/searchuser 123456789`\n\n"
                    "**Search by name:**\n"
                    "`/searchuser John`",
                    parse_mode='Markdown'
                )
                return
            
            search_term = " ".join(context.args).strip()
            
            # Remove @ if searching by username
            if search_term.startswith('@'):
                search_term = search_term[1:]
            
            # Try to search by user ID first (if numeric)
            if search_term.isdigit():
                user_data = await get_user_data(int(search_term))
                if user_data:
                    users = [user_data]
                else:
                    users = []
            else:
                # Search by username or name
                if BotConfig.DATABASE_TYPE == 'postgresql':
                    query = '''
                        SELECT * FROM users 
                        WHERE username ILIKE %s OR first_name ILIKE %s
                        ORDER BY created_at DESC
                        LIMIT 10
                    '''
                else:
                    query = '''
                        SELECT * FROM users 
                        WHERE username LIKE ? OR first_name LIKE ?
                        ORDER BY created_at DESC
                        LIMIT 10
                    '''
                
                search_pattern = f"%{search_term}%"
                users = await db_manager.execute_query(query, (search_pattern, search_pattern), fetch=True)
            
            if not users:
                await update.message.reply_text(f"❌ No users found matching '{search_term}'")
                return
            
            # Format results
            results_text = f"🔍 **Search Results for '{search_term}':**\n\n"
            
            for user in users:
                user_id_result = user.get('user_id')
                username = user.get('username', 'N/A')
                first_name = user.get('first_name', 'Unknown')
                verified = user.get('verified', False)
                status = "✅ Verified" if verified else "❌ Not Verified"
                created_at = user.get('created_at', 'Unknown')
                
                results_text += f"**{first_name}** (@{username})\n"
                results_text += f"🆔 ID: `{user_id_result}`\n"
                results_text += f"🔒 Status: {status}\n"
                results_text += f"📅 Joined: {created_at}\n"
                results_text += f"Commands: `/verify {user_id_result}` | `/reject {user_id_result}`\n\n"
            
            await update.message.reply_text(results_text, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error in admin_search_user_command: {e}")
            await update.message.reply_text("❌ Error searching for users.")

    async def admin_auto_verify_stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show auto-verification statistics and settings"""
        try:
            user_id = update.effective_user.id
            
            if not await self._is_admin(user_id):
                await update.message.reply_text("❌ Access denied. Admin only.")
                return
            
            # Get today's auto-verification stats
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
            
            result = await db_manager.execute_query(query, ('approved', True, today), fetch=True)
            today_auto_verified = result[0]['count'] if result else 0
            
            # Get total auto-verification stats
            if BotConfig.DATABASE_TYPE == 'postgresql':
                total_query = '''
                    SELECT COUNT(*) as count FROM verification_requests 
                    WHERE auto_verified = %s
                '''
            else:
                total_query = '''
                    SELECT COUNT(*) as count FROM verification_requests 
                    WHERE auto_verified = ?
                '''
            
            total_result = await db_manager.execute_query(total_query, (True,), fetch=True)
            total_auto_verified = total_result[0]['count'] if total_result else 0
            
            # Format stats
            stats_text = f"""🤖 **Auto-Verification Statistics**

📊 **Today's Stats:**
✅ Auto-verified today: {today_auto_verified}
📈 Daily limit: {BotConfig.DAILY_AUTO_APPROVAL_LIMIT}
📉 Remaining: {max(0, BotConfig.DAILY_AUTO_APPROVAL_LIMIT - today_auto_verified)}

📈 **Overall Stats:**
🎯 Total auto-verified: {total_auto_verified}

⚙️ **Settings:**
🔧 Auto-verify enabled: {'✅ Yes' if BotConfig.AUTO_VERIFY_ENABLED else '❌ No'}
🕐 Business hours only: {'✅ Yes' if BotConfig.AUTO_VERIFY_BUSINESS_HOURS_ONLY else '❌ No'}
⏰ Business hours: {BotConfig.BUSINESS_HOURS_START}:00 - {BotConfig.BUSINESS_HOURS_END}:00
📊 Daily limit: {BotConfig.DAILY_AUTO_APPROVAL_LIMIT}
💳 Min UID length: {BotConfig.MIN_UID_LENGTH}
💳 Max UID length: {BotConfig.MAX_UID_LENGTH}"""
            
            await update.message.reply_text(stats_text, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error in admin_auto_verify_stats_command: {e}")
            await update.message.reply_text("❌ Error retrieving auto-verification stats.")

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
            per_message=False,
            per_chat=True,
            per_user=False,
        )
        
        # Conversation handler for admin functions
        admin_conv = ConversationHandler(
            entry_points=[
                CommandHandler("broadcast", self.handle_broadcast),
                CommandHandler("lookup", self.handle_user_lookup)
            ],
            states={
                BROADCAST_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_broadcast_message)],
                USER_LOOKUP: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_lookup_user)],
            },
            fallbacks=[CommandHandler("cancel", self.cancel)],
            per_message=False,
            per_chat=True,
            per_user=False,
        )
        
        # User commands
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("vipsignals", self.vip_signals_command))
        self.application.add_handler(CommandHandler("myaccount", self.my_account_command))
        self.application.add_handler(CommandHandler("support", self.support_command))
        self.application.add_handler(CommandHandler("stats", self.stats_command))
        self.application.add_handler(CommandHandler("howitworks", self.how_it_works))
        self.application.add_handler(CommandHandler("menu", self.menu_command))
        self.application.add_handler(CommandHandler("getmyid", get_my_id_command))
        
        # Admin commands
        self.application.add_handler(CommandHandler("admin", self.admin_command))
        self.application.add_handler(CommandHandler("verify", self.admin_verify_command))
        self.application.add_handler(CommandHandler("reject", self.admin_reject_command))
        self.application.add_handler(CommandHandler("queue", self.admin_queue_command))
        self.application.add_handler(CommandHandler("admin_verify", self.admin_verify_command))
        self.application.add_handler(CommandHandler("admin_reject", self.admin_reject_command))
        self.application.add_handler(CommandHandler("admin_queue", self.admin_queue_command))
        self.application.add_handler(CommandHandler("admin_broadcast", self.admin_broadcast_command))
        self.application.add_handler(CommandHandler("admin_recent_activity", self.admin_recent_activity_command))
        self.application.add_handler(CommandHandler("admin_search_user", self.admin_search_user_command))
        self.application.add_handler(CommandHandler("admin_auto_verify_stats", self.admin_auto_verify_stats_command))
        self.application.add_handler(CommandHandler("broadcast", self.handle_broadcast))
        self.application.add_handler(CommandHandler("lookup", self.handle_user_lookup))
        self.application.add_handler(CommandHandler("searchuser", self.admin_search_user_command))
        self.application.add_handler(CommandHandler("activity", self.admin_recent_activity_command))
        self.application.add_handler(CommandHandler("autostats", self.admin_auto_verify_stats_command))
        self.application.add_handler(CommandHandler("chathistory", admin_chat_history_command))
        
        # Add conversation handlers FIRST (higher priority)
        self.application.add_handler(verification_conv)
        self.application.add_handler(admin_conv)
        
        # Specific callback handlers
        self.application.add_handler(CallbackQueryHandler(self.contact_support, pattern='^contact_support$'))
        self.application.add_handler(CallbackQueryHandler(self.button_callback))
        
        # Add text, photo, and document handlers (lower priority)
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
        # Initialize the application
        await self.application.initialize()
        await self.application.start()
        
        # Set webhook
        await self.application.bot.set_webhook(
            url=self.webhook_url + self.webhook_path,
            allowed_updates=["message", "callback_query"]
        )
        
        # Start webhook server using the application's built-in method
        from aiohttp import web
        import telegram
        
        # Create webhook handler
        async def webhook_handler(request):
            """Handle incoming webhook requests"""
            try:
                data = await request.json()
                update = telegram.Update.de_json(data, self.application.bot)
                if update:
                    await self.application.update_queue.put(update)
                return web.Response(status=200)
            except Exception as e:
                logger.error(f"Error processing webhook: {e}")
                return web.Response(status=500)
        
        # Create health check handler
        async def health_check(request):
            """Health check endpoint"""
            return web.Response(text="OK", status=200)
        
        # Create method not allowed handler
        async def method_not_allowed(request):
            """Handle unsupported HTTP methods"""
            return web.Response(text="Method Not Allowed", status=405)
        
        # Create and start the web server
        app = web.Application()
        app.router.add_post(self.webhook_path, webhook_handler)
        app.router.add_get("/health", health_check)
        app.router.add_get(self.webhook_path, method_not_allowed)
        app.router.add_route("*", "/{path:.*}", method_not_allowed)
        
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", self.webhook_port)
        await site.start()
        
        logger.info("✅ Webhook server started successfully")
        
        # Keep the application running
        try:
            import signal
            import asyncio
            
            def signal_handler(signum, frame):
                logger.info("Received shutdown signal")
                
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
            
            # Keep running until interrupted
            while True:
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("Shutting down webhook server...")
            await runner.cleanup()
            await self.application.stop()
            await self.application.shutdown()

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
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except RuntimeError as e:
        if "Cannot close a running event loop" in str(e):
            logger.info("Bot stopped gracefully")
        else:
            logger.error(f"Runtime error: {e}")
            raise
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise