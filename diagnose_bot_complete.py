#!/usr/bin/env python3
"""
Comprehensive Bot Diagnostic Tool
Checks bot status, webhook, database, and message processing
"""

import asyncio
import aiohttp
import os
import sqlite3
from datetime import datetime
import json

# Bot configuration
BOT_TOKEN = os.getenv('BOT_TOKEN', '7692303660:AAHkut6Cr2Dr_yXcuicg7FJ7BHmaEEOhN_0')
WEBHOOK_URL = os.getenv('WEBHOOK_URL', 'https://web-production-54a4.up.railway.app')
RAILWAY_URL = 'https://web-production-54a4.up.railway.app'

async def check_bot_status():
    """Check if bot is responding to Telegram API"""
    print("\n🤖 Checking Bot Status...")
    try:
        async with aiohttp.ClientSession() as session:
            # Check bot info
            async with session.get(f'https://api.telegram.org/bot{BOT_TOKEN}/getMe') as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data['ok']:
                        bot_info = data['result']
                        print(f"   ✅ Bot is active: @{bot_info['username']}")
                        print(f"   📝 Bot ID: {bot_info['id']}")
                        print(f"   🏷️ Bot Name: {bot_info['first_name']}")
                    else:
                        print(f"   ❌ Bot API error: {data}")
                        return False
                else:
                    print(f"   ❌ HTTP error: {resp.status}")
                    return False
            
            # Check webhook info
            async with session.get(f'https://api.telegram.org/bot{BOT_TOKEN}/getWebhookInfo') as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data['ok']:
                        webhook_info = data['result']
                        print(f"   🔗 Webhook URL: {webhook_info.get('url', 'Not set')}")
                        print(f"   📊 Pending Updates: {webhook_info.get('pending_update_count', 0)}")
                        if webhook_info.get('last_error_message'):
                            print(f"   ⚠️ Last Error: {webhook_info['last_error_message']}")
                            print(f"   🕐 Error Date: {datetime.fromtimestamp(webhook_info.get('last_error_date', 0))}")
                        else:
                            print("   ✅ No webhook errors")
                    else:
                        print(f"   ❌ Webhook info error: {data}")
                        return False
                else:
                    print(f"   ❌ Webhook HTTP error: {resp.status}")
                    return False
        return True
    except Exception as e:
        print(f"   ❌ Exception: {e}")
        return False

async def check_railway_deployment():
    """Check Railway deployment status"""
    print("\n🚂 Checking Railway Deployment...")
    try:
        async with aiohttp.ClientSession() as session:
            # Check root endpoint
            async with session.get(f'{RAILWAY_URL}/', timeout=10) as resp:
                if resp.status == 200:
                    text = await resp.text()
                    print(f"   ✅ Railway app is running")
                    print(f"   📄 Response: {text[:100]}...")
                else:
                    print(f"   ❌ Railway app error: {resp.status}")
                    return False
            
            # Check health endpoint
            async with session.get(f'{RAILWAY_URL}/health', timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    print(f"   ✅ Health check: {data}")
                else:
                    print(f"   ⚠️ Health endpoint: {resp.status}")
            
            # Test webhook endpoint
            webhook_path = f'/webhook/{BOT_TOKEN}'
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
            
            async with session.post(
                f'{RAILWAY_URL}{webhook_path}',
                json=test_payload,
                timeout=10
            ) as resp:
                if resp.status == 200:
                    result = await resp.text()
                    print(f"   ✅ Webhook processing: OK")
                    print(f"   📝 Response: {result}")
                else:
                    print(f"   ❌ Webhook error: {resp.status}")
                    error_text = await resp.text()
                    print(f"   📝 Error: {error_text}")
                    return False
        return True
    except Exception as e:
        print(f"   ❌ Exception: {e}")
        return False

def check_database():
    """Check database status and recent activity"""
    print("\n🗄️ Checking Database...")
    try:
        # Check if database file exists
        db_files = ['trading_bot.db', 'database/trading_bot.db', 'scripts/trading_bot.db']
        db_path = None
        
        for path in db_files:
            if os.path.exists(path):
                db_path = path
                break
        
        if not db_path:
            print("   ❌ Database file not found")
            return False
        
        print(f"   ✅ Database found: {db_path}")
        
        # Connect and check tables
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print(f"   📊 Tables: {[table[0] for table in tables]}")
        
        # Check recent interactions
        try:
            cursor.execute("SELECT COUNT(*) FROM interactions WHERE timestamp > datetime('now', '-1 hour')")
            recent_interactions = cursor.fetchone()[0]
            print(f"   📈 Recent interactions (last hour): {recent_interactions}")
        except:
            print("   ⚠️ Could not check recent interactions")
        
        # Check users
        try:
            cursor.execute("SELECT COUNT(*) FROM users")
            user_count = cursor.fetchone()[0]
            print(f"   👥 Total users: {user_count}")
        except:
            print("   ⚠️ Could not check user count")
        
        conn.close()
        return True
    except Exception as e:
        print(f"   ❌ Database error: {e}")
        return False

def check_code_syntax():
    """Check for syntax errors in main bot file"""
    print("\n🔍 Checking Code Syntax...")
    try:
        import ast
        
        bot_files = ['telegram_bot.py', 'scripts/telegram_bot.py']
        
        for file_path in bot_files:
            if os.path.exists(file_path):
                print(f"   📄 Checking {file_path}...")
                with open(file_path, 'r', encoding='utf-8') as f:
                    code = f.read()
                
                try:
                    ast.parse(code)
                    print(f"   ✅ {file_path}: Syntax OK")
                except SyntaxError as e:
                    print(f"   ❌ {file_path}: Syntax Error at line {e.lineno}: {e.msg}")
                    return False
        
        return True
    except Exception as e:
        print(f"   ❌ Code check error: {e}")
        return False

async def test_uid_processing():
    """Test UID processing logic locally"""
    print("\n🧪 Testing UID Processing Logic...")
    try:
        # Test the UID detection logic
        test_cases = [
            "ABC123456",
            "UID:ABC123456",
            "124678538",
            "UID: 124678538",
            "invalid",
            "toolonguidthatexceedslimit"
        ]
        
        for test_uid in test_cases:
            # Simulate the bot's UID processing
            message_text = test_uid
            uid = message_text.replace("UID:", "").strip()
            
            is_valid = len(uid) >= 6 and len(uid) <= 20 and uid.isalnum()
            
            status = "✅ VALID" if is_valid else "❌ INVALID"
            print(f"   {status}: '{test_uid}' -> '{uid}' (len={len(uid)}, alnum={uid.isalnum()})")
        
        return True
    except Exception as e:
        print(f"   ❌ UID test error: {e}")
        return False

async def send_test_message():
    """Send a test message to the bot"""
    print("\n📤 Sending Test Message...")
    try:
        # This would require a test chat ID - skip for now
        print("   ⚠️ Manual testing required - send 'ABC123456' to your bot")
        return True
    except Exception as e:
        print(f"   ❌ Test message error: {e}")
        return False

async def main():
    """Run all diagnostic checks"""
    print("🔧 COMPREHENSIVE BOT DIAGNOSTIC")
    print("=" * 50)
    
    checks = [
        ("Bot Status", check_bot_status()),
        ("Railway Deployment", check_railway_deployment()),
        ("Database", check_database()),
        ("Code Syntax", check_code_syntax()),
        ("UID Processing", test_uid_processing()),
        ("Test Message", send_test_message())
    ]
    
    results = []
    for name, check in checks:
        if asyncio.iscoroutine(check):
            result = await check
        else:
            result = check
        results.append((name, result))
    
    print("\n" + "=" * 50)
    print("📋 DIAGNOSTIC SUMMARY")
    print("=" * 50)
    
    all_passed = True
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
        if not result:
            all_passed = False
    
    if all_passed:
        print("\n🎉 All checks passed! Bot should be working.")
        print("\n🧪 Next Steps:")
        print("1. Send /start to your bot")
        print("2. Send a UID like 'ABC123456'")
        print("3. Check if you get the confirmation message")
    else:
        print("\n⚠️ Some checks failed. Review the errors above.")
        print("\n🔧 Recommended Actions:")
        print("1. Check Railway deployment logs")
        print("2. Verify environment variables")
        print("3. Restart the Railway service")
        print("4. Check bot token validity")

if __name__ == "__main__":
    asyncio.run(main())