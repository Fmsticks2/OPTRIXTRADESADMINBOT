#!/usr/bin/env python3
"""
Local webhook server test to verify fixes
"""

import asyncio
import logging
import json
import os
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import JSONResponse
import uvicorn
from telegram import Update
from telegram.ext import Application

from config import config
from telegram_bot import TradingBot

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class LocalWebhookServer:
    def __init__(self):
        self.bot_instance = TradingBot()
        self.application = None
        self.app = FastAPI(title="Local Webhook Test")
        self.setup_routes()
    
    def setup_routes(self):
        @self.app.get("/")
        async def root():
            return {"message": "Local Webhook Test Server", "status": "running"}
        
        @self.app.get("/health")
        async def health():
            return {"status": "healthy"}
        
        @self.app.post("/webhook")
        async def webhook(request: Request, background_tasks: BackgroundTasks):
            try:
                logger.info(f"Webhook called - Headers: {dict(request.headers)}")
                
                # Get update data
                try:
                    update_data = await request.json()
                    logger.info(f"Received update data: {json.dumps(update_data, indent=2)}")
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON in webhook request: {e}")
                    return JSONResponse({"status": "error", "message": "Invalid JSON"})
                
                # Check if application is initialized
                if not self.application:
                    logger.error("Application not initialized in webhook handler")
                    return JSONResponse({"status": "error", "message": "Application not ready"})
                
                # Process update in background
                background_tasks.add_task(self._safe_process_update, update_data)
                
                # Always return 200 OK
                return JSONResponse({"status": "ok"})
                
            except Exception as e:
                logger.error(f"Webhook handler error: {e}", exc_info=True)
                # Return 200 to prevent retries
                return JSONResponse({"status": "error", "message": "Processing error"})
    
    async def _safe_process_update(self, update_data: dict):
        """Safely process update with complete error isolation"""
        try:
            await self.process_update(update_data)
        except Exception as e:
            logger.error(f"Error in _safe_process_update: {e}", exc_info=True)
    
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
                    logger.error(f"Error processing update {update.update_id}: {process_error}", exc_info=True)
            else:
                logger.warning("Failed to create Update object from webhook data")
                
        except Exception as e:
            logger.error(f"Error in process_update: {e}", exc_info=True)
    
    async def startup(self):
        """Initialize the application"""
        logger.info("Starting local webhook test server...")
        
        # Initialize database
        try:
            from database import initialize_db
            await initialize_db()
            logger.info("Database initialized")
        except Exception as e:
            logger.error(f"Database initialization error: {e}")
        
        # Initialize application
        try:
            self.application = Application.builder().token(config.BOT_TOKEN).build()
            
            # Set the application instance in the bot
            self.bot_instance.set_application(self.application)
            
            # Add handlers
            from telegram.ext import CommandHandler, CallbackQueryHandler, MessageHandler, filters
            
            self.application.add_handler(CommandHandler("start", self.bot_instance.start_command))
            self.application.add_handler(CallbackQueryHandler(self.bot_instance.button_callback))
            self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.bot_instance.handle_text_message))
            self.application.add_handler(MessageHandler(filters.PHOTO, self.bot_instance.handle_photo))
            self.application.add_error_handler(self.bot_instance.error_handler)
            
            # Initialize application
            await self.application.initialize()
            await self.application.start()
            
            logger.info("Application initialized")
        except Exception as e:
            logger.error(f"Application initialization error: {e}", exc_info=True)
            raise
    
    async def shutdown(self):
        """Shutdown the application"""
        logger.info("Shutting down local webhook test server...")
        
        if self.application:
            await self.application.stop()
            await self.application.shutdown()

async def test_webhook():
    """Test the webhook server locally"""
    server = LocalWebhookServer()
    
    # Start the server
    await server.startup()
    
    # Create a test update
    test_update = {
        "update_id": 123456789,
        "message": {
            "message_id": 1,
            "from": {
                "id": 123456789,
                "is_bot": False,
                "first_name": "Test",
                "username": "testuser"
            },
            "chat": {
                "id": 123456789,
                "first_name": "Test",
                "username": "testuser",
                "type": "private"
            },
            "date": 1640995200,
            "text": "/start"
        }
    }
    
    # Process the update
    await server.process_update(test_update)
    
    # Shutdown the server
    await server.shutdown()

def run_local_server():
    """Run the local webhook server"""
    server = LocalWebhookServer()
    
    # Create lifespan events
    @server.app.on_event("startup")
    async def startup_event():
        await server.startup()
    
    @server.app.on_event("shutdown")
    async def shutdown_event():
        await server.shutdown()
    
    # Run the server
    port = int(os.environ.get("PORT", 8000))
    logger.info(f"Starting server on port {port}")
    
    uvicorn.run(
        server.app,
        host="0.0.0.0",
        port=port,
        log_level="debug"
    )

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        # Run the test
        asyncio.run(test_webhook())
    else:
        # Run the server
        run_local_server()