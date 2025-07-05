"""Main entry point for OPTRIXTRADES Telegram Bot

This file serves as the entry point for the OPTRIXTRADES Telegram Bot application.
The codebase has been refactored with the following improvements:

1. Modular Structure: Code organized into logical modules for better maintainability
2. Enhanced Error Handling: Comprehensive error handling with detailed logging
3. Improved Logging: Structured logging with different levels and formats
4. Database Connection Fix: Proper handling of DATABASE_URL with validation
5. ConversationHandler Fix: Updated per_message parameter to address PTBUserWarning
6. Utility Decorators: Added decorators for admin-only, verified-only, rate limiting
7. Documentation: Added comprehensive docstrings and README updates

The application supports both polling and webhook modes and includes features for
user verification, admin management, and VIP signal distribution.
"""

import asyncio
import logging
import os
import sys

# Add the project root directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import BotConfig, validate_and_report_config
from database.connection import DatabaseManager
from telegram_bot.bot import TradingBot
from telegram_bot.utils.logger import setup_logging


async def main():
    """Main function to initialize and run the bot."""
    # Setup logging
    setup_logging()
    logger = logging.getLogger(__name__)
    
    try:
        # Validate configuration
        logger.info("Validating configuration...")
        validation_result = validate_and_report_config(force_validation=True)
        if validation_result and not validation_result['valid']:
            logger.critical("Configuration validation failed. Please check your environment variables.")
            sys.exit(1)
        
        # Initialize database manager
        logger.info("Initializing database connection...")
        db_manager = DatabaseManager()
        await db_manager.initialize()
        
        # Initialize bot
        logger.info("Initializing Telegram bot...")
        bot = TradingBot(db_manager=db_manager)
        await bot.initialize()
        
        # Run the bot
        logger.info(f"Starting bot in {BotConfig.BOT_MODE} mode...")
        await bot.run()
        
    except Exception as e:
        logger.critical(f"Failed to start the bot: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    # Run the main function
    asyncio.run(main())