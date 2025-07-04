#!/usr/bin/env python3
"""
Quick verification script to test if the bot fixes are working on Railway
"""

import requests
import json
from datetime import datetime

def test_railway_deployment():
    """Test if Railway deployment is accessible"""
    print("🧪 Testing Railway Deployment...")
    
    base_url = "https://web-production-54a4.up.railway.app"
    
    endpoints = [
        ("/", "Root endpoint"),
        ("/health", "Health check"),
        ("/admin/webhook_info", "Webhook info")
    ]
    
    for endpoint, description in endpoints:
        try:
            response = requests.get(f"{base_url}{endpoint}", timeout=10)
            status = "✅ OK" if response.status_code == 200 else f"❌ {response.status_code}"
            print(f"   {description}: {status}")
        except Exception as e:
            print(f"   {description}: ❌ Error - {e}")

def test_webhook_processing():
    """Test webhook can process updates"""
    print("\n🧪 Testing Webhook Processing...")
    
    webhook_url = "https://web-production-54a4.up.railway.app/webhook/7692303660:AAHkut6Cr2Dr_yXcuicg7FJ7BHmaEEOhN_0"
    
    # Sample update for testing
    test_update = {
        "update_id": 123456789,
        "message": {
            "message_id": 1,
            "from": {
                "id": 123456789,
                "is_bot": False,
                "first_name": "Test",
                "username": "testuser"
            },
            "chat": {
                "id": 123456789,
                "first_name": "Test",
                "username": "testuser",
                "type": "private"
            },
            "date": 1234567890,
            "text": "/start"
        }
    }
    
    try:
        response = requests.post(
            webhook_url,
            json=test_update,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        if response.status_code == 200:
            print("   ✅ Webhook processing: OK")
            print(f"   Response: {response.text}")
        else:
            print(f"   ❌ Webhook processing failed: {response.status_code}")
            
    except Exception as e:
        print(f"   ❌ Webhook test error: {e}")

def check_webhook_status():
    """Check current webhook status"""
    print("\n🧪 Checking Webhook Status...")
    
    try:
        response = requests.get(
            "https://web-production-54a4.up.railway.app/admin/webhook_info",
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            print("   ✅ Webhook Status Retrieved")
            print(f"   URL: {data.get('url', 'Not set')}")
            print(f"   Pending Updates: {data.get('pending_update_count', 'Unknown')}")
            
            last_error = data.get('last_error_message')
            if last_error:
                print(f"   ⚠️  Last Error: {last_error}")
            else:
                print("   ✅ No errors reported")
        else:
            print(f"   ❌ Failed to get webhook status: {response.status_code}")
            
    except Exception as e:
        print(f"   ❌ Error checking webhook status: {e}")

def main():
    """Run verification tests"""
    print("🔧 OPTRIXTRADES Bot Fixes Verification")
    print("=" * 50)
    print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🌐 Testing Railway deployment...")
    
    # Test deployment accessibility
    test_railway_deployment()
    
    # Check webhook status
    check_webhook_status()
    
    # Test webhook processing
    test_webhook_processing()
    
    print("\n" + "=" * 50)
    print("📋 VERIFICATION COMPLETE")
    print("=" * 50)
    
    print("\n🎯 Next Steps:")
    print("1. If all tests pass ✅, your bot fixes are deployed successfully")
    print("2. Test manually in Telegram:")
    print("   • Send /start to your bot")
    print("   • Try the verification flow")
    print("   • Send a UID (e.g., ABC123456)")
    print("   • Upload a screenshot")
    print("   • Verify chat history is preserved")
    print("\n3. If tests fail ❌:")
    print("   • Check Railway dashboard for deployment status")
    print("   • Review deployment logs for errors")
    print("   • Ensure environment variables are set correctly")
    
    print("\n🚀 The fixes should resolve:")
    print("   ✅ Chat messages being deleted")
    print("   ✅ UID verification flow not working")
    print("   ✅ Generic responses instead of proper verification")

if __name__ == "__main__":
    main()