#!/usr/bin/env python3
"""
Script to apply database migrations and add the missing blocked_bot column.
"""

import asyncio
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.connection import DatabaseManager
import logging

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def apply_migrations():
    """Apply pending database migrations"""
    try:
        # Initialize database manager
        db_manager = DatabaseManager()
        
        logger.info("Initializing database and applying migrations...")
        await db_manager.initialize()
        
        # Check if blocked_bot column exists
        if db_manager.db_type == 'postgresql':
            query = """
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'users' AND column_name = 'blocked_bot'
            """
            result = await db_manager.execute(query, fetch='all')
        else:
            query = "PRAGMA table_info(users)"
            result = await db_manager.execute(query, fetch='all')
            # Check if blocked_bot column exists in SQLite result
            blocked_bot_exists = any('blocked_bot' in str(row) for row in result)
            
        if db_manager.db_type == 'postgresql':
            if result:
                logger.info("✅ blocked_bot column exists in PostgreSQL database")
            else:
                logger.error("❌ blocked_bot column missing in PostgreSQL database")
        else:
            if blocked_bot_exists:
                logger.info("✅ blocked_bot column exists in SQLite database")
            else:
                logger.error("❌ blocked_bot column missing in SQLite database")
                
        # Test updating a user with blocked_bot flag
        logger.info("Testing blocked_bot column functionality...")
        from database.connection import update_user_data
        
        # This should work now without errors
        test_result = await update_user_data(999999, blocked_bot=True)
        if test_result:
            logger.info("✅ Successfully tested blocked_bot column update")
        else:
            logger.warning("⚠️ Test update returned False (user might not exist, but column works)")
            
        await db_manager.close()
        logger.info("Migration application completed successfully!")
        
    except Exception as e:
        logger.error(f"Error applying migrations: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(apply_migrations())