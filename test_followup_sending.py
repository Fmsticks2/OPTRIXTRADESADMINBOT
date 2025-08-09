#!/usr/bin/env python3
"""Test script to directly test follow-up scheduler with real user ID"""

import asyncio
import logging
from telegram.ext import ApplicationBuilder
from collections import defaultdict

from config import BotConfig
from telegram_bot.utils.follow_up_scheduler import init_follow_up_scheduler
from telegram_bot.bot import TradingBot
from database.connection import DatabaseManager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_followup_sending():
    """Test follow-up sending with real user ID"""
    
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
    
    # Test user ID (real Telegram user)
    test_user_id = 8027303809
    logger.info(f"Testing follow-up sending for user {test_user_id}")
    
    # Test sequence 1 follow-up
    logger.info("Testing sequence 1 follow-up...")
    try:
        user_data = {'verification_status': 'pending'}
        await bot_instance.follow_up_scheduler._send_follow_up(test_user_id, 1, user_data)
        logger.info("✅ Sequence 1 follow-up sent successfully")
    except Exception as e:
        logger.error(f"❌ Sequence 1 follow-up failed: {e}")
    
    # Wait a bit
    await asyncio.sleep(2)
    
    # Test sequence 2 follow-up
    logger.info("Testing sequence 2 follow-up...")
    try:
        user_data = {'verification_status': 'pending'}
        await bot_instance.follow_up_scheduler._send_follow_up(test_user_id, 2, user_data)
        logger.info("✅ Sequence 2 follow-up sent successfully")
    except Exception as e:
        logger.error(f"❌ Sequence 2 follow-up failed: {e}")
    
    # Clean up
    await application.shutdown()
    logger.info("Test completed")

def main():
    """Run the test"""
    asyncio.run(test_followup_sending())

if __name__ == "__main__":
    main()