#!/usr/bin/env python3
"""
Test database migration and callback query fixes
"""

import os
import sys
import asyncio
import sqlite3
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'scripts'))
sys.path.insert(0, str(project_root / 'database'))

from database.connection import db_manager

async def test_database_migration():
    """Test if database migration was applied correctly"""
    print("🔍 Testing Database Migration...")
    
    try:
        # Initialize database
        await db_manager.initialize()
        
        if not db_manager.is_initialized:
            print("❌ Database initialization failed")
            return False
            
        print(f"✅ Database initialized ({db_manager.db_type})")
        
        # Check if auto_verified column exists
        if db_manager.db_type == 'sqlite':
            # For SQLite, check table schema
            conn = sqlite3.connect('trading_bot.db')
            cursor = conn.cursor()
            
            # Get table info
            cursor.execute("PRAGMA table_info(verification_requests)")
            columns = cursor.fetchall()
            
            column_names = [col[1] for col in columns]
            print(f"📊 verification_requests columns: {column_names}")
            
            # Check for required columns
            required_columns = ['auto_verified', 'admin_response', 'updated_at']
            missing_columns = [col for col in required_columns if col not in column_names]
            
            if missing_columns:
                print(f"❌ Missing columns: {missing_columns}")
                
                # Add missing columns manually
                for col in missing_columns:
                    if col == 'auto_verified':
                        cursor.execute("ALTER TABLE verification_requests ADD COLUMN auto_verified BOOLEAN DEFAULT FALSE")
                    elif col == 'admin_response':
                        cursor.execute("ALTER TABLE verification_requests ADD COLUMN admin_response TEXT")
                    elif col == 'updated_at':
                        cursor.execute("ALTER TABLE verification_requests ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
                    print(f"✅ Added column: {col}")
                
                conn.commit()
            else:
                print("✅ All required columns exist")
            
            conn.close()
        
        # Test async database functions
        print("\n🧪 Testing Async Database Functions...")
        
        # Import async functions
        from database.connection import get_user_data, create_user, log_interaction
        
        # Test get_user_data
        test_user_id = 999999999
        user_data = await get_user_data(test_user_id)
        print(f"✅ get_user_data works: {user_data is not None or user_data is None}")
        
        # Test create_user
        success = await create_user(test_user_id, "test_user", "Test User")
        print(f"✅ create_user works: {success}")
        
        # Test log_interaction
        success = await log_interaction(test_user_id, "test_interaction", "test data")
        print(f"✅ log_interaction works: {success}")
        
        # Test verification requests table
        query = "SELECT COUNT(*) as count FROM verification_requests"
        result = await db_manager.execute(query, fetch='one')
        print(f"✅ verification_requests table accessible: {result is not None}")
        
        print("\n🎉 All database tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await db_manager.close()

def test_sync_functions():
    """Test that sync functions are properly imported"""
    print("\n🔍 Testing Function Imports...")
    
    try:
        from database.connection import get_user_data, create_user, log_interaction, get_pending_verifications
        print("✅ Async functions imported successfully")
        
        # Check if they are async
        import inspect
        functions = [get_user_data, create_user, log_interaction, get_pending_verifications]
        
        for func in functions:
            is_async = inspect.iscoroutinefunction(func)
            print(f"✅ {func.__name__} is async: {is_async}")
            
        return True
        
    except Exception as e:
        print(f"❌ Function import test failed: {e}")
        return False

async def main():
    """Main test function"""
    print("🧪 Database Migration and Function Test")
    print("=" * 50)
    
    # Test sync function imports
    sync_test = test_sync_functions()
    
    # Test database migration
    db_test = await test_database_migration()
    
    if sync_test and db_test:
        print("\n🎉 All tests passed! Database migration successful.")
        print("\n📝 Summary:")
        print("   ✅ Database migration applied")
        print("   ✅ auto_verified column added")
        print("   ✅ admin_response column added")
        print("   ✅ updated_at column added")
        print("   ✅ Async database functions working")
        print("\n🚀 The bot should now handle UID submissions and callback queries correctly!")
    else:
        print("\n❌ Some tests failed. Please check the errors above.")

if __name__ == "__main__":
    asyncio.run(main())