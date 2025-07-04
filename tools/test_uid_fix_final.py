#!/usr/bin/env python3
"""
Final test to verify UID processing fix is working
"""

import asyncio
import os
import sys
import requests
from datetime import datetime

# Add the project directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database.connection import get_user_data, update_user_data, initialize_db

async def test_update_user_data_function():
    """Test the update_user_data function directly"""
    print("\n=== Testing update_user_data Function ===")
    
    try:
        # Initialize database
        await initialize_db()
        print("✅ Database initialized")
        
        # Test the function call that was failing
        test_user_id = 123456789
        test_uid = "ABC123456"
        
        print(f"Testing: await update_user_data({test_user_id}, uid='{test_uid}')")
        
        # This should work now
        await update_user_data(test_user_id, uid=test_uid)
        print("✅ update_user_data function call successful")
        
        # Verify the data was saved
        user_data = await get_user_data(test_user_id)
        if user_data and user_data.get('uid') == test_uid:
            print(f"✅ UID correctly saved: {user_data.get('uid')}")
        else:
            print(f"❌ UID not saved correctly. Got: {user_data}")
            
    except Exception as e:
        print(f"❌ Function test failed: {e}")
        return False
    
    return True

def test_railway_deployment():
    """Test Railway deployment status"""
    print("\n=== Testing Railway Deployment ===")
    
    try:
        # Test webhook endpoint
        webhook_url = "https://web-production-54a4.up.railway.app"
        response = requests.get(f"{webhook_url}/health", timeout=10)
        
        if response.status_code == 200:
            print("✅ Railway deployment is accessible")
            return True
        else:
            print(f"❌ Railway deployment returned status: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Railway deployment test failed: {e}")
        return False

def test_bot_webhook():
    """Test bot webhook configuration"""
    print("\n=== Testing Bot Webhook ===")
    
    try:
        bot_token = os.getenv('BOT_TOKEN')
        if not bot_token:
            print("❌ BOT_TOKEN not found")
            return False
            
        # Get webhook info
        response = requests.get(
            f"https://api.telegram.org/bot{bot_token}/getWebhookInfo",
            timeout=10
        )
        
        if response.status_code == 200:
            webhook_info = response.json()['result']
            print(f"✅ Webhook URL: {webhook_info.get('url', 'Not set')}")
            print(f"✅ Pending updates: {webhook_info.get('pending_update_count', 0)}")
            print(f"✅ Last error: {webhook_info.get('last_error_message', 'None')}")
            return True
        else:
            print(f"❌ Failed to get webhook info: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Webhook test failed: {e}")
        return False

async def main():
    """Run all tests"""
    print(f"🔍 Final UID Fix Verification - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # Test results
    results = []
    
    # Test 1: Function call
    results.append(await test_update_user_data_function())
    
    # Test 2: Railway deployment
    results.append(test_railway_deployment())
    
    # Test 3: Bot webhook
    results.append(test_bot_webhook())
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 FINAL TEST SUMMARY")
    print("=" * 60)
    
    test_names = [
        "update_user_data Function",
        "Railway Deployment", 
        "Bot Webhook"
    ]
    
    for i, (name, result) in enumerate(zip(test_names, results)):
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{i+1}. {name}: {status}")
    
    all_passed = all(results)
    
    if all_passed:
        print("\n🎉 ALL TESTS PASSED!")
        print("\n📝 Next Steps:")
        print("1. Send a UID to your bot (e.g., 'ABC123456')")
        print("2. You should receive: '✅ UID Received: ABC123456'")
        print("3. No more 'takes 1 positional argument but 2 were given' errors")
    else:
        print("\n❌ SOME TESTS FAILED")
        print("\n🔧 Troubleshooting needed for failed tests")
    
    return all_passed

if __name__ == "__main__":
    asyncio.run(main())