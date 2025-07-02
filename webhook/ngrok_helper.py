"""
Ngrok helper for local webhook testing
"""

import subprocess
import requests
import json
import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class NgrokHelper:
    def __init__(self):
        self.tunnel_url: Optional[str] = None
        self.process: Optional[subprocess.Popen] = None
    
    def start_tunnel(self, port: int = 8000) -> Optional[str]:
        """Start ngrok tunnel for local testing"""
        try:
            # Start ngrok process
            self.process = subprocess.Popen(
                ['ngrok', 'http', str(port)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Wait for ngrok to start
            time.sleep(3)
            
            # Get tunnel URL
            self.tunnel_url = self.get_tunnel_url()
            
            if self.tunnel_url:
                print(f"🌐 Ngrok tunnel started: {self.tunnel_url}")
                return self.tunnel_url
            else:
                print("❌ Failed to get ngrok tunnel URL")
                return None
                
        except FileNotFoundError:
            print("❌ Ngrok not found. Please install ngrok first:")
            print("   https://ngrok.com/download")
            return None
        except Exception as e:
            print(f"❌ Error starting ngrok: {e}")
            return None
    
    def get_tunnel_url(self) -> Optional[str]:
        """Get the current ngrok tunnel URL"""
        try:
            response = requests.get('http://localhost:4040/api/tunnels')
            data = response.json()
            
            for tunnel in data.get('tunnels', []):
                if tunnel.get('proto') == 'https':
                    return tunnel.get('public_url')
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting tunnel URL: {e}")
            return None
    
    def stop_tunnel(self):
        """Stop the ngrok tunnel"""
        if self.process:
            self.process.terminate()
            self.process.wait()
            print("🛑 Ngrok tunnel stopped")
    
    def get_webhook_url(self, bot_token: str) -> Optional[str]:
        """Get the complete webhook URL"""
        if self.tunnel_url:
            return f"{self.tunnel_url}/webhook/{bot_token}"
        return None

def test_webhook_locally():
    """Test webhook setup locally using ngrok"""
    from config import config
    from webhook_setup import WebhookManager
    import asyncio
    
    print("🧪 Local Webhook Testing with Ngrok")
    print("=" * 40)
    
    # Start ngrok tunnel
    ngrok = NgrokHelper()
    tunnel_url = ngrok.start_tunnel(config.WEBHOOK_PORT)
    
    if not tunnel_url:
        return
    
    # Get webhook URL
    webhook_url = ngrok.get_webhook_url(config.BOT_TOKEN)
    print(f"📡 Webhook URL: {webhook_url}")
    
    # Set webhook
    async def setup():
        manager = WebhookManager()
        success = await manager.set_webhook(webhook_url)
        
        if success:
            print("✅ Webhook set successfully!")
            print("🚀 Start your webhook server now:")
            print(f"   python webhook/webhook_server.py")
            print("\n📱 Test your bot in Telegram")
            print("⏹️  Press Ctrl+C to stop")
            
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n🛑 Stopping...")
                await manager.delete_webhook()
                ngrok.stop_tunnel()
        else:
            print("❌ Failed to set webhook")
            ngrok.stop_tunnel()
    
    asyncio.run(setup())

if __name__ == "__main__":
    test_webhook_locally()
