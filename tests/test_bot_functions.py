import asyncio
import sqlite3
import logging
from datetime import datetime
from telegram import Bot
from telegram.error import TelegramError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot Configuration - Your actual values
BOT_TOKEN = "7560905481:AAFm1Ra0zAknomOhXvjsR4kkruurz_O033s"
BROKER_LINK = "https://affiliate.iqbroker.com/redir/?aff=755757&aff_model=revenue&afftrack="
PREMIUM_CHANNEL_ID = "-1001002557285297"
ADMIN_USERNAME = "Optrixtradesadmin"

def test_database():
    """Test database functionality"""
    print("🗄️  Testing Database...")
    try:
        conn = sqlite3.connect('trading_bot.db')
        cursor = conn.cursor()
        
        # Create test tables
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                current_flow TEXT DEFAULT 'welcome',
                registration_status TEXT DEFAULT 'not_started',
                deposit_confirmed BOOLEAN DEFAULT FALSE,
                uid TEXT,
                join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_interaction TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                follow_up_day INTEGER DEFAULT 0,
                is_active BOOLEAN DEFAULT TRUE
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                interaction_type TEXT,
                interaction_data TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        # Test insert
        test_user_id = 123456789
        cursor.execute('''
            INSERT OR REPLACE INTO users (user_id, username, first_name, join_date, last_interaction)
            VALUES (?, ?, ?, ?, ?)
        ''', (test_user_id, "testuser", "Test User", datetime.now(), datetime.now()))
        
        # Test select
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (test_user_id,))
        user = cursor.fetchone()
        
        if user:
            print("   ✅ Database connection: OK")
            print("   ✅ Table creation: OK")
            print("   ✅ Insert/Select operations: OK")
        else:
            print("   ❌ Database operations failed")
            return False
            
        # Clean up test data
        cursor.execute('DELETE FROM users WHERE user_id = ?', (test_user_id,))
        conn.commit()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"   ❌ Database error: {e}")
        return False

async def test_bot_connection():
    """Test bot token and connection"""
    print("🤖 Testing Bot Connection...")
    try:
        bot = Bot(token=BOT_TOKEN)
        bot_info = await bot.get_me()
        
        print(f"   ✅ Bot connected successfully!")
        print(f"   📱 Bot name: {bot_info.first_name}")
        print(f"   🆔 Bot username: @{bot_info.username}")
        print(f"   🔑 Bot ID: {bot_info.id}")
        
        return True, bot
        
    except TelegramError as e:
        print(f"   ❌ Bot connection failed: {e}")
        return False, None
    except Exception as e:
        print(f"   ❌ Unexpected error: {e}")
        return False, None

async def test_channel_access(bot):
    """Test premium channel access"""
    print("📢 Testing Channel Access...")
    try:
        # Try to get chat info
        chat_info = await bot.get_chat(chat_id=PREMIUM_CHANNEL_ID)
        
        print(f"   ✅ Channel access: OK")
        print(f"   📺 Channel title: {chat_info.title}")
        print(f"   🆔 Channel ID: {chat_info.id}")
        print(f"   👥 Channel type: {chat_info.type}")
        
        return True
        
    except TelegramError as e:
        print(f"   ⚠️  Channel access warning: {e}")
        print(f"   💡 Note: Bot needs to be added to the channel as admin")
        return False
    except Exception as e:
        print(f"   ❌ Channel test error: {e}")
        return False

def test_configuration():
    """Test bot configuration"""
    print("⚙️  Testing Configuration...")
    
    config_ok = True
    
    # Test bot token format
    if len(BOT_TOKEN.split(':')) == 2 and BOT_TOKEN.split(':')[0].isdigit():
        print("   ✅ Bot token format: OK")
    else:
        print("   ❌ Bot token format: Invalid")
        config_ok = False
    
    # Test broker link
    if BROKER_LINK.startswith('https://') and 'iqbroker.com' in BROKER_LINK:
        print("   ✅ Broker link: OK")
    else:
        print("   ❌ Broker link: Invalid")
        config_ok = False
    
    # Test channel ID format
    if PREMIUM_CHANNEL_ID.startswith('-100') and len(PREMIUM_CHANNEL_ID) > 10:
        print("   ✅ Channel ID format: OK")
    else:
        print("   ❌ Channel ID format: Invalid")
        config_ok = False
    
    # Test admin username
    if ADMIN_USERNAME and len(ADMIN_USERNAME) > 0:
        print("   ✅ Admin username: OK")
    else:
        print("   ❌ Admin username: Missing")
        config_ok = False
    
    return config_ok

async def run_all_tests():
    """Run all tests"""
    print("🚀 OPTRIXTRADES Bot Testing Suite")
    print("=" * 50)
    
    all_tests_passed = True
    
    # Test 1: Configuration
    config_ok = test_configuration()
    all_tests_passed = all_tests_passed and config_ok
    print()
    
    # Test 2: Database
    db_ok = test_database()
    all_tests_passed = all_tests_passed and db_ok
    print()
    
    # Test 3: Bot Connection
    bot_ok, bot = await test_bot_connection()
    all_tests_passed = all_tests_passed and bot_ok
    print()
    
    # Test 4: Channel Access (if bot connected)
    if bot:
        channel_ok = await test_channel_access(bot)
        # Note: Channel access might fail if bot isn't added to channel yet
        print()
    
    # Final Results
    print("=" * 50)
    if all_tests_passed:
        print("🎉 ALL CORE TESTS PASSED!")
        print("✅ Your OPTRIXTRADES bot is ready to launch!")
        print()
        print("📋 Next Steps:")
        print("1. Run: python telegram_bot.py")
        print("2. Test with /start command in Telegram")
        print("3. Add bot to your premium channel as admin")
        print("4. Start the scheduler: python bot_scheduler.py")
    else:
        print("❌ SOME TESTS FAILED")
        print("Please fix the issues above before launching")
    
    print("=" * 50)
    
    return all_tests_passed

if __name__ == '__main__':
    print("Starting OPTRIXTRADES Bot Tests...")
    asyncio.run(run_all_tests())
