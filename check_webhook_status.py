#!/usr/bin/env python3
"""
Check Telegram webhook status
"""

import asyncio
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import BotConfig
from telegram import Bot

async def check_webhook_status():
    """Check current webhook configuration"""
    try:
        bot = Bot(BotConfig.BOT_TOKEN)
        
        print("🔍 Checking webhook status...")
        info = await bot.get_webhook_info()
        
        print(f"\n📊 **Webhook Information:**")
        print(f"  🌐 Webhook URL: {info.url or 'Not set'}")
        print(f"  📬 Pending updates: {info.pending_update_count}")
        print(f"  🔢 Max connections: {info.max_connections}")
        print(f"  📝 Allowed updates: {info.allowed_updates}")
        
        if info.last_error_message:
            print(f"  ❌ Last error: {info.last_error_message}")
            print(f"  📅 Last error date: {info.last_error_date}")
        else:
            print(f"  ✅ No recent errors")
        
        # Check if webhook is properly configured
        if not info.url:
            print(f"\n⚠️  **Issue Found**: No webhook URL is set!")
            print(f"💡 The bot is likely not receiving updates from Telegram.")
        elif info.pending_update_count > 0:
            print(f"\n⚠️  **Issue Found**: {info.pending_update_count} pending updates")
            print(f"💡 The webhook might not be processing updates correctly.")
        else:
            print(f"\n✅ Webhook appears to be configured correctly")
        
        # Test bot token
        me = await bot.get_me()
        print(f"\n🤖 **Bot Information:**")
        print(f"  📛 Username: @{me.username}")
        print(f"  🆔 Bot ID: {me.id}")
        print(f"  ✅ Bot token is valid")
        
    except Exception as e:
        print(f"❌ Error checking webhook status: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check_webhook_status())