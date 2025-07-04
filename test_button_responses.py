#!/usr/bin/env python3
"""
Test script to verify button callback responses
"""

import asyncio
import sys
import os
from unittest.mock import Mock, AsyncMock

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from telegram_bot import TradingBot

class MockUpdate:
    def __init__(self, callback_data, user_id=12345):
        self.callback_query = Mock()
        self.callback_query.data = callback_data
        self.callback_query.from_user = Mock()
        self.callback_query.from_user.id = user_id
        self.callback_query.answer = AsyncMock()
        self.effective_user = Mock()
        self.effective_user.id = user_id

class MockContext:
    def __init__(self):
        self.bot = Mock()
        self.bot.send_message = AsyncMock()

async def test_button_callback(callback_data, description):
    """Test a specific button callback"""
    try:
        bot = TradingBot()
        update = MockUpdate(callback_data)
        context = MockContext()
        
        print(f"Testing: {description} (callback_data: '{callback_data}')")
        
        # Test the button callback
        await bot.button_callback(update, context)
        
        print(f"✅ {description} - SUCCESS")
        return True
        
    except NameError as e:
        print(f"❌ {description} - FUNCTION NOT FOUND: {e}")
        return False
    except Exception as e:
        print(f"⚠️  {description} - ERROR: {e}")
        return False

async def main():
    """Test all button callbacks"""
    print("🔍 Testing Button Callback Responses...\n")
    
    # Test cases for buttons mentioned by user
    test_cases = [
        ("get_vip_access", "VIP Access Button"),
        ("account_menu", "Account Menu Button"),
        ("help_menu", "Help Menu Button"),
        ("main_menu", "Main Menu Button"),
        ("start_trading", "Start Trading Button"),
        ("notification_settings", "Notification Settings Button"),
        ("contact_support", "Contact Support Button"),
        ("verification_help", "Verification Help Button"),
        ("registered", "I've Registered Button"),
        ("help_signup", "Help Signup Button"),
        ("help_deposit", "Help Deposit Button"),
        ("how_it_works", "How It Works Button"),
        ("start_verification", "Start Verification Button"),
        ("uid_help", "UID Help Button"),
        ("my_account", "My Account Button"),
        ("support", "Support Button"),
        ("vip_signals", "VIP Signals Button"),
        ("stats", "Stats Button"),
        ("broadcast", "Broadcast Button"),
        ("user_lookup", "User Lookup Button"),
        ("request_group_access", "Request Group Access Button"),
        ("confirm_group_joined", "Confirm Group Joined Button"),
        ("not_interested", "Not Interested Button"),
        ("admin_queue", "Admin Queue Button"),
        ("admin_activity", "Admin Activity Button"),
        ("admin_dashboard", "Admin Dashboard Button"),
        ("unknown_button", "Unknown Button (should show 'Feature coming soon!')"),
    ]
    
    passed = 0
    failed = 0
    
    for callback_data, description in test_cases:
        success = await test_button_callback(callback_data, description)
        if success:
            passed += 1
        else:
            failed += 1
        print()  # Empty line for readability
    
    print(f"📊 SUMMARY:")
    print(f"  ✅ Passed: {passed}")
    print(f"  ❌ Failed: {failed}")
    print(f"  📋 Total: {passed + failed}")
    
    if failed > 0:
        print(f"\n🚨 {failed} button(s) are not working properly!")
        return False
    else:
        print(f"\n✅ All buttons are working correctly!")
        return True

if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        sys.exit(1)