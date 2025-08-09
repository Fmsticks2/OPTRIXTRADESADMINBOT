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
from telegram_bot.utils.batch_follow_up import BatchFollowUpManager, start_batch_follow_ups, get_batch_follow_up_stats

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
        admin_text += "🔍 **Search User** - Find user by ID or username\n"
        admin_text += "👥 **All Users** - View all registered users\n"
        admin_text += "📊 **User Activity** - View recent user interactions\n\n"
        admin_text += "Use the buttons below or type commands directly."
        
        keyboard = [
            [InlineKeyboardButton("📋 Queue", callback_data="admin_queue"),
             InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")],
            [InlineKeyboardButton("🔍 Search User", callback_data="admin_search_user"),
             InlineKeyboardButton("👥 All Users", callback_data="admin_all_users")],
            [InlineKeyboardButton("📊 User Activity", callback_data="admin_user_activity")],
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

async def admin_batch_followup_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /batchfollowup command"""
    user_id = update.effective_user.id
    if str(user_id) != BotConfig.ADMIN_USER_ID:
        await update.message.reply_text("⛔ You are not authorized to use admin commands.")
        return
    
    await admin_batch_followup_callback(update, context)

async def handle_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the /broadcast command"""
    user_id = update.effective_user.id
    if str(user_id) != BotConfig.ADMIN_USER_ID:
        await update.message.reply_text("⛔ You are not authorized to use admin commands.")
        return ConversationHandler.END

async def admin_batch_followup_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle batch follow-up management"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if str(user_id) != BotConfig.ADMIN_USER_ID:
        await query.message.reply_text("⛔ You are not authorized to use admin commands.")
        return ConversationHandler.END
    
    try:
        # Get bot instance from application
        bot_instance = context.application.bot_data.get('bot_instance')
        if not bot_instance:
            await query.message.reply_text("❌ Bot instance not available. Please restart the bot.")
            return ConversationHandler.END
        
        # Create batch follow-up manager
        batch_manager = BatchFollowUpManager(context.bot, db_manager)
        
        # Get current statistics
        stats = await batch_manager.get_follow_up_stats()
        unverified_users = await batch_manager.get_unverified_users()
        
        # Create response message
        response_text = "🔄 **Batch Follow-Up Management**\n\n"
        
        # Current statistics
        response_text += "📊 **Current Statistics:**\n"
        response_text += f"• Users with active follow-ups: {stats.get('total_users_with_follow_ups', 0)}\n"
        response_text += f"• Total scheduled tasks: {stats.get('total_scheduled_tasks', 0)}\n"
        response_text += f"• Scheduler status: {stats.get('scheduler_status', 'unknown')}\n\n"
        
        # Unverified users
        response_text += "👥 **Unverified Users:**\n"
        response_text += f"• Total unverified users: {len(unverified_users)}\n"
        
        if len(unverified_users) > 0:
            response_text += f"• Users without follow-ups: {len(unverified_users) - stats.get('total_users_with_follow_ups', 0)}\n\n"
            
            # Show sample of unverified users
            response_text += "📋 **Sample Unverified Users:**\n"
            for i, user in enumerate(unverified_users[:5]):
                status = user.get('verification_status', 'None')
                name = user.get('first_name', 'Unknown')
                response_text += f"• {name} (ID: {user['user_id']}) - Status: {status}\n"
            
            if len(unverified_users) > 5:
                response_text += f"... and {len(unverified_users) - 5} more\n"
        else:
            response_text += "• All users are verified! 🎉\n"
        
        # Create action buttons
        keyboard = []
        
        if len(unverified_users) > stats.get('total_users_with_follow_ups', 0):
            keyboard.append([
                InlineKeyboardButton("🚀 Start Follow-ups (All)", callback_data="batch_followup_start_all"),
                InlineKeyboardButton("🎯 Start Follow-ups (10)", callback_data="batch_followup_start_10")
            ])
        
        if stats.get('total_users_with_follow_ups', 0) > 0:
            keyboard.append([
                InlineKeyboardButton("📊 Refresh Stats", callback_data="batch_followup_stats"),
                InlineKeyboardButton("🛑 Cancel All", callback_data="batch_followup_cancel_all")
            ])
        else:
            keyboard.append([
                InlineKeyboardButton("📊 Refresh Stats", callback_data="batch_followup_stats")
            ])
        
        keyboard.append([InlineKeyboardButton("🔙 Back to Dashboard", callback_data="admin_dashboard")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.reply_text(
            response_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Error in batch follow-up callback: {e}")
        await query.message.reply_text(f"❌ Error: {str(e)}")
    
    return ConversationHandler.END

async def batch_followup_start_all_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start follow-ups for all unverified users"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if str(user_id) != BotConfig.ADMIN_USER_ID:
        await query.message.reply_text("⛔ You are not authorized to use admin commands.")
        return ConversationHandler.END
    
    try:
        await query.message.reply_text("🔄 Starting follow-ups for all unverified users...")
        
        # Start batch follow-ups
        result = await start_batch_follow_ups(db_manager, context.bot)
        
        response_text = "✅ **Batch Follow-Up Results**\n\n"
        response_text += f"• Users processed: {result.get('processed', 0)}\n"
        response_text += f"• Follow-ups scheduled: {result.get('scheduled', 0)}\n"
        response_text += f"• Already scheduled: {result.get('already_scheduled', 0)}\n"
        response_text += f"• Failed: {result.get('failed', 0)}\n\n"
        
        if result.get('scheduled', 0) > 0:
            response_text += "🎯 Follow-up sequences have been started for unverified users.\n"
            response_text += "Messages will be sent at 7.5-8 hour intervals."
        
        keyboard = [[InlineKeyboardButton("🔙 Back to Batch Management", callback_data="admin_batch_followup")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.reply_text(
            response_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Error starting batch follow-ups: {e}")
        await query.message.reply_text(f"❌ Error starting follow-ups: {str(e)}")
    
    return ConversationHandler.END

async def batch_followup_start_10_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start follow-ups for 10 unverified users"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if str(user_id) != BotConfig.ADMIN_USER_ID:
        await query.message.reply_text("⛔ You are not authorized to use admin commands.")
        return ConversationHandler.END
    
    try:
        await query.message.reply_text("🔄 Starting follow-ups for 10 unverified users...")
        
        # Start batch follow-ups with limit
        result = await start_batch_follow_ups(db_manager, context.bot, limit=10)
        
        response_text = "✅ **Batch Follow-Up Results (Limited)**\n\n"
        response_text += f"• Users processed: {result.get('processed', 0)}\n"
        response_text += f"• Follow-ups scheduled: {result.get('scheduled', 0)}\n"
        response_text += f"• Already scheduled: {result.get('already_scheduled', 0)}\n"
        response_text += f"• Failed: {result.get('failed', 0)}\n\n"
        
        if result.get('scheduled', 0) > 0:
            response_text += "🎯 Follow-up sequences have been started for 10 unverified users.\n"
            response_text += "Messages will be sent at 7.5-8 hour intervals."
        
        keyboard = [[InlineKeyboardButton("🔙 Back to Batch Management", callback_data="admin_batch_followup")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.reply_text(
            response_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Error starting limited batch follow-ups: {e}")
        await query.message.reply_text(f"❌ Error starting follow-ups: {str(e)}")
    
    return ConversationHandler.END

async def batch_followup_cancel_all_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel all scheduled follow-ups"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if str(user_id) != BotConfig.ADMIN_USER_ID:
        await query.message.reply_text("⛔ You are not authorized to use admin commands.")
        return ConversationHandler.END
    
    try:
        await query.message.reply_text("🛑 Cancelling all scheduled follow-ups...")
        
        # Cancel all follow-ups
        batch_manager = BatchFollowUpManager(context.bot, db_manager)
        cancelled_count = await batch_manager.cancel_all_follow_ups()
        
        response_text = "✅ **Follow-Up Cancellation Complete**\n\n"
        response_text += f"• Cancelled follow-ups for {cancelled_count} users\n\n"
        
        if cancelled_count > 0:
            response_text += "🛑 All scheduled follow-up messages have been cancelled."
        else:
            response_text += "ℹ️ No follow-ups were scheduled to cancel."
        
        keyboard = [[InlineKeyboardButton("🔙 Back to Batch Management", callback_data="admin_batch_followup")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.reply_text(
            response_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Error cancelling follow-ups: {e}")
        await query.message.reply_text(f"❌ Error cancelling follow-ups: {str(e)}")
    
    return ConversationHandler.END

async def batch_followup_stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Refresh batch follow-up statistics"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if str(user_id) != BotConfig.ADMIN_USER_ID:
        await query.message.reply_text("⛔ You are not authorized to use admin commands.")
        return ConversationHandler.END
    
    # Redirect to main batch follow-up callback to refresh stats
    return await admin_batch_followup_callback(update, context)
    
    broadcast_text = (
        "📢 **Broadcast Message**\n\n"
        "You can send either:\n"
        "• **Text message** - Just type your message\n"
        "• **Image with caption** - Send a photo with text caption\n\n"
        "The message will be sent to all registered users."
    )
    
    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="admin_dashboard")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(broadcast_text, parse_mode='Markdown', reply_markup=reply_markup)
    context.user_data['admin_action'] = 'broadcast'
    return BROADCAST_MESSAGE

async def handle_broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle broadcast message input (text or photo with caption)"""
    user_id = update.effective_user.id
    if str(user_id) != BotConfig.ADMIN_USER_ID:
        await update.message.reply_text("⛔ You are not authorized to use admin commands.")
        return ConversationHandler.END
    
    # Check if user is in broadcast conversation state
    if context.user_data.get('admin_action') != 'broadcast':
        logger.warning(f"User {user_id} sent broadcast message but not in broadcast state")
        return ConversationHandler.END
    
    # Determine message type and content
    message_type = 'text'
    broadcast_message = None
    photo_file_id = None
    
    if update.message.photo:
        message_type = 'photo'
        photo_file_id = update.message.photo[-1].file_id  # Get highest resolution
        broadcast_message = update.message.caption or ""  # Caption can be empty
        logger.info(f"Admin {user_id} attempting to broadcast photo with caption: {broadcast_message[:50] if broadcast_message else 'No caption'}...")
    elif update.message.text:
        message_type = 'text'
        broadcast_message = update.message.text
        logger.info(f"Admin {user_id} attempting to broadcast text message: {broadcast_message[:50]}...")
    else:
        await update.message.reply_text("❌ Please send either a text message or a photo with caption.")
        return BROADCAST_MESSAGE
    
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
        
        # Filter users to exclude only the admin sender (send to ALL users regardless of verification status)
        admin_user_id = int(BotConfig.ADMIN_USER_ID)
        target_users = [user for user in all_users if user.get('user_id') != admin_user_id]
        logger.info(f"Found {len(target_users)} users for broadcast (excluding admin sender, including all verification statuses)")
        
        if not all_users:
            logger.warning("No users found in database")
            confirmation_text = "❌ No users found to broadcast to."
            keyboard = [[InlineKeyboardButton("🔙 Back to Dashboard", callback_data="admin_dashboard")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(confirmation_text, reply_markup=reply_markup)
            return ConversationHandler.END
        
        if not target_users:
            logger.warning("No users found for broadcast (excluding admin)")
            confirmation_text = f"❌ No users found to broadcast to.\n\nTotal users in database: {len(all_users)}\nTarget users: 0\n\n💡 Only the admin user was found in the database."
            keyboard = [[InlineKeyboardButton("🔙 Back to Dashboard", callback_data="admin_dashboard")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(confirmation_text, reply_markup=reply_markup)
            return ConversationHandler.END
        
        # Send confirmation with persistent message
        if message_type == 'photo':
            confirmation_text = (
                f"📢 **Broadcasting photo to {len(target_users)} users...**\n\n"
                f"**Caption Preview:**\n{broadcast_message if broadcast_message else 'No caption'}\n\n"
                f"⏳ Please wait while the photo is being sent..."
            )
        else:
            confirmation_text = (
                f"📢 **Broadcasting message to {len(target_users)} users...**\n\n"
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
        logger.info(f"Confirmation message sent, starting broadcast to {len(target_users)} users")
        
        # Broadcast to all users
        success_count = 0
        failed_count = 0
        
        from security.security_manager import InputValidator
        
        for i, user in enumerate(target_users, 1):
            user_id_to_send = user.get('user_id')
            logger.info(f"Processing user {i}/{len(target_users)}: {user_id_to_send}")
            
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
                if message_type == 'photo':
                    await context.bot.send_photo(
                        chat_id=user_id_to_send,
                        photo=photo_file_id,
                        caption=broadcast_message if broadcast_message else None,
                        parse_mode='Markdown' if broadcast_message else None
                    )
                else:
                    await context.bot.send_message(
                        chat_id=user_id_to_send,
                        text=broadcast_message,
                        parse_mode='Markdown'
                    )
                success_count += 1
                logger.info(f"Broadcast sent successfully to user {user_id_to_send}")
                
                # Log the broadcast
                log_message = f"{message_type}: {broadcast_message if broadcast_message else 'Photo without caption'}"
                await log_interaction(user_id_to_send, 'broadcast_received', log_message)
                
            except Exception as e:
                logger.error(f"Failed to send broadcast to user {user_id_to_send}: {e}")
                failed_count += 1
        
        logger.info(f"Broadcast complete. Success: {success_count}, Failed: {failed_count}")
        
        # Update the confirmation message with final report
        report_text = f"✅ **Broadcast Complete!**\n\n"
        report_text += f"📊 **Results:**\n"
        report_text += f"• Successfully sent: {success_count}\n"
        report_text += f"• Failed: {failed_count}\n"
        report_text += f"• Total users: {len(target_users)}\n\n"
        
        if message_type == 'photo':
            report_text += f"**Original Photo Caption:**\n{broadcast_message if broadcast_message else 'No caption'}"
        else:
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
        await query.message.reply_text(response_text, reply_markup=reply_markup)
        
    except Exception as e:
        logger.error(f"Error in admin_recent_activity_callback: {e}")
        error_text = "❌ Error retrieving recent activity data."
        keyboard = [[InlineKeyboardButton("🔙 Back to Dashboard", callback_data="admin_dashboard")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(error_text, reply_markup=reply_markup)
        return ConversationHandler.END
    
    return ConversationHandler.END

async def admin_user_activity_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle admin user activity callback"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if str(user_id) != BotConfig.ADMIN_USER_ID:
        await query.message.reply_text("⛔ You are not authorized to use admin commands.")
        return ConversationHandler.END
    
    try:
        # Import the function to get recent activity
        from telegram_bot.utils.database_utils import get_recent_activity
        
        # Get recent user interactions (last 50 interactions)
        recent_interactions = await get_recent_activity(limit=50)
        
        response_text = "📊 **Recent User Activity**\n\n"
        
        if recent_interactions:
            response_text += f"📈 **Last {len(recent_interactions)} Interactions:**\n\n"
            
            for i, interaction in enumerate(recent_interactions[:20], 1):  # Show only first 20
                user_id_int = interaction.get('user_id', 'Unknown')
                action = interaction.get('action', 'Unknown')
                details = interaction.get('details', '')
                timestamp = interaction.get('timestamp', 'Unknown')
                
                # Format timestamp if it's a datetime object
                if hasattr(timestamp, 'strftime'):
                    time_str = timestamp.strftime('%Y-%m-%d %H:%M')
                else:
                    time_str = str(timestamp)
                
                response_text += f"{i}. **User {user_id_int}**\n"
                response_text += f"   Action: {action}\n"
                if details and len(details) > 50:
                    response_text += f"   Details: {details[:50]}...\n"
                elif details:
                    response_text += f"   Details: {details}\n"
                response_text += f"   Time: {time_str}\n\n"
            
            if len(recent_interactions) > 20:
                response_text += f"... and {len(recent_interactions) - 20} more interactions.\n\n"
            
            # Add summary statistics
            action_counts = {}
            for interaction in recent_interactions:
                action = interaction.get('action', 'Unknown')
                action_counts[action] = action_counts.get(action, 0) + 1
            
            response_text += "📋 **Action Summary:**\n"
            for action, count in sorted(action_counts.items(), key=lambda x: x[1], reverse=True):
                response_text += f"• {action}: {count}\n"
        else:
            response_text += "📭 No recent user interactions found."
        
        keyboard = [[InlineKeyboardButton("🔙 Back to Dashboard", callback_data="admin_dashboard")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.reply_text(response_text, parse_mode='Markdown', reply_markup=reply_markup)
        
    except Exception as e:
        logger.error(f"Error in admin_user_activity_callback: {e}")
        error_text = "❌ Error retrieving user activity data."
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
        await query.message.reply_text(response_text, reply_markup=reply_markup)
        
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

async def admin_all_users_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle admin all users callback"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if str(user_id) != BotConfig.ADMIN_USER_ID:
        await query.message.reply_text("⛔ You are not authorized to use admin commands.")
        return ConversationHandler.END
    
    try:
        # Get all users from database
        all_users = await get_all_users()
        
        if not all_users:
            response_text = "👥 All Users List\n\n"
            response_text += "📭 No users found in the database."
        else:
            response_text = f"👥 All Users List ({len(all_users)} total)\n\n"
            
            # Sort users by registration date (newest first)
            sorted_users = sorted(all_users, key=lambda x: x.get('created_at', ''), reverse=True)
            
            # Show first 20 users to avoid message length limits
            display_users = sorted_users[:20]
            
            for i, user in enumerate(display_users, 1):
                user_id_display = user.get('user_id', 'N/A')
                username = user.get('username', 'N/A')
                first_name = user.get('first_name', 'N/A')
                status = user.get('registration_status', 'unknown')
                uid = user.get('uid', 'N/A')
                
                # Format username display
                username_display = f"@{username}" if username and username != 'N/A' else 'No username'
                
                response_text += f"{i}. {first_name}\n"
                response_text += f"   🆔 ID: {user_id_display}\n"
                response_text += f"   👤 Username: {username_display}\n"
                response_text += f"   📊 Status: {status}\n"
                response_text += f"   🔢 UID: {uid}\n\n"
            
            if len(all_users) > 20:
                response_text += f"... and {len(all_users) - 20} more users.\n\n"
            
            # Add summary statistics
            registered_count = sum(1 for user in all_users if user.get('registration_status') not in ['not_started', 'unknown'])
            with_uid_count = sum(1 for user in all_users if user.get('uid') and user.get('uid') != 'N/A')
            
            response_text += f"📈 Summary:\n"
            response_text += f"• Total Users: {len(all_users)}\n"
            response_text += f"• Registered: {registered_count}\n"
            response_text += f"• With UID: {with_uid_count}\n"
            response_text += f"• Not Started: {len(all_users) - registered_count}"
        
        keyboard = [[InlineKeyboardButton("🔙 Back to Dashboard", callback_data="admin_dashboard")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Send a new message instead of editing the existing one
        await query.message.reply_text(response_text, reply_markup=reply_markup)
        
    except Exception as e:
        logger.error(f"Error in admin_all_users_callback: {e}")
        error_text = "❌ Error retrieving users list."
        keyboard = [[InlineKeyboardButton("🔙 Back to Dashboard", callback_data="admin_dashboard")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(error_text, reply_markup=reply_markup)
        return ConversationHandler.END
    
    return ConversationHandler.END

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
    admin_text += "🔍 **Search User** - Find user by ID or username\n"
    admin_text += "👥 **All Users** - View all registered users\n"
    admin_text += "📨 **Batch Follow-up** - Manage follow-up messages for unverified users\n\n"
    admin_text += "Use the buttons below or type commands directly."
    
    keyboard = [
        [InlineKeyboardButton("📋 Queue", callback_data="admin_queue"),
         InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")],
        [InlineKeyboardButton("🔍 Search User", callback_data="admin_search_user"),
         InlineKeyboardButton("👥 All Users", callback_data="admin_all_users")],
        [InlineKeyboardButton("📨 Batch Follow-up", callback_data="admin_batch_followup")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.reply_text(
        admin_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    return ConversationHandler.END