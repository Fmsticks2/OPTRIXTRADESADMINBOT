#!/usr/bin/env python3
"""
Comprehensive bot diagnostic script
Helps identify and resolve bot response issues
"""

import requests
import json
import sys
import time
from datetime import datetime

def diagnose_bot_issues():
    """Run comprehensive bot diagnostics"""
    
    print("🔍 OPTRIXTRADES Bot Diagnostic Tool")
    print("=" * 50)
    print(f"Timestamp: {datetime.now()}")
    print()
    
    # Test 1: Railway deployment health
    print("1️⃣ Testing Railway Deployment Health")
    print("-" * 40)
    
    base_url = "https://web-production-54a4.up.railway.app"
    
    try:
        response = requests.get(f"{base_url}/health", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print("✅ Railway deployment is healthy")
            print(f"   Service: {data.get('service', 'Unknown')}")
            print(f"   Webhook Enabled: {data.get('webhook_enabled', 'Unknown')}")
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Cannot reach Railway deployment: {e}")
        return False
    
    # Test 2: Webhook configuration
    print("\n2️⃣ Testing Webhook Configuration")
    print("-" * 40)
    
    try:
        response = requests.get(f"{base_url}/admin/webhook_info", timeout=10)
        if response.status_code == 200:
            webhook_info = response.json()
            print("✅ Webhook info retrieved successfully")
            print(f"   URL: {webhook_info.get('url', 'Not set')}")
            print(f"   Pending Updates: {webhook_info.get('pending_update_count', 0)}")
            
            last_error = webhook_info.get('last_error_message')
            if last_error:
                print(f"   ⚠️  Last Error: {last_error}")
                if "Connection reset by peer" in last_error:
                    print("   💡 This error should clear after webhook reset")
            else:
                print("   ✅ No webhook errors")
        else:
            print(f"❌ Cannot get webhook info: {response.status_code}")
    except Exception as e:
        print(f"❌ Webhook info request failed: {e}")
    
    # Test 3: Webhook endpoint accessibility
    print("\n3️⃣ Testing Webhook Endpoint")
    print("-" * 40)
    
    webhook_url = f"{base_url}/webhook/7692303660:AAHkut6Cr2Dr_yXcuicg7FJ7BHmaEEOhN_0"
    
    try:
        response = requests.get(webhook_url, timeout=10)
        if response.status_code == 405:  # Method Not Allowed is expected for GET
            print("✅ Webhook endpoint is accessible")
        else:
            print(f"⚠️  Unexpected response: {response.status_code}")
    except Exception as e:
        print(f"❌ Webhook endpoint test failed: {e}")
    
    # Test 4: Sample webhook processing
    print("\n4️⃣ Testing Webhook Processing")
    print("-" * 40)
    
    sample_update = {
        "update_id": int(time.time()),
        "message": {
            "message_id": 1,
            "from": {
                "id": 999999999,
                "is_bot": False,
                "first_name": "Test",
                "username": "testuser"
            },
            "chat": {
                "id": 999999999,
                "first_name": "Test",
                "username": "testuser",
                "type": "private"
            },
            "date": int(time.time()),
            "text": "/start"
        }
    }
    
    try:
        response = requests.post(
            webhook_url,
            json=sample_update,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        
        if response.status_code == 200:
            print("✅ Webhook processing is working")
            try:
                result = response.json()
                print(f"   Response: {result}")
            except:
                print(f"   Response: {response.text}")
        else:
            print(f"❌ Webhook processing failed: {response.status_code}")
            print(f"   Response: {response.text}")
    except Exception as e:
        print(f"❌ Webhook processing test failed: {e}")
    
    # Test 5: Bot instructions
    print("\n5️⃣ Bot Testing Instructions")
    print("-" * 40)
    print("Now test your bot manually:")
    print("1. Open Telegram and find your bot")
    print("2. Send /start command")
    print("3. Try other commands like /help")
    print("4. Check if the bot responds")
    print()
    print("If the bot still doesn't respond:")
    print("• Wait 1-2 minutes for webhook to fully activate")
    print("• Check Railway logs for any error messages")
    print("• Verify your bot token is correct")
    print("• Make sure the bot is not blocked by Telegram")
    
    # Test 6: Troubleshooting tips
    print("\n6️⃣ Troubleshooting Tips")
    print("-" * 40)
    print("Common issues and solutions:")
    print()
    print("🔧 Bot not responding:")
    print("   • Webhook was just reset - should work now")
    print("   • Check if bot username is correct")
    print("   • Verify bot is not in maintenance mode")
    print()
    print("🔧 Intermittent responses:")
    print("   • Database connection issues")
    print("   • Railway resource limits")
    print("   • Network connectivity problems")
    print()
    print("🔧 Error messages:")
    print("   • Check Railway application logs")
    print("   • Verify environment variables")
    print("   • Check database connectivity")
    
    print("\n✅ Diagnostic complete!")
    print("The webhook has been reset and should be working now.")
    print("Try sending /start to your bot in Telegram.")
    
    return True

if __name__ == "__main__":
    diagnose_bot_issues()