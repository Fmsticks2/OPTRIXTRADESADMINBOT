#!/usr/bin/env python3
"""
Script to start persistent follow-ups for all unverified users in the database.
This ensures that both new and existing unverified users receive the persistent follow-up sequence.
"""

import asyncio
import logging
from telegram import Bot
from config import BotConfig
from database.connection import initialize_db
from telegram_bot.bot import TradingBot

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def main():
    """Main function to start persistent follow-ups for all unverified users"""
    try:
        logger.info("Starting persistent follow-up initialization for all unverified users...")
        
        # Initialize database
        await initialize_db()
        logger.info("Database initialized")
        
        # Get database manager instance
        from database.connection import db_manager
        
        # Create bot instance
        bot = Bot(token=BotConfig.BOT_TOKEN)
        
        # Create TradingBot instance
        trading_bot = TradingBot(db_manager)
        
        # Initialize persistent schedulers
        trading_bot.init_persistent_scheduler(bot)
        logger.info("Persistent schedulers initialized")
        
        # Start persistent follow-ups for all unverified users
        stats = await trading_bot.start_persistent_follow_ups_for_all_unverified()
        
        # Display results
        logger.info("\n=== PERSISTENT FOLLOW-UP INITIALIZATION RESULTS ===")
        logger.info(f"Total users processed: {stats['processed']}")
        logger.info(f"Persistent follow-ups started: {stats['started_persistent']}")
        logger.info(f"Enhanced follow-ups started: {stats['started_enhanced']}")
        logger.info(f"Already active: {stats['already_active']}")
        logger.info(f"Failed: {stats['failed']}")
        
        if stats['processed'] > 0:
            success_rate = ((stats['started_persistent'] + stats['started_enhanced']) / (stats['processed'] * 2)) * 100
            logger.info(f"Success rate: {success_rate:.1f}%")
        
        logger.info("\n=== SUMMARY ===")
        if stats['started_persistent'] > 0 or stats['started_enhanced'] > 0:
            logger.info("✅ Persistent follow-ups have been successfully started for unverified users.")
            logger.info("📧 Users will now receive follow-up messages every 8 hours (persistent) and 3 messages every 24 hours (enhanced).")
            logger.info("🔄 The system will automatically check verification status and stop follow-ups when users complete verification.")
        else:
            logger.info("ℹ️ No new persistent follow-ups were started (users may already have active follow-ups).")
        
        logger.info("\nPersistent follow-up initialization completed successfully!")
        
    except Exception as e:
        logger.error(f"Error during persistent follow-up initialization: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())