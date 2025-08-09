"""Test script for the follow-up scheduler"""

import asyncio
import logging
import sys
import os

# Add the project root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from telegram import Bot
from telegram.ext import ContextTypes, ApplicationBuilder

from config import BotConfig
from telegram_bot.utils.follow_up_scheduler import init_follow_up_scheduler, get_follow_up_scheduler

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def test_scheduler():
    """Test the follow-up scheduler functionality"""
    # Create a bot instance
    bot = Bot(token=BotConfig.BOT_TOKEN)
    
    # Initialize the scheduler
    scheduler = init_follow_up_scheduler(bot)
    logger.info("Scheduler initialized")
    
    # Test user ID (replace with a real test user ID)
    test_user_id = 123456789  # Replace with your test user ID
    
    # Create a mock context
    application = ApplicationBuilder().token(BotConfig.BOT_TOKEN).build()
    await application.initialize()
    context = ContextTypes.DEFAULT_TYPE(application=application)
    
    # Initialize user_data properly
    from collections import defaultdict
    context._user_data = defaultdict(dict)
    context._user_data[test_user_id] = {'first_name': 'Test User'}
    
    # Set the user_data for the context
    context._user_id = test_user_id
    
    # Schedule follow-ups
    await scheduler.schedule_follow_ups(test_user_id, context)
    logger.info(f"Scheduled follow-ups for user {test_user_id}")
    
    # Wait for a short time to see if the first follow-up is sent
    logger.info("Waiting for 10 seconds to see if the first follow-up is scheduled...")
    await asyncio.sleep(10)
    
    # Cancel follow-ups
    await scheduler.cancel_follow_ups(test_user_id)
    logger.info(f"Cancelled follow-ups for user {test_user_id}")
    
    # Clean up
    await application.shutdown()
    logger.info("Test completed")

def main():
    """Run the test"""
    asyncio.run(test_scheduler())

if __name__ == "__main__":
    main()