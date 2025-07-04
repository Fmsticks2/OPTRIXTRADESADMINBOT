#!/usr/bin/env python3
"""
Webhook Fix Script - Diagnose and fix webhook issues
"""

import os
import asyncio
import aiohttp
from datetime import datetime

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
RAILWAY_URL = os.getenv('RAILWAY_URL', 'https://web-production-54a4.up.railway.app')
WEBHOOK_SECRET_TOKEN = os.getenv('WEBHOOK_SECRET_TOKEN')

async def check_current_webhook():
    """Check current webhook configuration"""
    print("\n🔍 Checking Current Webhook Configuration...")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f'https://api.telegram.org/bot{BOT_TOKEN}/getWebhookInfo') as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data['ok']:
                        webhook_info = data['result']
                        print(f"   🔗 Current Webhook URL: {webhook_info.get('url', 'Not set')}")
                        print(f"   📊 Pending Updates: {webhook_info.get('pending_update_count', 0)}")
                        print(f"   🔒 Has Custom Certificate: {webhook_info.get('has_custom_certificate', False)}")
                        print(f"   🔌 Max Connections: {webhook_info.get('max_connections', 0)}")
                        
                        if webhook_info.get('last_error_message'):
                            print(f"   ❌ Last Error: {webhook_info['last_error_message']}")
                            error_date = webhook_info.get('last_error_date', 0)
                            if error_date:
                                print(f"   🕐 Error Date: {datetime.fromtimestamp(error_date)}")
                        else:
                            print("   ✅ No webhook errors")
                        
                        return webhook_info
                    else:
                        print(f"   ❌ API Error: {data}")
                        return None
                else:
                    print(f"   ❌ HTTP Error: {resp.status}")
                    return None
    except Exception as e:
        print(f"   ❌ Exception: {e}")
        return None

async def test_railway_webhook():
    """Test if Railway webhook endpoint is accessible"""
    print("\n🚂 Testing Railway Webhook Endpoint...")
    try:
        webhook_url = f"{RAILWAY_URL}/webhook/{BOT_TOKEN}"
        print(f"   🔗 Testing URL: {webhook_url}")
        
        # Test with a dummy payload
        test_payload = {
            "update_id": 999999,
            "message": {
                "message_id": 999999,
                "from": {"id": 123456789, "first_name": "Test"},
                "chat": {"id": 123456789, "type": "private"},
                "date": int(datetime.now().timestamp()),
                "text": "TEST123456"
            }
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json=test_payload, timeout=10) as resp:
                if resp.status == 200:
                    result = await resp.text()
                    print(f"   ✅ Webhook endpoint is accessible")
                    print(f"   📝 Response: {result}")
                    return True
                else:
                    error_text = await resp.text()
                    print(f"   ❌ Webhook endpoint error: {resp.status}")
                    print(f"   📝 Error: {error_text}")
                    return False
    except Exception as e:
        print(f"   ❌ Exception: {e}")
        return False

async def set_new_webhook():
    """Set a new webhook URL"""
    print("\n🔧 Setting New Webhook...")
    try:
        webhook_url = f"{RAILWAY_URL}/webhook/{BOT_TOKEN}"
        print(f"   🔗 Setting webhook to: {webhook_url}")
        
        payload = {
            'url': webhook_url,
            'max_connections': 100,
            'drop_pending_updates': True,
            'allowed_updates': ['message', 'callback_query']
        }
        
        if WEBHOOK_SECRET_TOKEN:
            payload['secret_token'] = WEBHOOK_SECRET_TOKEN
            print(f"   🔒 Using secret token: {WEBHOOK_SECRET_TOKEN[:10]}...")
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f'https://api.telegram.org/bot{BOT_TOKEN}/setWebhook',
                json=payload,
                timeout=30
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data['ok']:
                        print(f"   ✅ Webhook set successfully!")
                        return True
                    else:
                        print(f"   ❌ Webhook set failed: {data}")
                        return False
                else:
                    error_text = await resp.text()
                    print(f"   ❌ HTTP Error: {resp.status}")
                    print(f"   📝 Error: {error_text}")
                    return False
    except Exception as e:
        print(f"   ❌ Exception: {e}")
        return False

async def delete_webhook():
    """Delete current webhook"""
    print("\n🗑️ Deleting Current Webhook...")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f'https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook',
                json={'drop_pending_updates': True},
                timeout=30
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data['ok']:
                        print(f"   ✅ Webhook deleted successfully!")
                        return True
                    else:
                        print(f"   ❌ Webhook deletion failed: {data}")
                        return False
                else:
                    error_text = await resp.text()
                    print(f"   ❌ HTTP Error: {resp.status}")
                    print(f"   📝 Error: {error_text}")
                    return False
    except Exception as e:
        print(f"   ❌ Exception: {e}")
        return False

async def send_test_message():
    """Send a test message to verify bot is working"""
    print("\n📤 Testing Bot Response...")
    print("   ⚠️ Manual testing required:")
    print("   1. Send 'ABC123456' to your bot")
    print("   2. Expected response: '✅ UID Received: ABC123456'")
    print("   3. If you get a generic response or no response, there's still an issue")

async def main():
    print("🔧 WEBHOOK FIX SCRIPT")
    print("=" * 50)
    
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN not found in environment variables")
        return
    
    print(f"🤖 Bot Token: {BOT_TOKEN[:10]}...")
    print(f"🚂 Railway URL: {RAILWAY_URL}")
    
    # Step 1: Check current webhook
    webhook_info = await check_current_webhook()
    
    # Step 2: Test Railway endpoint
    railway_ok = await test_railway_webhook()
    
    if not railway_ok:
        print("\n❌ Railway webhook endpoint is not accessible!")
        print("   This could be why the bot is not responding.")
        return
    
    # Step 3: Check if webhook needs to be reset
    expected_webhook = f"{RAILWAY_URL}/webhook/{BOT_TOKEN}"
    current_webhook = webhook_info.get('url', '') if webhook_info else ''
    
    if current_webhook != expected_webhook or (webhook_info and webhook_info.get('last_error_message')):
        print(f"\n🔄 Webhook needs to be reset:")
        print(f"   Current: {current_webhook}")
        print(f"   Expected: {expected_webhook}")
        
        # Delete old webhook
        await delete_webhook()
        
        # Wait a moment
        await asyncio.sleep(2)
        
        # Set new webhook
        success = await set_new_webhook()
        
        if success:
            # Wait for webhook to be active
            await asyncio.sleep(3)
            
            # Check webhook again
            await check_current_webhook()
            
            print("\n✅ Webhook has been reset!")
        else:
            print("\n❌ Failed to set new webhook")
            return
    else:
        print("\n✅ Webhook configuration looks correct")
    
    # Step 4: Test bot
    await send_test_message()
    
    print("\n" + "=" * 50)
    print("🎯 SUMMARY:")
    print("   - Webhook endpoint is accessible")
    print("   - Webhook has been configured/reset")
    print("   - Bot should now respond to UIDs")
    print("   - Test by sending 'ABC123456' to your bot")

if __name__ == "__main__":
    asyncio.run(main())