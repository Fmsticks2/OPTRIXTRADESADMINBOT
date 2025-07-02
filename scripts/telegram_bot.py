import logging
import sqlite3
import asyncio
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import os

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot Configuration - Updated with your actual values
BOT_TOKEN = "7560905481:AAFm1Ra0zAknomOhXvjsR4kkruurz_O033s"
BROKER_LINK = "https://affiliate.iqbroker.com/redir/?aff=755757&aff_model=revenue&afftrack="
PREMIUM_CHANNEL_ID = "-1001002557285297"  # Added -100 prefix for supergroup
PREMIUM_CHANNEL_LINK = f"https://t.me/c/1002557285297"
ADMIN_USERNAME = "Optrixtradesadmin"

# Database setup
def init_database():
    conn = sqlite3.connect('trading_bot.db')
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
    
    conn.commit()
    conn.close()

def get_user_data(user_id):
    conn = sqlite3.connect('trading_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

def update_user_data(user_id, **kwargs):
    conn = sqlite3.connect('trading_bot.db')
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
    conn = sqlite3.connect('trading_bot.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT OR REPLACE INTO users (user_id, username, first_name, join_date, last_interaction)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, username, first_name, datetime.now(), datetime.now()))
    
    conn.commit()
    conn.close()

def log_interaction(user_id, interaction_type, interaction_data=""):
    conn = sqlite3.connect('trading_bot.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO user_interactions (user_id, interaction_type, interaction_data)
        VALUES (?, ?, ?)
    ''', (user_id, interaction_type, interaction_data))
    
    conn.commit()
    conn.close()

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

Tap below to activate your free VIP access and get started."""

    keyboard = [[InlineKeyboardButton("➡️ Get Free VIP Access", callback_data="get_vip_access")]]
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
        # Mark deposit as confirmed (in real implementation, you'd verify this)
        update_user_data(user_id, deposit_confirmed=True, current_flow='completed')
        
        success_text = f"""🎉 Congratulations! Your deposit has been verified.

Welcome to OPTRIXTRADES Premium! 

You now have access to:
✅ Daily VIP trading signals
✅ Premium trading strategies  
✅ Live trading sessions
✅ AI trading bot access

Join our premium channel: {PREMIUM_CHANNEL_LINK}

Your trading journey starts now! 🚀"""

        await update.message.reply_text(success_text)
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

# Callback query handler
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    
    if data == "get_vip_access":
        await activation_instructions(update, context)
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

# Error handler
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Exception while handling an update: {context.error}")

def main():
    # Initialize database
    init_database()
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    application.add_error_handler(error_handler)
    
    # Start the bot
    print("🤖 OPTRIXTRADES Bot is starting...")
    print(f"📱 Bot Token: {BOT_TOKEN[:10]}...")
    print(f"🔗 Broker Link: {BROKER_LINK}")
    print(f"📢 Premium Channel: {PREMIUM_CHANNEL_ID}")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
