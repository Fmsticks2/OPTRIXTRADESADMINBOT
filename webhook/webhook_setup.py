"""
Webhook setup and management utilities
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from telegram import Bot
from telegram.request import HTTPXRequest
from config import config

logger = logging.getLogger(__name__)

class WebhookManager:
    def __init__(self):
        # Validate bot token
        if not config.BOT_TOKEN:
            raise ValueError("BOT_TOKEN is not set in environment variables")
        
        if ':' not in config.BOT_TOKEN:
            raise ValueError("BOT_TOKEN format is invalid (should contain ':')")
        
        print(f"🤖 Using bot token: {config.BOT_TOKEN[:10]}...{config.BOT_TOKEN[-10:]}")
        
        # Create request with extended timeout settings for better connectivity
        request = HTTPXRequest(
            connection_pool_size=8,
            connect_timeout=15.0,  # Increased from 10.0
            read_timeout=45.0,     # Increased from 30.0
            write_timeout=45.0,    # Increased from 30.0
            pool_timeout=10.0      # Increased from 5.0
        )
        self.bot = Bot(token=config.BOT_TOKEN, request=request)
    
    async def set_webhook(self, webhook_url: str, secret_token: str = None) -> bool:
        """Set webhook URL"""
        try:
            print(f"🔄 Setting webhook to: {webhook_url}")
            print("⏳ This may take up to 60 seconds...")
            
            result = await asyncio.wait_for(
                self.bot.set_webhook(
                    url=webhook_url,
                    secret_token=secret_token or config.WEBHOOK_SECRET_TOKEN,
                    max_connections=100,
                    drop_pending_updates=True,
                    allowed_updates=["message", "callback_query", "inline_query"]
                ),
                timeout=60.0  # Increased timeout to 60 seconds
            )
            
            if result:
                print(f"✅ Webhook set successfully: {webhook_url}")
                return True
            else:
                print("❌ Failed to set webhook")
                return False
                
        except asyncio.TimeoutError:
            print("❌ Error setting webhook: Connection timed out")
            print("💡 Possible causes:")
            print("   - Network connectivity issues")
            print("   - Invalid bot token")
            print("   - Telegram API temporarily unavailable")
            print("   - Firewall blocking outbound connections")
            return False
        except Exception as e:
            print(f"❌ Error setting webhook: {e}")
            return False
    
    async def delete_webhook(self) -> bool:
        """Delete current webhook"""
        try:
            print("🔄 Deleting webhook...")
            print("⏳ This may take up to 60 seconds...")
            
            result = await asyncio.wait_for(
                self.bot.delete_webhook(drop_pending_updates=True),
                timeout=60.0
            )
            
            if result:
                print("✅ Webhook deleted successfully")
                return True
            else:
                print("❌ Failed to delete webhook")
                return False
                
        except asyncio.TimeoutError:
            print("❌ Error deleting webhook: Connection timed out")
            print("💡 Check your internet connection and bot token")
            return False
        except Exception as e:
            print(f"❌ Error deleting webhook: {e}")
            return False
    
    async def get_webhook_info(self):
        """Get current webhook information"""
        try:
            print("🔄 Getting webhook information...")
            print("⏳ This may take up to 60 seconds...")
            
            webhook_info = await asyncio.wait_for(
                self.bot.get_webhook_info(),
                timeout=60.0
            )
            
            print("📡 Current Webhook Information:")
            print(f"  URL: {webhook_info.url or 'Not set'}")
            print(f"  Pending Updates: {webhook_info.pending_update_count}")
            print(f"  Max Connections: {webhook_info.max_connections}")
            print(f"  Last Error: {webhook_info.last_error_message or 'None'}")
            print(f"  Has Certificate: {webhook_info.has_custom_certificate}")
            
            return webhook_info
            
        except asyncio.TimeoutError:
            print("❌ Error getting webhook info: Connection timed out")
            print("💡 Check your internet connection and bot token")
            return None
        except Exception as e:
            print(f"❌ Error getting webhook info: {e}")
            return None

async def test_bot_token():
    """Test if the bot token is valid by getting bot information"""
    try:
        print("🔄 Testing bot token...")
        print("⏳ This may take up to 30 seconds...")
        
        # Create a temporary bot instance with extended timeouts
        request = HTTPXRequest(
            connection_pool_size=8,
            connect_timeout=15.0,
            read_timeout=30.0,
            write_timeout=30.0,
            pool_timeout=10.0
        )
        bot = Bot(token=config.BOT_TOKEN, request=request)
        
        # Try to get bot information
        bot_info = await asyncio.wait_for(bot.get_me(), timeout=30.0)
        
        print(f"✅ Bot token is valid!")
        print(f"🤖 Bot name: {bot_info.first_name}")
        print(f"👤 Username: @{bot_info.username}")
        print(f"🆔 Bot ID: {bot_info.id}")
        return True
        
    except asyncio.TimeoutError:
        print("❌ Bot token test failed: Connection timed out")
        print("💡 Check your internet connection")
        return False
    except Exception as e:
        print(f"❌ Bot token test failed: {e}")
        print("💡 Make sure your BOT_TOKEN is correct")
        return False

async def setup_webhook_interactive():
    """Interactive webhook setup"""
    print("🔧 OPTRIXTRADES Webhook Setup")
    print("=" * 40)
    
    # Test bot token first
    token_valid = await test_bot_token()
    if not token_valid:
        print("\n⚠️  Bot token validation failed. Please check your BOT_TOKEN.")
        print("   You can continue, but webhook operations may fail.")
    
    print()
    
    # Create webhook manager
    manager = WebhookManager()
    
    # Get current webhook info
    await manager.get_webhook_info()
    print()
    
    while True:
        print("Options:")
        print("1. Set new webhook URL")
        print("2. Delete current webhook")
        print("3. View webhook info")
        print("4. Test bot token")
        print("5. Exit")
        
        choice = input("\nEnter your choice (1-5): ").strip()
        
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
            await test_bot_token()
        
        elif choice == "5":
            break
        
        else:
            print("❌ Invalid choice")
        
        print()

def main():
    """Main function for webhook setup"""
    asyncio.run(setup_webhook_interactive())

if __name__ == "__main__":
    main()
