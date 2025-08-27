#!/usr/bin/env python3
"""
Get Channel Information
This script helps you get the correct channel ID and verify channel access.
"""

import asyncio
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.error import TelegramError
from config import BotConfig

async def get_channel_info():
    """Get information about channels the bot has access to"""
    print("🔍 OPTRIXTRADES Channel Information Retrieval")
    print("=" * 50)
    
    # Initialize bot
    bot = Bot(token=BotConfig.BOT_TOKEN)
    
    print(f"📋 Configuration:")
    print(f"   Current Channel ID: {BotConfig.PREMIUM_CHANNEL_ID}")
    print(f"   Bot Token: {BotConfig.BOT_TOKEN[:10]}...{BotConfig.BOT_TOKEN[-10:]}")
    print()
    
    try:
        # Test 1: Get bot info
        print("🤖 Bot Information:")
        bot_info = await bot.get_me()
        print(f"   ✅ Bot: @{bot_info.username} ({bot_info.first_name})")
        print(f"   🆔 Bot ID: {bot_info.id}")
        print()
        
        # Test different channel ID formats
        channel_id = BotConfig.PREMIUM_CHANNEL_ID
        print("🔍 Testing Different Channel ID Formats:")
        
        # Format 1: Current ID
        print(f"   Format 1: {channel_id}")
        try:
            chat = await bot.get_chat(channel_id)
            print(f"   ✅ Success: {chat.title} (Type: {chat.type})")
        except TelegramError as e:
            print(f"   ❌ Failed: {e}")
        
        # Format 2: Without -100 prefix (if it has one)
        if str(channel_id).startswith('-100'):
            alt_id = str(channel_id)[4:]  # Remove -100 prefix
            print(f"   Format 2: {alt_id}")
            try:
                chat = await bot.get_chat(alt_id)
                print(f"   ✅ Success: {chat.title} (Type: {chat.type})")
            except TelegramError as e:
                print(f"   ❌ Failed: {e}")
        
        # Format 3: With -100 prefix (if it doesn't have one)
        if not str(channel_id).startswith('-100'):
            alt_id = f"-100{channel_id}"
            print(f"   Format 3: {alt_id}")
            try:
                chat = await bot.get_chat(alt_id)
                print(f"   ✅ Success: {chat.title} (Type: {chat.type})")
            except TelegramError as e:
                print(f"   ❌ Failed: {e}")
        
        # Format 4: As positive number
        if str(channel_id).startswith('-'):
            alt_id = str(channel_id)[1:]  # Remove - prefix
            print(f"   Format 4: {alt_id}")
            try:
                chat = await bot.get_chat(alt_id)
                print(f"   ✅ Success: {chat.title} (Type: {chat.type})")
            except TelegramError as e:
                print(f"   ❌ Failed: {e}")
        
        print()
        print("📋 Instructions to Get Correct Channel ID:")
        print("   1. Go to your Telegram channel")
        print("   2. Add this bot as administrator: @Optrixtrades_bot")
        print("   3. Send a message in the channel mentioning the bot: @Optrixtrades_bot")
        print("   4. Forward any message from the channel to @userinfobot")
        print("   5. @userinfobot will show you the correct channel ID")
        print()
        print("   Alternative method:")
        print("   1. In your channel, type: /start")
        print("   2. The bot will respond with channel information if it has access")
        print()
        print("💡 Common Channel ID Formats:")
        print("   • Supergroups/Channels: -100xxxxxxxxxx")
        print("   • Groups: -xxxxxxxxx")
        print("   • Private chats: positive numbers")
        
    except TelegramError as e:
        print(f"❌ Bot authentication failed: {e}")
        print(f"💡 Check if the bot token is correct")

# Command handler to get chat info when bot receives a message
async def get_chat_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get chat ID when someone sends a command to the bot"""
    chat = update.effective_chat
    user = update.effective_user
    
    response = f"""🔍 **Chat Information**
    
**Chat Details:**
• Chat ID: `{chat.id}`
• Chat Type: {chat.type}
• Chat Title: {chat.title if chat.title else 'N/A'}
• Chat Username: @{chat.username if chat.username else 'N/A'}

**User Details:**
• User ID: `{user.id}`
• Username: @{user.username if user.username else 'N/A'}
• Name: {user.first_name} {user.last_name if user.last_name else ''}

**Instructions:**
If this is your premium channel, copy the Chat ID above and update your .env file:
`PREMIUM_CHANNEL_ID={chat.id}`
"""
    
    await update.message.reply_text(response, parse_mode='Markdown')

async def start_bot_for_id_detection():
    """Start bot to detect channel IDs"""
    print("🚀 Starting bot for channel ID detection...")
    print("💡 Add the bot to your channel and send /chatinfo to get the channel ID")
    print("⏹️  Press Ctrl+C to stop")
    
    application = Application.builder().token(BotConfig.BOT_TOKEN).build()
    application.add_handler(CommandHandler("chatinfo", get_chat_id))
    application.add_handler(CommandHandler("start", get_chat_id))
    
    await application.run_polling()

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--listen":
        # Start bot to listen for channel ID
        asyncio.run(start_bot_for_id_detection())
    else:
        # Just check current configuration
        asyncio.run(get_channel_info())