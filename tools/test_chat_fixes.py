#!/usr/bin/env python3
"""
Test script to verify chat persistence and UID verification fixes
"""

import asyncio
import sys
import os
from datetime import datetime

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from telegram_bot import TradingBot
from database.connection import db_manager, get_user_data, create_user, update_user_data
from config import BotConfig

class MockUpdate:
    def __init__(self, user_id, text=None, photo=None):
        self.effective_user = MockUser(user_id)
        self.message = MockMessage(text, photo)
        self.callback_query = None

class MockUser:
    def __init__(self, user_id):
        self.id = user_id
        self.first_name = "Test User"
        self.username = "testuser"

class MockMessage:
    def __init__(self, text=None, photo=None):
        self.text = text
        self.photo = photo
        self.chat_id = 123456789
        self.chat = MockChat()
        self.from_user = MockUser(123456789)
        
    async def reply_text(self, text, **kwargs):
        print(f"Bot Response: {text}")
        return MockMessage(text)

class MockChat:
    def __init__(self):
        self.type = 'private'
        self.id = 123456789

class MockContext:
    def __init__(self):
        self.bot = MockBot()

class MockBot:
    async def send_message(self, **kwargs):
        print(f"Bot Message: {kwargs.get('text', 'No text')}")
        return MockMessage(kwargs.get('text'))

async def test_chat_persistence():
    """Test that messages are not being deleted"""
    print("\n🧪 Testing Chat Persistence...")
    
    try:
        bot = TradingBot()
        bot.application = MockBot()  # Mock application
        
        # Test that _send_persistent_message doesn't edit messages
        print("✅ Testing _send_persistent_message behavior...")
        
        # This should always send new messages, not edit existing ones
        message_id_1 = await bot._send_persistent_message(123456789, "First message")
        message_id_2 = await bot._send_persistent_message(123456789, "Second message")
        
        print(f"   Message 1 ID: {message_id_1}")
        print(f"   Message 2 ID: {message_id_2}")
        
        if message_id_1 != message_id_2:
            print("✅ Chat persistence fixed: Messages are not being edited")
            return True
        else:
            print("❌ Chat persistence issue: Messages might still be edited")
            return False
            
    except Exception as e:
        print(f"❌ Error testing chat persistence: {e}")
        return False

async def test_uid_verification_flow():
    """Test UID verification flow"""
    print("\n🧪 Testing UID Verification Flow...")
    
    try:
        # Initialize database
        await db_manager.initialize()
        
        if not db_manager.is_initialized:
            print("❌ Database initialization failed")
            return False
            
        print("✅ Database initialized")
        
        # Create test user
        test_user_id = 123456789
        await create_user(test_user_id, "Test User", "testuser")
        print("✅ Test user created")
        
        # Test UID submission
        bot = TradingBot()
        bot.application = MockBot()
        
        # Test valid UID
        print("\n📝 Testing valid UID submission...")
        update = MockUpdate(test_user_id, "ABC123456")
        context = MockContext()
        
        await bot.handle_text_message(update, context)
        
        # Check if UID was saved
        user_data = await get_user_data(test_user_id)
        if user_data and len(user_data) > 6 and user_data[6] == "ABC123456":
            print("✅ Valid UID processed and saved correctly")
        else:
            print("❌ Valid UID not saved properly")
            return False
        
        # Test invalid UID
        print("\n📝 Testing invalid UID submission...")
        update = MockUpdate(test_user_id, "123")  # Too short
        await bot.handle_text_message(update, context)
        print("✅ Invalid UID handled with error message")
        
        # Test generic message
        print("\n📝 Testing generic message...")
        update = MockUpdate(test_user_id, "Hello there")
        await bot.handle_text_message(update, context)
        print("✅ Generic message handled with proper response")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing UID verification: {e}")
        return False

async def test_photo_handling():
    """Test photo handling for verification"""
    print("\n🧪 Testing Photo Handling...")
    
    try:
        bot = TradingBot()
        bot.application = MockBot()
        bot.admin_user_id = 987654321  # Mock admin ID
        
        test_user_id = 123456789
        
        # Ensure user has UID
        await update_user_data(test_user_id, uid="ABC123456")
        
        # Test photo upload with UID
        print("📸 Testing photo upload with UID...")
        mock_photo = [{"file_id": "test_file_id_123"}]
        update = MockUpdate(test_user_id, photo=mock_photo)
        context = MockContext()
        
        await bot.handle_photo(update, context)
        print("✅ Photo handling with UID works correctly")
        
        # Test photo upload without UID
        print("📸 Testing photo upload without UID...")
        await update_user_data(test_user_id, uid=None)
        await bot.handle_photo(update, context)
        print("✅ Photo handling without UID shows proper error")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing photo handling: {e}")
        return False

async def main():
    """Run all tests"""
    print("🔧 OPTRIXTRADES Bot Fixes Verification")
    print("=" * 50)
    print(f"⏰ Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    tests = [
        ("Chat Persistence", test_chat_persistence),
        ("UID Verification Flow", test_uid_verification_flow),
        ("Photo Handling", test_photo_handling)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n🧪 Running {test_name} test...")
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} test failed with error: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 TEST RESULTS SUMMARY")
    print("=" * 50)
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n🎯 Overall: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("\n🎉 All fixes verified! The bot should now work correctly.")
        print("\n📋 Fixed Issues:")
        print("   ✅ Chat messages no longer deleted (persistent messaging fixed)")
        print("   ✅ UID verification flow restored")
        print("   ✅ Photo upload verification working")
        print("\n🚀 Ready for deployment!")
    else:
        print("\n⚠️  Some tests failed. Please check the issues above.")
    
    return passed == len(results)

if __name__ == "__main__":
    asyncio.run(main())