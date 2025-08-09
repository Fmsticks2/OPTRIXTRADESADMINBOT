#!/usr/bin/env python3
"""
Test script for batch follow-up functionality.
This script tests starting follow-ups for existing unverified users in the database.
"""

import asyncio
import logging
from telegram import Bot
from telegram.ext import ApplicationBuilder

from telegram_bot.config import BotConfig
from database.connection import DatabaseManager
from telegram_bot.bot import TradingBot
from telegram_bot.utils.follow_up_scheduler import init_follow_up_scheduler
from telegram_bot.utils.batch_follow_up import BatchFollowUpManager, start_batch_follow_ups, get_batch_follow_up_stats

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_batch_follow_ups():
    """Test batch follow-up functionality"""
    
    logger.info("Starting batch follow-up test...")
    
    try:
        # Initialize database
        db_manager = DatabaseManager()
        await db_manager.initialize()
        logger.info("Database initialized")
        
        # Create bot instance
        bot_instance = TradingBot(db_manager)
        await bot_instance.initialize()
        logger.info("Bot instance created")
        
        # Create application and bot
        application = ApplicationBuilder().token(BotConfig.BOT_TOKEN).build()
        await application.initialize()
        bot = application.bot
        
        # Set bot instance in application's bot_data
        application.bot_data['bot_instance'] = bot_instance
        
        # Initialize follow-up scheduler
        bot_instance.follow_up_scheduler = init_follow_up_scheduler(bot)
        logger.info("Follow-up scheduler initialized")
        
        # Create batch follow-up manager
        batch_manager = BatchFollowUpManager(bot, db_manager)
        
        # Get initial statistics
        logger.info("\n=== INITIAL STATISTICS ===")
        initial_stats = await batch_manager.get_follow_up_stats()
        logger.info(f"Initial follow-up stats: {initial_stats}")
        
        # Get unverified users
        logger.info("\n=== UNVERIFIED USERS ===")
        unverified_users = await batch_manager.get_unverified_users()
        logger.info(f"Found {len(unverified_users)} unverified users")
        
        if unverified_users:
            # Show first few users (without sensitive data)
            for i, user in enumerate(unverified_users[:5]):
                logger.info(f"User {i+1}: ID={user['user_id']}, Name={user.get('first_name', 'Unknown')}, Status={user.get('verification_status', 'None')}")
            
            if len(unverified_users) > 5:
                logger.info(f"... and {len(unverified_users) - 5} more users")
        
        # Start follow-ups for a limited number of users (for testing)
        test_limit = 3  # Only process 3 users for testing
        logger.info(f"\n=== STARTING FOLLOW-UPS (Limited to {test_limit} users) ===")
        
        processing_stats = await batch_manager.start_follow_ups_for_unverified_users(limit=test_limit)
        logger.info(f"Processing results: {processing_stats}")
        
        # Get updated statistics
        logger.info("\n=== UPDATED STATISTICS ===")
        updated_stats = await batch_manager.get_follow_up_stats()
        logger.info(f"Updated follow-up stats: {updated_stats}")
        
        # Wait a moment to see if any immediate follow-ups are triggered
        logger.info("\n=== WAITING FOR IMMEDIATE FOLLOW-UPS ===")
        logger.info("Waiting 10 seconds to see if any immediate follow-ups are sent...")
        await asyncio.sleep(10)
        
        # Show final statistics
        logger.info("\n=== FINAL STATISTICS ===")
        final_stats = await batch_manager.get_follow_up_stats()
        logger.info(f"Final follow-up stats: {final_stats}")
        
        # Optional: Cancel the test follow-ups to clean up
        logger.info("\n=== CLEANUP (Optional) ===")
        user_input = input("Do you want to cancel the test follow-ups? (y/N): ")
        if user_input.lower() == 'y':
            cancelled_count = await batch_manager.cancel_all_follow_ups()
            logger.info(f"Cancelled follow-ups for {cancelled_count} users")
        else:
            logger.info("Follow-ups left running. They will continue as scheduled.")
        
        # Clean up
        await application.shutdown()
        logger.info("\n=== TEST COMPLETED SUCCESSFULLY ===")
        
    except Exception as e:
        logger.error(f"Error during batch follow-up test: {e}")
        raise

async def test_convenience_functions():
    """Test the convenience functions"""
    
    logger.info("\n=== TESTING CONVENIENCE FUNCTIONS ===")
    
    try:
        # Initialize database
        db_manager = DatabaseManager()
        await db_manager.initialize()
        
        # Create bot
        application = ApplicationBuilder().token(BotConfig.BOT_TOKEN).build()
        await application.initialize()
        bot = application.bot
        
        # Initialize follow-up scheduler
        init_follow_up_scheduler(bot)
        
        # Test convenience functions
        logger.info("Testing get_batch_follow_up_stats...")
        stats = await get_batch_follow_up_stats(db_manager, bot)
        logger.info(f"Stats from convenience function: {stats}")
        
        logger.info("Testing start_batch_follow_ups with limit=1...")
        result = await start_batch_follow_ups(db_manager, bot, limit=1)
        logger.info(f"Result from convenience function: {result}")
        
        # Clean up
        await application.shutdown()
        logger.info("Convenience function tests completed")
        
    except Exception as e:
        logger.error(f"Error during convenience function test: {e}")
        raise

def main():
    """Run the tests"""
    print("OPTRIXTRADES Batch Follow-Up Test")
    print("=" * 50)
    print("This script will test the batch follow-up functionality.")
    print("It will find unverified users and start follow-up sequences for them.")
    print("")
    
    choice = input("Choose test: (1) Full batch test, (2) Convenience functions test, (3) Both: ")
    
    if choice == '1':
        asyncio.run(test_batch_follow_ups())
    elif choice == '2':
        asyncio.run(test_convenience_functions())
    elif choice == '3':
        asyncio.run(test_batch_follow_ups())
        asyncio.run(test_convenience_functions())
    else:
        print("Invalid choice. Running full batch test...")
        asyncio.run(test_batch_follow_ups())

if __name__ == "__main__":
    main()