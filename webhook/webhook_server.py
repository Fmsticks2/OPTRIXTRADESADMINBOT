"""
FastAPI webhook server for OPTRIXTRADES Telegram bot
Handles incoming webhook updates from Telegram
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
import uvicorn
from telegram import Update
from telegram.ext import Application
import json
import hmac
import hashlib
from typing import Optional

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import config
from telegram_bot.bot import TradingBot
from database.connection import DatabaseManager

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=getattr(logging, config.LOG_LEVEL),
    handlers=[
        logging.FileHandler('webhook.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class WebhookServer:
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.bot_instance = TradingBot(db_manager)
        self.application: Optional[Application] = None
        # Setup templates
        self.templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))
        
    def setup_routes(self, app: FastAPI):
        """Setup FastAPI routes"""
        
        @app.get("/", response_class=HTMLResponse)
        async def root(request: Request):
            """Serve professional landing page"""
            try:
                # Get bot username for the Telegram link
                bot_username = await self.get_bot_username()
                return self.templates.TemplateResponse(
                    "landing.html", 
                    {
                        "request": request,
                        "bot_username": bot_username
                    }
                )
            except Exception as e:
                logger.error(f"Error serving landing page: {e}")
                # Fallback to JSON response
                return JSONResponse({"message": "OPTRIXTRADES Bot Webhook Server", "status": "running"})
        
        @app.get("/favicon.svg")
        async def favicon():
            """Serve the favicon"""
            favicon_path = os.path.join(os.path.dirname(__file__), "templates", "favicon.svg")
            if os.path.exists(favicon_path):
                return FileResponse(favicon_path, media_type="image/svg+xml")
            else:
                raise HTTPException(status_code=404, detail="Favicon not found")
        
        @app.get("/health")
        async def health_check():
            return {
                "status": "healthy",
                "service": "optrixtrades-webhook",
                "bot_token": config.BOT_TOKEN[:10] + "...",
                "webhook_enabled": True
            }
        
        @app.post(f"/webhook/{config.BOT_TOKEN}")
        async def webhook_handler(request: Request, background_tasks: BackgroundTasks):
            """Handle incoming webhook updates from Telegram"""
            try:
                logger.info(f"Webhook handler called - Headers: {dict(request.headers)}")
                
                # Verify webhook signature
                if not self.verify_webhook_signature(request):
                    logger.warning("Invalid webhook signature received")
                    raise HTTPException(status_code=403, detail="Invalid signature")
                
                # Get update data
                try:
                    update_data = await request.json()
                    logger.info(f"Received update data: {json.dumps(update_data, indent=2)}")
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON in webhook request: {e}")
                    # Return 200 to prevent Telegram from retrying
                    return JSONResponse({"status": "error", "message": "Invalid JSON"})
                
                # Check if application is initialized
                if not self.application:
                    logger.error("Application not initialized in webhook handler")
                    return JSONResponse({"status": "error", "message": "Application not ready"})
                
                # Process update in background with error isolation
                background_tasks.add_task(self._safe_process_update, update_data)
                
                # Always return 200 OK to Telegram
                return JSONResponse({"status": "ok"})
                
            except HTTPException as he:
                logger.error(f"HTTP Exception in webhook handler: {he.detail}")
                # Re-raise HTTP exceptions (like 403)
                raise
            except Exception as e:
                logger.error(f"Unexpected webhook handler error: {e}", exc_info=True)
                # Return 200 to prevent Telegram from retrying
                return JSONResponse({"status": "error", "message": "Processing error"})
        
        @app.post("/admin/set_webhook")
        async def set_webhook(request: Request):
            """Admin endpoint to set webhook URL"""
            try:
                data = await request.json()
                webhook_url = data.get('webhook_url')
                
                if not webhook_url:
                    raise HTTPException(status_code=400, detail="webhook_url required")
                
                # Set webhook
                success = await self.set_telegram_webhook(webhook_url)
                
                if success:
                    return {"status": "success", "webhook_url": webhook_url}
                else:
                    raise HTTPException(status_code=500, detail="Failed to set webhook")
                    
            except Exception as e:
                logger.error(f"Set webhook error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @app.delete("/admin/delete_webhook")
        async def delete_webhook():
            """Admin endpoint to delete webhook"""
            try:
                success = await self.delete_telegram_webhook()
                
                if success:
                    return {"status": "success", "message": "Webhook deleted"}
                else:
                    raise HTTPException(status_code=500, detail="Failed to delete webhook")
                    
            except Exception as e:
                logger.error(f"Delete webhook error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @app.get("/admin/webhook_info")
        async def webhook_info():
            """Get current webhook information"""
            try:
                from telegram import Bot
                bot = Bot(token=config.BOT_TOKEN)
                webhook_info = await bot.get_webhook_info()
                
                return {
                    "url": webhook_info.url,
                    "has_custom_certificate": webhook_info.has_custom_certificate,
                    "pending_update_count": webhook_info.pending_update_count,
                    "last_error_date": webhook_info.last_error_date,
                    "last_error_message": webhook_info.last_error_message,
                    "max_connections": webhook_info.max_connections,
                    "allowed_updates": webhook_info.allowed_updates
                }
                
            except Exception as e:
                logger.error(f"Webhook info error: {e}")
                raise HTTPException(status_code=500, detail=str(e))

    async def get_bot_username(self) -> str:
        """Get bot username for Telegram link"""
        try:
            from telegram import Bot
            bot = Bot(token=config.BOT_TOKEN)
            bot_info = await bot.get_me()
            return bot_info.username or "optrixtrades_bot"
        except Exception as e:
            logger.error(f"Error getting bot username: {e}")
            return "optrixtrades_bot"  # Fallback username
    
    def verify_webhook_signature(self, request: Request) -> bool:
        """Verify webhook signature for security"""
        try:
            # If no secret token is configured, skip verification
            if not config.WEBHOOK_SECRET_TOKEN:
                logger.debug("No webhook secret token configured, skipping signature verification")
                return True
                
            signature = request.headers.get('X-Telegram-Bot-Api-Secret-Token')
            is_valid = signature == config.WEBHOOK_SECRET_TOKEN
            
            if not is_valid:
                logger.warning(f"Invalid webhook signature. Expected: {config.WEBHOOK_SECRET_TOKEN}, Got: {signature}")
            
            return is_valid
        except Exception as e:
            logger.error(f"Signature verification error: {e}")
            return False

    async def _safe_process_update(self, update_data: dict):
        """Safely process update with complete error isolation"""
        try:
            await self.process_update(update_data)
        except Exception as e:
            logger.error(f"Error in _safe_process_update: {e}")
            # Completely isolate errors to prevent any propagation

    async def process_update(self, update_data: dict):
        """Process incoming Telegram update"""
        try:
            if not self.application:
                logger.error("Application not initialized")
                return
            
            # Validate update data
            if not update_data or not isinstance(update_data, dict):
                logger.error("Invalid update data received")
                return
            
            # Create Update object
            update = Update.de_json(update_data, self.application.bot)
            
            if update:
                # Process the update with error handling
                try:
                    await self.application.process_update(update)
                    logger.info(f"Processed update {update.update_id}")
                except Exception as process_error:
                    logger.error(f"Error processing update {update.update_id}: {process_error}")
                    # Don't re-raise to prevent 500 errors
            else:
                logger.warning("Failed to create Update object from webhook data")
                
        except Exception as e:
            logger.error(f"Error in process_update: {e}")
            # Don't re-raise to prevent 500 errors

    async def initialize_application(self):
        """Initialize Telegram application for webhook mode"""
        try:
            if self.application:
                logger.info("Application already initialized")
                return
                
            # Ensure database is initialized first
            if not self.db_manager.is_initialized:
                logger.info("Database not initialized, initializing now...")
                await self.db_manager.initialize()
                logger.info("Database initialized successfully")
            
            # Initialize bot instance with database
            await self.bot_instance.initialize()
            
            # Create application
            self.application = Application.builder().token(config.BOT_TOKEN).build()
            
            # Set the application instance in the bot (fix: use correct attribute)
            self.bot_instance.application = self.application
            
            # Store bot instance in application's bot_data for access from handlers
            self.application.bot_data['bot_instance'] = self.bot_instance
            
            # Setup handlers using the bot's setup method
            self.bot_instance._setup_handlers()
            
            # Initialize application
            await self.application.initialize()
            await self.application.start()
            
            logger.info("Telegram application initialized for webhook mode")
            
        except Exception as e:
            logger.error(f"Failed to initialize application: {e}")
            raise

    async def set_telegram_webhook(self, webhook_url: str) -> bool:
        """Set webhook URL in Telegram"""
        try:
            from telegram import Bot
            bot = Bot(token=config.BOT_TOKEN)
            
            # Set webhook
            secret_token = getattr(config, 'WEBHOOK_SECRET_TOKEN', None)
            result = await bot.set_webhook(
                url=webhook_url,
                secret_token=secret_token,
                max_connections=100,
                drop_pending_updates=True,
                allowed_updates=["message", "callback_query", "inline_query"]
            )
            
            if result:
                logger.info(f"Webhook set successfully: {webhook_url}")
                return True
            else:
                logger.error("Failed to set webhook")
                return False
                
        except Exception as e:
            logger.error(f"Error setting webhook: {e}")
            return False

    async def delete_telegram_webhook(self) -> bool:
        """Delete webhook from Telegram"""
        try:
            from telegram import Bot
            bot = Bot(token=config.BOT_TOKEN)
            
            result = await bot.delete_webhook(drop_pending_updates=True)
            
            if result:
                logger.info("Webhook deleted successfully")
                return True
            else:
                logger.error("Failed to delete webhook")
                return False
                
        except Exception as e:
            logger.error(f"Error deleting webhook: {e}")
            return False

    async def startup(self):
        """Startup tasks"""
        logger.info("🚀 OPTRIXTRADES Webhook Server starting...")
        logger.info(f"📱 Bot Token: {config.BOT_TOKEN[:10]}...")
        logger.info(f"🔗 Webhook Mode: Enabled")
        
        # Initialize database first - this is critical
        try:
            logger.info("Initializing database connection...")
            await self.db_manager.initialize()
            logger.info("✅ Database initialized successfully")
            
            # Verify database is actually ready
            if not self.db_manager.is_initialized or self.db_manager.pool is None:
                raise RuntimeError("Database initialization completed but pool is not ready")
                
        except Exception as e:
            logger.error(f"❌ Database initialization failed: {e}")
            # Don't continue if database fails - this will cause handler errors
            raise RuntimeError(f"Cannot start webhook server without database: {e}")
        
        # Initialize bot application (this will also verify database is ready)
        try:
            await self.initialize_application()
            logger.info("✅ Bot application initialized successfully")
        except Exception as e:
            logger.error(f"❌ Bot application initialization failed: {e}")
            raise

        # Set webhook on startup
        if config.WEBHOOK_URL:
            logger.info(f"Attempting to set webhook to: {config.WEBHOOK_URL}")
            success = await self.set_telegram_webhook(config.WEBHOOK_URL)
            if success:
                logger.info("✅ Webhook set successfully on startup.")
            else:
                logger.error("❌ Failed to set webhook on startup.")
        else:
            logger.warning("WEBHOOK_URL not configured. Skipping webhook setup.")

    async def shutdown(self):
        """Shutdown tasks"""
        logger.info("🛑 OPTRIXTRADES Webhook Server shutting down...")
        
        # Close database connection
        try:
            await self.db_manager.close()
            logger.info("✅ Database connection closed successfully")
        except Exception as e:
            logger.error(f"❌ Error closing database connection: {e}")

        if self.application:
            await self.application.stop()
            await self.application.shutdown()

# Create global webhook server instance
db_manager = DatabaseManager()
webhook_server = WebhookServer(db_manager)

# Lifespan context manager for FastAPI
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await webhook_server.startup()
    yield
    # Shutdown
    await webhook_server.shutdown()

# Create FastAPI app with lifespan
app = FastAPI(
    title="OPTRIXTRADES Bot Webhook",
    description="Webhook server for OPTRIXTRADES Telegram bot",
    version="1.0.0",
    lifespan=lifespan
)

# Setup routes
webhook_server.setup_routes(app)

def run_webhook_server():
    """Run the webhook server"""
    # Use Railway's PORT environment variable, fallback to config or 8080
    port = int(os.environ.get("PORT", getattr(config, 'WEBHOOK_PORT', 8080)))
    
    logger.info(f"Starting server on port {port}")
    
    uvicorn.run(
        "webhook.webhook_server:app",
        host="0.0.0.0",
        port=port,
        log_level=config.LOG_LEVEL.lower(),
        access_log=True,
        reload=False  # Disable reload in production
    )

if __name__ == "__main__":
    run_webhook_server()