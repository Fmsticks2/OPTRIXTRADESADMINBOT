"""Handler for chat join requests"""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import BotConfig
from database.connection import log_interaction

logger = logging.getLogger(__name__)

async def handle_chat_join_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle chat join requests:
    1. Send a welcome message with a deep link to the user (if enabled)
    2. Approve their join request (if auto-approve is enabled)
    3. Send a confirmation message
    """
    user = update.chat_join_request.from_user
    user_id = user.id
    chat_id = update.chat_join_request.chat.id
    username = user.username or ""
    first_name = user.first_name or "User"

    logger.info(f"Received chat join request from user {user_id} ({first_name}) for chat {chat_id}")

    # Log the interaction
    await log_interaction(user_id, "join_request", {
        "user_id": user_id,
        "username": username,
        "first_name": first_name,
        "chat_id": chat_id
    })

    # Check if welcome message is enabled
    if BotConfig.JOIN_REQUEST_WELCOME_MESSAGE_ENABLED:
        # Inline button (deep link to start command)
        keyboard = [
            [
                InlineKeyboardButton(
                    "🚀 Start", url=f"https://t.me/{context.bot.username}?start=1"
                )
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Message text (MarkdownV2, with blockquote formatting)
        welcome_message = (
            "*Welcome to OPTRIXTRADES* 🚀\n\n"
            "You now have two powerful ways to trade profitably:\n\n"
            "1️⃣ Manually copy our premium signals and trade with confidence\\.\n"
            "OR \n"
            "2️⃣ Activate Optrix AI, let it trade automatically for you, 100% hands\\-free\\. No experience required\\.\n\n"
            "> 👉 Tap \"Start\" to unlock FREE access today\\!"
        )

        # Send welcome message to the user
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=welcome_message,
                parse_mode="MarkdownV2",
                reply_markup=reply_markup,
            )
            logger.info(f"Sent welcome message to user {user_id}")
        except Exception as e:
            logger.error(f"Failed to send welcome message to user {user_id}: {e}")

    # Check if auto-approve is enabled
    if BotConfig.ENABLE_AUTO_APPROVE_JOIN_REQUESTS:
        # Approve the join request
        try:
            await context.bot.approve_chat_join_request(chat_id=chat_id, user_id=user_id)
            logger.info(f"Approved join request for user {user_id} in chat {chat_id}")

            # Send confirmation message
            try:
                confirmation_message = (
                    "✅ Channel joined successfully\n\n"
                    "> Your request to join *OPTRIXTRADES* has been approved\\!"
                )
                await context.bot.send_message(
                    chat_id=user_id, text=confirmation_message, parse_mode="MarkdownV2"
                )
                logger.info(f"Sent confirmation message to user {user_id}")
            except Exception as e:
                logger.error(f"Failed to send confirmation message to user {user_id}: {e}")
        except Exception as e:
            logger.error(f"Failed to approve join request for user {user_id} in chat {chat_id}: {e}")
    else:
        logger.info(f"Auto-approve disabled, join request for user {user_id} requires manual approval")

    # Notify admin about the join request
    try:
        admin_user_id = BotConfig.ADMIN_USER_ID
        if admin_user_id:
            auto_approved = "Yes" if BotConfig.ENABLE_AUTO_APPROVE_JOIN_REQUESTS else "No (manual approval required)"
            admin_notification = (
                f"📣 New channel join request:\n"
                f"User: {first_name} (ID: {user_id})\n"
                f"Username: @{username if username else 'None'}\n"
                f"Chat: {chat_id}\n"
                f"Auto-approved: {auto_approved}"
            )
            await context.bot.send_message(chat_id=admin_user_id, text=admin_notification)
    except Exception as e:
        logger.error(f"Failed to notify admin about join request: {e}")
