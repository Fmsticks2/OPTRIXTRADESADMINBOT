#!/usr/bin/env python3
"""
Fix webhook URL to include the correct path with bot token
"""

import asyncio
from telegram import Bot
from config import config


async def fix_webhook_url():
    """Fix the webhook URL to include the bot token in the path"""
    try:
        bot = Bot(token=config.BOT_TOKEN)

        # Current webhook URL
        current_info = await bot.get_webhook_info()
        print(f"🔍 Current webhook URL: {current_info.url}")
        print(f"📬 Pending updates: {current_info.pending_update_count}")

        if current_info.last_error_message:
            print(f"❌ Last error: {current_info.last_error_message}")

        # Correct webhook URL
        correct_webhook_url = f"https://bot.optrixtrades.com/webhook/{config.BOT_TOKEN}"
        print(f"\n🔧 Setting correct webhook URL: {correct_webhook_url}")

        # Set the correct webhook URL
        result = await bot.set_webhook(
            url=correct_webhook_url,
            secret_token=(
                config.WEBHOOK_SECRET_TOKEN if config.WEBHOOK_SECRET_TOKEN else None
            ),
            max_connections=100,
            drop_pending_updates=True,  # Clear pending updates
            allowed_updates=[
                "message",
                "callback_query",
                "inline_query",
                "chat_join_request",
            ],
        )

        if result:
            print("✅ Webhook URL updated successfully!")

            # Verify the new webhook
            new_info = await bot.get_webhook_info()
            print(f"\n📊 New webhook information:")
            print(f"  🌐 URL: {new_info.url}")
            print(f"  📬 Pending updates: {new_info.pending_update_count}")
            print(f"  🔢 Max connections: {new_info.max_connections}")
            print(f"  📝 Allowed updates: {new_info.allowed_updates}")

            if new_info.last_error_message:
                print(f"  ❌ Last error: {new_info.last_error_message}")
            else:
                print("  ✅ No errors")

        else:
            print("❌ Failed to set webhook URL")

    except Exception as e:
        print(f"❌ Error fixing webhook URL: {e}")
        return False

    return result


if __name__ == "__main__":
    print("🔧 OPTRIXTRADES Webhook URL Fix")
    print("=" * 40)

    result = asyncio.run(fix_webhook_url())

    if result:
        print("\n🎉 Webhook URL fixed successfully!")
        print("\n📱 Your bot should now work properly in Telegram.")
        print("\n🚀 Next steps:")
        print("   1. Make sure your webhook server is running")
        print("   2. Test the bot by sending /start in Telegram")
    else:
        print("\n❌ Failed to fix webhook URL. Please check your configuration.")
