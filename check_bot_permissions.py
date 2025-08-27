#!/usr/bin/env python3
"""
Check Bot Permissions in Channel
This script checks what permissions the bot currently has in the specified channel.
"""

import asyncio
from telegram import Bot
from telegram.error import TelegramError
from config import BotConfig

async def check_bot_permissions():
    """Check bot permissions in the channel"""
    print("🔍 OPTRIXTRADES Bot Permissions Check")
    print("=" * 50)
    
    # Initialize bot
    bot = Bot(token=BotConfig.BOT_TOKEN)
    channel_id = BotConfig.PREMIUM_CHANNEL_ID
    
    print(f"📋 Configuration:")
    print(f"   Channel ID: {channel_id}")
    print(f"   Bot Token: {BotConfig.BOT_TOKEN[:10]}...{BotConfig.BOT_TOKEN[-10:]}")
    print()
    
    try:
        # Test 1: Get bot info
        print("🤖 Test 1: Bot Authentication")
        bot_info = await bot.get_me()
        print(f"   ✅ Bot authenticated: @{bot_info.username} ({bot_info.first_name})")
        print()
        
        # Test 2: Get chat info
        print(f"📢 Test 2: Channel Information ({channel_id})")
        try:
            chat = await bot.get_chat(channel_id)
            print(f"   ✅ Channel found: {chat.title}")
            print(f"   📊 Type: {chat.type}")
            print(f"   👥 Members: {chat.member_count if hasattr(chat, 'member_count') else 'Unknown'}")
            print()
            
            # Test 3: Get bot's member status
            print("🔐 Test 3: Bot Member Status")
            try:
                member = await bot.get_chat_member(channel_id, bot_info.id)
                print(f"   ✅ Bot status: {member.status}")
                
                if member.status == 'administrator':
                    print("   🎯 Administrator Permissions:")
                    print(f"      • Can delete messages: {member.can_delete_messages}")
                    print(f"      • Can invite users: {member.can_invite_users}")
                    print(f"      • Can pin messages: {member.can_pin_messages}")
                    print(f"      • Can post messages: {member.can_post_messages}")
                    print(f"      • Can edit messages: {member.can_edit_messages}")
                    print(f"      • Can promote members: {member.can_promote_members}")
                    print(f"      • Can restrict members: {member.can_restrict_members}")
                    print(f"      • Can manage chat: {member.can_manage_chat}")
                    print(f"      • Can manage video chats: {member.can_manage_video_chats}")
                elif member.status == 'member':
                    print("   ⚠️  Bot is a regular member, not an administrator")
                elif member.status == 'left':
                    print("   ❌ Bot has left the channel")
                elif member.status == 'kicked':
                    print("   ❌ Bot has been banned from the channel")
                    
            except TelegramError as e:
                print(f"   ❌ Error getting member status: {e}")
                print(f"   💡 This might indicate the bot is not in the channel")
            print()
            
            # Test 4: Try to send a test message
            print("📤 Test 4: Send Test Message")
            try:
                test_message = await bot.send_message(
                    chat_id=channel_id,
                    text="🔧 Bot permissions test - this message will be deleted"
                )
                print("   ✅ Successfully sent test message")
                
                # Try to delete the test message
                try:
                    await bot.delete_message(channel_id, test_message.message_id)
                    print("   ✅ Successfully deleted test message")
                except TelegramError as e:
                    print(f"   ⚠️  Could not delete test message: {e}")
                    
            except TelegramError as e:
                print(f"   ❌ Error sending test message: {e}")
                print(f"   💡 Bot might not have permission to post messages")
                
        except TelegramError as e:
            print(f"   ❌ Channel not accessible: {e}")
            print(f"   💡 Possible issues:")
            print(f"      1. Channel ID is incorrect")
            print(f"      2. Bot is not added to the channel")
            print(f"      3. Channel doesn't exist or was deleted")
            print(f"      4. Bot was removed from the channel")
            
    except TelegramError as e:
        print(f"❌ Bot authentication failed: {e}")
        print(f"💡 Check if the bot token is correct")
        
    print()
    print("📋 Next Steps:")
    print("   1. If bot is not an admin, add it as administrator")
    print("   2. Grant these permissions: 'Invite Users via Link', 'Pin Messages', 'Delete Messages'")
    print("   3. If channel ID is wrong, get the correct ID from channel info")
    print("   4. Re-run this script to verify permissions")

if __name__ == "__main__":
    asyncio.run(check_bot_permissions())