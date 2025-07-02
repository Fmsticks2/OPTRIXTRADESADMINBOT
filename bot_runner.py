"""
Universal bot runner - supports both polling and webhook modes
"""

import asyncio
import logging
import sys
import os
import threading
import signal
from flask import Flask, jsonify
from config import config

logger = logging.getLogger(__name__)

# Global Flask app for health checks
health_app = Flask(__name__)

@health_app.route('/health')
def health_check():
    return jsonify({'status': 'healthy', 'service': 'optrixtrades-bot'}), 200

@health_app.route('/')
def home():
    return jsonify({'message': 'OPTRIXTRADES Bot is running', 'mode': getattr(config, 'BOT_MODE', 'polling')}), 200

def start_health_server():
    """Start health check server in a separate thread"""
    def run_health_server():
        port = int(os.environ.get('PORT', 8000))
        logger.info(f"🏥 Starting health check server on port {port}")
        health_app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
    
    health_thread = threading.Thread(target=run_health_server, daemon=True)
    health_thread.start()
    return health_thread

def run_polling_mode():
    """Run bot in polling mode (development)"""
    from telegram_bot import main
    print("🔄 Starting bot in POLLING mode...")
    
    # Start health server for Railway compatibility
    health_thread = start_health_server()
    
    # Give health server time to start
    import time
    time.sleep(2)
    
    # Run the bot
    main()

def run_webhook_mode():
    """Run bot in webhook mode (production)"""
    try:
        from webhook.webhook_server import run_webhook_server
        print("🌐 Starting bot in WEBHOOK mode...")
        
        # Check if webhook server handles health checks
        try:
            from health_check import start_health_server as webhook_health_server
            webhook_health_server()
        except ImportError:
            # Fallback to our health server
            logger.info("Using fallback health server for webhook mode")
            start_health_server()
            import time
            time.sleep(2)
        
        # Run webhook server
        run_webhook_server()
        
    except ImportError as e:
        logger.error(f"Webhook dependencies not found: {e}")
        logger.info("Falling back to polling mode with health server...")
        run_polling_mode()

def run_railway_mode():
    """Special mode for Railway deployment - always includes health server"""
    print("🚄 Starting bot in RAILWAY mode...")
    
    # Always start health server for Railway
    health_thread = start_health_server()
    
    # Give health server time to start
    import time
    time.sleep(3)
    
    # Determine which bot mode to use
    bot_mode = getattr(config, 'BOT_MODE', 'polling').lower()
    
    if bot_mode == 'webhook':
        try:
            from webhook.webhook_server import run_webhook_server
            logger.info("Running webhook server alongside health server...")
            run_webhook_server()
        except ImportError:
            logger.info("Webhook not available, using polling mode...")
            from telegram_bot import main
            main()
    else:
        # Default to polling
        from telegram_bot import main
        main()

def setup_signal_handlers():
    """Setup graceful shutdown handlers"""
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        sys.exit(0)
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

def main():
    """Main runner function"""
    print("🚀 OPTRIXTRADES Bot Runner")
    print("=" * 30)
    
    # Setup signal handlers
    setup_signal_handlers()
    
    # Detect if running on Railway
    is_railway = os.environ.get('RAILWAY_ENVIRONMENT') is not None
    
    # Check mode from environment or command line
    mode = getattr(config, 'BOT_MODE', 'polling').lower()
    
    # Command line override
    if len(sys.argv) > 1:
        mode = sys.argv[1].lower()
    
    # Force railway mode if on Railway platform
    if is_railway and mode not in ['railway', 'webhook']:
        mode = 'railway'
        print("🚄 Railway deployment detected, using Railway mode")
    
    print(f"📡 Mode: {mode.upper()}")
    print(f"🤖 Auto-verification: {'Enabled' if config.AUTO_VERIFY_ENABLED else 'Disabled'}")
    print(f"👨‍💼 Admin: @{config.ADMIN_USERNAME}")
    print(f"🌐 Platform: {'Railway' if is_railway else 'Local'}")
    
    if is_railway:
        port = os.environ.get('PORT', 8000)
        print(f"🔌 Health check port: {port}")
    
    print("=" * 30)
    
    try:
        if mode == 'railway':
            run_railway_mode()
        elif mode == 'webhook':
            run_webhook_mode()
        elif mode == 'polling':
            run_polling_mode()
        else:
            print("❌ Invalid mode. Use 'polling', 'webhook', or 'railway'")
            print("Usage: python bot_runner.py [polling|webhook|railway]")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot runner error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()