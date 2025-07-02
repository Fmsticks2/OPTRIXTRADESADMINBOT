import asyncio
import logging
from telegram_bot import main, BOT_TOKEN, BROKER_LINK, PREMIUM_CHANNEL_ID, ADMIN_USERNAME

def display_bot_info():
    """Display bot configuration before starting"""
    print("🚀 OPTRIXTRADES Telegram Bot")
    print("=" * 50)
    print(f"📱 Bot Token: {BOT_TOKEN[:10]}...{BOT_TOKEN[-10:]}")
    print(f"🔗 Broker Link: {BROKER_LINK}")
    print(f"📢 Premium Channel: {PREMIUM_CHANNEL_ID}")
    print(f"👨‍💼 Admin: @{ADMIN_USERNAME}")
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
        main()
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
    except Exception as e:
        print(f"\n❌ Bot error: {e}")
