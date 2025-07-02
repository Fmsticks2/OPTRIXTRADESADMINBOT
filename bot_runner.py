"""
Universal bot runner - supports both polling and webhook modes with FastAPI
"""

import asyncio
import logging
import sys
import os
import threading
import signal
from contextlib import asynccontextmanager
from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import JSONResponse
import uvicorn
from config import config

logger = logging.getLogger(__name__)

# Global variables for health server management
health_server = None
health_thread = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan context manager for startup/shutdown events"""
    logger.info("🚀 FastAPI application starting up...")
    yield
    logger.info("🛑 FastAPI application shutting down...")

# FastAPI app for health checks
health_app = FastAPI(
    title="OPTRIXTRADES Bot Health Check",
    description="Health check and status endpoint for OPTRIXTRADES Bot",
    version="1.0.0",
    lifespan=lifespan
)

@health_app.get('/health')
async def health_check():
    """Health check endpoint for Railway and other platforms"""
    try:
        # Add some basic health checks
        return JSONResponse(
            content={
                'status': 'healthy', 
                'service': 'optrixtrades-bot',
                'mode': getattr(config, 'BOT_MODE', 'polling'),
                'timestamp': str(asyncio.get_event_loop().time()),
                'platform': 'Railway' if os.environ.get('RAILWAY_ENVIRONMENT') else 'Local'
            },
            status_code=200,
            headers={
                'Cache-Control': 'no-cache',
                'Content-Type': 'application/json'
            }
        )
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return JSONResponse(
            content={
                'status': 'unhealthy',
                'error': str(e)
            },
            status_code=503
        )

@health_app.get('/')
async def home():
    """Root endpoint with bot information"""
    return JSONResponse(
        content={
            'message': 'OPTRIXTRADES Bot is running',
            'mode': getattr(config, 'BOT_MODE', 'polling'),
            'status': 'active',
            'admin': f"@{config.ADMIN_USERNAME}",
            'auto_verify': config.AUTO_VERIFY_ENABLED
        },
        status_code=200
    )

@health_app.get('/debug')
async def debug_info():
    """Debug endpoint to help troubleshoot Railway deployment"""
    import psutil
    import platform
    
    try:
        return JSONResponse(
            content={
                'python_version': platform.python_version(),
                'platform': platform.platform(),
                'railway_env': os.environ.get('RAILWAY_ENVIRONMENT', 'Not set'),
                'port': os.environ.get('PORT', 'Not set'),
                'cpu_percent': psutil.cpu_percent(),
                'memory_percent': psutil.virtual_memory().percent,
                'bot_config': {
                    'mode': getattr(config, 'BOT_MODE', 'polling'),
                    'admin': config.ADMIN_USERNAME,
                    'auto_verify': config.AUTO_VERIFY_ENABLED
                },
                'environment_vars': {
                    k: ('***' if 'token' in k.lower() or 'key' in k.lower() else v)
                    for k, v in os.environ.items() 
                    if k.startswith(('BOT_', 'RAILWAY_', 'PORT'))
                }
            },
            status_code=200
        )
    except ImportError:
        # psutil might not be available
        return JSONResponse(
            content={
                'python_version': platform.python_version(),
                'platform': platform.platform(),
                'railway_env': os.environ.get('RAILWAY_ENVIRONMENT', 'Not set'),
                'port': os.environ.get('PORT', 'Not set'),
                'bot_config': {
                    'mode': getattr(config, 'BOT_MODE', 'polling'),
                    'admin': config.ADMIN_USERNAME,
                    'auto_verify': config.AUTO_VERIFY_ENABLED
                }
            },
            status_code=200
        )
    except Exception as e:
        return JSONResponse(
            content={'error': f'Debug info failed: {str(e)}'},
            status_code=500
        )

def start_health_server():
    """Start FastAPI health check server in a separate thread"""
    global health_server, health_thread
    
    def run_health_server():
        port = int(os.environ.get('PORT', 8000))
        logger.info(f"🏥 Starting FastAPI health check server on port {port}")
        
        # Railway-specific configuration
        host = '0.0.0.0'
        if os.environ.get('RAILWAY_ENVIRONMENT'):
            # Listen on both IPv4 and IPv6 for Railway
            host = '::'
            logger.info("🚄 Railway detected: Using IPv6 binding")
        
        config_uvicorn = uvicorn.Config(
            health_app,
            host=host,
            port=port,
            log_level='info',
            access_log=True,  # Enable access logs for debugging
            loop='asyncio',
            timeout_keep_alive=30,  # Increase keep-alive timeout
            timeout_graceful_shutdown=30
        )
        
        global health_server
        health_server = uvicorn.Server(config_uvicorn)
        
        try:
            asyncio.run(health_server.serve())
        except Exception as e:
            logger.error(f"Health server error: {e}")
            import traceback
            traceback.print_exc()
    
    health_thread = threading.Thread(target=run_health_server, daemon=True)
    health_thread.start()
    return health_thread

async def stop_health_server():
    """Gracefully stop the health server"""
    global health_server
    if health_server:
        logger.info("🛑 Stopping health server...")
        health_server.should_exit = True

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
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 Polling mode stopped by user")
    finally:
        asyncio.run(stop_health_server())

def run_webhook_mode():
    """Run bot in webhook mode (production) with FastAPI"""
    try:
        # Try to import webhook server
        from webhook.webhook_server import run_webhook_server
        print("🌐 Starting bot in WEBHOOK mode with FastAPI...")
        
        # Check if webhook server has its own FastAPI health checks
        try:
            from health_check import start_health_server as webhook_health_server
            webhook_health_server()
        except ImportError:
            # Use our FastAPI health server
            logger.info("Using FastAPI health server for webhook mode")
            start_health_server()
            import time
            time.sleep(2)
        
        # Run webhook server
        run_webhook_server()
        
    except ImportError as e:
        logger.error(f"Webhook dependencies not found: {e}")
        logger.info("Falling back to polling mode with FastAPI health server...")
        run_polling_mode()

def run_railway_mode():
    """Special mode for Railway deployment with FastAPI"""
    print("🚄 Starting bot in RAILWAY mode with FastAPI...")
    
    # Always start FastAPI health server for Railway
    health_thread = start_health_server()
    
    # Give health server more time to start on Railway
    import time
    logger.info("⏳ Waiting for health server to initialize...")
    time.sleep(5)  # Increased from 3 to 5 seconds
    
    # Test the health endpoint internally
    try:
        import requests
        port = int(os.environ.get('PORT', 8000))
        test_url = f"http://localhost:{port}/health"
        response = requests.get(test_url, timeout=5)
        if response.status_code == 200:
            logger.info("✅ Health endpoint is responding correctly")
        else:
            logger.warning(f"⚠️ Health endpoint returned status {response.status_code}")
    except Exception as e:
        logger.warning(f"⚠️ Could not test health endpoint: {e}")
    
    # Determine which bot mode to use
    bot_mode = getattr(config, 'BOT_MODE', 'polling').lower()
    
    if bot_mode == 'webhook':
        try:
            from webhook.webhook_server import run_webhook_server
            logger.info("Running webhook server alongside FastAPI health server...")
            run_webhook_server()
        except ImportError:
            logger.info("Webhook not available, using polling mode...")
            from telegram_bot import main
            try:
                main()
            except KeyboardInterrupt:
                print("\n🛑 Railway mode stopped by user")
    else:
        # Default to polling
        from telegram_bot import main
        try:
            main()
        except KeyboardInterrupt:
            print("\n🛑 Railway polling mode stopped by user")

def setup_signal_handlers():
    """Setup graceful shutdown handlers"""
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        asyncio.run(stop_health_server())
        sys.exit(0)
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

def run_fastapi_only():
    """Run only the FastAPI health server (useful for debugging)"""
    print("🌐 Starting FastAPI health server only...")
    port = int(os.environ.get('PORT', 8000))
    
    # Railway-specific configuration
    host = '0.0.0.0'
    if os.environ.get('RAILWAY_ENVIRONMENT'):
        host = '::'
        logger.info("🚄 Railway detected: Using IPv6 binding for standalone server")
    
    logger.info(f"🏥 Starting FastAPI server on {host}:{port}")
    uvicorn.run(
        health_app,
        host=host,
        port=port,
        log_level='info',
        access_log=True,
        timeout_keep_alive=30
    )

def main():
    """Main runner function"""
    print("🚀 OPTRIXTRADES Bot Runner (FastAPI Edition)")
    print("=" * 40)
    
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
    print(f"⚡ Framework: FastAPI")
    
    if is_railway:
        port = os.environ.get('PORT', 8000)
        print(f"🔌 Health check port: {port}")
    
    print("=" * 40)
    
    try:
        if mode == 'railway':
            run_railway_mode()
        elif mode == 'webhook':
            run_webhook_mode()
        elif mode == 'polling':
            run_polling_mode()
        elif mode == 'fastapi':
            run_fastapi_only()
        else:
            print("❌ Invalid mode. Use 'polling', 'webhook', 'railway', or 'fastapi'")
            print("Usage: python bot_runner.py [polling|webhook|railway|fastapi]")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
        asyncio.run(stop_health_server())
    except Exception as e:
        logger.error(f"Bot runner error: {e}")
        import traceback
        traceback.print_exc()
        asyncio.run(stop_health_server())
        sys.exit(1)

if __name__ == "__main__":
    main()