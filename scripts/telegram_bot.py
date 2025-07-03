import logging
import sqlite3
import asyncio
import os
import sys
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram.error import TelegramError

# Add parent directory to path to import config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import BotConfig

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
    conn = sqlite3.connect(BotConfig.SQLITE_DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            current_flow TEXT DEFAULT 'welcome',
            registration_status TEXT DEFAULT 'not_started',
            deposit_confirmed BOOLEAN DEFAULT FALSE,
            uid TEXT,
            join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_interaction TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            follow_up_day INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT TRUE
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_interactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            interaction_type TEXT,
            interaction_data TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS verification_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            uid TEXT,
            screenshot_file_id TEXT,
            status TEXT DEFAULT 'pending',
            admin_response TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS broadcast_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_text TEXT,
            total_users INTEGER,
            successful_sends INTEGER DEFAULT 0,
            failed_sends INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

def get_user_data(user_id):
    conn = sqlite3.connect(BotConfig.SQLITE_DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

def update_user_data(user_id, **kwargs):
    conn = sqlite3.connect(BotConfig.SQLITE_DATABASE_PATH)
    cursor = conn.cursor()
    
    # Update last_interaction
    kwargs['last_interaction'] = datetime.now()
    
    # Build dynamic update query
    set_clause = ', '.join([f"{key} = ?" for key in kwargs.keys()])
    values = list(kwargs.values()) + [user_id]
    
    cursor.execute(f'UPDATE users SET {set_clause} WHERE user_id = ?', values)
    conn.commit()
    conn.close()

def create_user(user_id, username, first_name):
    conn = sqlite3.connect(BotConfig.SQLITE_DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT OR REPLACE INTO users (user_id, username, first_name, join_date, last_interaction)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, username, first_name, datetime.now(), datetime.now()))
    
    conn.commit()
    conn.close()

def log_interaction(user_id, interaction_type, interaction_data=""):
    conn = sqlite3.connect(BotConfig.SQLITE_DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO user_interactions (user_id, interaction_type, interaction_data)
        VALUES (?, ?, ?)
    ''', (user_id, interaction_type, interaction_data))
    
    conn.commit()
    conn.close()

def is_admin(user_id):
    """Check if user is admin"""
    return user_id == ADMIN_USER_ID

def create_verification_request(user_id, uid, screenshot_file_id):
    """Create a new verification request"""
    conn = sqlite3.connect(BotConfig.SQLITE_DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO verification_requests (user_id, uid, screenshot_file_id)
        VALUES (?, ?, ?)
    ''', (user_id, uid, screenshot_file_id))
    
    conn.commit()
    conn.close()

def get_pending_verifications():
    """Get all pending verification requests"""
    conn = sqlite3.connect(BotConfig.SQLITE_DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT vr.id, vr.user_id, u.first_name, u.username, vr.uid, vr.created_at
        FROM verification_requests vr
        JOIN users u ON vr.user_id = u.user_id
        WHERE vr.status = 'pending'
        ORDER BY vr.created_at ASC
    ''')
    
    requests = cursor.fetchall()
    conn.close()
    return requests

def update_verification_status(request_id, status, admin_response=""):
    """Update verification request status"""
    conn = sqlite3.connect(BotConfig.SQLITE_DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE verification_requests 
        SET status = ?, admin_response = ?, updated_at = ?
        WHERE id = ?
    ''', (status, admin_response, datetime.now(), request_id))
    
    conn.commit()
    conn.close()

def get_all_active_users():
    """Get all active users for broadcasting"""
    conn = sqlite3.connect(BotConfig.SQLITE_DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT user_id, first_name FROM users 
        WHERE is_active = TRUE
    ''')
    
    users = cursor.fetchall()
    conn.close()
    return users

# Flow 1: Welcome & Hook
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    username = user.username or ""
    first_name = user.first_name or "there"
    
    # Create or update user
    create_user(user_id, username, first_name)
    log_interaction(user_id, "start_command")
    
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

# Flow 2: Activation Instructions
async def activation_instructions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    update_user_data(user_id, current_flow='activation')
    log_interaction(user_id, "activation_instructions")
    
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
    
    await query.edit_message_text(activation_text, reply_markup=reply_markup)
    
    # Send second part of message
    second_part = """Why is it free?

We earn a small commission from the broker through your trading volume, not your money. So we are more focused on your success - the more you win, the better for both of us. ✅

Want to unlock even higher-tier bonuses or full bot access?
Send "UPGRADE" """

    await context.bot.send_message(chat_id=query.from_user.id, text=second_part)

# Flow 3: Confirmation
async def registration_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    update_user_data(user_id, current_flow='confirmation', registration_status='registered')
    log_interaction(user_id, "registration_confirmation")
    
    confirmation_text = """Send in your UID and deposit screenshot to gain access to OPTRIXTRADES premium signal channel.

BONUS: We're hosting a live session soon with exclusive insights. Stay tuned. Get early access now into our premium channel - only limited slots are available! 🚀"""

    await query.edit_message_text(confirmation_text)
    await context.bot.send_message(
        chat_id=user_id, 
        text="Please send your UID and deposit screenshot as separate messages."
    )

# Handle text messages (UID, UPGRADE, etc.)
async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.upper()
    
    user_data = get_user_data(user_id)
    if not user_data:
        await start_command(update, context)
        return
    
    log_interaction(user_id, "text_message", update.message.text)
    
    if text == "UPGRADE":
        await handle_upgrade_request(update, context)
    elif user_data[3] == 'confirmation':  # current_flow is confirmation
        # Assume this is a UID
        update_user_data(user_id, uid=update.message.text)
        await update.message.reply_text(
            "UID received! Now please send your deposit screenshot."
        )

# Handle photo messages (deposit screenshots)
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data = get_user_data(user_id)
    
    if not user_data:
        await update.message.reply_text("Please start with /start first.")
        return
    
    log_interaction(user_id, "photo_upload", "deposit_screenshot")
    
    if user_data[3] == 'confirmation':  # current_flow is confirmation
        # Get the user's UID from database
        uid = user_data[6] if user_data[6] else "Not provided"
        screenshot_file_id = update.message.photo[-1].file_id
        
        # Create verification request
        create_verification_request(user_id, uid, screenshot_file_id)
        
        # Send confirmation to user
        confirmation_text = f"""✅ **Screenshot Received Successfully!**

📋 **Verification Details:**
• UID: {uid}
• Screenshot: Uploaded
• Status: Under Review

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
                chat_id=ADMIN_USER_ID,
                photo=screenshot_file_id,
                caption=admin_notification,
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Failed to notify admin: {e}")
            
    else:
        await update.message.reply_text("Please complete the registration process first by using /start")

# Handle upgrade requests
async def handle_upgrade_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    log_interaction(user_id, "upgrade_request")
    
    upgrade_text = f"""🔥 UPGRADE REQUEST RECEIVED

For premium upgrade options and full bot access, please contact our support team directly.

Our team will help you unlock:
🚀 Advanced AI trading algorithms
💎 VIP-only trading signals  
📈 Personal trading mentor
💰 Higher deposit bonuses

Contact: @{ADMIN_USERNAME}"""

    await update.message.reply_text(upgrade_text)

# Help handlers
async def help_signup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    log_interaction(query.from_user.id, "help_signup")
    
    help_text = f"""📹 SIGNUP HELP

Step-by-step registration guide:

1. Click this link: {BROKER_LINK}
2. Fill in your personal details
3. Verify your email address
4. Complete account verification
5. Make your first deposit ($20 minimum)

Need personal assistance? Contact @{ADMIN_USERNAME}

[Video tutorial coming soon]"""

    await query.edit_message_text(help_text)

async def help_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    log_interaction(query.from_user.id, "help_deposit")
    
    help_text = f"""💳 DEPOSIT HELP

How to make your first deposit:

1. Log into your broker account
2. Go to "Deposit" section
3. Choose your payment method
4. Enter amount ($20 minimum)
5. Complete the transaction
6. Take a screenshot of confirmation

Need help? Contact @{ADMIN_USERNAME}

[Video tutorial coming soon]"""

    await query.edit_message_text(help_text)

# Add this after the existing callback handlers, before the button_callback function

async def handle_not_interested(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    update_user_data(user_id, is_active=False)
    log_interaction(user_id, "not_interested")
    
    farewell_text = """Alright, no problem! 👋

Feel free to reach us at any time @Optrixtradesadmin if you change your mind.

We'll be here when you're ready to start your trading journey! 🚀"""

    await query.edit_message_text(farewell_text)

# New handler for group access request
async def handle_group_access_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    first_name = query.from_user.first_name or "there"
    
    log_interaction(user_id, "group_access_request")
    
    # Simulate automatic addition to group (in real implementation, you'd use bot.add_chat_member)
    success_text = f"""🎉 **Welcome to OPTRIXTRADES Premium Group!**

Hi {first_name}! You've been successfully added to our premium trading group.

🔗 **Group Link:** {PREMIUM_GROUP_LINK}

✅ **What you get:**
• Real-time trading signals
• Market analysis and insights
• Direct access to our trading experts
• Exclusive trading strategies
• Community support

🚀 **Ready to start your trading journey?**"""
    
    keyboard = [[InlineKeyboardButton("🚀 Start Trading Journey", callback_data="get_vip_access")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(success_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    # Update user status
    update_user_data(user_id, current_flow='group_member')

# Callback query handler
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    
    if data == "get_vip_access":
        await activation_instructions(update, context)
    elif data == "request_group_access":
        await handle_group_access_request(update, context)
    elif data == "registered":
        await registration_confirmation(update, context)
    elif data == "help_signup":
        await help_signup(update, context)
    elif data == "help_deposit":
        await help_deposit(update, context)
    elif data == "contact_support":
        await query.answer()
        await query.edit_message_text(f"Please contact our support team: @{ADMIN_USERNAME}")
    elif data == "not_interested":
        await handle_not_interested(update, context)

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
        update_user_data(target_user_id, deposit_confirmed=True, current_flow='completed')
        
        # Update verification request status
        conn = sqlite3.connect(BotConfig.SQLITE_DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE verification_requests 
            SET status = 'approved', admin_response = 'Manually approved by admin', updated_at = ?
            WHERE user_id = ? AND status = 'pending'
        ''', (datetime.now(), target_user_id))
        conn.commit()
        conn.close()
        
        # Get user data for notification
        user_data = get_user_data(target_user_id)
        if user_data:
            # Notify user of approval
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

Your trading journey starts now! 🚀"""
            
            try:
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text=success_message,
                    parse_mode='Markdown'
                )
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
        conn = sqlite3.connect(BotConfig.SQLITE_DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE verification_requests 
            SET status = 'rejected', admin_response = ?, updated_at = ?
            WHERE user_id = ? AND status = 'pending'
        ''', (reason, datetime.now(), target_user_id))
        conn.commit()
        conn.close()
        
        # Get user data for notification
        user_data = get_user_data(target_user_id)
        if user_data:
            # Notify user of rejection
            rejection_message = f"""❌ **Verification Rejected**

Unfortunately, your verification request has been rejected.

**Reason:** {reason}

📞 **Need Help?**
Please contact our support team for assistance: @{ADMIN_USERNAME}

You can resubmit your verification with the correct information."""
            
            try:
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text=rejection_message,
                    parse_mode='Markdown'
                )
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
    
    pending_requests = get_pending_verifications()
    
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
    users = get_all_active_users()
    
    if not users:
        await update.message.reply_text("❌ No active users found for broadcasting.")
        return
    
    # Create broadcast record
    conn = sqlite3.connect(BotConfig.SQLITE_DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO broadcast_messages (message_text, total_users)
        VALUES (?, ?)
    ''', (message_text, len(users)))
    broadcast_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
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
        except Exception as e:
            failed_sends += 1
            logger.error(f"Failed to send broadcast to {user_id_target}: {e}")
    
    # Update broadcast record
    conn = sqlite3.connect(BotConfig.SQLITE_DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE broadcast_messages 
        SET successful_sends = ?, failed_sends = ?, completed_at = ?
        WHERE id = ?
    ''', (successful_sends, failed_sends, datetime.now(), broadcast_id))
    conn.commit()
    conn.close()
    
    # Send delivery confirmation to admin
    confirmation_text = f"""✅ **Broadcast Complete!**

📊 **Delivery Report:**
• Total Users: {len(users)}
• Successful: {successful_sends}
• Failed: {failed_sends}
• Success Rate: {(successful_sends/len(users)*100):.1f}%

📝 **Message:** {message_text[:100]}{'...' if len(message_text) > 100 else ''}"""
    
    await status_message.edit_text(confirmation_text, parse_mode='Markdown')

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
    
    # Add admin command handlers
    application.add_handler(CommandHandler("verify", admin_verify_command))
    application.add_handler(CommandHandler("reject", admin_reject_command))
    application.add_handler(CommandHandler("queue", admin_queue_command))
    application.add_handler(CommandHandler("broadcast", admin_broadcast_command))
    
    # Add callback and message handlers
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_error_handler(error_handler)
    
    # Start the bot
    print("🤖 OPTRIXTRADES Bot is starting...")
    print(f"📱 Bot Token: {BOT_TOKEN[:10]}...")
    print(f"🔗 Broker Link: {BROKER_LINK}")
    print(f"📢 Premium Channel: {PREMIUM_CHANNEL_ID}")
    print(f"🔗 Premium Group: {PREMIUM_GROUP_LINK}")
    print(f"👨‍💼 Admin User ID: {ADMIN_USER_ID}")
    print("\n📋 Available Admin Commands:")
    print("• /verify <user_id> - Approve user verification")
    print("• /reject <user_id> [reason] - Reject user verification")
    print("• /queue - View pending verifications")
    print("• /broadcast <message> - Send message to all users")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
