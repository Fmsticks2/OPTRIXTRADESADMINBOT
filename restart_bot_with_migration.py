#!/usr/bin/env python3
"""
Restart bot with database migration
"""

import os
import sys
import asyncio
import logging
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'scripts'))
sys.path.insert(0, str(project_root / 'database'))

from database.connection import db_manager
from scripts.telegram_bot import main

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def restart_with_migration():
    """Restart bot with database migration"""
    try:
        logger.info("🔄 Restarting bot with database migration...")
        
        # Initialize database (this will run migrations)
        logger.info("📊 Initializing database with migrations...")
        await db_manager.initialize()
        
        if db_manager.is_initialized:
            logger.info("✅ Database initialized successfully")
            logger.info(f"📊 Database type: {db_manager.db_type}")
        else:
            logger.error("❌ Database initialization failed")
            return
        
        # Start the bot
        logger.info("🤖 Starting Telegram bot...")
        await main()
        
    except Exception as e:
        logger.error(f"❌ Error during restart: {e}")
        raise

if __name__ == "__main__":
    # Force polling mode
    os.environ['FORCE_POLLING'] = 'true'
    
    try:
        asyncio.run(restart_with_migration())
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped by user")
    except Exception as e:
        logger.error(f"💥 Fatal error: {e}")
        sys.exit(1)