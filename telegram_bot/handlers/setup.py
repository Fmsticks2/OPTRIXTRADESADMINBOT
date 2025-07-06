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
    handle_broadcast_message,
    handle_user_lookup,
    handle_search_input,
    cancel_admin_action,
    cancel_admin,
    admin_chat_history_command,
    admin_queue_callback,
    admin_broadcast_callback,
    admin_search_user_callback,
    admin_recent_activity_callback,
    admin_auto_verify_stats_callback,
    admin_chat_history_callback,
    admin_dashboard_callback
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
    handle_remove_from_list,
    free_tips_callback,
    join_community_callback,
    market_analysis_callback,
    learning_resources_callback,
    community_rules_callback,
    back_to_verification_callback,
    approve_verification_callback,
    reject_verification_callback,
    view_user_callback,
    vip_verification_requirements_callback,
    vip_continue_registration_callback,
    approve_vip_verification_callback,
    reject_vip_verification_callback
)

# Conversation states
REGISTER_UID = 0
UPLOAD_SCREENSHOT = 1
BROADCAST_MESSAGE = 2
USER_LOOKUP = 3
SEARCH_USER = 4

logger = logging.getLogger(__name__)

def setup_all_handlers(bot):
    """Setup all handlers for the bot"""
    # Add handler to track message history
    bot.application.add_handler(MessageHandler(filters.ALL, bot._track_messages), group=-1)
    
    # Conversation handler for verification flow
    verification_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(registered_confirmation, pattern="^registered$"),
            CallbackQueryHandler(vip_continue_registration_callback, pattern="^vip_continue_registration$")
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
            CommandHandler("admin", admin_command),
            CallbackQueryHandler(admin_dashboard_callback, pattern='^admin_dashboard$'),
            CallbackQueryHandler(admin_broadcast_callback, pattern='^admin_broadcast$'),
            CallbackQueryHandler(admin_search_user_callback, pattern='^admin_search_user$'),
            CallbackQueryHandler(admin_chat_history_callback, pattern='^admin_chat_history$'),
            CallbackQueryHandler(admin_queue_callback, pattern='^admin_queue$'),
            CallbackQueryHandler(admin_recent_activity_callback, pattern='^admin_recent_activity$'),
            CallbackQueryHandler(admin_auto_verify_stats_callback, pattern='^admin_auto_verify_stats$')
        ],
        states={
            BROADCAST_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_broadcast_message)],
            USER_LOOKUP: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search_input)],
            SEARCH_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search_input)],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_admin_action),
            CallbackQueryHandler(cancel_admin, pattern='^cancel_admin$'),
            CallbackQueryHandler(admin_dashboard_callback, pattern='^admin_dashboard$')
        ],
        per_message=False,
        per_chat=True,
        per_user=True,
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
    bot.application.add_handler(CommandHandler("status", stats_command))
    bot.application.add_handler(CommandHandler("howitworks", how_it_works))
    bot.application.add_handler(CommandHandler("menu", menu_command))
    bot.application.add_handler(CommandHandler("getmyid", get_my_id_command))
    
    # Admin commands
    bot.application.add_handler(CommandHandler("verify", admin_verify_command))
    bot.application.add_handler(CommandHandler("reject", admin_reject_command))
    bot.application.add_handler(CommandHandler("queue", admin_queue_command))
    bot.application.add_handler(CommandHandler("admin_verify", admin_verify_command))
    bot.application.add_handler(CommandHandler("admin_reject", admin_reject_command))
    bot.application.add_handler(CommandHandler("admin_queue", admin_queue_command))
    bot.application.add_handler(CommandHandler("admin_broadcast", admin_broadcast_command))
    bot.application.add_handler(CommandHandler("admin_search_user", admin_search_user_command))
    bot.application.add_handler(CommandHandler("broadcast", handle_broadcast))
    bot.application.add_handler(CommandHandler("lookup", handle_user_lookup))
    bot.application.add_handler(CommandHandler("searchuser", admin_search_user_command))
    
    # Specific callback handlers
    bot.application.add_handler(CallbackQueryHandler(contact_support, pattern='^contact_support$'))
    # Note: admin_broadcast_callback, admin_search_user_callback, and admin_chat_history_callback
    # are handled by the ConversationHandler above, not as standalone handlers
    
    # Verification flow callback handlers
    bot.application.add_handler(CallbackQueryHandler(start_verification, pattern='^start_verification$'))
    bot.application.add_handler(CallbackQueryHandler(activation_instructions, pattern='^activation_instructions$'))
    bot.application.add_handler(CallbackQueryHandler(signup_help, pattern='^signup_help$'))
    bot.application.add_handler(CallbackQueryHandler(deposit_help, pattern='^deposit_help$'))
    bot.application.add_handler(CallbackQueryHandler(handle_not_interested, pattern='^not_interested$'))
    bot.application.add_handler(CallbackQueryHandler(handle_remove_from_list, pattern='^remove_from_list$'))
    
    # User engagement callback handlers
    bot.application.add_handler(CallbackQueryHandler(free_tips_callback, pattern='^free_tips$'))
    bot.application.add_handler(CallbackQueryHandler(join_community_callback, pattern='^join_community$'))
    bot.application.add_handler(CallbackQueryHandler(market_analysis_callback, pattern='^market_analysis$'))
    bot.application.add_handler(CallbackQueryHandler(learning_resources_callback, pattern='^learning_resources$'))
    bot.application.add_handler(CallbackQueryHandler(community_rules_callback, pattern='^community_rules$'))
    bot.application.add_handler(CallbackQueryHandler(back_to_verification_callback, pattern='^back_to_verification$'))
    
    # VIP verification callback handlers
    bot.application.add_handler(CallbackQueryHandler(vip_verification_requirements_callback, pattern='^vip_verification_requirements$'))
    
    # Admin verification action handlers
    bot.application.add_handler(CallbackQueryHandler(approve_verification_callback, pattern='^approve_verification_\\d+$'))
    bot.application.add_handler(CallbackQueryHandler(reject_verification_callback, pattern='^reject_verification_\\d+$'))
    bot.application.add_handler(CallbackQueryHandler(approve_vip_verification_callback, pattern='^approve_vip_verification_\\d+$'))
    bot.application.add_handler(CallbackQueryHandler(reject_vip_verification_callback, pattern='^reject_vip_verification_\\d+$'))
    bot.application.add_handler(CallbackQueryHandler(view_user_callback, pattern='^view_user_\\d+$'))
    
    # Default callback handler (must be last)
    bot.application.add_handler(CallbackQueryHandler(button_callback))
    
    # Add text, photo, and document handlers (lower priority)
    # Note: Admin text messages are handled by the admin conversation handler above
    bot.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    bot.application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    bot.application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    
    bot.application.add_error_handler(bot.error_handler)
    
    logger.info("All handlers have been set up")