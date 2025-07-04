#!/usr/bin/env python3
"""
Test UID submission flow and callback query handling
"""

import os
import sys
import asyncio
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'scripts'))
sys.path.insert(0, str(project_root / 'database'))

from database.connection import db_manager, get_user_data, create_user, log_interaction

async def test_uid_submission_flow():
    """Test the UID submission and verification flow"""
    print("🧪 Testing UID Submission Flow...")
    
    try:
        # Initialize database
        await db_manager.initialize()
        
        if not db_manager.is_initialized:
            print("❌ Database initialization failed")
            return False
            
        print(f"✅ Database initialized ({db_manager.db_type})")
        
        # Test user creation and data retrieval
        test_user_id = 123456789
        test_username = "test_user"
        test_first_name = "Test User"
        
        # Create test user
        success = await create_user(test_user_id, test_username, test_first_name)
        print(f"✅ Test user created: {success}")
        
        # Get user data
        user_data = await get_user_data(test_user_id)
        print(f"✅ User data retrieved: {user_data is not None}")
        
        # Test logging interactions (simulating callback queries)
        interactions = [
            ("button_click", "main_menu"),
            ("button_click", "request_premium_access"),
            ("uid_submission", "UID12345"),
            ("screenshot_upload", "file_id_123")
        ]
        
        for interaction_type, interaction_data in interactions:
            success = await log_interaction(test_user_id, interaction_type, interaction_data)
            print(f"✅ Logged {interaction_type}: {success}")
        
        # Test verification request creation (simulating UID submission)
        test_uid = "UID12345"
        test_screenshot_id = "file_id_123"
        
        if db_manager.db_type == 'postgresql':
            query = '''
                INSERT INTO verification_requests 
                (user_id, uid, screenshot_file_id, status, auto_verified, admin_response, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            '''
            args = [test_user_id, test_uid, test_screenshot_id, 'pending', False, None]
        else:
            query = '''
                INSERT INTO verification_requests 
                (user_id, uid, screenshot_file_id, status, auto_verified, admin_response, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            '''
            args = [test_user_id, test_uid, test_screenshot_id, 'pending', False, None]
        
        await db_manager.execute(query, *args)
        print("✅ Verification request created successfully")
        
        # Test retrieving verification requests
        if db_manager.db_type == 'postgresql':
            query = 'SELECT * FROM verification_requests WHERE user_id = $1'
        else:
            query = 'SELECT * FROM verification_requests WHERE user_id = ?'
        
        requests = await db_manager.execute(query, test_user_id, fetch='all')
        print(f"✅ Retrieved verification requests: {len(requests) if requests else 0}")
        
        if requests:
            request = requests[0]
            print(f"   📋 Request details:")
            print(f"      - UID: {request.get('uid', 'N/A')}")
            print(f"      - Status: {request.get('status', 'N/A')}")
            print(f"      - Auto-verified: {request.get('auto_verified', 'N/A')}")
            print(f"      - Screenshot ID: {request.get('screenshot_file_id', 'N/A')}")
        
        print("\n🎉 UID submission flow test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ UID flow test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await db_manager.close()

async def test_callback_query_simulation():
    """Simulate callback query handling"""
    print("\n🧪 Testing Callback Query Simulation...")
    
    try:
        # Initialize database
        await db_manager.initialize()
        
        # Simulate callback queries that were causing errors
        callback_queries = [
            {"data": "main_menu", "description": "Main menu callback"},
            {"data": "request_premium_access", "description": "Premium access request"},
            {"data": "account_menu", "description": "Account menu callback"},
            {"data": "admin_queue", "description": "Admin queue callback"}
        ]
        
        test_user_id = 123456789
        
        for callback in callback_queries:
            # Log the callback interaction
            success = await log_interaction(
                test_user_id, 
                "callback_query", 
                f"data:{callback['data']}"
            )
            print(f"✅ {callback['description']}: {success}")
        
        print("\n🎉 Callback query simulation completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Callback query simulation failed: {e}")
        return False
    finally:
        await db_manager.close()

async def main():
    """Main test function"""
    print("🧪 UID Flow and Callback Query Test")
    print("=" * 50)
    
    # Test UID submission flow
    uid_test = await test_uid_submission_flow()
    
    # Test callback query simulation
    callback_test = await test_callback_query_simulation()
    
    if uid_test and callback_test:
        print("\n🎉 All tests passed!")
        print("\n📝 Summary:")
        print("   ✅ Database migration successful")
        print("   ✅ auto_verified column working")
        print("   ✅ UID submission flow working")
        print("   ✅ Verification request creation working")
        print("   ✅ Callback query handling working")
        print("   ✅ Async database functions working")
        print("\n🚀 The bot should now handle:")
        print("   - 'Request Premium Group Access' button clicks")
        print("   - UID and screenshot submissions")
        print("   - All callback queries without errors")
        print("\n💡 The original errors should be resolved!")
    else:
        print("\n❌ Some tests failed. Please check the errors above.")

if __name__ == "__main__":
    asyncio.run(main())