# Telegram Bot Commands Reference

## User Commands
- `/start` - Initialize the bot and show welcome message
- `/menu` - Show main menu with available options
- `UPGRADE` - Information about premium features
- `Send UID + screenshot` - Verification instructions

## Admin Commands
- `/admin` - Access admin dashboard
- `/verify` - Approve user verification
- `/reject` - Reject user verification
- `/queue` - View verification queue
- `/stats` - View system statistics

## Button Callbacks
- `main_menu` - Return to main menu
- `account_menu` - Account management
- `help_menu` - Show help information
- `admin_menu` - Admin dashboard
- `account_status` - View account status
- `notification_settings` - Notification preferences
- `admin_stats` - System statistics
- `admin_queue` - Verification queue
- `post_signal` - Create new trading signal
- `edit_signal` - Edit last signal
- `cancel_signal` - Cancel current action

## BotFather Update Instructions

### Inline Command Settings
```
start - Initialize the bot
menu - Show main menu
upgrade - Premium features info
admin - Admin dashboard (admin only)
verify - Approve verification (admin only)
reject - Reject verification (admin only)
queue - View verification queue (admin only)
stats - View system stats (admin only)
```

### Admin Command Setup
1. **All admin commands** should be set up together in BotFather
2. Mark admin commands clearly with "(admin only)"
3. Recommended order:
   - First set user commands (start, menu, upgrade)
   - Then set admin commands (admin, verify, reject, queue, stats)
4. BotFather doesn't enforce permissions - actual admin checks are handled in your code

1. Copy the above block and paste into BotFather
2. Each command should be on a new line with format: `command - description`
3. Admin commands are marked as '(admin only)'
4. Remember to include both user and admin commands

This documentation provides a complete reference for all commands and callbacks used in the bot, along with BotFather update guidance.