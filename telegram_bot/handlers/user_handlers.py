"""User command handlers for OPTRIXTRADES Telegram Bot"""

import logging
from typing import Dict, Any, Optional, List

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from config import BotConfig
from database.connection import log_interaction, get_user_data
from telegram_bot.utils.channel_manager import add_user_to_channel

logger = logging.getLogger(__name__)

# Placeholder functions that will need to be implemented with actual logic
# These would be extracted from the original telegram_bot.py file

# Removed duplicate get_started_callback function - using the one at line 526 instead


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the /start command"""
    try:
        user = update.effective_user
        user_id = user.id
        username = user.username or ""
        first_name = user.first_name or "User"

        # Check if user came from landing page with start parameter
        start_param = None
        if context.args:
            start_param = context.args[0] if context.args else None

        # Enhanced logging for webhook debugging
        logger.info(
            f"START_COMMAND: Processing /start for user {user_id} ({username}) - {first_name}"
        )
        logger.info(f"START_COMMAND: context.args = {context.args}")
        logger.info(f"START_COMMAND: start_param = {start_param}")

        # Check database connection status before attempting user registration
        from database.connection import create_user, db_manager

        try:
            # Verify database connection
            if not db_manager.pool:
                logger.error(
                    f"START_COMMAND: Database pool not initialized for user {user_id}"
                )
                await update.message.reply_text(
                    "⚠️ Service temporarily unavailable. Please try again in a moment."
                )
                return

            logger.info(
                f"START_COMMAND: Database connection verified for user {user_id}"
            )

            # Attempt user registration with detailed logging
            logger.info(
                f"START_COMMAND: Attempting to register/update user {user_id} in database"
            )
            result = await create_user(user_id, username, first_name)

            if result:
                logger.info(
                    f"START_COMMAND: ✅ User {user_id} ({username}) successfully registered/updated in database"
                )
            else:
                logger.warning(
                    f"START_COMMAND: ⚠️ User registration returned False for user {user_id}"
                )

        except Exception as e:
            logger.error(
                f"START_COMMAND: ❌ Failed to register user {user_id} in database: {type(e).__name__}: {e}"
            )
            logger.error(
                f"START_COMMAND: Database error details - Pool status: {bool(db_manager.pool)}, DB type: {getattr(db_manager, 'db_type', 'unknown')}"
            )
            # Continue execution even if user registration fails

        # Log user interaction with error handling
        try:
            await log_interaction(
                user_id, "start_command", f"User started bot with param: {start_param}"
            )
            logger.info(f"START_COMMAND: User interaction logged for {user_id}")
        except Exception as e:
            logger.error(
                f"START_COMMAND: Failed to log interaction for user {user_id}: {e}"
            )

        # Check if user is admin first
        if str(user_id) == BotConfig.ADMIN_USER_ID:
            logger.info(
                f"START_COMMAND: Redirecting admin user {user_id} to admin dashboard"
            )
            # Show admin dashboard for admin users
            from telegram_bot.handlers.admin_handlers import admin_command

            return await admin_command(update, context)
        else:
            # Automatically add user to premium channel
            try:
                channel_added = await add_user_to_channel(context.bot, user_id)
                if channel_added:
                    logger.info(
                        f"User {user_id} automatically added to premium channel"
                    )
                else:
                    logger.warning(
                        f"Failed to automatically add user {user_id} to premium channel"
                    )
            except Exception as e:
                logger.error(f"Error adding user {user_id} to channel: {e}")

            # Get user data to check verification status
            from database.connection import get_user_data

            user_data = await get_user_data(user_id)

            # Check if user is a new channel member and send welcome message
            try:
                from telegram_bot.utils.channel_monitor import get_channel_monitor

                monitor = get_channel_monitor()
                if monitor and start_param == "welcome":
                    success = await monitor.send_channel_join_welcome(user_id)
                    if success:
                        logger.info(
                            f"Enhanced welcome message sent to new channel member {user_id}"
                        )
                        return
                    else:
                        logger.warning(
                            f"Failed to send enhanced welcome message to user {user_id}, falling back to regular flow"
                        )
            except Exception as e:
                logger.error(f"Failed to send welcome message to user {user_id}: {e}")

            # Handle different start scenarios
            if start_param == "welcome":
                logger.info(
                    f"START_COMMAND: New user {user_id} from landing page, showing channel links"
                )
                welcome_message = (
                    f"🎉 Welcome to OPTRIXTRADES\n\n"
                    f"Glad to have you onboard with us, join these channels to get access to our free trading tools and signals (either vip signals or our auto trading bot)\n\n"
                    f"DO WELL TO PIN AND UNMUTE THE CHANNEL\n\n"
                )

                # Create inline keyboard with channel links
                keyboard = InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "📱 Join Telegram Channel",
                                url="https://t.me/+g7AYDytK3IBhN2U0",
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                "📱 Join WhatsApp Channel",
                                url="https://whatsapp.com/channel/0029VbALds8GufIqYtg4uY1W",
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                "🚀 Get Started", callback_data="get_started"
                            )
                        ],
                    ]
                )

                await update.message.reply_text(
                    welcome_message, reply_markup=keyboard, parse_mode="Markdown"
                )
                return
            else:
                # Regular start command - check user status
                if user_data and user_data.get("verification_status") == "approved":
                    # Existing verified user
                    logger.info(
                        f"START_COMMAND: Verified user {user_id} accessing main menu"
                    )
                    keyboard = InlineKeyboardMarkup(
                        [
                            [
                                InlineKeyboardButton(
                                    "📊 Main Menu", callback_data="main_menu"
                                )
                            ],
                            [
                                InlineKeyboardButton(
                                    "👤 My Account", callback_data="account_menu"
                                )
                            ],
                        ]
                    )
                    await update.message.reply_text(
                        f"👋 Welcome back, {first_name}!\n\n"
                        f"Your account is verified and active.\n"
                        f"Ready to access premium trading signals!",
                        reply_markup=keyboard,
                    )
                else:
                    # New or unverified user
                    logger.info(
                        f"START_COMMAND: Starting verification flow for user {user_id}"
                    )
                    from telegram_bot.handlers.verification import start_verification

                    return await start_verification(update, context)

    except Exception as e:
        logger.error(
            f"START_COMMAND: Unexpected error for user {update.effective_user.id if update.effective_user else 'unknown'}: {type(e).__name__}: {e}"
        )
        try:
            await update.message.reply_text(
                "🔧 **System Update in Progress**\n\n"
                "We're currently updating our systems to serve you better.\n\n"
                "Please try again in a few moments. If the issue persists, contact our support team.",
                parse_mode="Markdown",
            )
        except Exception as reply_error:
            logger.error(f"START_COMMAND: Failed to send error message: {reply_error}")
        return None


async def vip_signals_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle the /vipsignals command"""
    user_id = update.effective_user.id
    await log_interaction(user_id, "vip_signals_command", "User accessed VIP signals")

    # Placeholder
    await update.message.reply_text(
        "🔒 VIP Signals are available to verified users only."
    )


async def my_account_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle the /myaccount command"""
    # Placeholder
    await update.message.reply_text(
        "👤 Your account information will be displayed here."
    )


async def support_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /support command"""
    user_id = update.effective_user.id
    await log_interaction(user_id, "support_command", "User requested support")

    # Direct link to admin with pre-filled message
    keyboard = [
        [
            InlineKeyboardButton(
                "Contact Support",
                url=f"https://t.me/{BotConfig.ADMIN_USERNAME}?text=I need help with my account",
            )
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "📞 Need help? Our support team is here for you.", reply_markup=reply_markup
    )


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /status command - Show user verification status"""
    user = update.effective_user
    user_id = user.id

    # Log user interaction
    await log_interaction(user_id, "stats_command", "User checked account status")

    try:
        # Import database utilities
        from database.connection import get_user_data

        # Get user data from database
        user_data = await get_user_data(user_id)

        if not user_data:
            # User not found in database
            status_text = "📊 **Account Status**\n\n"
            status_text += "❌ **Status:** Not Registered\n"
            status_text += (
                "📝 **Action Required:** Please use /start to begin registration\n\n"
            )
            status_text += "💡 **Next Steps:**\n"
            status_text += "• Complete account registration\n"
            status_text += "• Provide your trading UID\n"
            status_text += "• Submit verification documents"
        else:
            # Check verification status
            verification_status = user_data.get("verification_status", "not_verified")
            registration_status = user_data.get("registration_status", "incomplete")

            status_text = "📊 **Account Status**\n\n"
            status_text += f"👤 **Name:** {user.first_name}\n"
            status_text += f"🆔 **User ID:** {user_id}\n"

            # Show verification status with appropriate emoji and message
            if verification_status == "approved" or verification_status == "verified":
                status_text += "✅ **Verification Status:** Verified\n"
                status_text += "🎉 **Access Level:** Premium Member\n\n"
                status_text += "🚀 **Available Features:**\n"
                status_text += "• VIP Trading Signals\n"
                status_text += "• Premium Community Access\n"
                status_text += "• Advanced Trading Tools\n"
                status_text += "• Priority Support"
            elif verification_status == "pending":
                status_text += "⏳ **Verification Status:** Pending Review\n"
                status_text += "🔍 **Access Level:** Under Review\n\n"
                status_text += "📋 **What's Next:**\n"
                status_text += "• Our team is reviewing your submission\n"
                status_text += "• Expected review time: 2-24 hours\n"
                status_text += "• You'll be notified once approved\n"
                status_text += f"• Need help? Contact @{BotConfig.ADMIN_USERNAME}"
            elif verification_status == "rejected":
                status_text += "❌ **Verification Status:** Rejected\n"
                status_text += "🔄 **Access Level:** Resubmission Required\n\n"
                status_text += "📝 **Action Required:**\n"
                status_text += "• Review rejection reason\n"
                status_text += "• Submit new verification documents\n"
                status_text += "• Ensure all requirements are met\n"
                status_text += f"• Contact support: @{BotConfig.ADMIN_USERNAME}"
            else:
                status_text += "❌ **Verification Status:** Not Verified\n"
                status_text += "📝 **Access Level:** Basic User\n\n"
                status_text += "🎯 **To Get Verified:**\n"
                status_text += "• Use /start to begin verification\n"
                status_text += "• Provide your trading account UID\n"
                status_text += "• Submit deposit screenshot\n"
                status_text += "• Wait for admin approval"

        # Add helpful buttons
        keyboard = []
        if not user_data or user_data.get("verification_status") not in [
            "approved",
            "verified",
        ]:
            if user_data and user_data.get("verification_status") == "rejected":
                keyboard.append(
                    [
                        InlineKeyboardButton(
                            "🔄 Retry Verification", callback_data="start_verification"
                        )
                    ]
                )
            else:
                keyboard.append(
                    [
                        InlineKeyboardButton(
                            "🚀 Start Verification", callback_data="start_verification"
                        )
                    ]
                )

            # Add admin contact options for unverified users
            keyboard.append(
                [
                    InlineKeyboardButton(
                        "💬 Message Admin",
                        url=f"https://t.me/{BotConfig.ADMIN_USERNAME}",
                    ),
                    InlineKeyboardButton(
                        "📞 Contact Support",
                        url=f"https://t.me/{BotConfig.ADMIN_USERNAME}?text=I need help with verification",
                    ),
                ]
            )
        else:
            # For verified users, show support option
            keyboard.append(
                [
                    InlineKeyboardButton(
                        "💬 Contact Support",
                        url=f"https://t.me/{BotConfig.ADMIN_USERNAME}",
                    )
                ]
            )

        keyboard.append(
            [InlineKeyboardButton("🔙 Main Menu", callback_data="start_verification")]
        )

        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            status_text, parse_mode="Markdown", reply_markup=reply_markup
        )

    except Exception as e:
        logger.error(f"Error in stats_command: {e}")
        await update.message.reply_text(
            "❌ **Error**\n\n"
            "Unable to retrieve your account status at the moment.\n"
            f"Please try again later or contact support: @{BotConfig.ADMIN_USERNAME}",
            parse_mode="Markdown",
        )


async def how_it_works(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /howitworks command"""
    # Placeholder
    await update.message.reply_text(
        "ℹ️ Information about how the bot works will be displayed here."
    )


async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /menu command"""
    user_id = update.effective_user.id
    await log_interaction(user_id, "menu_command", "User accessed menu")

    # Placeholder
    await update.message.reply_text("📋 Menu options will be displayed here.")


async def get_my_id_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /getmyid command"""
    user_id = update.effective_user.id
    await update.message.reply_text(f"Your Telegram ID is: {user_id}")


async def handle_text_message(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle text messages with proper UID detection, UPGRADE command, and admin recognition"""
    user = update.effective_user
    user_id = str(user.id)
    message_text = update.message.text.strip()

    # Log user interaction
    await log_interaction(
        int(user_id), "text_message", f"User sent: {message_text[:50]}..."
    )

    # Automatically add user to premium channel (for users who didn't use /start)
    try:
        channel_added = await add_user_to_channel(context.bot, int(user_id))
        if channel_added:
            logger.info(
                f"User {user_id} automatically added to premium channel via text message"
            )
    except Exception as e:
        logger.error(f"Error adding user {user_id} to channel via text message: {e}")

    # Check if user is admin first - only handle specific admin commands outside conversation
    if str(user_id) == BotConfig.ADMIN_USER_ID:
        # Let conversation handler process admin messages when in conversation states
        # Only handle standalone admin commands here
        from telegram_bot.handlers.admin_handlers import (
            handle_text_message_admin_standalone,
        )

        await handle_text_message_admin_standalone(update, context)
        return

    # Handle UPGRADE command
    if message_text.upper() == "UPGRADE":
        upgrade_text = "🚀 **PREMIUM UPGRADE AVAILABLE**\n\n"
        upgrade_text += "Ready to unlock the full power of OPTRIXTRADES?\n\n"
        upgrade_text += "**Premium Features Include:**\n"
        upgrade_text += "✅ Advanced AI Trading Bot (Auto-trades for you)\n"
        upgrade_text += "✅ VIP Signal Alerts (SMS + Email + Push)\n"
        upgrade_text += "✅ Private 1-on-1 Strategy Sessions\n"
        upgrade_text += "✅ Risk Management Blueprint\n"
        upgrade_text += "✅ Priority Support (24/7)\n"
        upgrade_text += "✅ Exclusive Market Analysis\n\n"
        upgrade_text += f"Contact our team for upgrade: @{BotConfig.ADMIN_USERNAME}"

        keyboard = [
            [
                InlineKeyboardButton(
                    "💬 Contact Support", url=f"https://t.me/{BotConfig.ADMIN_USERNAME}"
                )
            ],
            [
                InlineKeyboardButton(
                    "🌟 Join VIP Group", callback_data="vip_verification_requirements"
                )
            ],
            [
                InlineKeyboardButton(
                    "🔙 Back to Menu", callback_data="start_verification"
                )
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            upgrade_text, reply_markup=reply_markup, parse_mode="Markdown"
        )
        return

    # Check if message looks like a UID (6-20 alphanumeric characters)
    if is_valid_uid(message_text):
        # This looks like a UID - start verification flow
        context.user_data["uid"] = message_text
        await update.message.reply_text(
            f"✅ UID received: {message_text}\n\n"
            "Great! Now please send a screenshot of your deposit as proof to complete verification."
        )
        return

    # Default response for other text messages
    await update.message.reply_text(
        "I've received your message. How can I help you?\n\n"
        "💡 **Quick Actions:**\n"
        "• Send your UID to start verification\n"
        "• Type 'UPGRADE' for premium features\n"
        "• Use /start to see the main menu"
    )


def is_valid_uid(text: str) -> bool:
    """Check if text looks like a valid UID"""
    if not text:
        return False

    # Remove any whitespace
    text = text.strip()

    # Check length
    if len(text) < BotConfig.MIN_UID_LENGTH or len(text) > BotConfig.MAX_UID_LENGTH:
        return False

    # Check if alphanumeric (letters and numbers only)
    if not text.isalnum():
        return False

    # Additional validation: should contain at least one number or letter
    has_letter = any(c.isalpha() for c in text)
    has_number = any(c.isdigit() for c in text)

    return has_letter or has_number


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle photo messages for verification"""
    user = update.effective_user
    user_id = user.id

    # Automatically add user to premium channel (for users who didn't use /start)
    try:
        channel_added = await add_user_to_channel(context.bot, user_id)
        if channel_added:
            logger.info(
                f"User {user_id} automatically added to premium channel via photo upload"
            )
    except Exception as e:
        logger.error(f"Error adding user {user_id} to channel via photo upload: {e}")

    # Check if user has provided UID and is in verification process
    uid = context.user_data.get("uid")

    if uid:
        # User has UID, this photo is likely a deposit screenshot
        file_id = update.message.photo[-1].file_id
        context.user_data["screenshot_file_id"] = file_id

        # Notify user
        await update.message.reply_text(
            "✅ **Verification Submitted Successfully!**\n\n"
            f"**Your Details:**\n"
            f"• UID: {uid}\n"
            f"• Screenshot: Received\n\n"
            "🔍 Our team will review your submission and grant you access to the premium channel shortly.\n\n"
            "⏰ **Expected Review Time:** 2-24 hours\n"
            "📞 **Need Help?** Contact @" + BotConfig.ADMIN_USERNAME,
            parse_mode="Markdown",
        )

        # Notify admin if configured
        if BotConfig.ADMIN_USER_ID:
            admin_message = (
                f"🔔 **New Verification Request**\n\n"
                f"**User Details:**\n"
                f"• Name: {user.first_name} {user.last_name if user.last_name else ''}\n"
                f"• Username: @{user.username if user.username else 'None'}\n"
                f"• User ID: {user_id}\n"
                f"• UID: {uid}\n\n"
                f"**Actions:**\n"
                f"/verify {user_id} - Approve verification\n"
                f"/reject {user_id} - Reject verification"
            )

            try:
                await context.bot.send_message(
                    chat_id=BotConfig.ADMIN_USER_ID,
                    text=admin_message,
                    parse_mode="Markdown",
                )
                await context.bot.send_photo(
                    chat_id=BotConfig.ADMIN_USER_ID,
                    photo=file_id,
                    caption=f"Deposit screenshot from {user.first_name} (UID: {uid})",
                )
            except Exception as e:
                logger.error(f"Failed to notify admin: {e}")

        # Clear the UID from context since verification is submitted
        context.user_data.pop("uid", None)

    else:
        # User sent photo without UID
        await update.message.reply_text(
            "📸 I received your photo!\n\n"
            "To complete verification, please:\n"
            "1️⃣ Send your UID first\n"
            "2️⃣ Then send your deposit screenshot\n\n"
            "💡 **Tip:** Send your UID as a text message, then upload your screenshot."
        )


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle document messages"""
    # Placeholder
    await update.message.reply_text("I've received your document. How can I help you?")


async def get_started_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle get started callback from channel welcome message"""
    query = update.callback_query
    user_id = query.from_user.id

    try:
        # Check if user is verified
        from database.connection import get_user_data

        user_data = await get_user_data(user_id)
        is_verified = user_data and user_data.get("verification_status") == "approved"

        if is_verified:
            # User is already verified, show main menu
            await show_main_menu(update, context)
        else:
            # User needs verification, check if they came from channel join flow
            # Check if user is actually in the channel
            from telegram_bot.utils.channel_manager import check_user_channel_membership

            is_channel_member = await check_user_channel_membership(
                context.bot, user_id
            )

            if is_channel_member:
                # Send enhanced welcome message for users coming from channel
                welcome_text = (
                    "🎉 **Welcome to OPTRIXTRADES!**\n\n"
                    "✅ Great! You've successfully joined our premium channel.\n\n"
                    "🚀 **Let's get you started with your trading journey:**\n\n"
                    "📈 Click the button below to begin your registration and unlock exclusive trading signals!"
                )

                keyboard = InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "🚀 Start Verification",
                                callback_data="start_verification",
                            )
                        ]
                    ]
                )

                await query.edit_message_text(
                    welcome_text, reply_markup=keyboard, parse_mode="Markdown"
                )
                return
            else:
                # User not in channel, ask them to join first
                await query.edit_message_text(
                    "❌ **Please join our channel first!**\n\n"
                    "You need to be a member of our premium channel to access the bot.\n\n"
                    "👆 Click the link below to join:",
                    reply_markup=InlineKeyboardMarkup(
                        [
                            [
                                InlineKeyboardButton(
                                    "📢 Join Channel",
                                    url="https://t.me/+g7AYDytK3IBhN2U0",
                                )
                            ],
                            [
                                InlineKeyboardButton(
                                    "🔄 I've Joined", callback_data="check_membership"
                                )
                            ],
                        ]
                    ),
                    parse_mode="Markdown",
                )
                return

            # Show verification menu for other cases
            from telegram_bot.handlers.verification import start_verification

            return await start_verification(update, context)

    except Exception as e:
        logger.error(f"Error in get_started_callback for user {user_id}: {e}")
        await query.edit_message_text(
            "❌ An error occurred. Please try again.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔄 Try Again", callback_data="get_started")]]
            ),
        )


async def check_membership_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle check membership callback"""
    query = update.callback_query
    user_id = query.from_user.id

    try:
        # Check if user is actually in the channel
        from telegram_bot.utils.channel_manager import check_user_channel_membership

        is_channel_member = await check_user_channel_membership(context.bot, user_id)

        if is_channel_member:
            # User has joined, proceed with verification
            welcome_text = (
                "🎉 **Welcome to OPTRIXTRADES!**\n\n"
                "✅ Great! You've successfully joined our premium channel.\n\n"
                "🚀 **Let's get you started with your trading journey:**\n\n"
                "📈 Click the button below to begin your registration and unlock exclusive trading signals!"
            )

            keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🚀 Start Verification", callback_data="start_verification"
                        )
                    ]
                ]
            )

            await query.edit_message_text(
                welcome_text, reply_markup=keyboard, parse_mode="Markdown"
            )
        else:
            # User still not in channel
            await query.edit_message_text(
                "❌ **You haven't joined our channel yet!**\n\n"
                "Please join our premium channel first to access the bot.\n\n"
                "👆 Click the link below to join:",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "📢 Join Channel", url="https://t.me/+g7AYDytK3IBhN2U0"
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                "🔄 I've Joined", callback_data="check_membership"
                            )
                        ],
                    ]
                ),
                parse_mode="Markdown",
            )

    except Exception as e:
        logger.error(f"Error in check_membership_callback for user {user_id}: {e}")
        await query.edit_message_text(
            "❌ An error occurred while checking membership. Please try again.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🔄 Try Again", callback_data="check_membership"
                        )
                    ]
                ]
            ),
        )


async def handle_callback_query(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle callback queries from inline keyboards"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    data = query.data

    logger.info(f"Callback query received from user {user_id}: {data}")

    # Ignore admin callbacks to avoid overriding admin handlers
    if data and data.startswith("admin_"):
        return

    try:
        if data == "get_started":
            return await get_started_callback(update, context)
        elif data == "start_verification":
            from telegram_bot.handlers.verification import start_verification

            return await start_verification(update, context)
        elif data == "check_membership":
            return await check_membership_callback(update, context)
        elif data == "main_menu":
            await show_main_menu(update, context)
        elif data == "account_menu":
            await show_account_menu(update, context)
        else:
            await query.edit_message_text("❌ Unknown command. Please try again.")

    except Exception as e:
        logger.error(f"Error handling callback query {data}: {e}")
        await query.edit_message_text(
            "❌ An error occurred. Please try again.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔄 Try Again", callback_data="get_started")]]
            ),
        )


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show main menu for verified users"""
    query = update.callback_query
    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📊 VIP Signals", callback_data="vip_signals")],
            [InlineKeyboardButton("👤 My Account", callback_data="account_menu")],
            [
                InlineKeyboardButton(
                    "📞 Support", url=f"https://t.me/{BotConfig.ADMIN_USERNAME}"
                )
            ],
        ]
    )

    await query.edit_message_text(
        "📊 **Main Menu**\n\n" "Welcome to your premium dashboard!",
        reply_markup=keyboard,
        parse_mode="Markdown",
    )


async def show_account_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show account menu"""
    query = update.callback_query
    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📊 Account Status", callback_data="account_status")],
            [InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")],
        ]
    )

    await query.edit_message_text(
        "👤 **Account Menu**\n\n" "Manage your account settings here.",
        reply_markup=keyboard,
        parse_mode="Markdown",
    )


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button callbacks - deprecated, use handle_callback_query instead"""
    return await handle_callback_query(update, context)


async def handle_chat_member_update(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle chat member updates (when users join/leave the channel)"""
    try:
        # Get the chat member update
        chat_member_update = update.chat_member or update.my_chat_member

        if not chat_member_update:
            return

        # Check if this is our premium channel
        chat_id = str(chat_member_update.chat.id)
        if chat_id != BotConfig.PREMIUM_CHANNEL_ID:
            return

        # Get user info
        user = chat_member_update.from_user
        user_id = user.id

        # Check if user joined the channel
        old_status = chat_member_update.old_chat_member.status
        new_status = chat_member_update.new_chat_member.status

        # User joined if they went from not being a member to being a member
        if old_status in ["left", "kicked"] and new_status in [
            "member",
            "administrator",
            "creator",
        ]:
            logger.info(
                f"User {user_id} ({user.first_name}) joined the premium channel"
            )

            # Send welcome message immediately
            try:
                from telegram_bot.utils.channel_monitor import get_channel_monitor

                monitor = get_channel_monitor()

                if monitor:
                    success = await monitor.send_welcome_message(user_id)
                    if success:
                        logger.info(
                            f"Welcome message sent to new channel member {user_id}"
                        )
                    else:
                        logger.warning(
                            f"Failed to send welcome message to user {user_id}"
                        )
                else:
                    logger.warning(
                        "Channel monitor not available for sending welcome message"
                    )

            except Exception as e:
                logger.error(f"Error sending welcome message to user {user_id}: {e}")

        # Log member leaving for monitoring
        elif old_status in ["member", "administrator"] and new_status in [
            "left",
            "kicked",
        ]:
            logger.info(f"User {user_id} ({user.first_name}) left the premium channel")

    except Exception as e:
        logger.error(f"Error handling chat member update: {e}")
