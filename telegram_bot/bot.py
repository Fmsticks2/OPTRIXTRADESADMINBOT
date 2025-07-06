"""Main bot class for OPTRIXTRADES Telegram Bot"""

import asyncio
import logging
from typing import Dict, Any, Optional, List

from telegram import Update, Bot
from telegram.ext import (
    Application,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import BotConfig
from database.connection import DatabaseManager

logger = logging.getLogger(__name__)

class TradingBot:
    """Main bot class for OPTRIXTRADES Telegram Bot"""
    
    def __init__(self, db_manager: DatabaseManager):
        """Initialize the bot with database manager"""
        self.db_manager = db_manager
        
        # Load configuration
        self.bot_token = BotConfig.BOT_TOKEN
        self.broker_link = BotConfig.BROKER_LINK
        self.premium_channel_id = BotConfig.PREMIUM_CHANNEL_ID
        self.admin_username = BotConfig.ADMIN_USERNAME
        self.admin_user_id = BotConfig.ADMIN_USER_ID
        
        # Webhook configuration
        self.webhook_url = BotConfig.WEBHOOK_URL
        self.webhook_port = BotConfig.WEBHOOK_PORT
        self.webhook_path = BotConfig.WEBHOOK_PATH
        
        # Initialize application to None (will be set later)
        self.application = None
        
        # Message history tracking
        self.message_history = {}
        self.user_states = {}
        
        logger.info("TradingBot initialized")
    
    async def initialize(self):
        """Initialize the bot"""
        await self.db_manager.initialize()
        logger.info("Database initialized")
    
    def _setup_handlers(self):
        """Setup all bot handlers - this will be refactored to use modular handlers"""
        # This method will be updated to use handlers from the handlers module
        from telegram_bot.handlers.setup import setup_all_handlers
        setup_all_handlers(self)
    
    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Log errors caused by updates."""
        logger.error("Exception while handling an update:", exc_info=context.error)
        
        # Notify admin of critical errors
        if self.admin_user_id:
            try:
                await context.bot.send_message(
                    chat_id=self.admin_user_id,
                    text=f"🚨 Bot Error: {str(context.error)[:500]}"
                )
            except Exception as e:
                logger.error(f"Failed to send error notification: {e}")
    
    async def start_polling(self):
        """Start bot in polling mode"""
        logger.info("🔄 Starting bot in polling mode...")
        # Initialize the application
        await self.application.initialize()
        await self.application.start()
        
        # Start polling
        await self.application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        
        logger.info("✅ Bot started successfully in polling mode")
        
        # Keep the application running
        try:
            import signal
            import asyncio
            
            def signal_handler(signum, frame):
                logger.info("Received shutdown signal")
                
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
            
            # Keep running until interrupted
            while True:
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("Shutting down bot...")
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
    
    async def start_webhook(self):
        """Start bot in webhook mode"""
        logger.info("🔄 Starting bot in webhook mode...")
        # Initialize the application
        await self.application.initialize()
        await self.application.start()
        
        # Set webhook
        await self.application.bot.set_webhook(
            url=self.webhook_url,
            allowed_updates=["message", "callback_query"]
        )
        
        # Start webhook server using the application's built-in method
        from aiohttp import web
        import telegram
        
        # Create webhook handler
        async def webhook_handler(request):
            """Handle incoming webhook requests"""
            try:
                data = await request.json()
                update = telegram.Update.de_json(data, self.application.bot)
                if update:
                    await self.application.update_queue.put(update)
                return web.Response(status=200)
            except Exception as e:
                logger.error(f"Error processing webhook: {e}")
                return web.Response(status=500)
        
        # Create health check handler
        async def health_check(request):
            """Health check endpoint"""
            return web.Response(text="OK", status=200)
        
        # Create method not allowed handler
        async def method_not_allowed(request):
            """Handle unsupported HTTP methods"""
            return web.Response(text="Method Not Allowed", status=405)
        
        # Create and start the web server
        app = web.Application()
        app.router.add_post(f"/webhook/{self.bot_token}", webhook_handler)
        app.router.add_get("/health", health_check)
        app.router.add_get(f"/webhook/{self.bot_token}", method_not_allowed)
        app.router.add_route("*", "/{path:.*}", method_not_allowed)
        
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", self.webhook_port)
        await site.start()
        
        logger.info("✅ Webhook server started successfully")
        
        # Keep the application running
        try:
            import signal
            import asyncio
            
            def signal_handler(signum, frame):
                logger.info("Received shutdown signal")
                
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
            
            # Keep running until interrupted
            while True:
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("Shutting down webhook server...")
            await runner.cleanup()
            await self.application.stop()
            await self.application.shutdown()
    
    async def run(self):
        """Run the bot with all handlers"""
        try:
            await self.initialize()
            
            # Create application
            self.application = Application.builder().token(self.bot_token).build()
            
            # Store bot instance in application's bot_data for access from handlers
            self.application.bot_data['bot_instance'] = self
            
            self._setup_handlers()
            
            # Initialize follow-up scheduler
            from telegram_bot.utils.follow_up_scheduler import init_follow_up_scheduler
            self.follow_up_scheduler = init_follow_up_scheduler(self.application.bot)
            logger.info("Follow-up scheduler initialized")
            
            # Start the bot
            logger.info("Bot is running...")
            # Check BOT_MODE instead of webhook_url presence
            from config import BotConfig
            if BotConfig.BOT_MODE.lower() == 'webhook' and BotConfig.WEBHOOK_ENABLED:
                await self.start_webhook()
            else:
                await self.start_polling()
        except Exception as e:
            logger.error(f"Error in bot run: {e}")
            raise
            
    async def _track_messages(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Track messages for analytics and monitoring"""
        try:
            if update.effective_user and update.effective_message:
                user_id = update.effective_user.id
                message_text = update.effective_message.text or "[Non-text message]"
                
                # Store in message history
                if user_id not in self.message_history:
                    self.message_history[user_id] = []
                
                self.message_history[user_id].append({
                    'timestamp': update.effective_message.date,
                    'text': message_text[:100],  # Limit text length
                    'message_id': update.effective_message.message_id
                })
                
                # Keep only last 10 messages per user
                if len(self.message_history[user_id]) > 10:
                    self.message_history[user_id] = self.message_history[user_id][-10:]
                    
        except Exception as e:
            logger.error(f"Error tracking message: {e}")
    
    async def handle_broadcast_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle broadcast message from admin"""
        # This is a placeholder - implement actual broadcast logic
        await update.message.reply_text("Broadcast functionality not yet implemented.")
        logger.info(f"Broadcast message received from admin: {update.effective_user.id}")
    
    async def handle_lookup_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle user lookup from admin"""
        # This is a placeholder - implement actual user lookup logic
        await update.message.reply_text("User lookup functionality not yet implemented.")
        logger.info(f"User lookup request from admin: {update.effective_user.id}")
    
    async def schedule_follow_ups(self, user_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Schedule follow-up messages for a user who started but didn't complete verification"""
        if hasattr(self, 'follow_up_scheduler') and self.follow_up_scheduler:
            await self.follow_up_scheduler.schedule_follow_ups(user_id, context)
            logger.info(f"Scheduled follow-ups for user {user_id}")
        else:
            logger.warning(f"Follow-up scheduler not initialized, can't schedule follow-ups for user {user_id}")