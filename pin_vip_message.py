#!/usr/bin/env python3
"""
Script to pin a 'Free VIP channel' message with a button redirecting to the bot
"""

import asyncio
import os
import tempfile
import requests
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
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "FREE PREMIUM ACCESS",
                        url=f"{bot_url}",
                    )
                ]
            ]
        )

        # Message text (caption for the video)
        message_text = (
            "🎉 Free VIP Channel 🎉\n\n"
            "Get exclusive trading signals and premium content!\n"
            "Click the button below to get started"
        )

        # Download the video and send as a file
        print("📥 Downloading video...")

        # Create a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as temp_file:
            temp_path = temp_file.name

        # Download the video
        video_url = "https://res.cloudinary.com/dapoadedire/video/upload/v1756314223/video_2025-08-27_18-02-34_eftzum.mp4"
        response = requests.get(video_url, stream=True)
        response.raise_for_status()

        with open(temp_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        print(f"✅ Video downloaded to {temp_path}")

        # Send the video
        print("📤 Sending video message to channel...")
        with open(temp_path, "rb") as video_file:
            message = await bot.send_video(
                chat_id=BotConfig.PREMIUM_CHANNEL_ID,
                video=video_file,
                caption=message_text,
                reply_markup=keyboard,
                supports_streaming=True,
                parse_mode="Markdown",
            )

        # Clean up the temporary file
        os.unlink(temp_path)
        print("🧹 Temporary file cleaned up")

        print(f"✅ Message sent successfully! Message ID: {message.message_id}")

        # Pin the message
        print("📌 Pinning message...")
        await bot.pin_chat_message(
            chat_id=BotConfig.PREMIUM_CHANNEL_ID,
            message_id=message.message_id,
            disable_notification=False,  # Set to True if you don't want to notify channel members
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
        elif "Wrong type of the web page content" in str(e):
            print(
                "💡 Solution: The video URL format is not supported. Try using a different method or format."
            )
    except Exception as e:
        print(f"❌ Unexpected error: {e}")


if __name__ == "__main__":
    print("🚀 Starting VIP Message Pinning...")
    print("=" * 50)

    # Check if running in Railway environment
    if os.getenv("RAILWAY_ENVIRONMENT"):
        print("🚄 Railway Environment Detected")
    else:
        print("🏠 Local Development Environment")
        print("💡 Set VALIDATE_CONFIG=true to enable configuration validation locally")

    # Run the async function
    asyncio.run(pin_vip_message())
