import asyncio
import os
import sys
import logging
from datetime import datetime, timedelta
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError

# Add parent directory to path to import config
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from config import BotConfig
from database.db_manager import db_manager

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('scheduler.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
BOT_TOKEN = BotConfig.BOT_TOKEN
BROKER_LINK = BotConfig.BROKER_LINK
ADMIN_USERNAME = BotConfig.ADMIN_USERNAME

class FollowUpScheduler:
    def __init__(self):
        self.bot = Bot(token=BOT_TOKEN)

    async def update_user_follow_up_day(self, user_id, day):
        """Update user follow-up day"""
        try:
            if BotConfig.DATABASE_TYPE == 'postgresql':
                query = 'UPDATE users SET follow_up_day = %s, last_interaction = CURRENT_TIMESTAMP WHERE user_id = %s'
            else:
                query = 'UPDATE users SET follow_up_day = ?, last_interaction = CURRENT_TIMESTAMP WHERE user_id = ?'
            await db_manager.execute_query(query, (day, user_id))
        except Exception as e:
            logger.error(f"Error updating follow-up day for user {user_id}: {e}")

    async def log_interaction(self, user_id, interaction_type, interaction_data=""):
        """Log interaction"""
        try:
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
        except Exception as e:
            logger.error(f"Error logging interaction for user {user_id}: {e}")

    async def send_follow_up_messages(self):
        """Send follow-up messages to users"""
        try:
            # Follow-up 1 (6 hours after last interaction)
            six_hours_ago = datetime.now() - timedelta(hours=6)
            if BotConfig.DATABASE_TYPE == 'postgresql':
                query1 = '''
                    SELECT user_id, first_name FROM users 
                    WHERE last_interaction < %s 
                    AND deposit_confirmed = FALSE 
                    AND follow_up_day = 0
                    AND is_active = TRUE
                '''
            else:
                query1 = '''
                    SELECT user_id, first_name FROM users 
                    WHERE last_interaction < ? 
                    AND deposit_confirmed = FALSE 
                    AND follow_up_day = 0
                    AND is_active = TRUE
                '''
            
            follow_up_1_users = await db_manager.execute_query(query1, (six_hours_ago,), fetch=True) or []
            
            for user_id, first_name in follow_up_1_users:
                try:
                    text = f"""Hey {first_name} 👋 just checking in…

You haven't completed your free VIP access setup yet. If you still want:

✅ Daily signals
✅ Auto trading bot
✅ Bonus deposit rewards

…then don't miss out. Traders are already making serious moves this week.

Tap below to continue your registration. You're just one step away 👇"""

                    keyboard = [
                        [InlineKeyboardButton("➡️ Claim Free Access Now", callback_data="get_vip_access")],
                        [InlineKeyboardButton("➡️ Contact support team", url=f"https://t.me/{ADMIN_USERNAME}")]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    await self.bot.send_message(chat_id=user_id, text=text, reply_markup=reply_markup)
                    await self.update_user_follow_up_day(user_id, 1)
                    await self.log_interaction(user_id, "follow_up_1")
                    
                except TelegramError as e:
                    logger.error(f"Failed to send follow-up 1 to user {user_id}: {e}")
                except Exception as e:
                    logger.error(f"Unexpected error sending follow-up 1 to user {user_id}: {e}")

            # Follow-up 2 (Day 2)
            day_2_cutoff = datetime.now() - timedelta(hours=23)
            if BotConfig.DATABASE_TYPE == 'postgresql':
                query2 = '''
                    SELECT user_id, first_name FROM users 
                    WHERE last_interaction < %s 
                    AND deposit_confirmed = FALSE 
                    AND follow_up_day = 1
                    AND is_active = TRUE
                '''
            else:
                query2 = '''
                    SELECT user_id, first_name FROM users 
                    WHERE last_interaction < ? 
                    AND deposit_confirmed = FALSE 
                    AND follow_up_day = 1
                    AND is_active = TRUE
                '''
            
            day_2_users = await db_manager.execute_query(query2, (day_2_cutoff,), fetch=True) or []
            
            for user_id, first_name in day_2_users:
                try:
                    text = """🔥 Just an update…

We've already had 42 traders activate their access this week and most of them are already using the free bot + signals to start profiting.

You're still eligible but access may close soon once we hit this week's quota.

Don't miss your shot."""

                    keyboard = [
                        [InlineKeyboardButton("➡️ Complete My Free access", callback_data="get_vip_access")],
                        [InlineKeyboardButton("➡️ Contact support team", url=f"https://t.me/{ADMIN_USERNAME}")]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    await self.bot.send_message(chat_id=user_id, text=text, reply_markup=reply_markup)
                    await self.update_user_follow_up_day(user_id, 2)
                    await self.log_interaction(user_id, "follow_up_2")
                    
                except TelegramError as e:
                    logger.error(f"Failed to send follow-up 2 to user {user_id}: {e}")
                except Exception as e:
                    logger.error(f"Unexpected error sending follow-up 2 to user {user_id}: {e}")
            logger.info(f"Follow-up messages sent: Follow-up 1: {len(follow_up_1_users)}, Day 2: {len(day_2_users)}")
            
        except Exception as e:
            logger.error(f"Error in send_follow_up_messages: {e}")

    async def run_scheduler(self):
        """Run the scheduler continuously"""
        logger.info("🕐 OPTRIXTRADES Bot Scheduler starting...")
        
        while True:
            try:
                await self.send_follow_up_messages()
                logger.info("✅ Follow-up messages check completed")
            except Exception as e:
                logger.error(f"❌ Error in scheduler: {e}")
            
            # Wait 1 hour before next check
            await asyncio.sleep(3600)

def main():
    """Main function for scheduler"""
    try:
        scheduler = FollowUpScheduler()
        asyncio.run(scheduler.run_scheduler())
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user")
    except Exception as e:
        logger.error(f"Scheduler crashed: {e}")
        raise

if __name__ == '__main__':
    main()
