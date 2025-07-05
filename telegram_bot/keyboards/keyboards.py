"""Keyboard layouts for OPTRIXTRADES Telegram Bot"""

from typing import List, Dict, Any, Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup


def get_start_keyboard() -> InlineKeyboardMarkup:
    """Return the keyboard for the start command"""
    keyboard = [
        [InlineKeyboardButton("📊 VIP Signals", callback_data="vip_signals")],
        [InlineKeyboardButton("👤 My Account", callback_data="my_account")],
        [InlineKeyboardButton("📝 Verify Account", callback_data="verify_account")],
        [InlineKeyboardButton("ℹ️ How It Works", callback_data="how_it_works")],
        [InlineKeyboardButton("📞 Support", callback_data="support")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_verification_keyboard() -> InlineKeyboardMarkup:
    """Return the keyboard for the verification process"""
    keyboard = [
        [InlineKeyboardButton("Start Verification", callback_data="start_verification")],
        [InlineKeyboardButton("Cancel", callback_data="cancel_verification")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_verification_confirm_keyboard() -> InlineKeyboardMarkup:
    """Return the keyboard for confirming verification submission"""
    keyboard = [
        [InlineKeyboardButton("Confirm", callback_data="confirm_verification")],
        [InlineKeyboardButton("Cancel", callback_data="cancel_verification")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_admin_keyboard() -> InlineKeyboardMarkup:
    """Return the keyboard for the admin panel"""
    keyboard = [
        [InlineKeyboardButton("Queue", callback_data="admin_queue")],
        [InlineKeyboardButton("Broadcast", callback_data="admin_broadcast")],
        [InlineKeyboardButton("Search User", callback_data="admin_search_user")],
        [InlineKeyboardButton("Recent Activity", callback_data="admin_recent_activity")],
        [InlineKeyboardButton("Auto-Verify Stats", callback_data="admin_auto_verify_stats")],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_support_keyboard() -> InlineKeyboardMarkup:
    """Return the keyboard for the support command"""
    keyboard = [
        [InlineKeyboardButton("Contact Support", callback_data="contact_support")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_back_keyboard(callback_data: str = "back") -> InlineKeyboardMarkup:
    """Return a simple back button keyboard"""
    keyboard = [
        [InlineKeyboardButton("« Back", callback_data=callback_data)]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_yes_no_keyboard(yes_data: str = "yes", no_data: str = "no") -> InlineKeyboardMarkup:
    """Return a simple yes/no keyboard"""
    keyboard = [
        [InlineKeyboardButton("Yes", callback_data=yes_data),
         InlineKeyboardButton("No", callback_data=no_data)]
    ]
    return InlineKeyboardMarkup(keyboard)