"""
Webhook setup and management utilities
"""

import asyncio
import logging
from telegram import Bot
from config import config

logger = logging.getLogger(__name__)

class WebhookManager:
    def __init__(self):
        self.bot = Bot(token=config.BOT_TOKEN)
    
    async def set_webhook(self, webhook_url: str, secret_token: str = None) -> bool:
        """Set webhook URL"""
        try:
            result = await self.bot.set_webhook(
                url=webhook_url,
                secret_token=secret_token or config.WEBHOOK_SECRET_TOKEN,
                max_connections=100,
                drop_pending_updates=True,
                allowed_updates=["message", "callback_query", "inline_query"]
            )
            
            if result:
                print(f"✅ Webhook set successfully: {webhook_url}")
                return True
            else:
                print("❌ Failed to set webhook")
                return False
                
        except Exception as e:
            print(f"❌ Error setting webhook: {e}")
            return False
    
    async def delete_webhook(self) -> bool:
        """Delete current webhook"""
        try:
            result = await self.bot.delete_webhook(drop_pending_updates=True)
            
            if result:
                print("✅ Webhook deleted successfully")
                return True
            else:
                print("❌ Failed to delete webhook")
                return False
                
        except Exception as e:
            print(f"❌ Error deleting webhook: {e}")
            return False
    
    async def get_webhook_info(self):
        """Get current webhook information"""
        try:
            webhook_info = await self.bot.get_webhook_info()
            
            print("📡 Current Webhook Information:")
            print(f"  URL: {webhook_info.url or 'Not set'}")
            print(f"  Pending Updates: {webhook_info.pending_update_count}")
            print(f"  Max Connections: {webhook_info.max_connections}")
            print(f"  Last Error: {webhook_info.last_error_message or 'None'}")
            print(f"  Has Certificate: {webhook_info.has_custom_certificate}")
            
            return webhook_info
            
        except Exception as e:
            print(f"❌ Error getting webhook info: {e}")
            return None

async def setup_webhook_interactive():
    """Interactive webhook setup"""
    manager = WebhookManager()
    
    print("🔧 OPTRIXTRADES Webhook Setup")
    print("=" * 40)
    
    # Get current webhook info
    await manager.get_webhook_info()
    print()
    
    while True:
        print("Options:")
        print("1. Set new webhook URL")
        print("2. Delete current webhook")
        print("3. View webhook info")
        print("4. Exit")
        
        choice = input("\nEnter your choice (1-4): ").strip()
        
        if choice == "1":
            webhook_url = input("Enter webhook URL: ").strip()
            if webhook_url:
                secret_token = input("Enter secret token (optional): ").strip()
                await manager.set_webhook(webhook_url, secret_token or None)
            else:
                print("❌ Invalid URL")
        
        elif choice == "2":
            confirm = input("Delete current webhook? (y/N): ").strip().lower()
            if confirm == 'y':
                await manager.delete_webhook()
        
        elif choice == "3":
            await manager.get_webhook_info()
        
        elif choice == "4":
            break
        
        else:
            print("❌ Invalid choice")
        
        print()

def main():
    """Main function for webhook setup"""
    asyncio.run(setup_webhook_interactive())

if __name__ == "__main__":
    main()
