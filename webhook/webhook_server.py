"""
FastAPI webhook server for OPTRIXTRADES Telegram bot
Handles incoming webhook updates from Telegram
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
import uvicorn
from telegram import Update
from telegram.ext import Application
import json
import hmac
import hashlib
from typing import Optional

from config import config
from telegram_bot import TradingBot

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
    def __init__(self):
        self.bot_instance = TradingBot()
        self.application: Optional[Application] = None
        
    def setup_routes(self, app: FastAPI):
        """Setup FastAPI routes"""
        
        @app.get("/")
        async def root():
            return {"message": "OPTRIXTRADES Bot Webhook Server", "status": "running"}
        
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
                # Verify webhook secret if configured
                if hasattr(config, 'WEBHOOK_SECRET_TOKEN') and config.WEBHOOK_SECRET_TOKEN:
                    if not self.verify_webhook_signature(request):
                        raise HTTPException(status_code=403, detail="Invalid signature")
                
                # Get update data
                update_data = await request.json()
                logger.info(f"Received webhook update: {update_data.get('update_id', 'unknown')}")
                
                # Process update in background
                background_tasks.add_task(self.process_update, update_data)
                
                return JSONResponse({"status": "ok"})
                
            except json.JSONDecodeError:
                logger.error("Invalid JSON in webhook request")
                raise HTTPException(status_code=400, detail="Invalid JSON")
            except Exception as e:
                logger.error(f"Webhook handler error: {e}")
                raise HTTPException(status_code=500, detail="Internal server error")
        
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

    def verify_webhook_signature(self, request: Request) -> bool:
        """Verify webhook signature for security"""
        try:
            signature = request.headers.get('X-Telegram-Bot-Api-Secret-Token')
            return signature == config.WEBHOOK_SECRET_TOKEN
        except Exception as e:
            logger.error(f"Signature verification error: {e}")
            return False

    async def process_update(self, update_data: dict):
        """Process incoming Telegram update"""
        try:
            if not self.application:
                logger.error("Application not initialized")
                return
            
            # Create Update object
            update = Update.de_json(update_data, self.application.bot)
            
            if update:
                # Process the update
                await self.application.process_update(update)
                logger.info(f"Processed update {update.update_id}")
            else:
                logger.warning("Failed to create Update object from webhook data")
                
        except Exception as e:
            logger.error(f"Error processing update: {e}")

    async def initialize_application(self):
        """Initialize Telegram application for webhook mode"""
        try:
            if self.application:
                logger.info("Application already initialized")
                return
                
            # Create application
            self.application = Application.builder().token(config.BOT_TOKEN).build()
            
            # Add handlers (same as polling mode)
            from telegram.ext import CommandHandler, CallbackQueryHandler, MessageHandler, filters
            
            self.application.add_handler(CommandHandler("start", self.bot_instance.start_command))
            self.application.add_handler(CallbackQueryHandler(self.bot_instance.button_callback))
            self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.bot_instance.handle_text_message))
            self.application.add_handler(MessageHandler(filters.PHOTO, self.bot_instance.handle_photo))
            self.application.add_error_handler(self.bot_instance.error_handler)
            
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
        
        # Initialize bot application
        await self.initialize_application()

    async def shutdown(self):
        """Shutdown tasks"""
        logger.info("🛑 OPTRIXTRADES Webhook Server shutting down...")
        
        if self.application:
            await self.application.stop()
            await self.application.shutdown()

# Create global webhook server instance
webhook_server = WebhookServer()

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