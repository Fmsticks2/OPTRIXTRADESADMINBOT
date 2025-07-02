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
    import platform
    
    try:
        return JSONResponse(
            content={
                'python_version': platform.python_version(),
                'platform': platform.platform(),
                'railway_env': os.environ.get('RAILWAY_ENVIRONMENT', 'Not set'),
                'port': os.environ.get('PORT', 'Not set'),
                'webhook_port': os.environ.get('WEBHOOK_PORT', 'Not set'),
                'bot_config': {
                    'mode': getattr(config, 'BOT_MODE', 'polling'),
                    'admin': config.ADMIN_USERNAME,
                    'auto_verify': config.AUTO_VERIFY_ENABLED
                },
                'environment_vars': {
                    k: ('***' if 'token' in k.lower() or 'key' in k.lower() else v)
                    for k, v in os.environ.items() 
                    if k.startswith(('BOT_', 'RAILWAY_', 'PORT', 'WEBHOOK_'))
                }
            },
            status_code=200
        )
    except Exception as e:
        return JSONResponse(
            content={'error': f'Debug info failed: {str(e)}'},
            status_code=500
        )

def run_polling_mode():
    """Run bot in polling mode (development)"""
    from telegram_bot import main
    print("🔄 Starting bot in POLLING mode...")
    
    # Start health server on a different port for polling mode
    health_port = int(os.environ.get('HEALTH_PORT', 8001))
    os.environ['PORT'] = str(health_port)
    
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
    """Run bot in webhook mode (production) with FastAPI - FIXED VERSION"""
    try:
        # Import webhook server
        from webhook.webhook_server import run_webhook_server
        print("🌐 Starting bot in WEBHOOK mode with FastAPI...")
        
        # DON'T start a separate health server - let webhook server handle it
        # The webhook server should include health endpoints
        
        # Check if webhook server already has health endpoints
        try:
            from webhook.webhook_server import app as webhook_app
            # If webhook server has its own FastAPI app, use that
            logger.info("Using webhook server's own FastAPI app")
            run_webhook_server()
        except ImportError:
            # Fallback: webhook server doesn't have health endpoints
            logger.info("Webhook server doesn't have health endpoints, starting combined server")
            run_combined_webhook_health_server()
        
    except ImportError as e:
        logger.error(f"Webhook dependencies not found: {e}")
        logger.info("Falling back to polling mode...")
        run_polling_mode()

def run_combined_webhook_health_server():
    """Run webhook with health endpoints in the same FastAPI app"""
    try:
        from webhook.webhook_server import app as webhook_app, setup_webhook_routes
        
        # Add health endpoints to webhook app
        @webhook_app.get('/health')
        async def webhook_health_check():
            return await health_check()
        
        @webhook_app.get('/debug')
        async def webhook_debug_info():
            return await debug_info()
        
        # Setup webhook routes
        setup_webhook_routes(webhook_app)
        
        # Run the combined server
        port = int(os.environ.get('PORT', 8080))
        logger.info(f"🌐 Starting combined webhook + health server on port {port}")
        
        uvicorn.run(
            webhook_app,
            host='0.0.0.0',
            port=port,
            log_level='info',
            access_log=True,
            timeout_keep_alive=30
        )
        
    except Exception as e:
        logger.error(f"Combined server failed: {e}")
        # Final fallback: just run health server
        run_fastapi_only()

def start_health_server():
    """Start FastAPI health check server in a separate thread"""
    global health_server, health_thread
    
    def run_health_server():
        port = int(os.environ.get('PORT', 8000))
        logger.info(f"🏥 Starting FastAPI health check server on port {port}")
        
        host = '0.0.0.0'
        
        config_uvicorn = uvicorn.Config(
            health_app,
            host=host,
            port=port,
            log_level='info',
            access_log=True,
            loop='asyncio',
            timeout_keep_alive=30,
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

def run_railway_mode():
    """Special mode for Railway deployment - SIMPLIFIED"""
    print("🚄 Starting bot in RAILWAY mode...")
    
    # Determine which bot mode to use based on config
    bot_mode = getattr(config, 'BOT_MODE', 'polling').lower()
    
    if bot_mode == 'webhook':
        logger.info("Railway: Using webhook mode")
        run_webhook_mode()
    else:
        logger.info("Railway: Using polling mode with health server")
        run_fastapi_only()  # Just run health server for Railway

def setup_signal_handlers():
    """Setup graceful shutdown handlers"""
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        asyncio.run(stop_health_server())
        sys.exit(0)
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

def run_fastapi_only():
    """Run only the FastAPI health server"""
    print("🌐 Starting FastAPI health server only...")
    port = int(os.environ.get('PORT', 8000))
    
    host = '0.0.0.0'
    
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
    if is_railway:
        mode = 'railway'
        print("🚄 Railway deployment detected, using Railway mode")
    
    print(f"📡 Mode: {mode.upper()}")
    print(f"🤖 Auto-verification: {'Enabled' if config.AUTO_VERIFY_ENABLED else 'Disabled'}")
    print(f"👨‍💼 Admin: @{config.ADMIN_USERNAME}")
    print(f"🌐 Platform: {'Railway' if is_railway else 'Local'}")
    print(f"⚡ Framework: FastAPI")
    
    if is_railway:
        port = os.environ.get('PORT', 8000)
        print(f"🔌 Port: {port}")
    
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