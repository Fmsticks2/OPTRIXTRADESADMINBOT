#!/usr/bin/env python3
"""Test script to check channel access"""

import asyncio
from telegram import Bot
from config import BotConfig

async def test_channel_access():
    """Test if bot can access the configured channel"""
    print(f"Testing channel access for ID: {BotConfig.PREMIUM_CHANNEL_ID}")
    
    bot = Bot(BotConfig.BOT_TOKEN)
    
    try:
        # Try to get chat info
        chat = await bot.get_chat(BotConfig.PREMIUM_CHANNEL_ID)
        print(f"✅ Channel found: {chat.title} (ID: {chat.id})")
        print(f"   Type: {chat.type}")
        print(f"   Description: {chat.description[:100] if chat.description else 'No description'}")
        
        # Try to get member count
        if hasattr(chat, 'member_count') and chat.member_count:
            print(f"   Member count: {chat.member_count}")
        
        # Check bot's status in the channel
        try:
            bot_member = await bot.get_chat_member(chat_id=BotConfig.PREMIUM_CHANNEL_ID, user_id=bot.id)
            print(f"   Bot status: {bot_member.status}")
        except Exception as e:
            print(f"   ⚠️ Could not get bot status: {e}")
            
        return True
        
    except Exception as e:
        print(f"❌ Error accessing channel: {e}")
        print(f"   Error type: {type(e).__name__}")
        return False

if __name__ == "__main__":
    asyncio.run(test_channel_access())