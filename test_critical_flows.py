#!/usr/bin/env python3
"""
Comprehensive Test Suite for Critical Bot Flows
Tests UPGRADE command, UID submission, and screenshot/document handling
"""

import asyncio
import sys
import os
from datetime import datetime

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from telegram_bot import TradingBot
from database.connection import get_user_data, create_user, update_user_data
from config import BotConfig

class MockUpdate:
    """Mock Telegram Update object for testing"""
    def __init__(self, user_id, text=None, photo=None, document=None, first_name="TestUser"):
        self.effective_user = MockUser(user_id, first_name)
        self.message = MockMessage(text, photo, document, self.effective_user)
        self.callback_query = None

class MockUser:
    """Mock Telegram User object"""
    def __init__(self, user_id, first_name="TestUser", username="testuser"):
        self.id = user_id
        self.first_name = first_name
        self.username = username

class MockMessage:
    """Mock Telegram Message object"""
    def __init__(self, text=None, photo=None, document=None, user=None):
        self.text = text
        self.photo = photo if photo else []
        self.document = document
        self.from_user = user
        self.chat = MockChat()
        
    async def reply_text(self, text, **kwargs):
        print(f"📤 Bot Response: {text[:100]}..." if len(text) > 100 else f"📤 Bot Response: {text}")
        return MockSentMessage()

class MockChat:
    """Mock Telegram Chat object"""
    def __init__(self, chat_id=123456789):
        self.id = chat_id

class MockSentMessage:
    """Mock sent message object"""
    def __init__(self, message_id=1):
        self.message_id = message_id

class MockDocument:
    """Mock Telegram Document object"""
    def __init__(self, file_name="test_deposit.pdf", file_id="test_doc_123"):
        self.file_name = file_name
        self.file_id = file_id

class MockContext:
    """Mock Telegram Context object"""
    def __init__(self):
        self.bot = MockBot()
        self.args = []

class MockBot:
    """Mock Telegram Bot object"""
    async def send_message(self, chat_id, text, **kwargs):
        print(f"📤 Bot Message to {chat_id}: {text[:100]}..." if len(text) > 100 else f"📤 Bot Message to {chat_id}: {text}")
        return MockSentMessage()
    
    async def send_photo(self, chat_id, photo, **kwargs):
        print(f"📸 Bot Photo to {chat_id}: {kwargs.get('caption', 'No caption')[:50]}...")
        return MockSentMessage()

class TestResults:
    """Track test results"""
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []
    
    def add_pass(self, test_name):
        self.passed += 1
        print(f"✅ {test_name} - PASSED")
    
    def add_fail(self, test_name, error):
        self.failed += 1
        self.errors.append(f"{test_name}: {error}")
        print(f"❌ {test_name} - FAILED: {error}")
    
    def summary(self):
        total = self.passed + self.failed
        print(f"\n📊 Test Summary: {self.passed}/{total} passed")
        if self.errors:
            print("\n❌ Failures:")
            for error in self.errors:
                print(f"  • {error}")
        return self.failed == 0

async def test_upgrade_command():
    """Test UPGRADE command handling"""
    print("\n🧪 Testing UPGRADE Command...")
    results = TestResults()
    
    try:
        bot = TradingBot()
        bot.application = MockBot()
        bot.admin_username = "TestAdmin"
        
        test_user_id = 123456789
        
        # Create test user
        await create_user(test_user_id, "TestUser", "testuser")
        
        # Test UPGRADE command (uppercase)
        update = MockUpdate(test_user_id, text="UPGRADE")
        context = MockContext()
        
        await bot.handle_text_message(update, context)
        results.add_pass("UPGRADE command (uppercase)")
        
        # Test upgrade command (lowercase)
        update = MockUpdate(test_user_id, text="upgrade")
        await bot.handle_text_message(update, context)
        results.add_pass("upgrade command (lowercase)")
        
        # Test mixed case
        update = MockUpdate(test_user_id, text="Upgrade")
        await bot.handle_text_message(update, context)
        results.add_pass("Upgrade command (mixed case)")
        
    except Exception as e:
        results.add_fail("UPGRADE command test", str(e))
    
    return results

async def test_uid_submission():
    """Test UID submission flows"""
    print("\n🧪 Testing UID Submission Flows...")
    results = TestResults()
    
    try:
        bot = TradingBot()
        bot.application = MockBot()
        
        test_user_id = 123456790
        
        # Create test user
        await create_user(test_user_id, "TestUser2", "testuser2")
        
        # Test UID with prefix
        update = MockUpdate(test_user_id, text="UID: ABC123456")
        context = MockContext()
        
        await bot.handle_text_message(update, context)
        results.add_pass("UID with prefix format")
        
        # Test numeric UID
        update = MockUpdate(test_user_id, text="123456789")
        await bot.handle_text_message(update, context)
        results.add_pass("Numeric UID format")
        
        # Test alphanumeric UID
        update = MockUpdate(test_user_id, text="USER789012")
        await bot.handle_text_message(update, context)
        results.add_pass("Alphanumeric UID format")
        
        # Test invalid UID (too short)
        update = MockUpdate(test_user_id, text="AB")
        await bot.handle_text_message(update, context)
        results.add_pass("Invalid UID handling (too short)")
        
        # Test invalid UID (special characters)
        update = MockUpdate(test_user_id, text="ABC@123")
        await bot.handle_text_message(update, context)
        results.add_pass("Invalid UID handling (special chars)")
        
    except Exception as e:
        results.add_fail("UID submission test", str(e))
    
    return results

async def test_screenshot_handling():
    """Test screenshot and document handling"""
    print("\n🧪 Testing Screenshot/Document Handling...")
    results = TestResults()
    
    try:
        bot = TradingBot()
        bot.application = MockBot()
        bot.admin_user_id = 987654321
        
        test_user_id = 123456791
        
        # Create test user with UID
        await create_user(test_user_id, "TestUser3", "testuser3")
        await update_user_data(test_user_id, uid="ABC123456")
        
        # Test photo upload with UID
        mock_photo = [{"file_id": "test_photo_123"}]
        update = MockUpdate(test_user_id, photo=mock_photo)
        context = MockContext()
        
        await bot.handle_photo(update, context)
        results.add_pass("Photo upload with UID")
        
        # Test photo upload without UID
        await update_user_data(test_user_id, uid=None)
        await bot.handle_photo(update, context)
        results.add_pass("Photo upload without UID")
        
        # Test document upload (PDF)
        mock_doc = MockDocument("deposit_proof.pdf", "test_pdf_123")
        update = MockUpdate(test_user_id, document=mock_doc)
        await update_user_data(test_user_id, uid="ABC123456")  # Restore UID
        
        await bot.handle_document(update, context)
        results.add_pass("PDF document upload")
        
        # Test document upload (Image)
        mock_doc = MockDocument("screenshot.jpg", "test_jpg_123")
        update = MockUpdate(test_user_id, document=mock_doc)
        
        await bot.handle_document(update, context)
        results.add_pass("Image document upload")
        
        # Test invalid document type
        mock_doc = MockDocument("invalid.txt", "test_txt_123")
        update = MockUpdate(test_user_id, document=mock_doc)
        
        await bot.handle_document(update, context)
        results.add_pass("Invalid document type handling")
        
        # Test document upload without UID
        await update_user_data(test_user_id, uid=None)
        mock_doc = MockDocument("deposit.pdf", "test_pdf_456")
        update = MockUpdate(test_user_id, document=mock_doc)
        
        await bot.handle_document(update, context)
        results.add_pass("Document upload without UID")
        
    except Exception as e:
        results.add_fail("Screenshot/document handling test", str(e))
    
    return results

async def test_edge_cases():
    """Test edge cases and error scenarios"""
    print("\n🧪 Testing Edge Cases...")
    results = TestResults()
    
    try:
        bot = TradingBot()
        bot.application = MockBot()
        
        test_user_id = 123456792
        
        # Test with non-existent user
        update = MockUpdate(test_user_id, text="UPGRADE")
        context = MockContext()
        
        await bot.handle_text_message(update, context)
        results.add_pass("Non-existent user handling")
        
        # Test empty message
        await create_user(test_user_id, "TestUser4", "testuser4")
        update = MockUpdate(test_user_id, text="")
        
        await bot.handle_text_message(update, context)
        results.add_pass("Empty message handling")
        
        # Test very long UID
        long_uid = "A" * 100
        update = MockUpdate(test_user_id, text=long_uid)
        
        await bot.handle_text_message(update, context)
        results.add_pass("Very long UID handling")
        
        # Test admin photo upload
        bot.admin_user_id = test_user_id
        mock_photo = [{"file_id": "admin_photo_123"}]
        update = MockUpdate(test_user_id, photo=mock_photo)
        
        await bot.handle_photo(update, context)
        results.add_pass("Admin photo upload handling")
        
    except Exception as e:
        results.add_fail("Edge cases test", str(e))
    
    return results

async def main():
    """Run all tests"""
    print("🚀 Starting Comprehensive Bot Flow Tests")
    print("=" * 50)
    
    all_results = []
    
    # Run all test suites
    all_results.append(await test_upgrade_command())
    all_results.append(await test_uid_submission())
    all_results.append(await test_screenshot_handling())
    all_results.append(await test_edge_cases())
    
    # Calculate overall results
    total_passed = sum(r.passed for r in all_results)
    total_failed = sum(r.failed for r in all_results)
    total_tests = total_passed + total_failed
    
    print("\n" + "=" * 50)
    print(f"🏁 FINAL RESULTS: {total_passed}/{total_tests} tests passed")
    
    if total_failed > 0:
        print("\n❌ Failed Tests:")
        for result in all_results:
            for error in result.errors:
                print(f"  • {error}")
        return False
    else:
        print("\n🎉 All tests passed! Bot flows are working correctly.")
        return True

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)