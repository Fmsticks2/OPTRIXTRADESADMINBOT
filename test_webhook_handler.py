#!/usr/bin/env python3
"""
Test webhook handler with a sample Telegram update
"""

import requests
import json
import sys

def test_webhook_handler():
    """Test webhook handler with sample update"""
    
    webhook_url = "https://web-production-54a4.up.railway.app/webhook/7692303660:AAHkut6Cr2Dr_yXcuicg7FJ7BHmaEEOhN_0"
    
    # Sample Telegram update (start command)
    sample_update = {
        "update_id": 123456789,
        "message": {
            "message_id": 1,
            "from": {
                "id": 123456789,
                "is_bot": False,
                "first_name": "Test",
                "username": "testuser",
                "language_code": "en"
            },
            "chat": {
                "id": 123456789,
                "first_name": "Test",
                "username": "testuser",
                "type": "private"
            },
            "date": 1625097600,
            "text": "/start",
            "entities": [
                {
                    "offset": 0,
                    "length": 6,
                    "type": "bot_command"
                }
            ]
        }
    }
    
    print("🧪 Testing Webhook Handler")
    print("=" * 30)
    print(f"URL: {webhook_url}")
    print(f"Sample Update: {json.dumps(sample_update, indent=2)}")
    
    try:
        # Send POST request to webhook
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'TelegramBot (like TwitterBot)'
        }
        
        response = requests.post(
            webhook_url, 
            json=sample_update,
            headers=headers,
            timeout=30
        )
        
        print(f"\n📊 Response Status: {response.status_code}")
        print(f"📊 Response Headers: {dict(response.headers)}")
        
        try:
            response_data = response.json()
            print(f"📊 Response Body: {json.dumps(response_data, indent=2)}")
        except:
            print(f"📊 Response Body: {response.text}")
        
        if response.status_code == 200:
            print("\n✅ Webhook handler is working correctly!")
        else:
            print(f"\n❌ Webhook handler returned error: {response.status_code}")
            
    except requests.exceptions.Timeout:
        print("\n❌ Timeout - Webhook handler is taking too long to respond")
        print("💡 This could indicate a processing issue in the bot")
    except requests.exceptions.ConnectionError as e:
        print(f"\n❌ Connection Error: {e}")
        print("💡 The webhook endpoint may not be properly configured")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
    
    print("\n🔍 Additional Debugging:")
    print("1. Check Railway logs for any error messages")
    print("2. Verify bot token is correct in environment variables")
    print("3. Check if database connection is working")
    print("4. Ensure all required environment variables are set")

if __name__ == "__main__":
    test_webhook_handler()