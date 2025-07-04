"""
Local development environment setup and testing script
Provides comprehensive local testing with PostgreSQL and webhook support
"""

import asyncio
import subprocess
import sys
import os
import time
import logging
from typing import Optional, Dict, Any

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import config
from database import db_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LocalDevelopmentManager:
    """Manages local development environment"""
    
    def __init__(self):
        self.processes = []
        self.ngrok_process = None
        self.webhook_url = None
    
    async def setup_development_environment(self):
        """Setup complete development environment"""
        logger.info("🚀 Setting up OPTRIXTRADES Local Development Environment")
        logger.info("=" * 60)
        
        # Step 1: Validate configuration
        await self.validate_configuration()
        
        # Step 2: Setup database
        await self.setup_database()
        
        # Step 3: Run system tests
        await self.run_system_tests()
        
        # Step 4: Setup webhook (if enabled)
        if config.BOT_MODE == 'webhook':
            await self.setup_webhook_environment()
        
        # Step 5: Start bot
        await self.start_bot()
    
    async def validate_configuration(self):
        """Validate development configuration"""
        logger.info("🔧 Validating Configuration...")
        
        # Check required dependencies
        required_packages = ['asyncpg', 'psycopg2', 'python-telegram-bot', 'fastapi']
        missing_packages = []
        
        for package in required_packages:
            try:
                __import__(package.replace('-', '_'))
            except ImportError:
                missing_packages.append(package)
        
        if missing_packages:
            logger.error(f"❌ Missing packages: {', '.join(missing_packages)}")
            logger.info("Install with: pip install " + " ".join(missing_packages))
            raise SystemExit(1)
        
        # Validate environment variables
        validation_result = config.validate_config()
        if not validation_result['valid']:
            logger.error("❌ Configuration validation failed:")
            for error in validation_result['errors']:
                logger.error(f"   - {error}")
            raise SystemExit(1)
        
        if validation_result['warnings']:
            logger.warning("⚠️  Configuration warnings:")
            for warning in validation_result['warnings']:
                logger.warning(f"   - {warning}")
        
        logger.info("   ✅ Configuration valid")
    
    async def setup_database(self):
        """Setup and test database connection"""
        logger.info("🗄️  Setting up Database...")
        
        try:
            # Initialize database
            await db_manager.initialize()
            
            # Test connection
            health = await db_manager.health_check()
            if health['status'] != 'healthy':
                raise Exception(f"Database health check failed: {health}")
            
            logger.info(f"   ✅ Database connected ({db_manager.db_type})")
            logger.info(f"   📊 Response time: {health.get('response_time_ms', 'N/A')}ms")
            
        except Exception as e:
            logger.error(f"❌ Database setup failed: {e}")
            
            if config.DATABASE_TYPE == 'postgresql':
                logger.info("💡 PostgreSQL Setup Tips:")
                logger.info("   1. Ensure PostgreSQL is running locally")
                logger.info("   2. Create database: createdb optrixtrades")
                logger.info("   3. Check connection string in .env")
                logger.info("   4. For Railway: DATABASE_URL is auto-populated")
            
            raise SystemExit(1)
    
    async def run_system_tests(self):
        """Run comprehensive system tests"""
        logger.info("🧪 Running System Tests...")
        
        try:
            # Import and run tests
            from tests.test_system_comprehensive import SystemTester
            
            tester = SystemTester()
            report = await tester.run_all_tests()
            
            if report['success_rate'] < 80:
                logger.error(f"❌ System tests failed ({report['success_rate']}% success rate)")
                logger.error("Fix issues before continuing development")
                raise SystemExit(1)
            
            logger.info(f"   ✅ System tests passed ({report['success_rate']}% success rate)")
            
        except ImportError:
            logger.warning("⚠️  System tests not available - continuing without testing")
        except Exception as e:
            logger.error(f"❌ System tests failed: {e}")
            raise SystemExit(1)
    
    async def setup_webhook_environment(self):
        """Setup webhook development environment with ngrok"""
        logger.info("🌐 Setting up Webhook Environment...")
        
        try:
            # Check if ngrok is available
            subprocess.run(['ngrok', 'version'], capture_output=True, check=True)
            
            # Start ngrok tunnel
            logger.info("   🚇 Starting ngrok tunnel...")
            self.ngrok_process = subprocess.Popen(
                ['ngrok', 'http', str(config.WEBHOOK_PORT)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Wait for ngrok to start
            time.sleep(3)
            
            # Get tunnel URL
            self.webhook_url = await self.get_ngrok_url()
            
            if self.webhook_url:
                logger.info(f"   ✅ Ngrok tunnel: {self.webhook_url}")
                
                # Set webhook
                await self.set_telegram_webhook()
            else:
                logger.error("❌ Failed to get ngrok tunnel URL")
                raise SystemExit(1)
                
        except FileNotFoundError:
            logger.error("❌ Ngrok not found")
            logger.info("💡 Install ngrok:")
            logger.info("   1. Download from https://ngrok.com/download")
            logger.info("   2. Or use: brew install ngrok (macOS)")
            logger.info("   3. Or use: choco install ngrok (Windows)")
            raise SystemExit(1)
        except Exception as e:
            logger.error(f"❌ Webhook setup failed: {e}")
            raise SystemExit(1)
    
    async def get_ngrok_url(self) -> Optional[str]:
        """Get ngrok tunnel URL"""
        try:
            import requests
            response = requests.get('http://localhost:4040/api/tunnels', timeout=5)
            data = response.json()
            
            for tunnel in data.get('tunnels', []):
                if tunnel.get('proto') == 'https':
                    return tunnel.get('public_url')
            
            return None
        except Exception as e:
            logger.error(f"Error getting ngrok URL: {e}")
            return None
    
    async def set_telegram_webhook(self):
        """Set Telegram webhook URL"""
        try:
            from telegram import Bot
            
            bot = Bot(token=config.BOT_TOKEN)
            webhook_url = f"{self.webhook_url}/webhook/{config.BOT_TOKEN}"
            
            result = await bot.set_webhook(
                url=webhook_url,
                secret_token=config.WEBHOOK_SECRET_TOKEN,
                drop_pending_updates=True
            )
            
            if result:
                logger.info(f"   ✅ Webhook set: {webhook_url}")
            else:
                logger.error("❌ Failed to set webhook")
                
        except Exception as e:
            logger.error(f"❌ Webhook setup failed: {e}")
    
    async def start_bot(self):
        """Start the bot in appropriate mode"""
        logger.info("🤖 Starting Bot...")
        
        try:
            if config.BOT_MODE == 'webhook':
                # Start webhook server
                logger.info("   🌐 Starting webhook server...")
                from webhook.webhook_server import run_webhook_server
                
                # Run in background
                import threading
                webhook_thread = threading.Thread(target=run_webhook_server)
                webhook_thread.daemon = True
                webhook_thread.start()
                
                logger.info(f"   ✅ Webhook server started on port {config.WEBHOOK_PORT}")
                logger.info(f"   🔗 Webhook URL: {self.webhook_url}/webhook/{config.BOT_TOKEN}")
                
            else:
                # Start polling mode
                logger.info("   🔄 Starting polling mode...")
                from telegram_bot import main
                import asyncio
                await main()
                
        except Exception as e:
            logger.error(f"❌ Bot startup failed: {e}")
            raise SystemExit(1)
    
    def cleanup(self):
        """Cleanup development environment"""
        logger.info("🧹 Cleaning up development environment...")
        
        # Stop ngrok
        if self.ngrok_process:
            self.ngrok_process.terminate()
            logger.info("   🚇 Ngrok tunnel stopped")
        
        # Stop other processes
        for process in self.processes:
            try:
                process.terminate()
            except:
                pass
        
        logger.info("   ✅ Cleanup completed")

async def interactive_setup():
    """Interactive development setup"""
    print("🚀 OPTRIXTRADES Local Development Setup")
    print("=" * 50)
    
    # Check current configuration
    print(f"📊 Current Configuration:")
    print(f"   Database: {config.DATABASE_TYPE}")
    print(f"   Bot Mode: {config.BOT_MODE}")
    print(f"   Auto-Verification: {'Enabled' if config.AUTO_VERIFY_ENABLED else 'Disabled'}")
    print(f"   Debug Mode: {'Enabled' if config.DEBUG_MODE else 'Disabled'}")
    print()
    
    # Ask for confirmation
    proceed = input("Proceed with development setup? (y/N): ").strip().lower()
    if proceed != 'y':
        print("Setup cancelled.")
        return
    
    # Setup development environment
    manager = LocalDevelopmentManager()
    
    try:
        await manager.setup_development_environment()
        
        print("\n🎉 Development environment ready!")
        print("=" * 50)
        print("📋 Next Steps:")
        print("1. Test your bot by sending /start in Telegram")
        print("2. Check logs for any issues")
        print("3. Use admin commands to test verification")
        print("4. Press Ctrl+C to stop when done")
        print("=" * 50)
        
        # Keep running
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 Stopping development environment...")
            
    except Exception as e:
        logger.error(f"Development setup failed: {e}")
    finally:
        manager.cleanup()

def main():
    """Main function"""
    try:
        asyncio.run(interactive_setup())
    except KeyboardInterrupt:
        print("\n👋 Development setup interrupted")
    except Exception as e:
        logger.error(f"Setup failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
