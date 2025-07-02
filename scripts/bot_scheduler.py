import asyncio
import sqlite3
from datetime import datetime, timedelta
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot Configuration - Updated with your actual values
BOT_TOKEN = "7560905481:AAFm1Ra0zAknomOhXvjsR4kkruurz_O033s"
BROKER_LINK = "https://affiliate.iqbroker.com/redir/?aff=755757&aff_model=revenue&afftrack="
ADMIN_USERNAME = "Optrixtradesadmin"

def update_user_follow_up_day(user_id, day):
    conn = sqlite3.connect('trading_bot.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET follow_up_day = ?, last_interaction = ? WHERE user_id = ?', 
                   (day, datetime.now(), user_id))
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

async def send_follow_up_messages():
    bot = Bot(token=BOT_TOKEN)
    conn = sqlite3.connect('trading_bot.db')
    cursor = conn.cursor()
    
    # Follow-up 2 (Day 2) - Scarcity + Social Proof
    day_2_cutoff = datetime.now() - timedelta(hours=23)
    cursor.execute('''
        SELECT user_id, first_name FROM users 
        WHERE last_interaction < ? 
        AND deposit_confirmed = FALSE 
        AND follow_up_day = 1
        AND is_active = TRUE
    ''', (day_2_cutoff,))
    
    day_2_users = cursor.fetchall()
    
    for user_id, first_name in day_2_users:
        try:
            text = """📈 Just an update...

We've already had 42 traders activate their access this week and most of them are already using the free bot + signals to start profiting.

You're still eligible but access may close soon once we hit this week's quota.

Don't miss your shot! 🎯"""

            keyboard = [
                [InlineKeyboardButton("➡️ Complete My Free Access", callback_data="get_vip_access")],
                [InlineKeyboardButton("➡️ Contact support team", url=f"https://t.me/{ADMIN_USERNAME}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await bot.send_message(chat_id=user_id, text=text, reply_markup=reply_markup)
            update_user_follow_up_day(user_id, 2)
            log_interaction(user_id, "follow_up_2")
            
        except Exception as e:
            logger.error(f"Failed to send follow-up 2 to user {user_id}: {e}")
    
    # Follow-up 3 (Day 3) - Friendly Reminder + Value Recap
    day_3_cutoff = datetime.now() - timedelta(hours=22)
    cursor.execute('''
        SELECT user_id, first_name FROM users 
        WHERE last_interaction < ? 
        AND deposit_confirmed = FALSE 
        AND follow_up_day = 2
        AND is_active = TRUE
    ''', (day_3_cutoff,))
    
    day_3_users = cursor.fetchall()
    
    for user_id, first_name in day_3_users:
        try:
            text = f"""Hey {first_name}! 👋

Just wanted to remind you of everything you get for free once you sign up:

✅ Daily VIP signals
✅ Auto-trading bot
✅ Strategy sessions  
✅ Private trader group
✅ Up to $500 in deposit bonuses

And yes, it's still 100% free when you use our broker link! 🆓"""

            keyboard = [
                [InlineKeyboardButton("➡️ I'm Ready to Activate", callback_data="get_vip_access")],
                [InlineKeyboardButton("➡️ Contact support team", url=f"https://t.me/{ADMIN_USERNAME}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await bot.send_message(chat_id=user_id, text=text, reply_markup=reply_markup)
            update_user_follow_up_day(user_id, 3)
            log_interaction(user_id, "follow_up_3")
            
        except Exception as e:
            logger.error(f"Failed to send follow-up 3 to user {user_id}: {e}")
    
    # Follow-up 4 (Day 4) - Personal + Soft CTA
    day_4_cutoff = datetime.now() - timedelta(days=1)
    cursor.execute('''
        SELECT user_id, first_name FROM users 
        WHERE last_interaction < ? 
        AND deposit_confirmed = FALSE 
        AND follow_up_day = 3
        AND is_active = TRUE
    ''', (day_4_cutoff,))
    
    day_4_users = cursor.fetchall()
    
    for user_id, first_name in day_4_users:
        try:
            text = f"""💭 {first_name}, you've been on our early access list for a few days...

If you're still interested but something's holding you back, reply to this message and let's help you sort it out.

Even if you don't have a big budget right now, we'll guide you to start small and smart. 💪"""

            keyboard = [
                [InlineKeyboardButton("➡️ I Have a Question", url=f"https://t.me/{ADMIN_USERNAME}")],
                [InlineKeyboardButton("➡️ Continue Activation", callback_data="get_vip_access")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await bot.send_message(chat_id=user_id, text=text, reply_markup=reply_markup)
            update_user_follow_up_day(user_id, 4)
            log_interaction(user_id, "follow_up_4")
            
        except Exception as e:
            logger.error(f"Failed to send follow-up 4 to user {user_id}: {e}")
    
    # Follow-up 5 (Day 5) - Last Chance + Exit Option
    day_5_cutoff = datetime.now() - timedelta(days=1)
    cursor.execute('''
        SELECT user_id, first_name FROM users 
        WHERE last_interaction < ? 
        AND deposit_confirmed = FALSE 
        AND follow_up_day = 4
        AND is_active = TRUE
    ''', (day_5_cutoff,))
    
    day_5_users = cursor.fetchall()
    
    for user_id, first_name in day_5_users:
        try:
            text = """⏰ Last call to claim your free access to OPTRIXTRADES.

This week's onboarding closes in a few hours. After that, you'll need to wait for the next batch - no guarantees it'll still be free.

Want in? 🤔"""

            keyboard = [
                [InlineKeyboardButton("✅ Yes, Activate Me Now", callback_data="get_vip_access")],
                [InlineKeyboardButton("❌ Not Interested", callback_data="not_interested")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await bot.send_message(chat_id=user_id, text=text, reply_markup=reply_markup)
            update_user_follow_up_day(user_id, 5)
            log_interaction(user_id, "follow_up_5")
            
        except Exception as e:
            logger.error(f"Failed to send follow-up 5 to user {user_id}: {e}")
    
    conn.close()
    logger.info(f"Follow-up messages sent: Day 2: {len(day_2_users)}, Day 3: {len(day_3_users)}, Day 4: {len(day_4_users)}, Day 5: {len(day_5_users)}")

async def main():
    while True:
        try:
            await send_follow_up_messages()
            logger.info("✅ Follow-up messages check completed")
        except Exception as e:
            logger.error(f"❌ Error in scheduler: {e}")
        
        # Wait 1 hour before next check
        await asyncio.sleep(3600)

if __name__ == '__main__':
    print("🕐 OPTRIXTRADES Bot Scheduler starting...")
    print(f"📱 Bot Token: {BOT_TOKEN[:10]}...")
    asyncio.run(main())
