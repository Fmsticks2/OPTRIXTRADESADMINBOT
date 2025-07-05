import asyncio
import logging
from main import main
from config import BotConfig

def display_bot_info():
    """Display bot configuration before starting"""
    print("🚀 OPTRIXTRADES Telegram Bot")
    print("=" * 50)
    print(f"📱 Bot Token: {BotConfig.BOT_TOKEN[:10]}...{BotConfig.BOT_TOKEN[-10:]}")
    print(f"🔗 Broker Link: {BotConfig.BROKER_LINK}")
    print(f"📢 Premium Channel: {BotConfig.PREMIUM_CHANNEL_ID}")
    print(f"👨‍💼 Admin: @{BotConfig.ADMIN_USERNAME}")
    print("=" * 50)
    print()
    print("🎯 Bot Features:")
    print("✅ Welcome & Hook Flow")
    print("✅ Registration & Activation")
    print("✅ UID & Deposit Verification")
    print("✅ Premium Channel Access")
    print("✅ 10-Day Follow-up Sequences")
    print("✅ Admin Support Integration")
    print()
    print("🔄 Starting bot...")
    print("Press Ctrl+C to stop")
    print("=" * 50)

if __name__ == '__main__':
    display_bot_info()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
    except Exception as e:
        print(f"\n❌ Bot error: {e}")
