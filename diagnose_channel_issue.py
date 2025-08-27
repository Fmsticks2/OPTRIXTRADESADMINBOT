#!/usr/bin/env python3
"""Diagnose channel access issues and provide solutions"""

import asyncio
from telegram import Bot
from telegram.error import BadRequest, Forbidden
from config import BotConfig

async def diagnose_channel_issue():
    """Diagnose why the bot cannot access the channel"""
    print("🔍 OPTRIXTRADES Channel Access Diagnostic")
    print("=" * 50)
    
    channel_id = BotConfig.PREMIUM_CHANNEL_ID
    bot_token = BotConfig.BOT_TOKEN
    
    print(f"📋 Configuration:")
    print(f"   Channel ID: {channel_id}")
    print(f"   Bot Token: {bot_token[:10]}...{bot_token[-10:] if len(bot_token) > 20 else bot_token}")
    print()
    
    if not channel_id:
        print("❌ PREMIUM_CHANNEL_ID is not configured!")
        print("   Solution: Set PREMIUM_CHANNEL_ID in your .env file")
        return
    
    if not bot_token:
        print("❌ BOT_TOKEN is not configured!")
        print("   Solution: Set BOT_TOKEN in your .env file")
        return
    
    bot = Bot(bot_token)
    
    # Test 1: Basic bot functionality
    print("🤖 Test 1: Bot Authentication")
    try:
        me = await bot.get_me()
        print(f"   ✅ Bot authenticated: @{me.username} ({me.first_name})")
        bot_id = me.id
    except Exception as e:
        print(f"   ❌ Bot authentication failed: {e}")
        return
    
    # Test 2: Channel access
    print(f"\n📢 Test 2: Channel Access ({channel_id})")
    try:
        chat = await bot.get_chat(channel_id)
        print(f"   ✅ Channel found: {chat.title}")
        print(f"   📝 Type: {chat.type}")
        if chat.description:
            print(f"   📄 Description: {chat.description[:100]}...")
        
        # Test 3: Bot membership status
        print(f"\n👤 Test 3: Bot Membership Status")
        try:
            bot_member = await bot.get_chat_member(chat_id=channel_id, user_id=bot_id)
            print(f"   ✅ Bot status in channel: {bot_member.status}")
            
            if bot_member.status == 'administrator':
                print(f"   ✅ Bot has administrator privileges")
                # Check specific permissions
                if hasattr(bot_member, 'can_invite_users'):
                    print(f"   📋 Can invite users: {bot_member.can_invite_users}")
            elif bot_member.status == 'member':
                print(f"   ⚠️  Bot is only a member, not an administrator")
                print(f"   💡 Solution: Make the bot an administrator in the channel")
            else:
                print(f"   ❌ Bot status '{bot_member.status}' may not allow channel operations")
                
        except BadRequest as e:
            if "user not found" in str(e).lower():
                print(f"   ❌ Bot is not a member of the channel")
                print(f"   💡 Solution: Add the bot to the channel as an administrator")
            else:
                print(f"   ❌ Error checking bot membership: {e}")
        
        # Test 4: Member count access
        print(f"\n📊 Test 4: Member Count Access")
        try:
            if hasattr(chat, 'member_count') and chat.member_count:
                print(f"   ✅ Member count: {chat.member_count}")
            else:
                print(f"   ⚠️  Member count not available (may require admin privileges)")
        except Exception as e:
            print(f"   ❌ Error getting member count: {e}")
            
    except BadRequest as e:
        if "chat not found" in str(e).lower():
            print(f"   ❌ Channel not found")
            print(f"   💡 Possible solutions:")
            print(f"      1. Verify the channel ID is correct")
            print(f"      2. Ensure the channel exists")
            print(f"      3. Add the bot to the channel")
            print(f"      4. Make sure the channel is not deleted")
        else:
            print(f"   ❌ BadRequest error: {e}")
    except Forbidden as e:
        print(f"   ❌ Forbidden error: {e}")
        print(f"   💡 Solution: Bot needs to be added to the channel with proper permissions")
    except Exception as e:
        print(f"   ❌ Unexpected error: {e}")
    
    print(f"\n📋 Next Steps:")
    print(f"   1. Go to your Telegram channel: {channel_id}")
    print(f"   2. Click on the channel name → 'Administrators'")
    print(f"   3. Click 'Add Admin' and search for your bot: @{me.username if 'me' in locals() else 'your_bot'}")
    print(f"   4. Grant 'Invite Users via Link' permission")
    print(f"   5. Run this diagnostic again to verify")
    
if __name__ == "__main__":
    asyncio.run(diagnose_channel_issue())