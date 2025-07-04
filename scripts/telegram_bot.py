import logging
import asyncio
import os
import sys
import re
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram.error import TelegramError

# Add parent directory to path to import config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import BotConfig
from database.db_manager import db_manager

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot Configuration from environment variables
BOT_TOKEN = BotConfig.BOT_TOKEN
BROKER_LINK = BotConfig.BROKER_LINK
PREMIUM_CHANNEL_ID = BotConfig.PREMIUM_CHANNEL_ID
PREMIUM_CHANNEL_LINK = f"https://t.me/c/{BotConfig.PREMIUM_CHANNEL_ID.replace('-100', '')}"
PREMIUM_GROUP_LINK = "https://t.me/+LTnKwBO54DRiOTNk"  # Premium group link
ADMIN_USERNAME = BotConfig.ADMIN_USERNAME
ADMIN_USER_ID = int(BotConfig.ADMIN_USER_ID) if BotConfig.ADMIN_USER_ID.isdigit() else 123456789

# Database setup
def init_database():
    """Initialize database using the database manager"""
    db_manager.init_database()

def is_admin(user_id):
    """Check if user is admin"""
    return str(user_id) == str(BotConfig.ADMIN_USER_ID)

async def get_user_data(user_id):
    """Get user data from database"""
    if BotConfig.DATABASE_TYPE == 'postgresql':
        query = 'SELECT * FROM users WHERE user_id = %s'
    else:
        query = 'SELECT * FROM users WHERE user_id = ?'
    
    result = await db_manager.execute_query(query, (user_id,), fetch=True)
    return result[0] if result else None

async def update_user_data(user_id, **kwargs):
    """Update user data in database"""
    if not kwargs:
        return
    
    # Build dynamic update query
    set_clause = ', '.join([f"{key} = {'%s' if BotConfig.DATABASE_TYPE == 'postgresql' else '?'}" for key in kwargs.keys()])
    values = list(kwargs.values()) + [user_id]
    
    if BotConfig.DATABASE_TYPE == 'postgresql':
        query = f"UPDATE users SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE user_id = %s"
    else:
        query = f"UPDATE users SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?"
    
    await db_manager.execute_query(query, values)

async def create_user(user_id, username, first_name):
    """Create new user in database"""
    if BotConfig.DATABASE_TYPE == 'postgresql':
        query = '''
            INSERT INTO users (user_id, username, first_name, created_at, updated_at)
            VALUES (%s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT (user_id) DO UPDATE SET
            username = EXCLUDED.username,
            first_name = EXCLUDED.first_name,
            updated_at = CURRENT_TIMESTAMP
        '''
    else:
        query = '''
            INSERT OR REPLACE INTO users (user_id, username, first_name, created_at, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        '''
    
    await db_manager.execute_query(query, (user_id, username, first_name))

async def log_interaction(user_id, interaction_type, interaction_data=""):
    """Log user interaction"""
    if BotConfig.DATABASE_TYPE == 'postgresql':
        query = '''
            INSERT INTO interactions (user_id, interaction_type, interaction_data)
            VALUES (%s, %s, %s)
        '''
    else:
        query = '''
            INSERT INTO interactions (user_id, interaction_type, interaction_data)
            VALUES (?, ?, ?)
        '''
    
    await db_manager.execute_query(query, (user_id, interaction_type, interaction_data))

# Removed duplicate is_admin function - using the one above

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
        # For SQLite, we'd need to get the last insert rowid differently
        return None

async def get_pending_verifications():
    """Get all pending verification requests"""
    if BotConfig.DATABASE_TYPE == 'postgresql':
        query = '''
            SELECT vr.id, vr.user_id, u.first_name, u.username, vr.uid, vr.created_at
            FROM verification_requests vr
            JOIN users u ON vr.user_id = u.user_id
            WHERE vr.status = %s
            ORDER BY vr.created_at ASC
        '''
    else:
        query = '''
            SELECT vr.id, vr.user_id, u.first_name, u.username, vr.uid, vr.created_at
            FROM verification_requests vr
            JOIN users u ON vr.user_id = u.user_id
            WHERE vr.status = ?
            ORDER BY vr.created_at ASC
        '''
    
    return await db_manager.execute_query(query, ('pending',), fetch=True)

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

# Auto-verification functions
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
        r'test',
        r'demo',
        r'sample',
        r'example',
        r'fake',
        r'trial',
        r'temp',
        r'123456',
        r'000000',
        r'111111',
        r'999999',
    
    # Sequential patterns
        r'012345',
        r'123457',
        r'234567',
        r'345678',
        r'456789',
        r'567890',
        r'098765',
        r'987654',
    
    # Repeated patterns
        r'222222',
        r'333333',
        r'444444',
        r'555555',
        r'666666',
        r'777777',
        r'888888',
        r'aaaaaa',
        r'bbbbbb',
    
    # Common test/placeholder text
        r'lorem',
        r'ipsum',
        r'placeholder',
        r'dummy',
        r'mock',
        r'stub',
        r'testing',
        r'debug',
        r'dev',
        r'sandbox',
    
    # Default/admin patterns
        r'admin',
        r'default',
        r'guest',
        r'user',
        r'anonymous',
        r'null',
        r'undefined',
        r'empty',
        r'blank',
    
    # Keyboard patterns
        r'qwerty',
        r'asdfgh',
        r'zxcvbn',
        r'qaz',
        r'wsx',
        r'edc',
    
    # Phone/ID patterns
        r'555-?0000',
        r'555-?1234',
        r'000-?0000',
        r'123-?4567',
        
        # Email patterns
        r'test@',
        r'demo@',
        r'sample@',
        r'example@',
        r'fake@',
        r'noreply@',
        r'donotreply@',
        
        # Date patterns (obviously fake)
        r'01/01/1900',
        r'12/31/9999',
        r'01-01-0001',
        r'1900-01-01',
        r'9999-12-31',
        
        # Generic/template patterns
        r'template',
        r'generic',
        r'boilerplate',
        r'prototype',
        r'draft',
        r'preliminary',
        r'provisional',
        
        # Development/testing environments
        r'localhost',
        r'127\.0\.0\.1',
        r'dev\..*',
        r'test\..*',
        r'staging\..*',
        r'beta\..*',
        r'alpha\..*'
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
    
    result = await db_manager.execute_query(query, ('approved', True, today), fetch=True)
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
                         current_flow='verified',
                         verification_status='approved')
        
        # Get user info for personalized message
        user_data = await get_user_data(user_id)
        first_name = user_data[2] if user_data else "there"
        
        # Send immediate premium access message
        success_text = f"""🎉 **Verification Approved - Auto-Verified!**

Congratulations {first_name}! Your verification has been automatically approved.

✅ **Status:** Verified
💳 **UID:** {uid}
🤖 **Method:** Auto-verification

🔗 **Premium Channels & Groups:**
• Premium Signals: {PREMIUM_GROUP_LINK}
• VIP Trading Group: {PREMIUM_GROUP_LINK}

🚀 **You now have access to:**
• Daily VIP trading signals
• Expert market analysis
• Private trader community
• Exclusive bonuses up to $500
• Automated trading strategies

**Ready to start trading? Click below to continue!**"""
        
        keyboard = [
            [InlineKeyboardButton("📈 Start Trading", callback_data="start_trading")],
            [InlineKeyboardButton("📞 Contact Support", callback_data="contact_support"),
             InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Send success message to user
        await context.bot.send_message(
            chat_id=user_id,
            text=success_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
        # Log the auto-verification success message
        await db_manager.log_chat_message(user_id, "bot_response", success_text, {
            "action": "auto_verification_success",
            "verification_method": "auto",
            "uid": uid,
            "premium_links_provided": True,
            "buttons": ["Start Trading", "Contact Support", "Main Menu"]
        })
        
        logger.info(f"Auto-verified user {user_id} with UID {uid} and provided premium access")
        return True, request_id
        
    except Exception as e:
        logger.error(f"Failed to auto-verify user {user_id}: {e}")
        return False, None

# Command to get user ID for admin setup
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
    await db_manager.log_chat_message(user_id, "command", "/getmyid", {
        "username": username,
        "first_name": first_name,
        "current_admin_status": is_admin(user_id)
    })
    
    await db_manager.log_chat_message(user_id, "bot_response", id_info_text, {
        "action": "user_id_info",
        "user_id_revealed": user_id
    })

# Flow 1: Welcome & Hook
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    username = user.username or ""
    first_name = user.first_name or "there"
    
    # Create or update user
    await create_user(user_id, username, first_name)
    await log_interaction(user_id, "start_command")
    
    # Log chat history
    await db_manager.log_chat_message(user_id, "command", "/start", {
        "username": username,
        "first_name": first_name,
        "is_admin": is_admin(user_id)
    })
    
    # Check if user is admin and provide different response
    if is_admin(user_id):
        admin_welcome_text = f"""🔧 **Admin Panel - Welcome {first_name}!**

**Bot Status:** ✅ Running | **Database:** ✅ Connected
**Broker Link:** {BROKER_LINK[:50]}...
**Premium Group:** {PREMIUM_GROUP_LINK}

🎯 **Admin Dashboard:**"""
        
        keyboard = [
            [InlineKeyboardButton("📋 Pending Queue", callback_data="admin_queue"),
             InlineKeyboardButton("📊 User Activity", callback_data="admin_activity")],
            [InlineKeyboardButton("📢 Broadcast Message", callback_data="admin_broadcast"),
             InlineKeyboardButton("👥 All Users", callback_data="admin_users")],
            [InlineKeyboardButton("🔍 Search User", callback_data="admin_search"),
             InlineKeyboardButton("📈 Bot Stats", callback_data="admin_stats")],
            [InlineKeyboardButton("⚙️ Settings", callback_data="admin_settings"),
             InlineKeyboardButton("🔄 Restart Bot", callback_data="admin_restart")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            admin_welcome_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
        # Log admin welcome
        await db_manager.log_chat_message(user_id, "bot_response", admin_welcome_text, {
            "action": "admin_welcome",
            "admin_auto_detected": True,
            "buttons": ["Pending Queue", "User Activity", "Broadcast Message", "All Users", "Search User", "Bot Stats", "Settings", "Restart Bot"]
        })
        
        return
    
    # Regular user welcome
    welcome_text = f"""Heyy {first_name}! 👋

Welcome to OPTRIXTRADES

You're one step away from unlocking high-accuracy trading signals, expert strategies, and real trader bonuses, completely free.

Here's what you get as a member:

✅ Daily VIP trading signals
✅ Strategy sessions from 6-figure traders  
✅ Access to our private trader community
✅ Exclusive signup bonuses (up to $500)
✅ Automated trading bot – trade while you sleep

Choose your next step:"""

    keyboard = [
        [InlineKeyboardButton("🚀 Request Premium Group Access", callback_data="request_group_access")],
        [InlineKeyboardButton("➡️ Get Free VIP Access", callback_data="get_vip_access")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)
    
    # Log bot response
    await db_manager.log_chat_message(user_id, "bot_response", welcome_text, {
        "buttons": ["Request Premium Group Access", "Get Free VIP Access"]
    })

# Flow 2: Activation Instructions
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
    
    activation_text = f"""To activate your free access and join our VIP Signal Channel, follow these steps:

1️⃣ Click the link below to register with our official broker partner
{BROKER_LINK}

2️⃣ Deposit $20 or more

3️⃣ Send your proof of deposit

Once your proof has been confirmed, your access will be unlocked immediately.

The more you deposit, the more powerful your AI access:

✅ $100+ → Full access to OPTRIX Web AI Portal, Live Signals & AI tools

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

We earn a small commission from the broker through your trading volume, not your money. So we are more focused on your success - the more you win, the better for both of us. ✅

Want to unlock even higher-tier bonuses or full bot access?
Send "UPGRADE" """

    await context.bot.send_message(chat_id=query.from_user.id, text=second_part)
    
    # Log second part
    await db_manager.log_chat_message(user_id, "bot_response", second_part)

# Flow 3: Confirmation
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
    
    confirmation_text = """Send in your UID and deposit screenshot to gain access to OPTRIXTRADES premium signal channel.

BONUS: We're hosting a live session soon with exclusive insights. Stay tuned. Get early access now into our premium channel - only limited slots are available! 🚀"""

    # Send new message instead of editing to preserve chat history
    await context.bot.send_message(
        chat_id=user_id,
        text=confirmation_text
    )
    
    # Log bot response
    await db_manager.log_chat_message(user_id, "bot_response", confirmation_text)
    
    instruction_text = "Please send your UID and deposit screenshot as separate messages."
    await context.bot.send_message(
        chat_id=user_id, 
        text=instruction_text
    )
    
    # Log instruction
    await db_manager.log_chat_message(user_id, "bot_response", instruction_text)

# Handle text messages (UID, UPGRADE, etc.)
async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    message_text = update.message.text.strip()
    text = message_text.upper()
    
    user_data = await get_user_data(user_id)
    if not user_data:
        await start_command(update, context)
        return
    
    await log_interaction(user_id, "text_message", message_text)
    
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
        
    elif text == "UPGRADE":
        await handle_upgrade_request(update, context)
    elif user_data[3] == 'confirmation':  # current_flow is confirmation
        # Assume this is a UID
        await update_user_data(user_id, uid=message_text)
        response_text = "UID received! Now please send your deposit screenshot."
        await update.message.reply_text(response_text)
        
        # Log bot response
        await db_manager.log_chat_message(user_id, "bot_response", response_text, {"uid": message_text})
    else:
        # Default response for unrecognized messages
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        keyboard = [
            [InlineKeyboardButton("📞 Contact Support", callback_data="contact_support")],
            [InlineKeyboardButton("❓ Get Help", callback_data="help_signup")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        response_text = "I didn't understand that. How can I help you?"
        await update.message.reply_text(response_text, reply_markup=reply_markup)
        
        # Log bot response
        await db_manager.log_chat_message(user_id, "bot_response", response_text, {
            "buttons": ["Contact Support", "Get Help"]
        })

# Handle photo messages (deposit screenshots)
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data = await get_user_data(user_id)
    
    # Check if user is admin first
    if is_admin(user_id):
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
    
    if not user_data:
        await update.message.reply_text("Please start with /start first.")
        return
    
    await log_interaction(user_id, "photo_upload", "deposit_screenshot")
    
    if user_data[3] == 'confirmation':  # current_flow is confirmation
        # Get the user's UID from database
        uid = user_data[6] if user_data[6] else "Not provided"
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
        
        # Manual verification process (original logic)
        # Create verification request
        from database.connection import create_verification_request as async_create_verification_request
        await async_create_verification_request(user_id, uid, screenshot_file_id)
        
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
• Status: Under Review (Manual)
• Reason: {auto_verify_reason}

⏳ Your verification request has been submitted to our admin team. You'll receive a notification once your deposit is verified.

🕐 **Processing Time:** Usually within 2-4 hours

Thank you for your patience! 🙏"""
        
        await update.message.reply_text(confirmation_text, parse_mode='Markdown')
        
        # Notify admin about new verification request
        admin_notification = f"""🔔 **NEW VERIFICATION REQUEST**

👤 **User:** {user_data[2]} (@{user_data[1] or 'No username'})
🆔 **User ID:** {user_id}
💳 **UID:** {uid}
📸 **Screenshot:** Uploaded
⏰ **Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Use /verify {user_id} to approve or /reject {user_id} to reject."""
        
        try:
            await context.bot.send_photo(
                chat_id=BotConfig.ADMIN_USER_ID,
                photo=screenshot_file_id,
                caption=admin_notification,
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Failed to notify admin: {e}")
        
        # Log chat history for photo upload
        await db_manager.log_chat_message(user_id, "user_action", "Uploaded deposit screenshot", {
            "action_type": "photo_upload",
            "uid": uid,
            "file_id": screenshot_file_id
        })
        
        # Log bot response
        await db_manager.log_chat_message(user_id, "bot_response", confirmation_text, {
            "action": "verification_submitted",
            "uid": uid
        })
        
        # Update user flow to pending verification
        await update_user_data(user_id, current_flow='pending_verification')
        
        # Provide next steps to user
        next_steps_text = """🎯 **What's Next?**

⏳ **Your verification is being reviewed**
• Our admin team will check your deposit
• You'll get notified once approved
• Usually takes 2-4 hours

🚀 **While you wait:**
• Join our premium group for trading tips
• Contact support if you have questions

📞 **Need help?** Contact @{}""".format(BotConfig.ADMIN_USERNAME)
        
        keyboard = [
            [InlineKeyboardButton("🔗 Join Premium Group", callback_data="request_group_access")],
            [InlineKeyboardButton("📞 Contact Support", callback_data="contact_support")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            next_steps_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
        # Log the next steps message
        await db_manager.log_chat_message(user_id, "bot_response", next_steps_text, {
            "action": "verification_next_steps",
            "buttons": ["Join Premium Group", "Contact Support"]
        })
        
        # Send enhanced follow-up message with timeline and status tracking
        follow_up_text = f"""⏰ **Verification Timeline & Status:**

🔄 **Step 1:** Screenshot submitted ✅
🔄 **Step 2:** Admin review (2-4 hours) ⏳
🔄 **Step 3:** Approval notification 📧
🔄 **Step 4:** Premium access granted 🎯

📋 **Current Status:** PENDING REVIEW

🔔 **Important:** You will receive an automatic notification when your verification is:
✅ **APPROVED** - Instant premium access
❌ **REJECTED** - Resubmission instructions

⚠️ **Do not submit multiple screenshots - this may delay your verification!**"""
        
        # Add helpful action buttons including main menu
        keyboard = [
            [InlineKeyboardButton("❓ Verification Help", callback_data="verification_help")],
            [InlineKeyboardButton("📞 Contact Support", callback_data="contact_support")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(
            chat_id=user_id,
            text=follow_up_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
        # Log follow-up message
        await db_manager.log_chat_message(user_id, "bot_response", follow_up_text, {
            "action": "verification_timeline",
            "status": "pending_review",
            "buttons": ["Verification Help", "Contact Support"]
        })
        
        # Update user flow to indicate they're waiting for verification
        await update_user_data(user_id, current_flow='awaiting_verification')
            
    else:
        await update.message.reply_text("Please complete the registration process first by using /start")
        
        # Log chat history for invalid photo upload
        await db_manager.log_chat_message(user_id, "user_action", "Uploaded photo outside of flow", {
            "action_type": "invalid_photo_upload",
            "current_flow": user_data[3] if user_data else "unknown"
        })
        
        await db_manager.log_chat_message(user_id, "bot_response", "Please complete the registration process first by using /start", {
            "action": "invalid_photo_response"
        })

# Handle document uploads (PDF and image files)
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    document = update.message.document
    
    # Check if user is admin
    if is_admin(user_id):
        await update.message.reply_text("📄 Document received by admin.")
        return
    
    # Get user data
    user_data = await get_user_data(user_id)
    
    if user_data and user_data[3] == 'awaiting_deposit_screenshot':
        # Check if document is a valid format (PDF or image)
        file_name = document.file_name.lower() if document.file_name else ""
        mime_type = document.mime_type.lower() if document.mime_type else ""
        
        valid_formats = [
            'application/pdf',
            'image/jpeg',
            'image/jpg', 
            'image/png'
        ]
        
        valid_extensions = ['.pdf', '.jpg', '.jpeg', '.png']
        
        is_valid_format = (
            mime_type in valid_formats or 
            any(file_name.endswith(ext) for ext in valid_extensions)
        )
        
        if not is_valid_format:
            await update.message.reply_text(
                "❌ **Invalid file format!**\n\n"
                "Please upload one of these formats:\n"
                "📄 PDF files (.pdf)\n"
                "🖼️ Image files (.jpg, .jpeg, .png)\n\n"
                "Try uploading your deposit screenshot again.",
                parse_mode='Markdown'
            )
            return
        
        # Process the document as deposit proof
        file_info = await context.bot.get_file(document.file_id)
        
        # Create verification request
        from database.connection import create_verification_request as async_create_verification_request
        await async_create_verification_request(user_id, user_data[6] if user_data[6] else "Unknown", document.file_id)
        
        # Send confirmation to user
        await update.message.reply_text("📄 **Document Received Successfully!**\n\nYour deposit proof has been submitted for verification.")
        
        # Log the document submission
        await db_manager.log_chat_message(user_id, "user_action", f"Uploaded document: {file_name}", {
            "action_type": "document_upload",
            "file_type": mime_type,
            "file_name": file_name,
            "file_id": document.file_id
        })
        
        # Notify admin with document
        first_name = update.effective_user.first_name or "User"
        username = update.effective_user.username or "No username"
        uid = user_data[2] if user_data else "Unknown"
        
        admin_notification = f"""🔔 **NEW VERIFICATION REQUEST**

👤 **User:** {first_name} (@{username})
🆔 **User ID:** `{user_id}`
💳 **UID:** {uid}
📄 **Document:** {file_name}
📊 **Type:** {mime_type}

**Commands:**
• `/verify {user_id}` - Approve
• `/reject {user_id} [reason]` - Reject"""
        
        await context.bot.send_document(
            chat_id=ADMIN_USER_ID,
            document=document.file_id,
            caption=admin_notification,
            parse_mode='Markdown'
        )
        
        # Log admin notification
        await db_manager.log_chat_message(user_id, "bot_response", "Document submitted for admin review", {
            "action": "admin_notification_sent",
            "admin_id": ADMIN_USER_ID,
            "file_type": mime_type
        })
        
        # Provide next steps to user
        next_steps_text = """🎯 **What's Next?**

⏳ **Your verification is being reviewed**
• Our admin team will check your deposit
• You'll get notified once approved
• Usually takes 2-4 hours

🚀 **While you wait:**
• Join our premium group for trading tips
• Contact support if you have questions

📞 **Need help?** Contact @{}""".format(BotConfig.ADMIN_USERNAME)
        
        keyboard = [
            [InlineKeyboardButton("🔗 Join Premium Group", callback_data="request_group_access")],
            [InlineKeyboardButton("📞 Contact Support", callback_data="contact_support")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            next_steps_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
        # Log the next steps message
        await db_manager.log_chat_message(user_id, "bot_response", next_steps_text, {
            "action": "verification_next_steps",
            "buttons": ["Join Premium Group", "Contact Support"]
        })
        
        # Send enhanced follow-up message with timeline and status tracking
        follow_up_text = f"""⏰ **Verification Timeline & Status:**

🔄 **Step 1:** Document submitted ✅
🔄 **Step 2:** Admin review (2-4 hours) ⏳
🔄 **Step 3:** Approval notification 📧
🔄 **Step 4:** Premium access granted 🎯

📋 **Current Status:** PENDING REVIEW

🔔 **Important:** You will receive an automatic notification when your verification is:
✅ **APPROVED** - Instant premium access
❌ **REJECTED** - Resubmission instructions

⚠️ **Do not submit multiple documents - this may delay your verification!**"""
        
        # Add helpful action buttons including main menu
        keyboard = [
            [InlineKeyboardButton("❓ Verification Help", callback_data="verification_help")],
            [InlineKeyboardButton("📞 Contact Support", callback_data="contact_support")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(
            chat_id=user_id,
            text=follow_up_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
        # Log follow-up message
        await db_manager.log_chat_message(user_id, "bot_response", follow_up_text, {
            "action": "verification_timeline",
            "status": "pending_review",
            "buttons": ["Verification Help", "Contact Support", "Main Menu"]
        })
        
        # Update user flow to indicate they're waiting for verification
        await update_user_data(user_id, current_flow='awaiting_verification')
            
    else:
        await update.message.reply_text("Please complete the registration process first by using /start")
        
        # Log chat history for invalid document upload
        await db_manager.log_chat_message(user_id, "user_action", "Uploaded document outside of flow", {
            "action_type": "invalid_document_upload",
            "current_flow": user_data[3] if user_data else "unknown",
            "file_name": document.file_name if document.file_name else "unknown"
        })
        
        await db_manager.log_chat_message(user_id, "bot_response", "Please complete the registration process first by using /start", {
            "action": "invalid_document_response"
        })

# Handle upgrade requests
async def handle_upgrade_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await log_interaction(user_id, "upgrade_request")
    
    # Log chat history
    await db_manager.log_chat_message(user_id, "user_message", "UPGRADE", {
        "action_type": "upgrade_request"
    })
    
    upgrade_text = f"""🔥 UPGRADE REQUEST RECEIVED

For premium upgrade options and full bot access, please contact our support team directly.

Our team will help you unlock:
🚀 Advanced AI trading algorithms
💎 VIP-only trading signals  
📈 Personal trading mentor
💰 Higher deposit bonuses

Contact: @{ADMIN_USERNAME}"""

    await update.message.reply_text(upgrade_text)
    
    # Log bot response
    await db_manager.log_chat_message(user_id, "bot_response", upgrade_text, {
        "action": "upgrade_response",
        "admin_contact": ADMIN_USERNAME
    })

# Help handlers
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

1. Click this link: {BROKER_LINK}
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

# Add this after the existing callback handlers, before the button_callback function

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

# New handler for group access request
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
1. Register with our broker: {BROKER_LINK[:50]}...
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

# Admin callback handlers
async def handle_admin_queue_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if not is_admin(user_id):
        await context.bot.send_message(chat_id=query.message.chat_id, text="❌ You don't have permission to use this command.")
        return
    
    pending_requests = await get_pending_verifications()
    
    if not pending_requests:
        queue_text = "✅ No pending verification requests."
    else:
        queue_text = "📋 **Pending Verification Queue:**\n\n"
        
        for req in pending_requests:
            req_id, user_id_req, first_name, username, uid, created_at = req
            username_display = f"@{username}" if username else "No username"
            queue_text += f"**#{req_id}** - {first_name} ({username_display})\n"
            queue_text += f"🆔 User ID: `{user_id_req}`\n"
            queue_text += f"💳 UID: {uid}\n"
            queue_text += f"⏰ Submitted: {created_at}\n"
            queue_text += f"**Commands:** `/verify {user_id_req}` | `/reject {user_id_req}`\n\n"
    
    # Add admin dashboard button to preserve menu
    keyboard = [[InlineKeyboardButton("⬅️ Back to Admin Dashboard", callback_data="admin_dashboard")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(chat_id=query.message.chat_id, text=queue_text, reply_markup=reply_markup, parse_mode='Markdown')

async def handle_admin_activity_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    
    recent_activity = await db_manager.execute_query(activity_query, (10,), fetch=True)
    
    if not recent_activity:
        activity_text = "📊 No recent activity found."
    else:
        activity_text = "📊 **Recent Activity (Last 10):**\n\n"
        
        for activity in recent_activity:
            user_id_act, first_name, msg_type, msg_content, created_at = activity
            # Truncate long messages
            content_preview = msg_content[:50] + "..." if len(msg_content) > 50 else msg_content
            activity_text += f"👤 {first_name} (`{user_id_act}`)\n"
            activity_text += f"📝 {msg_type}: {content_preview}\n"
            activity_text += f"⏰ {created_at}\n\n"
    
    # Add admin dashboard button to preserve menu
    keyboard = [[InlineKeyboardButton("⬅️ Back to Admin Dashboard", callback_data="admin_dashboard")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(chat_id=query.message.chat_id, text=activity_text, reply_markup=reply_markup, parse_mode='Markdown')

# New handler for verification help
async def handle_verification_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
• Approval typically takes 2-24 hours

**Common reasons for rejection:**
❌ Screenshot is unclear or blurry
❌ Deposit amount is less than $20 minimum
❌ Screenshot doesn't show transaction confirmation
❌ Wrong broker platform used

**Tips for faster approval:**
✅ Use clear, high-quality screenshots
✅ Ensure all transaction details are visible
✅ Use the correct broker: {BROKER_LINK[:50]}...
✅ Wait for one verification before resubmitting

**Need immediate help?**
Contact: @{ADMIN_USERNAME}

**Your current status:** PENDING REVIEW"""
    
    await context.bot.send_message(
        chat_id=user_id,
        text=help_text,
        parse_mode='Markdown'
    )
    
    # Log bot response
    await db_manager.log_chat_message(user_id, "bot_response", help_text, {
        "action": "verification_help_response"
    })

# New handler for contact support
async def handle_contact_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    await log_interaction(user_id, "contact_support")
    
    # Log chat history
    await db_manager.log_chat_message(user_id, "user_action", "Clicked contact support", {
        "action_type": "button_click",
        "button_data": "contact_support"
    })
    
    response_text = f"Please contact our support team: @{BotConfig.ADMIN_USERNAME}"
    
    # Send new message instead of editing to preserve chat history
    await context.bot.send_message(
        chat_id=user_id,
        text=response_text
    )
    
    # Log bot response
    await db_manager.log_chat_message(user_id, "bot_response", response_text, {
        "action": "contact_support"
    })

# New handler for group join confirmation
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
    
    keyboard = [[InlineKeyboardButton("🚀 Start Trading Journey", callback_data="get_vip_access")]]
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

# Callback query handler
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    
    # Check if it's an admin callback
    admin_callbacks = [
        "admin_queue", "admin_activity", "admin_broadcast", "admin_users", 
        "admin_search", "admin_stats", "admin_settings", "admin_restart", "admin_dashboard"
    ]
    
    if data in admin_callbacks:
        await handle_admin_callbacks(update, context)
    elif data == "get_vip_access":
        await activation_instructions(update, context)
    elif data == "request_group_access":
        await handle_group_access_request(update, context)
    elif data == "confirm_group_joined":
        await handle_group_join_confirmation(update, context)
    elif data == "registered":
        await registration_confirmation(update, context)
    elif data == "help_signup":
        await help_signup(update, context)
    elif data == "help_deposit":
        await help_deposit(update, context)
    elif data == "contact_support":
        await handle_contact_support(update, context)
    elif data == "verification_help":
        await handle_verification_help(update, context)
    elif data == "not_interested":
        await handle_not_interested(update, context)
    elif data == "main_menu":
        await main_menu_callback(update, context)
    elif data == "start_trading":
        await start_trading_callback(update, context)
    elif data == "account_menu":
        await account_menu_callback(update, context)
    elif data == "help_menu":
        await help_menu_callback(update, context)
    elif data == "notification_settings":
        await notification_settings_callback(update, context)
    else:
        await query.answer("Unknown action")

# Menu Command
async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show main menu to user"""
    user = update.effective_user
    user_id = user.id
    first_name = user.first_name or "there"
    
    await log_interaction(user_id, "menu_command")
    
    # Get user data to check verification status
    user_data = await get_user_data(user_id)
    is_verified = user_data and user_data[4] == 1 if user_data else False
    
    menu_text = f"""🎯 **OPTRIXTRADES Main Menu**

Hi {first_name}! Welcome to your trading dashboard.

**Your Status:** {'✅ Verified' if is_verified else '⏳ Pending Verification'}

📋 **Available Options:**"""
    
    keyboard = [
        [InlineKeyboardButton("👤 Account Status", callback_data="account_menu"),
         InlineKeyboardButton("❓ Help & Support", callback_data="help_menu")],
        [InlineKeyboardButton("🔔 Notifications", callback_data="notification_settings"),
         InlineKeyboardButton("📞 Contact Support", callback_data="contact_support")]
    ]
    
    if is_verified:
        keyboard.insert(0, [InlineKeyboardButton("🔗 Join Premium Group", callback_data="request_group_access")])
    else:
        keyboard.insert(0, [InlineKeyboardButton("🚀 Get Verified", callback_data="get_vip_access")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        menu_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    # Log chat history
    await db_manager.log_chat_message(user_id, "command", "/menu", {
        "username": user.username or "",
        "first_name": first_name,
        "verification_status": "verified" if is_verified else "pending"
    })

# Menu Callback Handlers
async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle main menu callback"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    first_name = query.from_user.first_name or "there"
    
    # Get user data to check verification status
    user_data = await get_user_data(user_id)
    is_verified = user_data and user_data.get('deposit_confirmed') == 1 if user_data else False
    
    menu_text = f"""🎯 **OPTRIXTRADES Main Menu**

Hi {first_name}! Welcome to your trading dashboard.

**Your Status:** {'✅ Verified' if is_verified else '⏳ Pending Verification'}

📋 **Available Options:**"""
    
    keyboard = [
        [InlineKeyboardButton("👤 Account Status", callback_data="account_menu"),
         InlineKeyboardButton("❓ Help & Support", callback_data="help_menu")],
        [InlineKeyboardButton("🔔 Notifications", callback_data="notification_settings"),
         InlineKeyboardButton("📞 Contact Support", callback_data="contact_support")]
    ]
    
    if is_verified:
        keyboard.insert(0, [InlineKeyboardButton("🔗 Join Premium Group", callback_data="request_group_access")])
    else:
        keyboard.insert(0, [InlineKeyboardButton("🚀 Get Verified", callback_data="get_vip_access")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=menu_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def account_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle account menu callback"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user_data = await get_user_data(user_id)
    
    if not user_data:
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="❌ User data not found. Please use /start to register."
        )
        return
    
    username = user_data.get('username') or "Not set"
    first_name = user_data.get('first_name')
    current_flow = user_data.get('current_flow')
    is_verified = user_data.get('deposit_confirmed') == 1
    uid = user_data.get('uid') or "Not provided"
    
    status_text = f"""👤 **Account Information**

**Name:** {first_name}
**Username:** @{username}
**User ID:** {user_id}
**UID:** {uid}
**Status:** {'✅ Verified' if is_verified else '⏳ Pending Verification'}
**Current Flow:** {current_flow}

📊 **Account Actions:**"""
    
    keyboard = [
        [InlineKeyboardButton("🔄 Refresh Status", callback_data="account_menu")],
        [InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main_menu")]
    ]
    
    if not is_verified:
        keyboard.insert(0, [InlineKeyboardButton("🚀 Complete Verification", callback_data="get_vip_access")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=status_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def help_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle help menu callback"""
    query = update.callback_query
    await query.answer()
    
    help_text = f"""❓ **Help & Support Center**

🔍 **Common Questions:**
• How to get verified?
• How to deposit?
• How to join premium group?
• How to contact support?

📚 **Resources:**
• Verification guide
• Deposit instructions
• Trading tutorials
• FAQ section

📞 **Support Options:**"""
    
    keyboard = [
        [InlineKeyboardButton("❓ Verification Help", callback_data="verification_help"),
         InlineKeyboardButton("💰 Deposit Help", callback_data="help_deposit")],
        [InlineKeyboardButton("📝 Registration Help", callback_data="help_signup"),
         InlineKeyboardButton("📞 Contact Support", callback_data="contact_support")],
        [InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main_menu")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=help_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def start_trading_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle start trading callback"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    first_name = query.from_user.first_name or "there"
    
    # Log the action
    await log_interaction(user_id, "start_trading")
    
    trading_text = f"""📈 **Ready to Start Trading, {first_name}!**

🎯 **Your Trading Journey Begins:**

🔗 **Premium Group Access:**
• Join: {PREMIUM_GROUP_LINK}
• Get real-time signals
• Connect with expert traders

💰 **Trading Platform:**
• Login to your broker account: {BROKER_LINK}
• Start with recommended strategies
• Follow our daily signals

🚀 **Next Steps:**
1. Join the premium group
2. Set up your trading dashboard
3. Start following signals
4. Track your progress

**Ready to make your first trade?**"""
    
    keyboard = [
        [InlineKeyboardButton("🔗 Join Premium Group", callback_data="request_group_access")],
        [InlineKeyboardButton("💰 Open Trading Platform", url=BROKER_LINK)],
        [InlineKeyboardButton("📞 Contact Support", callback_data="contact_support"),
         InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=trading_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    # Log the response
    await db_manager.log_chat_message(user_id, "bot_response", trading_text, {
        "action": "start_trading_guide",
        "buttons": ["Join Premium Group", "Open Trading Platform", "Contact Support", "Main Menu"]
    })

async def notification_settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle notification settings callback"""
    query = update.callback_query
    await query.answer()
    
    settings_text = f"""🔔 **Notification Settings**

⚙️ **Current Settings:**
• Follow-up messages: ✅ Enabled
• Verification updates: ✅ Enabled
• Trading signals: ✅ Enabled
• Admin notifications: ✅ Enabled

📱 **Available Options:**

⚠️ **Note:** This feature is currently under development. All notifications are enabled by default to ensure you don't miss important updates.

💡 **Note:** All notifications are currently enabled to ensure you receive important updates."""
    
    keyboard = [
        [InlineKeyboardButton("🔄 Refresh Settings", callback_data="notification_settings")],
        [InlineKeyboardButton("📞 Request Feature", callback_data="contact_support")],
        [InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main_menu")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=settings_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# Admin Commands
async def admin_verify_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command to verify a user"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ You don't have permission to use this command.")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /verify <user_id>")
        return
    
    try:
        target_user_id = int(context.args[0])
        
        # Update user as verified
        await update_user_data(target_user_id, deposit_confirmed=True, current_flow='completed')
        
        # Update verification request status
        if BotConfig.DATABASE_TYPE == 'postgresql':
            query = '''
                UPDATE verification_requests 
                SET status = 'approved', admin_response = 'Manually approved by admin', updated_at = CURRENT_TIMESTAMP
                WHERE user_id = %s AND status = 'pending'
            '''
        else:
            query = '''
                UPDATE verification_requests 
                SET status = 'approved', admin_response = 'Manually approved by admin', updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ? AND status = 'pending'
            '''
        await db_manager.execute_query(query, (target_user_id,))
        
        # Get user data for notification
        user_data = await get_user_data(target_user_id)
        if user_data:
            # Notify user of approval with immediate premium access
            success_message = f"""🎉 **Verification Approved!**

Congratulations! Your deposit has been verified by our admin team.

**Welcome to OPTRIXTRADES Premium!**

You now have access to:
✅ Daily VIP trading signals
✅ Premium trading strategies
✅ Live trading sessions
✅ AI trading bot access

🔗 **Premium Channel:** {PREMIUM_CHANNEL_LINK}
🔗 **Premium Group:** {PREMIUM_GROUP_LINK}

📱 **Next Steps:**
1. Click the links above to join our premium channels
2. Start receiving daily trading signals
3. Access exclusive trading strategies

Your trading journey starts now! 🚀"""
            
            # Create action buttons for approved user
            keyboard = [
                [InlineKeyboardButton("📞 Contact Support", callback_data="contact_support")],
                [InlineKeyboardButton("🎯 Start Trading", callback_data="get_vip_access")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            try:
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text=success_message,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
                
                # Log the approval notification
                await db_manager.log_chat_message(target_user_id, "bot_response", success_message, {
                    "action": "verification_approved",
                    "approved_by_admin": user_id,
                    "buttons": ["Join Premium Group", "Contact Support", "Start Trading"]
                })
                await update.message.reply_text(f"✅ User {target_user_id} ({user_data[2]}) has been verified and notified.")
            except Exception as e:
                await update.message.reply_text(f"✅ User {target_user_id} verified, but notification failed: {e}")
        else:
            await update.message.reply_text(f"✅ User {target_user_id} verified, but user data not found.")
            
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID. Please provide a numeric user ID.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error verifying user: {e}")

async def admin_reject_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command to reject a user verification"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ You don't have permission to use this command.")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /reject <user_id> [reason]")
        return
    
    try:
        target_user_id = int(context.args[0])
        reason = " ".join(context.args[1:]) if len(context.args) > 1 else "Verification rejected by admin"
        
        # Update verification request status
        if BotConfig.DATABASE_TYPE == 'postgresql':
            query = '''
                UPDATE verification_requests 
                SET status = 'rejected', admin_response = %s, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = %s AND status = 'pending'
            '''
        else:
            query = '''
                UPDATE verification_requests 
                SET status = 'rejected', admin_response = ?, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ? AND status = 'pending'
            '''
        await db_manager.execute_query(query, (reason, target_user_id))
        
        # Get user data for notification
        user_data = await get_user_data(target_user_id)
        if user_data:
            # Notify user of rejection with helpful action buttons
            rejection_message = f"""❌ **Verification Rejected**

Unfortunately, your verification request has been rejected.

**Reason:** {reason}

📋 **Next Steps:**
• Review the rejection reason above
• Check our verification help guide
• Resubmit with correct information
• Contact support if you need assistance

💡 **Tip:** Most rejections are due to unclear screenshots or insufficient deposit amounts."""
            
            # Create action buttons for rejected user
            keyboard = [
                [InlineKeyboardButton("❓ Verification Help", callback_data="verification_help")],
                [InlineKeyboardButton("📞 Contact Support", callback_data="contact_support")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            try:
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text=rejection_message,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
                
                # Log the rejection notification
                await db_manager.log_chat_message(target_user_id, "bot_response", rejection_message, {
                    "action": "verification_rejected",
                    "rejected_by_admin": user_id,
                    "reason": reason,
                    "buttons": ["Verification Help", "Contact Support"]
                })
                await update.message.reply_text(f"❌ User {target_user_id} ({user_data[2]}) verification rejected and notified.")
            except Exception as e:
                await update.message.reply_text(f"❌ User {target_user_id} rejected, but notification failed: {e}")
        else:
            await update.message.reply_text(f"❌ User {target_user_id} rejected, but user data not found.")
            
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID. Please provide a numeric user ID.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error rejecting user: {e}")

async def admin_queue_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command to view pending verifications"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ You don't have permission to use this command.")
        return
    
    pending_requests = await get_pending_verifications()
    
    if not pending_requests:
        await update.message.reply_text("✅ No pending verification requests.")
        return
    
    queue_text = "📋 **Pending Verification Queue:**\n\n"
    
    for req in pending_requests:
        req_id, user_id_req, first_name, username, uid, created_at = req
        username_display = f"@{username}" if username else "No username"
        queue_text += f"**#{req_id}** - {first_name} ({username_display})\n"
        queue_text += f"🆔 User ID: `{user_id_req}`\n"
        queue_text += f"💳 UID: {uid}\n"
        queue_text += f"⏰ Submitted: {created_at}\n"
        queue_text += f"**Commands:** `/verify {user_id_req}` | `/reject {user_id_req}`\n\n"
    
    await update.message.reply_text(queue_text, parse_mode='Markdown')

async def admin_broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command to broadcast message to all users"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ You don't have permission to use this command.")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /broadcast <message>\n\nExample: /broadcast Hello everyone! New signals are available.")
        return
    
    message_text = " ".join(context.args)
    users = await get_all_active_users()
    
    if not users:
        await update.message.reply_text("❌ No active users found for broadcasting.")
        return
    
    # Create broadcast record
    if BotConfig.DATABASE_TYPE == 'postgresql':
        query = '''
            INSERT INTO broadcast_messages (message_text, total_users)
            VALUES (%s, %s) RETURNING id
        '''
        result = await db_manager.execute_query(query, (message_text, len(users)), fetch=True)
        broadcast_id = result[0]['id'] if result else None
    else:
        query = '''
            INSERT INTO broadcast_messages (message_text, total_users)
            VALUES (?, ?)
        '''
        await db_manager.execute_query(query, (message_text, len(users)))
        broadcast_id = None  # SQLite lastrowid not easily accessible through db_manager
    
    successful_sends = 0
    failed_sends = 0
    
    # Send broadcast message
    status_message = await update.message.reply_text(f"📡 Broadcasting to {len(users)} users...")
    
    for user_id_target, first_name in users:
        try:
            await context.bot.send_message(
                chat_id=user_id_target,
                text=f"📢 **OPTRIXTRADES Announcement**\n\n{message_text}",
                parse_mode='Markdown'
            )
            successful_sends += 1
            # Log broadcast message to each user's chat history
            await db_manager.log_chat_message(user_id_target, "broadcast", message_text, {
                "sent_by_admin": True,
                "admin_id": user_id
            })
        except Exception as e:
            failed_sends += 1
            logger.error(f"Failed to send broadcast to {user_id_target}: {e}")
    
    # Update broadcast record
    if broadcast_id:  # Only update if we have a valid broadcast_id
        if BotConfig.DATABASE_TYPE == 'postgresql':
            query = '''
                UPDATE broadcast_messages 
                SET sent_count = %s, failed_count = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            '''
        else:
            query = '''
                UPDATE broadcast_messages 
                SET sent_count = ?, failed_count = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            '''
        await db_manager.execute_query(query, (successful_sends, failed_sends, broadcast_id))
    
    # Send delivery confirmation to admin
    confirmation_text = f"""✅ **Broadcast Complete!**

📊 **Delivery Report:**
• Total Users: {len(users)}
• Successful: {successful_sends}
• Failed: {failed_sends}
• Success Rate: {(successful_sends/len(users)*100):.1f}%

📝 **Message:** {message_text[:100]}{'...' if len(message_text) > 100 else ''}"""
    
    await status_message.edit_text(confirmation_text, parse_mode='Markdown')

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

async def admin_recent_activity_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command to view recent activity across all users"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
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

# Admin callback handlers
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
        pending_requests = await get_pending_verifications()
        
        if not pending_requests:
            queue_text = "✅ No pending verification requests."
        else:
            queue_text = "📋 **Pending Verification Queue:**\n\n"
            
            for req in pending_requests[:5]:  # Show only first 5
                req_data = req
                req_id = req_data.get('id')
                user_id_req = req_data.get('user_id')
                first_name = req_data.get('first_name')
                username = req_data.get('username')
                uid = req_data.get('uid')
                created_at = req_data.get('created_at')
                username_display = f"@{username}" if username else "No username"
                queue_text += f"**#{req_id}** - {first_name} ({username_display})\n"
                queue_text += f"🆔 User ID: `{user_id_req}`\n"
                queue_text += f"💳 UID: {uid}\n"
                queue_text += f"⏰ Submitted: {created_at}\n\n"
            
            if len(pending_requests) > 5:
                queue_text += f"... and {len(pending_requests) - 5} more requests\n"
        
        keyboard = [
            [InlineKeyboardButton("🔄 Refresh", callback_data="admin_queue")],
            [InlineKeyboardButton("⬅️ Back to Dashboard", callback_data="admin_dashboard")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Edit the existing message instead of sending a new one to preserve chat history
        try:
            await query.edit_message_text(
                text=queue_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        except Exception as e:
            # If editing fails, send a new message
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=queue_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
    
    elif callback_data == "admin_activity":
        recent_activity = await db_manager.get_recent_activity(10)
        
        if not recent_activity:
            await context.bot.send_message(chat_id=query.message.chat_id, text="No recent activity found.")
            return
        
        activity_text = "📊 **Recent Activity (Last 10):**\n\n"
        
        for entry in recent_activity:
            user_id_entry = entry[1]
            timestamp = entry[2][:16]  # Truncate timestamp
            message_type = entry[3]
            content = entry[4][:30] + "..." if len(entry[4]) > 30 else entry[4]
            
            activity_text += f"👤 User {user_id_entry} | {timestamp}\n"
            activity_text += f"📝 {message_type}: {content}\n\n"
        
        keyboard = [
            [InlineKeyboardButton("🔄 Refresh", callback_data="admin_activity")],
            [InlineKeyboardButton("⬅️ Back to Dashboard", callback_data="admin_dashboard")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(chat_id=query.message.chat_id, text=activity_text, reply_markup=reply_markup)
    
    elif callback_data == "admin_broadcast":
        broadcast_text = "📢 **Broadcast Message**\n\nTo send a broadcast message, use:\n`/broadcast Your message here`\n\nExample:\n`/broadcast 🚀 New trading signals available!`"
        
        keyboard = [
            [InlineKeyboardButton("⬅️ Back to Dashboard", callback_data="admin_dashboard")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(chat_id=query.message.chat_id, text=broadcast_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    elif callback_data == "admin_users":
        users = await get_all_active_users()
        
        if not users:
            await context.bot.send_message(chat_id=query.message.chat_id, text="No active users found.")
            return
        
        users_text = f"👥 **All Users ({len(users)} total):**\n\n"
        
        for user_id_entry, first_name in users[:10]:  # Show only first 10
            users_text += f"👤 {first_name} (ID: {user_id_entry})\n"
        
        if len(users) > 10:
            users_text += f"\n... and {len(users) - 10} more users"
        
        keyboard = [
            [InlineKeyboardButton("🔄 Refresh", callback_data="admin_users")],
            [InlineKeyboardButton("⬅️ Back to Dashboard", callback_data="admin_dashboard")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(chat_id=query.message.chat_id, text=users_text, reply_markup=reply_markup)
    
    elif callback_data == "admin_stats":
        users = await get_all_active_users()
        pending = await get_pending_verifications()
        
        stats_text = f"📈 **Bot Statistics:**\n\n"
        stats_text += f"👥 Total Users: {len(users)}\n"
        stats_text += f"⏳ Pending Verifications: {len(pending)}\n"
        stats_text += f"✅ Bot Status: Running\n"
        stats_text += f"🔗 Broker Link: Active\n"
        stats_text += f"📊 Database: Connected"
        
        keyboard = [
            [InlineKeyboardButton("🔄 Refresh", callback_data="admin_stats")],
            [InlineKeyboardButton("⬅️ Back to Dashboard", callback_data="admin_dashboard")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(chat_id=query.message.chat_id, text=stats_text, reply_markup=reply_markup)
    
    elif callback_data == "admin_dashboard":
        # Return to main admin dashboard
        first_name = query.from_user.first_name or "Admin"
        
        admin_welcome_text = f"""🔧 **Admin Panel - Welcome {first_name}!**

**Bot Status:** ✅ Running | **Database:** ✅ Connected
**Broker Link:** {BROKER_LINK[:50]}...
**Premium Group:** {PREMIUM_GROUP_LINK}

🎯 **Admin Dashboard:**"""
        
        keyboard = [
            [InlineKeyboardButton("📋 Pending Queue", callback_data="admin_queue"),
             InlineKeyboardButton("📊 User Activity", callback_data="admin_activity")],
            [InlineKeyboardButton("📢 Broadcast Message", callback_data="admin_broadcast"),
             InlineKeyboardButton("👥 All Users", callback_data="admin_users")],
            [InlineKeyboardButton("🔍 Search User", callback_data="admin_search"),
             InlineKeyboardButton("📈 Bot Stats", callback_data="admin_stats")],
            [InlineKeyboardButton("⚙️ Settings", callback_data="admin_settings"),
             InlineKeyboardButton("🔄 Restart Bot", callback_data="admin_restart")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=admin_welcome_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    elif callback_data == "admin_settings":
        settings_text = f"""⚙️ **Bot Settings & Configuration**

🔧 **Current Configuration:**
• Bot Token: {BOT_TOKEN[:10]}...
• Admin ID: {ADMIN_USER_ID}
• Premium Channel: {PREMIUM_CHANNEL_ID}
• Premium Group: {PREMIUM_GROUP_LINK[:30]}...
• Broker Link: {BROKER_LINK[:30]}...

📊 **Database Status:** ✅ Connected
🤖 **Bot Status:** ✅ Running

⚠️ **Note:** Configuration changes require bot restart.

**Available Commands:**
• `/broadcast <message>` - Send message to all users
• `/verify <user_id>` - Approve verification
• `/reject <user_id> [reason]` - Reject verification"""
        
        keyboard = [
            [InlineKeyboardButton("🔄 Restart Bot", callback_data="admin_restart")],
            [InlineKeyboardButton("⬅️ Back to Dashboard", callback_data="admin_dashboard")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=settings_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    elif callback_data == "admin_search":
        search_text = """🔍 **Search User**

To search for a user, use one of these commands:

**Search by User ID:**
`/chathistory <user_id>`

**Search by Username:**
Use the format: `/searchuser @username`

**Examples:**
• `/chathistory 123456789` - View chat history
• `/searchuser @john_doe` - Search by username

📋 **What you can find:**
• User registration details
• Verification status
• Chat history
• Recent activity
• Deposit information"""
        
        keyboard = [
            [InlineKeyboardButton("👥 View All Users", callback_data="admin_users")],
            [InlineKeyboardButton("📊 User Activity", callback_data="admin_activity")],
            [InlineKeyboardButton("⬅️ Back to Dashboard", callback_data="admin_dashboard")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=search_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    elif callback_data == "admin_restart":
        restart_text = """🔄 **Bot Restart**

⚠️ **Warning:** Restarting the bot will:
• Stop all current operations
• Disconnect all users temporarily
• Reload configuration
• Clear temporary data

🔧 **To restart the bot:**
1. Stop the current process
2. Run the bot script again
3. Check logs for successful startup

📝 **Note:** This action should be performed manually from the server console."""
        
        keyboard = [
            [InlineKeyboardButton("⬅️ Back to Dashboard", callback_data="admin_dashboard")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=restart_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    else:
        await context.bot.send_message(chat_id=query.message.chat_id, text="⚠️ Unknown admin command!")

# Admin search user command
async def admin_search_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ You don't have permission to use this command.")
        return
    
    if not context.args:
        await update.message.reply_text(
            "🔍 **Search User Usage:**\n\n"
            "**Search by username:**\n"
            "`/searchuser @username`\n\n"
            "**Search by user ID:**\n"
            "`/searchuser 123456789`\n\n"
            "**Examples:**\n"
            "• `/searchuser @john_doe`\n"
            "• `/searchuser 987654321`",
            parse_mode='Markdown'
        )
        return
    
    search_term = context.args[0]
    
    # Remove @ if present for username search
    if search_term.startswith('@'):
        username = search_term[1:]
        # Search by username
        user_data = await db_manager.search_user_by_username(username)
        if not user_data:
            await update.message.reply_text(f"❌ No user found with username: @{username}")
            return
    else:
        # Try to search by user ID
        try:
            search_user_id = int(search_term)
            user_data = await get_user_data(search_user_id)
            if not user_data:
                await update.message.reply_text(f"❌ No user found with ID: {search_user_id}")
                return
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID format. Please use numbers only.")
            return
    
    # Extract user information
    found_user_id, first_name, uid, current_flow, username_db, created_at = user_data
    username_display = f"@{username_db}" if username_db else "No username"
    
    # Check verification status
    verification_status = "❌ Not Verified"
    pending_verification = await db_manager.get_verification_request(found_user_id)
    if pending_verification:
        verification_status = "⏳ Pending Verification"
    elif await db_manager.is_user_verified(found_user_id):
        verification_status = "✅ Verified"
    
    # Get recent activity count
    recent_activity = await db_manager.get_recent_activity_for_user(found_user_id, 5)
    activity_count = len(recent_activity) if recent_activity else 0
    
    user_info = f"""👤 **User Information**

🆔 **User ID:** `{found_user_id}`
👤 **Name:** {first_name}
📱 **Username:** {username_display}
💳 **UID:** {uid if uid else 'Not provided'}
📊 **Status:** {verification_status}
🔄 **Current Flow:** {current_flow if current_flow else 'None'}
📅 **Joined:** {created_at if created_at else 'Unknown'}
📈 **Recent Activity:** {activity_count} messages

**Available Actions:**
• `/verify {found_user_id}` - Approve verification
• `/reject {found_user_id} [reason]` - Reject verification
• `/chathistory {found_user_id}` - View chat history"""
    
    await update.message.reply_text(user_info, parse_mode='Markdown')

# Admin auto-verification statistics command
async def admin_auto_verify_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show auto-verification statistics and settings"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("❌ Access denied. Admin only.")
        return
    
    try:
        # Get today's auto-verification stats
        today = datetime.now().date()
        if BotConfig.DATABASE_TYPE == 'postgresql':
            auto_approved_query = '''
                SELECT COUNT(*) as count FROM verification_requests 
                WHERE status = %s AND auto_verified = %s 
                AND DATE(created_at) = %s
            '''
            manual_pending_query = '''
                SELECT COUNT(*) as count FROM verification_requests 
                WHERE status = %s AND (auto_verified = %s OR auto_verified IS NULL)
                AND DATE(created_at) = %s
            '''
            total_today_query = '''
                SELECT COUNT(*) as count FROM verification_requests 
                WHERE DATE(created_at) = %s
            '''
        else:
            auto_approved_query = '''
                SELECT COUNT(*) as count FROM verification_requests 
                WHERE status = ? AND auto_verified = ? 
                AND DATE(created_at) = ?
            '''
            manual_pending_query = '''
                SELECT COUNT(*) as count FROM verification_requests 
                WHERE status = ? AND (auto_verified = ? OR auto_verified IS NULL)
                AND DATE(created_at) = ?
            '''
            total_today_query = '''
                SELECT COUNT(*) as count FROM verification_requests 
                WHERE DATE(created_at) = ?
            '''
        
        auto_approved_result = await db_manager.execute_query(auto_approved_query, ('approved', True, today), fetch=True)
        manual_pending_result = await db_manager.execute_query(manual_pending_query, ('pending', False, today), fetch=True)
        total_today_result = await db_manager.execute_query(total_today_query, (today,), fetch=True)
        
        auto_approved_count = auto_approved_result[0]['count'] if auto_approved_result else 0
        manual_pending_count = manual_pending_result[0]['count'] if manual_pending_result else 0
        total_today_count = total_today_result[0]['count'] if total_today_result else 0
        
        # Calculate percentages
        auto_percentage = (auto_approved_count / total_today_count * 100) if total_today_count > 0 else 0
        
        # Get current hour for business hours check
        current_hour = datetime.now().hour
        is_business_hours = BotConfig.BUSINESS_HOURS_START <= current_hour < BotConfig.BUSINESS_HOURS_END
        
        stats_text = f"""🤖 **AUTO-VERIFICATION STATISTICS**

📊 **Today's Performance ({today}):**
• Total Verifications: {total_today_count}
• Auto-Approved: {auto_approved_count} ({auto_percentage:.1f}%)
• Manual Pending: {manual_pending_count}
• Daily Limit: {auto_approved_count}/{BotConfig.DAILY_AUTO_APPROVAL_LIMIT}

⚙️ **Current Settings:**
• Status: {'🟢 Enabled' if BotConfig.AUTO_VERIFY_ENABLED else '🔴 Disabled'}
• UID Length: {BotConfig.MIN_UID_LENGTH}-{BotConfig.MAX_UID_LENGTH} characters
• Daily Limit: {BotConfig.DAILY_AUTO_APPROVAL_LIMIT} approvals
• Business Hours Only: {'Yes' if BotConfig.AUTO_VERIFY_BUSINESS_HOURS_ONLY else 'No'}
• Business Hours: {BotConfig.BUSINESS_HOURS_START}:00-{BotConfig.BUSINESS_HOURS_END}:00
• Current Time Status: {'🟢 Business Hours' if is_business_hours else '🔴 Outside Business Hours'}

🔔 **Notifications:**
• Auto-Approval Alerts: {'On' if BotConfig.NOTIFY_ON_AUTO_APPROVAL else 'Off'}
• Manual Review Alerts: {'On' if BotConfig.NOTIFY_ON_MANUAL_NEEDED else 'Off'}
• Rejection Alerts: {'On' if BotConfig.NOTIFY_ON_REJECTION else 'Off'}

📋 **Validation Criteria:**
• Alphanumeric characters only ✅
• No test/demo patterns ✅
• No excessive repetition ✅
• Length requirements ✅
• Business hours check {'✅' if not BotConfig.AUTO_VERIFY_BUSINESS_HOURS_ONLY or is_business_hours else '❌'}
• Daily limit check {'✅' if auto_approved_count < BotConfig.DAILY_AUTO_APPROVAL_LIMIT else '❌'}

💡 **System Status:** {'🟢 Ready for Auto-Verification' if BotConfig.AUTO_VERIFY_ENABLED and (not BotConfig.AUTO_VERIFY_BUSINESS_HOURS_ONLY or is_business_hours) and auto_approved_count < BotConfig.DAILY_AUTO_APPROVAL_LIMIT else '🟡 Limited/Disabled'}"""
        
        await update.message.reply_text(stats_text, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error getting auto-verification stats: {e}")
        await update.message.reply_text(f"❌ Error retrieving auto-verification statistics: {str(e)}")

# Error handler
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Exception while handling an update: {context.error}")

def main():
    # Initialize database
    init_database()
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add user command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("menu", menu_command))
    application.add_handler(CommandHandler("getmyid", get_my_id_command))
    
    # Add admin command handlers
    application.add_handler(CommandHandler("verify", admin_verify_command))
    application.add_handler(CommandHandler("reject", admin_reject_command))
    application.add_handler(CommandHandler("queue", admin_queue_command))
    application.add_handler(CommandHandler("broadcast", admin_broadcast_command))
    application.add_handler(CommandHandler("chathistory", admin_chat_history_command))
    application.add_handler(CommandHandler("activity", admin_recent_activity_command))
    application.add_handler(CommandHandler("searchuser", admin_search_user_command))
    application.add_handler(CommandHandler("autostats", admin_auto_verify_stats_command))
    
    # Add callback and message handlers
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_handler(MessageHandler(filters.Document.PDF | filters.Document.IMAGE, handle_document))
    application.add_error_handler(error_handler)
    
    # Start the bot
    print("🤖 OPTRIXTRADES Bot is starting...")
    print(f"📱 Bot Token: {BOT_TOKEN[:10]}...")
    print(f"🔗 Broker Link: {BROKER_LINK}")
    print(f"📢 Premium Channel: {PREMIUM_CHANNEL_ID}")
    print(f"🔗 Premium Group: {PREMIUM_GROUP_LINK}")
    print(f"👨‍💼 Admin User ID: {ADMIN_USER_ID}")
    print("\n📋 Available Commands:")
    print("• /start - Start the bot")
    print("• /getmyid - Get your Telegram user ID (for admin setup)")
    print("\n📋 Available Admin Commands:")
    print("• /verify <user_id> - Approve user verification")
    print("• /reject <user_id> [reason] - Reject user verification")
    print("• /queue - View pending verifications")
    print("• /broadcast <message> - Send message to all users")
    print("• /chathistory <user_id> [limit] - View chat history for user")
    print("• /activity [limit] - View recent activity across all users")
    print("• /autostats - View auto-verification statistics and settings")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
