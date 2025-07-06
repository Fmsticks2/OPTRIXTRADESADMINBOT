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

# Conversation states (must match setup.py)
BROADCAST_MESSAGE = 2
USER_LOOKUP = 3
SEARCH_USER = 4

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
        admin_text += "🔍 **Search User** - Find user by ID or username\n\n"
        admin_text += "Use the buttons below or type commands directly."
        
        keyboard = [
            [InlineKeyboardButton("📋 Queue", callback_data="admin_queue"),
             InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")],
            [InlineKeyboardButton("🔍 Search User", callback_data="admin_search_user")],
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
    logger.info(f"Admin {user_id} attempting to broadcast message: {broadcast_message[:50]}...")
    
    # Check if user is in broadcast conversation state
    if context.user_data.get('admin_action') != 'broadcast':
        logger.warning(f"User {user_id} sent broadcast message but not in broadcast state")
        return ConversationHandler.END
    
    try:
        # Get all users
        logger.info("Fetching all users from database...")
        all_users = await get_all_users()
        logger.info(f"Retrieved {len(all_users)} total users from database")
        
        # Debug: Log user statuses
        if all_users:
            status_counts = {}
            for user in all_users:
                status = user.get('status', 'unknown')
                status_counts[status] = status_counts.get(status, 0) + 1
            logger.info(f"User status breakdown: {status_counts}")
        
        # Filter users to only include those with verified or approved status, excluding the admin sender
        admin_user_id = int(BotConfig.ADMIN_USER_ID)
        verified_users = [user for user in all_users if user.get('status') in ('approved', 'verified') and user.get('user_id') != admin_user_id]
        logger.info(f"Found {len(verified_users)} verified/approved users for broadcast (excluding admin sender)")
        
        if not all_users:
            logger.warning("No users found in database")
            confirmation_text = "❌ No users found to broadcast to."
            keyboard = [[InlineKeyboardButton("🔙 Back to Dashboard", callback_data="admin_dashboard")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(confirmation_text, reply_markup=reply_markup)
            return ConversationHandler.END
        
        if not verified_users:
            logger.warning("No verified users found for broadcast")
            confirmation_text = f"❌ No verified users found to broadcast to.\n\nTotal users in database: {len(all_users)}\nVerified users: 0\n\n💡 Users need to have 'approved' or 'verified' status to receive broadcasts."
            keyboard = [[InlineKeyboardButton("🔙 Back to Dashboard", callback_data="admin_dashboard")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(confirmation_text, reply_markup=reply_markup)
            return ConversationHandler.END
        
        # Send confirmation with persistent message
        confirmation_text = (
            f"📢 **Broadcasting message to {len(verified_users)} users...**\n\n"
            f"**Message Preview:**\n{broadcast_message}\n\n"
            f"⏳ Please wait while the message is being sent..."
        )
        
        keyboard = [[InlineKeyboardButton("🔙 Back to Dashboard", callback_data="admin_dashboard")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        logger.info(f"Sending confirmation message to admin")
        confirmation_msg = await update.message.reply_text(
            confirmation_text, 
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        logger.info(f"Confirmation message sent, starting broadcast to {len(verified_users)} users")
        
        # Broadcast to all users
        success_count = 0
        failed_count = 0
        
        from security.security_manager import InputValidator
        
        for i, user in enumerate(verified_users, 1):
            user_id_to_send = user.get('user_id')
            logger.info(f"Processing user {i}/{len(verified_users)}: {user_id_to_send}")
            
            # Validate user ID
            if not InputValidator.validate_user_id(user_id_to_send):
                logger.warning(f"Skipping invalid user ID {user_id_to_send} in broadcast")
                failed_count += 1
                continue
            
            # Skip blocked user check for now as it's not implemented
            # if hasattr(SecurityManager, 'blocked_users') and user_id_to_send in SecurityManager.blocked_users:
            #     logger.info(f"Skipping blocked user {user_id_to_send} in broadcast")
            #     failed_count += 1
            #     continue
            
            try:
                await context.bot.send_message(
                    chat_id=user_id_to_send,
                    text=f"📢 **OPTRIXTRADES Announcement**\n\n{broadcast_message}",
                    parse_mode='Markdown'
                )
                success_count += 1
                logger.info(f"Broadcast sent successfully to user {user_id_to_send}")
                
                # Log the broadcast
                await log_interaction(user_id_to_send, 'broadcast_received', broadcast_message)
                
            except Exception as e:
                logger.error(f"Failed to send broadcast to user {user_id_to_send}: {e}")
                failed_count += 1
        
        logger.info(f"Broadcast complete. Success: {success_count}, Failed: {failed_count}")
        
        # Update the confirmation message with final report
        report_text = f"✅ **Broadcast Complete!**\n\n"
        report_text += f"📊 **Results:**\n"
        report_text += f"• Successfully sent: {success_count}\n"
        report_text += f"• Failed: {failed_count}\n"
        report_text += f"• Total users: {len(verified_users)}\n\n"
        report_text += f"**Original Message:**\n{broadcast_message}"
        
        keyboard = [[InlineKeyboardButton("🔙 Back to Dashboard", callback_data="admin_dashboard")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        logger.info("Updating confirmation message with final results")
        await confirmation_msg.edit_text(report_text, parse_mode='Markdown', reply_markup=reply_markup)
        logger.info("Final broadcast report sent to admin")
        
        # Log admin action
        await log_interaction(user_id, 'admin_broadcast', f"Sent to {success_count} users")
        
        # Clear conversation state
        context.user_data.clear()
        
    except Exception as e:
        logger.error(f"Error in handle_broadcast_message: {e}")
        error_text = "❌ Error sending broadcast message."
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
    
    await update.message.reply_text("🔍 Please enter the User ID to lookup:")
    context.user_data['admin_action'] = 'user_lookup'
    return USER_LOOKUP

async def handle_search_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle search input for user lookup"""
    user_id = update.effective_user.id
    if str(user_id) != BotConfig.ADMIN_USER_ID:
        await update.message.reply_text("⛔ You are not authorized to use admin commands.")
        return ConversationHandler.END
    
    search_term = update.message.text.strip()
    
    try:
        # Search for users based on the input
        if search_term.isdigit():
            # Search by user ID
            user_data = await get_user_data(int(search_term))
            if user_data:
                users = [user_data]
            else:
                users = []
        else:
            # Search by username or name
            search_term_clean = search_term.replace('@', '').lower()
            
            if db_manager.db_type == 'postgresql':
                search_query = '''
                    SELECT * FROM users 
                    WHERE LOWER(username) LIKE $1 OR LOWER(first_name) LIKE $1 OR uid LIKE $1
                    LIMIT 10
                '''
                users = await db_manager.execute(search_query, f'%{search_term_clean}%', fetch='all')
            else:
                search_query = '''
                    SELECT * FROM users 
                    WHERE LOWER(username) LIKE ? OR LOWER(first_name) LIKE ? OR uid LIKE ?
                    LIMIT 10
                '''
                users = await db_manager.execute(search_query, f'%{search_term_clean}%', f'%{search_term_clean}%', f'%{search_term_clean}%', fetch='all')
        
        if not users:
            response_text = f"❌ No users found matching '{search_term}'"
        else:
            response_text = f"🔍 **Search Results for '{search_term}'**\n\n"
            
            for i, user in enumerate(users, 1):
                username = user.get('username', 'N/A')
                first_name = user.get('first_name', 'N/A')
                status = user.get('registration_status', 'unknown')
                uid = user.get('uid', 'N/A')
                
                response_text += f"{i}. **{first_name}** (@{username})\n"
                response_text += f"   User ID: `{user['user_id']}`\n"
                response_text += f"   UID: `{uid}`\n"
                response_text += f"   Status: {status}\n\n"
        
        keyboard = [[InlineKeyboardButton("🔙 Back to Dashboard", callback_data="admin_dashboard")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(response_text, parse_mode='Markdown', reply_markup=reply_markup)
        
        # Clear conversation state
        context.user_data.clear()
        
    except Exception as e:
        logger.error(f"Error in handle_search_input: {e}")
        error_text = "❌ Error searching for users."
        keyboard = [[InlineKeyboardButton("🔙 Back to Dashboard", callback_data="admin_dashboard")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(error_text, reply_markup=reply_markup)
    
    return ConversationHandler.END

async def cancel_admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel admin action and return to dashboard"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if str(user_id) != BotConfig.ADMIN_USER_ID:
        await query.message.reply_text("⛔ You are not authorized to use admin commands.")
        return ConversationHandler.END
    
    # Clear conversation state
    context.user_data.clear()
    
    # Return to admin dashboard
    await admin_dashboard_callback(update, context)
    return ConversationHandler.END

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle text messages from admin in conversation states"""
    user_id = update.effective_user.id
    if str(user_id) != BotConfig.ADMIN_USER_ID:
        await update.message.reply_text("⛔ You are not authorized to use admin commands.")
        return ConversationHandler.END
    
    admin_action = context.user_data.get('admin_action')
    
    if admin_action == 'broadcast':
        return await handle_broadcast_message(update, context)
    elif admin_action == 'search_user' or admin_action == 'user_lookup':
        return await handle_search_input(update, context)
    else:
        # No active admin action, treat as regular message
        await update.message.reply_text("Please use the admin dashboard to perform actions.")
        return ConversationHandler.END

# Add missing callback handlers
async def cancel_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle cancel admin callback"""
    return await cancel_admin_action(update, context)

async def broadcast_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle broadcast message functionality"""
    try:
        user_id = update.effective_user.id
        broadcast_message = update.message.text
        
        # Get all users from database
        all_users = await get_all_users()  # Assuming this function exists
        
        if not all_users:
            keyboard = [[InlineKeyboardButton("🔙 Back to Dashboard", callback_data="admin_dashboard")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "❌ No users found in the database.",
                reply_markup=reply_markup
            )
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

async def handle_text_message_admin_standalone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle standalone admin text commands (not used in conversation handler)"""
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
        # Only respond to specific commands, don't show dashboard for every message
        pass

# Callback query handlers for admin buttons
async def admin_queue_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin queue callback"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if str(user_id) != BotConfig.ADMIN_USER_ID:
        await query.message.reply_text("⛔ You are not authorized to use admin commands.")
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
        
        await query.message.reply_text(response_text, parse_mode='Markdown', reply_markup=reply_markup)
        
    except Exception as e:
        logger.error(f"Error in admin_queue_callback: {e}")
        error_text = "❌ Error retrieving verification queue."
        keyboard = [[InlineKeyboardButton("🔙 Back to Dashboard", callback_data="admin_dashboard")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(error_text, reply_markup=reply_markup)

async def admin_broadcast_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle admin broadcast callback"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if str(user_id) != BotConfig.ADMIN_USER_ID:
        await query.message.reply_text("⛔ You are not authorized to use admin commands.")
        return ConversationHandler.END
    
    response_text = "📢 **Broadcast Message**\n\n"
    response_text += "Please type the message you want to broadcast to all users.\n\n"
    response_text += "⚠️ **Note:** This will send the message to ALL registered users."
    
    # Set conversation state
    context.user_data['admin_action'] = 'broadcast'
    
    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="admin_dashboard")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Send a new message instead of editing the existing one
    await query.message.reply_text(response_text, parse_mode='Markdown', reply_markup=reply_markup)
    return BROADCAST_MESSAGE

async def admin_search_user_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle admin search user callback"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if str(user_id) != BotConfig.ADMIN_USER_ID:
        await query.message.reply_text("⛔ You are not authorized to use admin commands.")
        return ConversationHandler.END
    
    response_text = "🔍 **Search User**\n\n"
    response_text += "📋 **Instructions:**\n"
    response_text += "• Enter a User ID (numbers only)\n"
    response_text += "• Enter a username (with or without @)\n"
    response_text += "• Enter a UID to search\n\n"
    response_text += "🔢 Please enter your search term:"
    
    # Set conversation state
    context.user_data['admin_action'] = 'search_user'
    
    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="admin_dashboard")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.reply_text(response_text, parse_mode='Markdown', reply_markup=reply_markup)
    return SEARCH_USER

async def admin_recent_activity_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle admin recent activity callback"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if str(user_id) != BotConfig.ADMIN_USER_ID:
        await query.message.reply_text("⛔ You are not authorized to use admin commands.")
        return ConversationHandler.END
    
    try:
        # Get recent user activity from interactions table
        recent_cutoff = datetime.now() - timedelta(days=7)
        
        if db_manager.db_type == 'postgresql':
            # Get users with recent interactions
            recent_query = '''
                SELECT DISTINCT u.user_id, u.username, u.first_name, u.registration_status,
                       MAX(ui.created_at) as last_activity
                FROM users u
                LEFT JOIN user_interactions ui ON u.user_id = ui.user_id
                WHERE ui.created_at >= $1 OR u.last_interaction >= $1
                GROUP BY u.user_id, u.username, u.first_name, u.registration_status
                ORDER BY last_activity DESC
            '''
            recent_users = await db_manager.execute(recent_query, recent_cutoff, fetch='all')
            
            # Get total user count
            total_query = 'SELECT COUNT(*) as total FROM users'
            total_result = await db_manager.execute(total_query, fetch='one')
            total_users = total_result['total'] if total_result else 0
        else:
            # SQLite version
            recent_query = '''
                SELECT DISTINCT u.user_id, u.username, u.first_name, u.registration_status,
                       MAX(ui.created_at) as last_activity
                FROM users u
                LEFT JOIN user_interactions ui ON u.user_id = ui.user_id
                WHERE ui.created_at >= ? OR u.last_interaction >= ?
                GROUP BY u.user_id, u.username, u.first_name, u.registration_status
                ORDER BY last_activity DESC
            '''
            recent_users = await db_manager.execute(recent_query, recent_cutoff, recent_cutoff, fetch='all')
            
            # Get total user count
            total_query = 'SELECT COUNT(*) as total FROM users'
            total_result = await db_manager.execute(total_query, fetch='one')
            total_users = total_result['total'] if total_result else 0
        
        response_text = "📊 **Recent Activity (Last 7 Days)**\n\n"
        
        if not recent_users:
            response_text += "📭 No recent user activity found.\n\n"
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
                response_text += f"... and {len(recent_users) - 15} more active users.\n\n"
        
        # Add enhanced statistics
        response_text += f"📈 **Statistics:**\n"
        response_text += f"• Total Users: {total_users}\n"
        response_text += f"• Active (7 days): {len(recent_users)}\n"
        response_text += f"• Activity Rate: {(len(recent_users)/total_users*100):.1f}%" if total_users > 0 else "• Activity Rate: 0%"
        
        keyboard = [[InlineKeyboardButton("🔙 Back to Dashboard", callback_data="admin_dashboard")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Send a new message instead of editing the existing one
        await query.message.reply_text(response_text, parse_mode='Markdown', reply_markup=reply_markup)
        
    except Exception as e:
        logger.error(f"Error in admin_recent_activity_callback: {e}")
        error_text = "❌ Error retrieving recent activity data."
        keyboard = [[InlineKeyboardButton("🔙 Back to Dashboard", callback_data="admin_dashboard")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(error_text, reply_markup=reply_markup)
        return ConversationHandler.END
    
    return ConversationHandler.END

async def admin_auto_verify_stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle admin auto verify stats callback"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if str(user_id) != BotConfig.ADMIN_USER_ID:
        await query.message.reply_text("⛔ You are not authorized to use admin commands.")
        return ConversationHandler.END
    
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
        
        # Send a new message instead of editing the existing one
        await query.message.reply_text(response_text, parse_mode='Markdown', reply_markup=reply_markup)
        
    except Exception as e:
        logger.error(f"Error in admin_auto_verify_stats_callback: {e}")
        error_text = "❌ Error retrieving verification statistics."
        keyboard = [[InlineKeyboardButton("🔙 Back to Dashboard", callback_data="admin_dashboard")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(error_text, reply_markup=reply_markup)
        return ConversationHandler.END
    
    return ConversationHandler.END

async def admin_chat_history_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle admin chat history callback"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if str(user_id) != BotConfig.ADMIN_USER_ID:
        await query.message.reply_text("⛔ You are not authorized to use admin commands.")
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
    
    await query.message.reply_text(response_text, parse_mode='Markdown', reply_markup=reply_markup)
    return USER_LOOKUP

# Dashboard callback
async def admin_dashboard_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Return to admin dashboard"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if str(user_id) != BotConfig.ADMIN_USER_ID:
        await query.message.reply_text("⛔ You are not authorized to use admin commands.")
        return ConversationHandler.END
    
    # Clear any conversation state
    context.user_data.clear()
    
    # Show admin dashboard by editing the current message
    admin_text = "🔐 **OPTRIXTRADES Admin Dashboard**\n\n"
    admin_text += "Welcome to the admin control panel. Choose an action below:\n\n"
    admin_text += "📋 **Queue** - View pending verification requests\n"
    admin_text += "📢 **Broadcast** - Send message to all users\n"
    admin_text += "🔍 **Search User** - Find user by ID or username\n\n"
    admin_text += "Use the buttons below or type commands directly."
    
    keyboard = [
        [InlineKeyboardButton("📋 Queue", callback_data="admin_queue"),
         InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")],
        [InlineKeyboardButton("🔍 Search User", callback_data="admin_search_user")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.reply_text(
        admin_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    return ConversationHandler.END