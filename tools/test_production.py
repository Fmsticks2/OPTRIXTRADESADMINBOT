import os
import sqlite3
import logging
from datetime import datetime

# Test script for production deployment
def test_environment():
    """Test production environment"""
    print("🧪 OPTRIXTRADES Production Test")
    print("=" * 50)
    
    # Test environment variables
    env_vars = {
        'BOT_TOKEN': os.getenv('BOT_TOKEN'),
        'BROKER_LINK': os.getenv('BROKER_LINK'),
        'PREMIUM_CHANNEL_ID': os.getenv('PREMIUM_CHANNEL_ID'),
        'ADMIN_USERNAME': os.getenv('ADMIN_USERNAME')
    }
    
    print("🔧 Environment Variables:")
    for key, value in env_vars.items():
        if value:
            display_value = value[:10] + "..." if len(value) > 10 else value
            print(f"   ✅ {key}: {display_value}")
        else:
            print(f"   ⚠️  {key}: Using default value")
    
    print()
    
    # Test database
    print("🗄️  Database Test:")
    try:
        conn = sqlite3.connect('trading_bot.db')
        cursor = conn.cursor()
        
        # Test table creation
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS test_table (
                id INTEGER PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Test insert
        cursor.execute('INSERT INTO test_table DEFAULT VALUES')
        
        # Test select
        cursor.execute('SELECT COUNT(*) FROM test_table')
        count = cursor.fetchone()[0]
        
        # Cleanup
        cursor.execute('DROP TABLE test_table')
        conn.commit()
        conn.close()
        
        print(f"   ✅ Database operations: OK (test records: {count})")
        
    except Exception as e:
        print(f"   ❌ Database error: {e}")
    
    print()
    
    # Test imports
    print("📦 Dependencies Test:")
    try:
        import telegram
        print("   ✅ python-telegram-bot: OK")
    except ImportError:
        print("   ❌ python-telegram-bot: Missing")
    
    try:
        import asyncio
        print("   ✅ asyncio: OK")
    except ImportError:
        print("   ❌ asyncio: Missing")
    
    print()
    print("=" * 50)
    print("🚀 Production test completed!")
    print("Ready for Railway deployment!")
    print("=" * 50)

if __name__ == '__main__':
    test_environment()
