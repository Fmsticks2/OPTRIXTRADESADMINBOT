"""Handler setup for OPTRIXTRADES Telegram Bot"""

import logging
from telegram.ext import (
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters
)

from telegram_bot.handlers.user_handlers import (
    start_command,
    vip_signals_command,
    my_account_command,
    support_command,
    stats_command,
    how_it_works,
    menu_command,
    get_my_id_command,
    handle_text_message,
    handle_photo,
    handle_document,
    contact_support,
    button_callback
)

from telegram_bot.handlers.admin_handlers import (
    admin_command,
    admin_verify_command,
    admin_reject_command,
    admin_queue_command,
    admin_broadcast_command,
    admin_recent_activity_command,
    admin_search_user_command,
    admin_auto_verify_stats_command,
    handle_broadcast,
    handle_user_lookup,
    admin_chat_history_command,
    admin_queue_callback,
    admin_broadcast_callback,
    admin_search_user_callback,
    admin_recent_activity_callback,
    admin_auto_verify_stats_callback,
    admin_chat_history_callback
)

from telegram_bot.handlers.verification import (
    start_verification,
    handle_uid_confirmation,
    handle_screenshot_upload,
    cancel,
    activation_instructions,
    registered_confirmation,
    signup_help,
    deposit_help,
    followup_day1,
    followup_day2,
    followup_day3,
    followup_day4,
    followup_day5,
    followup_day6,
    followup_day7,
    followup_day8,
    followup_day9,
    followup_day10,
    handle_not_interested,
    handle_remove_from_list
)

# Conversation states
REGISTER_UID = 0
UPLOAD_SCREENSHOT = 1
BROADCAST_MESSAGE = 0
USER_LOOKUP = 0

logger = logging.getLogger(__name__)

def setup_all_handlers(bot):
    """Setup all handlers for the bot"""
    # Add handler to track message history
    bot.application.add_handler(MessageHandler(filters.ALL, bot._track_messages), group=-1)
    
    # Conversation handler for verification flow
    verification_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(registered_confirmation, pattern="^registered$")
        ],
        states={
            REGISTER_UID: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_uid_confirmation)],
            UPLOAD_SCREENSHOT: [
                MessageHandler(filters.PHOTO, handle_screenshot_upload),
                MessageHandler(filters.Document.IMAGE, handle_screenshot_upload)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
        per_message=False,  # Fixed: Set to False since we use MessageHandler and CommandHandler
        per_chat=True,
        per_user=True,  # Changed to True for proper user-based conversation tracking
    )
    
    # Conversation handler for admin functions
    admin_conv = ConversationHandler(
        entry_points=[
            CommandHandler("broadcast", handle_broadcast),
            CommandHandler("lookup", handle_user_lookup)
        ],
        states={
            BROADCAST_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_broadcast_message)],
            USER_LOOKUP: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_lookup_user)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False,  # Fixed: Set to False since we use MessageHandler and CommandHandler
        per_chat=True,
        per_user=True,  # Changed to True for proper user-based conversation tracking
    )
    
    # Add conversation handlers FIRST (highest priority)
    bot.application.add_handler(verification_conv)
    bot.application.add_handler(admin_conv)
    
    # User commands
    bot.application.add_handler(CommandHandler("start", start_command))
    bot.application.add_handler(CommandHandler("vipsignals", vip_signals_command))
    bot.application.add_handler(CommandHandler("myaccount", my_account_command))
    bot.application.add_handler(CommandHandler("support", support_command))
    bot.application.add_handler(CommandHandler("stats", stats_command))
    bot.application.add_handler(CommandHandler("howitworks", how_it_works))
    bot.application.add_handler(CommandHandler("menu", menu_command))
    bot.application.add_handler(CommandHandler("getmyid", get_my_id_command))
    
    # Admin commands
    bot.application.add_handler(CommandHandler("admin", admin_command))
    bot.application.add_handler(CommandHandler("verify", admin_verify_command))
    bot.application.add_handler(CommandHandler("reject", admin_reject_command))
    bot.application.add_handler(CommandHandler("queue", admin_queue_command))
    bot.application.add_handler(CommandHandler("admin_verify", admin_verify_command))
    bot.application.add_handler(CommandHandler("admin_reject", admin_reject_command))
    bot.application.add_handler(CommandHandler("admin_queue", admin_queue_command))
    bot.application.add_handler(CommandHandler("admin_broadcast", admin_broadcast_command))
    bot.application.add_handler(CommandHandler("admin_recent_activity", admin_recent_activity_command))
    bot.application.add_handler(CommandHandler("admin_search_user", admin_search_user_command))
    bot.application.add_handler(CommandHandler("admin_auto_verify_stats", admin_auto_verify_stats_command))
    bot.application.add_handler(CommandHandler("broadcast", handle_broadcast))
    bot.application.add_handler(CommandHandler("lookup", handle_user_lookup))
    bot.application.add_handler(CommandHandler("searchuser", admin_search_user_command))
    bot.application.add_handler(CommandHandler("activity", admin_recent_activity_command))
    bot.application.add_handler(CommandHandler("autostats", admin_auto_verify_stats_command))
    bot.application.add_handler(CommandHandler("chathistory", admin_chat_history_command))
    
    # Specific callback handlers
    bot.application.add_handler(CallbackQueryHandler(contact_support, pattern='^contact_support$'))
    
    # Admin callback handlers
    bot.application.add_handler(CallbackQueryHandler(admin_queue_callback, pattern='^admin_queue$'))
    bot.application.add_handler(CallbackQueryHandler(admin_broadcast_callback, pattern='^admin_broadcast$'))
    bot.application.add_handler(CallbackQueryHandler(admin_search_user_callback, pattern='^admin_search_user$'))
    bot.application.add_handler(CallbackQueryHandler(admin_recent_activity_callback, pattern='^admin_recent_activity$'))
    bot.application.add_handler(CallbackQueryHandler(admin_auto_verify_stats_callback, pattern='^admin_auto_verify_stats$'))
    bot.application.add_handler(CallbackQueryHandler(admin_chat_history_callback, pattern='^admin_chat_history$'))
    
    # Verification flow callback handlers
    bot.application.add_handler(CallbackQueryHandler(start_verification, pattern='^start_verification$'))
    bot.application.add_handler(CallbackQueryHandler(activation_instructions, pattern='^activation_instructions$'))
    bot.application.add_handler(CallbackQueryHandler(signup_help, pattern='^signup_help$'))
    bot.application.add_handler(CallbackQueryHandler(deposit_help, pattern='^deposit_help$'))
    bot.application.add_handler(CallbackQueryHandler(handle_not_interested, pattern='^not_interested$'))
    bot.application.add_handler(CallbackQueryHandler(handle_remove_from_list, pattern='^remove_from_list$'))
    
    # Default callback handler (must be last)
    bot.application.add_handler(CallbackQueryHandler(button_callback))
    
    # Add text, photo, and document handlers (lower priority)
    bot.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    bot.application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    bot.application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    
    bot.application.add_error_handler(bot.error_handler)
    
    logger.info("All handlers have been set up")