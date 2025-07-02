"""
Universal bot runner - supports both polling and webhook modes
"""

import asyncio
import logging
import sys
from config import config

logger = logging.getLogger(__name__)

def run_polling_mode():
    """Run bot in polling mode (development)"""
    from telegram_bot import main
    print("🔄 Starting bot in POLLING mode...")
    main()

def run_webhook_mode():
    """Run bot in webhook mode (production)"""
    from webhook.webhook_server import run_webhook_server
    print("🌐 Starting bot in WEBHOOK mode...")
    run_webhook_server()

def main():
    """Main runner function"""
    print("🚀 OPTRIXTRADES Bot Runner")
    print("=" * 30)
    
    # Check mode from environment or command line
    mode = config.BOT_MODE.lower() if hasattr(config, 'BOT_MODE') else 'polling'
    
    # Command line override
    if len(sys.argv) > 1:
        mode = sys.argv[1].lower()
    
    print(f"📡 Mode: {mode.upper()}")
    print(f"🤖 Auto-verification: {'Enabled' if config.AUTO_VERIFY_ENABLED else 'Disabled'}")
    print(f"👨‍💼 Admin: @{config.ADMIN_USERNAME}")
    print("=" * 30)
    
    try:
        if mode == 'webhook':
            run_webhook_mode()
        elif mode == 'polling':
            run_polling_mode()
        else:
            print("❌ Invalid mode. Use 'polling' or 'webhook'")
            print("Usage: python bot_runner.py [polling|webhook]")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot runner error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
