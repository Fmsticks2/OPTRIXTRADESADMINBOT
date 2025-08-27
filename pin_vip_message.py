#!/usr/bin/env python3
"""
Script to pin a 'Free VIP channel' message with a button redirecting to the bot
"""

import asyncio
import os
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError
from config import BotConfig

async def pin_vip_message():
    """
    Pin a message with 'Free VIP channel' text and a button redirecting to the bot
    """
    # Initialize bot
    bot = Bot(token=BotConfig.BOT_TOKEN)
    
    try:
        # Get bot info to create the redirect URL
        bot_info = await bot.get_me()
        bot_username = bot_info.username
        bot_url = f"https://t.me/Optrixtradesadmin"
        
        print(f"🤖 Bot: @{bot_username}")
        print(f"📢 Channel ID: {BotConfig.PREMIUM_CHANNEL_ID}")
        print(f"🔗 Bot URL: {bot_url}")
        
        # Create inline keyboard with "FREE VIP" button
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("FREE PREMIUM ACCESS", url=f"{bot_url}?start=premium_access&text=I%20want%20to%20get%20access%20to%20the%20premium%20channel")]
        ])
        
        # Message text
        message_text = "🎉 Free VIP Channel 🎉\n\n" \
                      "Get exclusive trading signals and premium content!\n" \
                      "Click the button below to get started"
        
        # Send the message to the channel
        print("📤 Sending message to channel...")
        message = await bot.send_message(
            chat_id=BotConfig.PREMIUM_CHANNEL_ID,
            text=message_text,
            parse_mode='Markdown',
            reply_markup=keyboard
        )
        
        print(f"✅ Message sent successfully! Message ID: {message.message_id}")
        
        # Pin the message
        print("📌 Pinning message...")
        await bot.pin_chat_message(
            chat_id=BotConfig.PREMIUM_CHANNEL_ID,
            message_id=message.message_id,
            disable_notification=False  # Set to True if you don't want to notify channel members
        )
        
        print("🎯 Message pinned successfully!")
        print(f"\n📋 Summary:")
        print(f"   - Channel: {BotConfig.PREMIUM_CHANNEL_ID}")
        print(f"   - Message ID: {message.message_id}")
        print(f"   - Bot URL: {bot_url}")
        print(f"   - Status: ✅ Pinned")
        
    except TelegramError as e:
        print(f"❌ Telegram Error: {e}")
        if "Chat not found" in str(e):
            print("💡 Solution: Add the bot as administrator to the channel first")
        elif "Not enough rights" in str(e):
            print("💡 Solution: Grant 'Pin Messages' permission to the bot")
        elif "CHAT_ADMIN_REQUIRED" in str(e):
            print("💡 Solution: Bot needs admin rights in the channel")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

if __name__ == "__main__":
    print("🚀 Starting VIP Message Pinning...")
    print("=" * 50)
    
    # Check if running in Railway environment
    if os.getenv('RAILWAY_ENVIRONMENT'):
        print("🚄 Railway Environment Detected")
    
    # Run the async function
    asyncio.run(pin_vip_message())