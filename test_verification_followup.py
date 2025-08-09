#!/usr/bin/env python3
"""Test script to verify follow-up scheduling in verification process"""

import asyncio
import logging
from telegram import Update, User, Message, Chat
from telegram.ext import ApplicationBuilder, ContextTypes
from collections import defaultdict

from config import BotConfig
from telegram_bot.utils.follow_up_scheduler import init_follow_up_scheduler
from telegram_bot.handlers.verification import start_verification
from telegram_bot.bot import TradingBot
from database.connection import DatabaseManager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_verification_followup():
    """Test if follow-ups are scheduled when verification starts"""
    
    # Initialize database
    db_manager = DatabaseManager()
    await db_manager.initialize()
    
    # Create bot instance
    bot_instance = TradingBot(db_manager)
    await bot_instance.initialize()
    
    # Create application
    application = ApplicationBuilder().token(BotConfig.BOT_TOKEN).build()
    await application.initialize()
    
    # Set bot instance in application's bot_data
    application.bot_data['bot_instance'] = bot_instance
    
    # Initialize follow-up scheduler
    bot_instance.follow_up_scheduler = init_follow_up_scheduler(application.bot)
    logger.info("Follow-up scheduler initialized")
    
    # Create a fake update for testing
    test_user_id = 8027303809
    fake_user = User(
        id=test_user_id,
        is_bot=False,
        first_name="Test",
        username="testuser"
    )
    
    fake_chat = Chat(
        id=test_user_id,
        type="private"
    )
    
    fake_message = Message(
        message_id=1,
        date=None,
        chat=fake_chat,
        from_user=fake_user
    )
    
    fake_update = Update(
        update_id=1,
        message=fake_message
    )
    
    # Create context
    context = ContextTypes.DEFAULT_TYPE(application=application)
    context._user_data = defaultdict(dict)
    context._user_data[test_user_id] = {}
    context._user_id = test_user_id
    
    logger.info(f"Testing verification start for user {test_user_id}")
    
    try:
        # Call start_verification
        result = await start_verification(fake_update, context)
        logger.info(f"Verification started, result: {result}")
        
        # Check if follow-ups were scheduled
        if hasattr(bot_instance, 'follow_up_scheduler') and bot_instance.follow_up_scheduler:
            scheduled_tasks = bot_instance.follow_up_scheduler.scheduled_tasks
            if test_user_id in scheduled_tasks:
                logger.info(f"✅ Follow-ups scheduled for user {test_user_id}: {len(scheduled_tasks[test_user_id])} tasks")
            else:
                logger.warning(f"❌ No follow-ups scheduled for user {test_user_id}")
        else:
            logger.error("❌ Follow-up scheduler not available")
            
    except Exception as e:
        logger.error(f"Error during verification test: {e}")
    
    # Clean up
    await application.shutdown()
    logger.info("Test completed")

def main():
    """Run the test"""
    asyncio.run(test_verification_followup())

if __name__ == "__main__":
    main()