#!/usr/bin/env python3
"""
Test script for batch follow-up functionality
"""

import asyncio
import sys
import os

# Add the parent directory to the path so we can import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import DatabaseManager
from telegram_bot.utils.batch_follow_up import BatchFollowUpManager, start_batch_follow_ups, get_batch_follow_up_stats
from telegram_bot.utils.follow_up_scheduler import FollowUpScheduler
from telegram import Bot
from config import BotConfig

async def test_batch_follow_ups():
    """Test the batch follow-up functionality"""
    print("🔄 Testing Batch Follow-up System...")
    
    # Initialize database
    db_manager = DatabaseManager()
    await db_manager.initialize()
    
    # Initialize bot and scheduler
    bot = Bot(token=BotConfig.BOT_TOKEN)
    scheduler = FollowUpScheduler(bot)
    
    # Initialize batch manager
    batch_manager = BatchFollowUpManager(scheduler, db_manager)
    
    print("\n📊 Getting current statistics...")
    stats = await batch_manager.get_follow_up_stats()
    print(f"Current follow-up stats: {stats}")
    
    print("\n🔍 Getting unverified users...")
    unverified_users = await batch_manager.get_unverified_users()
    print(f"Found {len(unverified_users)} unverified users")
    
    if unverified_users:
        print("\nFirst 3 unverified users:")
        for i, user in enumerate(unverified_users[:3]):
            print(f"  {i+1}. User ID: {user['user_id']}, Name: {user.get('first_name', 'N/A')}, Status: {user.get('verification_status', 'N/A')}")
        
        print("\n🚀 Starting follow-ups for first 2 users (test mode)...")
        result = await batch_manager.start_follow_ups_for_unverified_users(limit=2)
        print(f"Batch follow-up result: {result}")
        
        print("\n📊 Updated statistics...")
        updated_stats = await batch_manager.get_follow_up_stats()
        print(f"Updated follow-up stats: {updated_stats}")
    else:
        print("No unverified users found to test with.")
    
    print("\n✅ Batch follow-up test completed!")
    
    # Cleanup option
    cleanup = input("\nDo you want to cancel all scheduled follow-ups? (y/N): ")
    if cleanup.lower() == 'y':
        print("🧹 Cancelling all follow-ups...")
        cancel_result = await batch_manager.cancel_all_follow_ups()
        print(f"Cancel result: {cancel_result}")
    
    await db_manager.close()

async def test_convenience_functions():
    """Test the convenience functions"""
    print("\n🔧 Testing convenience functions...")
    
    # Initialize required components
    db_manager = DatabaseManager()
    await db_manager.initialize()
    bot = Bot(token=BotConfig.BOT_TOKEN)
    
    # Test start_batch_follow_ups
    print("Testing start_batch_follow_ups function...")
    result = await start_batch_follow_ups(db_manager, bot, limit=1)
    print(f"start_batch_follow_ups result: {result}")
    
    # Test get_batch_follow_up_stats
    print("\nTesting get_batch_follow_up_stats function...")
    stats = await get_batch_follow_up_stats(db_manager, bot)
    print(f"get_batch_follow_up_stats result: {stats}")
    
    await db_manager.close()
    print("✅ Convenience functions test completed!")

if __name__ == "__main__":
    print("🤖 OPTRIXTRADES Batch Follow-up Test")
    print("=====================================")
    
    try:
        asyncio.run(test_batch_follow_ups())
        asyncio.run(test_convenience_functions())
    except KeyboardInterrupt:
        print("\n⚠️ Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()