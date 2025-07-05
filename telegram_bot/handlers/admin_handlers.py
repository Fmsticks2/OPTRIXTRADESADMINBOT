"""Admin command handlers for OPTRIXTRADES Telegram Bot"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from config import BotConfig
from database.connection import (
    get_all_users, get_pending_verifications, update_verification_status,
    get_user_data, db_manager, log_interaction
)

logger = logging.getLogger(__name__)

# Conversation states
BROADCAST_MESSAGE = 0
USER_LOOKUP = 1
SEARCH_USER = 2

# Placeholder functions that will need to be implemented with actual logic
# These would be extracted from the original telegram_bot.py file

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /admin command"""
    user_id = update.effective_user.id
    if str(user_id) == BotConfig.ADMIN_USER_ID:
        admin_text = "🔐 **OPTRIXTRADES Admin Dashboard**\n\n"
        admin_text += "Welcome to the admin control panel. Choose an action below:\n\n"
        admin_text += "📋 **Queue** - View pending verification requests\n"
        admin_text += "📢 **Broadcast** - Send message to all users\n"
        admin_text += "🔍 **Search User** - Find user by ID or username\n"
        admin_text += "📊 **Recent Activity** - View recent bot activity\n"
        admin_text += "🤖 **Auto-Verify Stats** - Check auto-verification statistics\n"
        admin_text += "💬 **Chat History** - View user chat logs\n\n"
        admin_text += "Use the buttons below or type commands directly."
        
        keyboard = [
            [InlineKeyboardButton("📋 Queue", callback_data="admin_queue"),
             InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")],
            [InlineKeyboardButton("🔍 Search User", callback_data="admin_search_user"),
             InlineKeyboardButton("📊 Recent Activity", callback_data="admin_recent_activity")],
            [InlineKeyboardButton("🤖 Auto-Verify Stats", callback_data="admin_auto_verify_stats"),
             InlineKeyboardButton("💬 Chat History", callback_data="admin_chat_history")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            admin_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text("⛔ You are not authorized to use admin commands.")

async def admin_verify_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /verify or /admin_verify command"""
    # Placeholder
    user_id = update.effective_user.id
    if str(user_id) == BotConfig.ADMIN_USER_ID:
        await update.message.reply_text("Please provide the user ID to verify.")
    else:
        await update.message.reply_text("⛔ You are not authorized to use admin commands.")

async def admin_reject_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /reject or /admin_reject command"""
    # Placeholder
    user_id = update.effective_user.id
    if str(user_id) == BotConfig.ADMIN_USER_ID:
        await update.message.reply_text("Please provide the user ID to reject.")
    else:
        await update.message.reply_text("⛔ You are not authorized to use admin commands.")

async def admin_queue_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /queue or /admin_queue command"""
    # Placeholder
    user_id = update.effective_user.id
    if str(user_id) == BotConfig.ADMIN_USER_ID:
        await update.message.reply_text("Verification queue will be displayed here.")
    else:
        await update.message.reply_text("⛔ You are not authorized to use admin commands.")

async def admin_broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /admin_broadcast command"""
    # Placeholder
    user_id = update.effective_user.id
    if str(user_id) == BotConfig.ADMIN_USER_ID:
        await update.message.reply_text("Please enter the message to broadcast.")
    else:
        await update.message.reply_text("⛔ You are not authorized to use admin commands.")

async def admin_recent_activity_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /admin_recent_activity or /activity command"""
    # Placeholder
    user_id = update.effective_user.id
    if str(user_id) == BotConfig.ADMIN_USER_ID:
        await update.message.reply_text("Recent activity will be displayed here.")
    else:
        await update.message.reply_text("⛔ You are not authorized to use admin commands.")

async def admin_search_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /admin_search_user or /searchuser command"""
    # Placeholder
    user_id = update.effective_user.id
    if str(user_id) == BotConfig.ADMIN_USER_ID:
        await update.message.reply_text("Please enter the user ID or username to search.")
    else:
        await update.message.reply_text("⛔ You are not authorized to use admin commands.")

async def admin_auto_verify_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /admin_auto_verify_stats or /autostats command"""
    # Placeholder
    user_id = update.effective_user.id
    if str(user_id) == BotConfig.ADMIN_USER_ID:
        await update.message.reply_text("Auto-verification stats will be displayed here.")
    else:
        await update.message.reply_text("⛔ You are not authorized to use admin commands.")

async def handle_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the /broadcast command"""
    user_id = update.effective_user.id
    if str(user_id) != BotConfig.ADMIN_USER_ID:
        await update.message.reply_text("⛔ You are not authorized to use admin commands.")
        return ConversationHandler.END
    
    await update.message.reply_text("📢 Please enter the message to broadcast to all users:")
    context.user_data['admin_action'] = 'broadcast'
    return BROADCAST_MESSAGE

async def handle_broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle broadcast message input"""
    user_id = update.effective_user.id
    if str(user_id) != BotConfig.ADMIN_USER_ID:
        await update.message.reply_text("⛔ You are not authorized to use admin commands.")
        return ConversationHandler.END
    
    broadcast_message = update.message.text
    
    # Check if user is in broadcast conversation state
    if context.user_data.get('admin_action') != 'broadcast':
        logger.warning(f"User {user_id} sent broadcast message but not in broadcast state")
        return ConversationHandler.END
    
    try:
        # Get all users
        all_users = await get_all_users()
        
        if not all_users:
            confirmation_text = "❌ No users found to broadcast to."
            keyboard = [[InlineKeyboardButton("🔙 Back to Dashboard", callback_data="admin_dashboard")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(confirmation_text, reply_markup=reply_markup)
            return ConversationHandler.END
        
        # Send confirmation with persistent message
        confirmation_text = (
            f"📢 **Broadcasting message to {len(all_users)} users...**\n\n"
            f"**Message Preview:**\n{broadcast_message}\n\n"
            f"⏳ Please wait while the message is being sent..."
        )
        
        keyboard = [[InlineKeyboardButton("🔙 Back to Dashboard", callback_data="admin_dashboard")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        confirmation_msg = await update.message.reply_text(
            confirmation_text, 
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        
        # Broadcast to all users
        success_count = 0
        failed_count = 0
        
        for user in all_users:
            try:
                await context.bot.send_message(
                    chat_id=user['user_id'],
                    text=f"📢 **OPTRIXTRADES Announcement**\n\n{broadcast_message}",
                    parse_mode='Markdown'
                )
                success_count += 1
                
                # Log the broadcast
                await log_interaction(user['user_id'], 'broadcast_received', broadcast_message)
                
            except Exception as e:
                logger.error(f"Failed to send broadcast to user {user['user_id']}: {e}")
                failed_count += 1
        
        # Update the confirmation message with final report
        report_text = f"✅ **Broadcast Complete!**\n\n"
        report_text += f"📊 **Results:**\n"
        report_text += f"• Successfully sent: {success_count}\n"
        report_text += f"• Failed: {failed_count}\n"
        report_text += f"• Total users: {len(all_users)}\n\n"
        report_text += f"**Original Message:**\n{broadcast_message}"
        
        keyboard = [[InlineKeyboardButton("🔙 Back to Dashboard", callback_data="admin_dashboard")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await confirmation_msg.edit_text(report_text, parse_mode='Markdown', reply_markup=reply_markup)
        
        # Log admin action
        await log_interaction(user_id, 'admin_broadcast', f"Sent to {success_count} users")
        
        # Clear conversation state
        context.user_data.clear()
        
    except Exception as e:
        logger.error(f"Error in broadcast: {e}")
        error_text = "❌ Error occurred while broadcasting message."
        keyboard = [[InlineKeyboardButton("🔙 Back to Dashboard", callback_data="admin_dashboard")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(error_text, reply_markup=reply_markup)
    
    return ConversationHandler.END

async def handle_user_lookup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the /lookup command"""
    user_id = update.effective_user.id
    if str(user_id) != BotConfig.ADMIN_USER_ID:
        await update.message.reply_text("⛔ You are not authorized to use admin commands.")
        return ConversationHandler.END
    
    await update.message.reply_text("🔍 Please enter the user ID or username to lookup:")
    context.user_data['admin_action'] = 'user_lookup'
    return USER_LOOKUP

async def handle_search_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle search input for users or chat history"""
    user_id = update.effective_user.id
    if str(user_id) != BotConfig.ADMIN_USER_ID:
        await update.message.reply_text("⛔ You are not authorized to use admin commands.")
        return ConversationHandler.END
    
    search_term = update.message.text.strip()
    admin_action = context.user_data.get('admin_action', '')
    
    try:
        if admin_action == 'search_user':
            # Search for user
            user_data = None
            
            # Try to search by user ID first
            if search_term.isdigit():
                user_data = await get_user_data(int(search_term))
            
            # If not found, search by username or UID
            if not user_data:
                all_users = await get_all_users()
                search_term_clean = search_term.replace('@', '').lower()
                
                for user in all_users:
                    username = user.get('username', '').lower()
                    uid = user.get('uid', '').lower()
                    
                    if (username == search_term_clean or 
                        uid == search_term.lower() or 
                        search_term.lower() in uid):
                        user_data = user
                        break
            
            if user_data:
                response_text = f"👤 **User Found:**\n\n"
                response_text += f"**Name:** {user_data.get('first_name', 'N/A')}\n"
                response_text += f"**Username:** @{user_data.get('username', 'N/A')}\n"
                response_text += f"**User ID:** `{user_data['user_id']}`\n"
                response_text += f"**UID:** {user_data.get('uid', 'N/A')}\n"
                response_text += f"**Status:** {user_data.get('registration_status', 'N/A')}\n"
                response_text += f"**Deposit Confirmed:** {'✅' if user_data.get('deposit_confirmed') else '❌'}\n"
                response_text += f"**Join Date:** {user_data.get('join_date', 'N/A')}\n"
                response_text += f"**Last Interaction:** {user_data.get('last_interaction', 'N/A')}"
                
                await update.message.reply_text(response_text, parse_mode='Markdown')
            else:
                await update.message.reply_text(f"❌ No user found matching: `{search_term}`")
        
        elif admin_action == 'chat_history':
            # Get chat history for user
            if not search_term.isdigit():
                await update.message.reply_text("❌ Please enter a valid User ID (numbers only).")
                return ConversationHandler.END
            
            target_user_id = int(search_term)
            
            # Check if user exists
            user_data = await get_user_data(target_user_id)
            if not user_data:
                await update.message.reply_text(f"❌ No user found with ID: `{target_user_id}`")
                return ConversationHandler.END
            
            # Get chat history
            chat_history = await db_manager.get_chat_history(target_user_id, limit=20)
            
            response_text = f"💬 **Chat History for {user_data.get('first_name', 'Unknown')}**\n"
            response_text += f"**User ID:** `{target_user_id}`\n\n"
            
            if not chat_history:
                response_text += "📭 No chat history found."
            else:
                response_text += f"📝 **Last {len(chat_history)} messages:**\n\n"
                
                for i, msg in enumerate(chat_history[:10], 1):  # Show max 10
                    msg_type = msg.get('message_type', 'unknown')
                    msg_text = msg.get('message_text', '')[:100]  # Truncate long messages
                    timestamp = msg.get('timestamp', 'N/A')
                    
                    response_text += f"{i}. **{msg_type}** - {timestamp}\n"
                    if msg_text:
                        response_text += f"   `{msg_text}...`\n\n"
                    else:
                        response_text += "\n"
                
                if len(chat_history) > 10:
                    response_text += f"... and {len(chat_history) - 10} more messages."
            
            await update.message.reply_text(response_text, parse_mode='Markdown')
        
        else:
            await update.message.reply_text("❌ Unknown admin action.")
    
    except Exception as e:
        logger.error(f"Error in handle_search_input: {e}")
        await update.message.reply_text("❌ Error occurred while processing your request.")
    
    return ConversationHandler.END

async def cancel_admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel admin action"""
    context.user_data.clear()
    await update.message.reply_text("❌ Action cancelled.")
    return ConversationHandler.END

async def admin_chat_history_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /chathistory command"""
    # Placeholder
    user_id = update.effective_user.id
    if str(user_id) == BotConfig.ADMIN_USER_ID:
        await update.message.reply_text("Chat history will be displayed here.")
    else:
        await update.message.reply_text("⛔ You are not authorized to use admin commands.")

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text messages for admin users"""
    user_id = update.effective_user.id
    
    # Check if user is admin
    if str(user_id) != BotConfig.ADMIN_USER_ID:
        return  # Let other handlers process this
    
    message_text = update.message.text.strip()
    
    # Admin-specific text commands
    if message_text.upper() == "ADMIN":
        await admin_command(update, context)
    elif message_text.upper() == "QUEUE":
        await admin_queue_command(update, context)
    elif message_text.upper() == "BROADCAST":
        await handle_broadcast(update, context)
    elif message_text.upper() == "SEARCH":
        await handle_user_lookup(update, context)
    elif message_text.upper() == "ACTIVITY":
        await admin_recent_activity_command(update, context)
    elif message_text.upper() == "STATS":
        await admin_auto_verify_stats_command(update, context)
    elif message_text.upper() == "HISTORY":
        await admin_chat_history_command(update, context)
    else:
        # Show admin dashboard for any other text
        await admin_command(update, context)

# Callback query handlers for admin buttons
async def admin_queue_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin queue callback"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if str(user_id) != BotConfig.ADMIN_USER_ID:
        await query.edit_message_text("⛔ You are not authorized to use admin commands.")
        return
    
    try:
        # Get pending verification requests
        pending_requests = await get_pending_verifications()
        
        if not pending_requests:
            response_text = "📋 **Verification Queue**\n\n✅ No pending verification requests."
        else:
            response_text = f"📋 **Verification Queue**\n\n📊 **{len(pending_requests)} pending requests:**\n\n"
            
            for i, request in enumerate(pending_requests[:10], 1):  # Show max 10
                username = request.get('username', 'N/A')
                first_name = request.get('first_name', 'N/A')
                uid = request.get('uid', 'N/A')
                created_at = request.get('created_at', 'N/A')
                
                response_text += f"{i}. **{first_name}** (@{username})\n"
                response_text += f"   UID: `{uid}`\n"
                response_text += f"   User ID: `{request['user_id']}`\n"
                response_text += f"   Submitted: {created_at}\n\n"
            
            if len(pending_requests) > 10:
                response_text += f"... and {len(pending_requests) - 10} more requests."
        
        # Add back button
        keyboard = [[InlineKeyboardButton("🔙 Back to Dashboard", callback_data="admin_dashboard")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(response_text, parse_mode='Markdown', reply_markup=reply_markup)
        
    except Exception as e:
        logger.error(f"Error in admin_queue_callback: {e}")
        await query.edit_message_text("❌ Error retrieving verification queue.")

async def admin_broadcast_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle admin broadcast callback"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if str(user_id) != BotConfig.ADMIN_USER_ID:
        await query.edit_message_text("⛔ You are not authorized to use admin commands.")
        return ConversationHandler.END
    
    response_text = "📢 **Broadcast Message**\n\n"
    response_text += "Please type the message you want to broadcast to all users.\n\n"
    response_text += "⚠️ **Note:** This will send the message to ALL registered users."
    
    # Set conversation state
    context.user_data['admin_action'] = 'broadcast'
    
    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="admin_dashboard")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Edit the existing message instead of creating a new one
    await query.edit_message_text(response_text, parse_mode='Markdown', reply_markup=reply_markup)
    return BROADCAST_MESSAGE

async def admin_search_user_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle admin search user callback"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if str(user_id) != BotConfig.ADMIN_USER_ID:
        await query.edit_message_text("⛔ You are not authorized to use admin commands.")
        return ConversationHandler.END
    
    search_text = (
        "🔍 **USER SEARCH**\n\n"
        "Search for users by:\n"
        "• User ID\n"
        "• Username\n"
        "• UID\n\n"
        "📝 **Instructions:**\n"
        "• Type the search term\n"
        "• Use exact matches for best results\n"
        "• Search is case-insensitive\n\n"
        "💡 **Examples:**\n"
        "• `123456789` (User ID)\n"
        "• `@username` (Username)\n"
        "• `UID12345` (Trading UID)\n\n"
        "Please enter your search term:"
    )
    
    keyboard = [
        [InlineKeyboardButton("❌ Cancel Search", callback_data="admin_dashboard")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Edit the existing message instead of creating a new one
    await query.edit_message_text(search_text, parse_mode='Markdown', reply_markup=reply_markup)
    
    # Set conversation state for search input
    context.user_data['admin_action'] = 'search_user'
    
    return SEARCH_USER

async def admin_recent_activity_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin recent activity callback"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if str(user_id) != BotConfig.ADMIN_USER_ID:
        await query.edit_message_text("⛔ You are not authorized to use admin commands.")
        return
    
    try:
        # Get recent user activity
        all_users = await get_all_users()
        
        # Filter users with recent activity (last 7 days)
        recent_cutoff = datetime.now() - timedelta(days=7)
        recent_users = []
        
        for user in all_users:
            try:
                if user.get('last_interaction'):
                    # Handle different datetime formats
                    last_interaction = user['last_interaction']
                    if isinstance(last_interaction, str):
                        # Try to parse string datetime
                        try:
                            last_interaction = datetime.fromisoformat(last_interaction.replace('Z', '+00:00'))
                        except:
                            continue
                    
                    if last_interaction >= recent_cutoff:
                        recent_users.append(user)
            except Exception as e:
                logger.error(f"Error processing user activity: {e}")
                continue
        
        response_text = "📊 **Recent Activity (Last 7 Days)**\n\n"
        
        if not recent_users:
            response_text += "📭 No recent user activity found."
        else:
            response_text += f"👥 **{len(recent_users)} active users:**\n\n"
            
            for i, user in enumerate(recent_users[:15], 1):  # Show max 15
                username = user.get('username', 'N/A')
                first_name = user.get('first_name', 'N/A')
                status = user.get('registration_status', 'unknown')
                
                response_text += f"{i}. **{first_name}** (@{username})\n"
                response_text += f"   Status: {status}\n"
                response_text += f"   User ID: `{user['user_id']}`\n\n"
            
            if len(recent_users) > 15:
                response_text += f"... and {len(recent_users) - 15} more active users."
        
        # Add statistics
        total_users = len(all_users)
        response_text += f"\n📈 **Statistics:**\n"
        response_text += f"• Total Users: {total_users}\n"
        response_text += f"• Active (7 days): {len(recent_users)}\n"
        response_text += f"• Activity Rate: {(len(recent_users)/total_users*100):.1f}%" if total_users > 0 else "• Activity Rate: 0%"
        
        keyboard = [[InlineKeyboardButton("🔙 Back to Dashboard", callback_data="admin_dashboard")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Edit the existing message instead of creating a new one
        await query.edit_message_text(response_text, parse_mode='Markdown', reply_markup=reply_markup)
        
    except Exception as e:
        logger.error(f"Error in admin_recent_activity_callback: {e}")
        await query.edit_message_text("❌ Error retrieving recent activity data.")

async def admin_auto_verify_stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin auto verify stats callback"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if str(user_id) != BotConfig.ADMIN_USER_ID:
        await query.edit_message_text("⛔ You are not authorized to use admin commands.")
        return
    
    try:
        # Get verification statistics
        if db_manager.db_type == 'postgresql':
            stats_query = '''
                SELECT 
                    COUNT(*) as total_requests,
                    COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending,
                    COUNT(CASE WHEN status = 'approved' THEN 1 END) as approved,
                    COUNT(CASE WHEN status = 'rejected' THEN 1 END) as rejected,
                    COUNT(CASE WHEN auto_verified = true THEN 1 END) as auto_verified
                FROM verification_requests
            '''
        else:
            stats_query = '''
                SELECT 
                    COUNT(*) as total_requests,
                    COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending,
                    COUNT(CASE WHEN status = 'approved' THEN 1 END) as approved,
                    COUNT(CASE WHEN status = 'rejected' THEN 1 END) as rejected,
                    COUNT(CASE WHEN auto_verified = 1 THEN 1 END) as auto_verified
                FROM verification_requests
            '''
        
        stats = await db_manager.execute(stats_query, fetch='one')
        
        response_text = "🤖 **Auto-Verify Statistics**\n\n"
        
        if stats:
            total = stats.get('total_requests', 0)
            pending = stats.get('pending', 0)
            approved = stats.get('approved', 0)
            rejected = stats.get('rejected', 0)
            auto_verified = stats.get('auto_verified', 0)
            
            response_text += f"📊 **Overall Statistics:**\n"
            response_text += f"• Total Requests: {total}\n"
            response_text += f"• Pending: {pending}\n"
            response_text += f"• Approved: {approved}\n"
            response_text += f"• Rejected: {rejected}\n"
            response_text += f"• Auto-Verified: {auto_verified}\n\n"
            
            if total > 0:
                response_text += f"📈 **Success Rates:**\n"
                response_text += f"• Approval Rate: {(approved/total*100):.1f}%\n"
                response_text += f"• Auto-Verify Rate: {(auto_verified/total*100):.1f}%\n"
                response_text += f"• Rejection Rate: {(rejected/total*100):.1f}%"
            else:
                response_text += "📭 No verification requests found."
        else:
            response_text += "📭 No verification data available."
        
        keyboard = [[InlineKeyboardButton("🔙 Back to Dashboard", callback_data="admin_dashboard")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Edit the existing message instead of creating a new one
        await query.edit_message_text(response_text, parse_mode='Markdown', reply_markup=reply_markup)
        
    except Exception as e:
        logger.error(f"Error in admin_auto_verify_stats_callback: {e}")
        await query.edit_message_text("❌ Error retrieving verification statistics.")

async def admin_chat_history_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle admin chat history callback"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if str(user_id) != BotConfig.ADMIN_USER_ID:
        await query.edit_message_text("⛔ You are not authorized to use admin commands.")
        return ConversationHandler.END
    
    response_text = "💬 **Chat History Lookup**\n\n"
    response_text += "📋 **Instructions:**\n"
    response_text += "• Enter a User ID to view their chat history\n"
    response_text += "• Shows last 20 messages and interactions\n"
    response_text += "• Includes timestamps and message types\n\n"
    response_text += "🔢 Please enter the User ID:"
    
    # Set conversation state
    context.user_data['admin_action'] = 'chat_history'
    
    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="admin_dashboard")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(response_text, parse_mode='Markdown', reply_markup=reply_markup)
    return USER_LOOKUP

# Dashboard callback
async def admin_dashboard_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Return to admin dashboard"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if str(user_id) != BotConfig.ADMIN_USER_ID:
        await query.edit_message_text("⛔ You are not authorized to use admin commands.")
        return
    
    # Clear any conversation state
    context.user_data.clear()
    
    # Show admin dashboard by editing the current message
    admin_text = "🔐 **OPTRIXTRADES Admin Dashboard**\n\n"
    admin_text += "Welcome to the admin control panel. Choose an action below:\n\n"
    admin_text += "📋 **Queue** - View pending verification requests\n"
    admin_text += "📢 **Broadcast** - Send message to all users\n"
    admin_text += "🔍 **Search User** - Find user by ID or username\n"
    admin_text += "📊 **Recent Activity** - View recent bot activity\n"
    admin_text += "🤖 **Auto-Verify Stats** - Check auto-verification statistics\n"
    admin_text += "💬 **Chat History** - View user chat logs\n\n"
    admin_text += "Use the buttons below or type commands directly."
    
    keyboard = [
        [InlineKeyboardButton("📋 Queue", callback_data="admin_queue"),
         InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")],
        [InlineKeyboardButton("🔍 Search User", callback_data="admin_search_user"),
         InlineKeyboardButton("📊 Recent Activity", callback_data="admin_recent_activity")],
        [InlineKeyboardButton("🤖 Auto-Verify Stats", callback_data="admin_auto_verify_stats"),
         InlineKeyboardButton("💬 Chat History", callback_data="admin_chat_history")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        admin_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )