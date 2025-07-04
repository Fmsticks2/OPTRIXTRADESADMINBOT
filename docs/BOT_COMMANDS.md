# Telegram Bot Commands Reference

## User Commands
- `/start` - Initialize the bot and show welcome message with registration flow
- `/menu` - Show main menu with available options
- `UPGRADE` - Request premium upgrade and contact support
- `Send UID + screenshot` - Complete verification process with deposit proof
- `Text messages` - General text input handling and UID collection
- `Photo uploads` - Deposit screenshot verification

## Admin Commands
- `/admin` - Access comprehensive admin dashboard
- `/verify` - Approve user verification manually
- `/reject` - Reject user verification with reason
- `/queue` - View pending verification queue
- `/stats` - View detailed system statistics and user metrics
- `/users` - Manage all registered users
- `/delete_user` - Remove user from system
- `/health` - Check system health and database status

## Button Callbacks
- `main_menu` - Return to main menu
- `account_menu` - Account management and status
- `help_menu` - Show help information and guides
- `admin_menu` - Comprehensive admin dashboard
- `account_status` - View detailed account status and verification
- `notification_settings` - Notification preferences and settings
- `admin_stats` - Detailed system statistics and metrics
- `admin_queue` - Pending verification queue management
- `admin_users` - User management and administration
- `post_signal` - Create new trading signal
- `edit_signal` - Edit last trading signal
- `cancel_signal` - Cancel current action
- `how_it_works` - Show platform explanation and features
- `deposit_info` - Display deposit instructions and methods
- `contact_support` - Contact admin support
- `premium_features` - Show premium feature details

## BotFather Update Instructions

### Inline Command Settings
```
start - Initialize the bot and registration
menu - Show main menu
upgrade - Request premium upgrade
admin - Admin dashboard (admin only)
verify - Approve verification (admin only)
reject - Reject verification (admin only)
queue - View verification queue (admin only)
stats - View system statistics (admin only)
users - Manage all users (admin only)
delete_user - Remove user (admin only)
health - Check system health (admin only)
```

### Admin Command Setup
1. **All admin commands** should be set up together in BotFather
2. Mark admin commands clearly with "(admin only)"
3. Recommended order:
   - First set user commands (start, menu, upgrade)
   - Then set admin commands (admin, verify, reject, queue, stats, users, delete_user, health)
4. BotFather doesn't enforce permissions - actual admin checks are handled in your code

## Database Operations
- **User Management**: Create, read, update, delete user data
- **Verification System**: Track pending verifications and approval status
- **Interaction Logging**: Log all user interactions for analytics
- **Health Monitoring**: Database connection and system health checks
- **Data Cleanup**: Automated cleanup of old records and sessions

## Webhook Features
- **FastAPI Integration**: Modern webhook server with automatic documentation
- **Signature Verification**: Secure webhook payload validation
- **Admin Endpoints**: RESTful API for webhook management
- **Health Checks**: Built-in health monitoring endpoints
- **Ngrok Support**: Local development tunnel integration

## Enhanced Bot Features
- **Photo Processing**: Automatic deposit screenshot verification
- **Text Analysis**: Smart text message handling and UID extraction
- **State Management**: User flow tracking and session persistence
- **Error Handling**: Comprehensive error logging and admin notifications
- **Premium Integration**: Automated premium channel access management

## Setup Instructions
1. Copy the command block above and paste into BotFather
2. Each command should be on a new line with format: `command - description`
3. Admin commands are marked as '(admin only)'
4. Configure environment variables for database and webhook settings
5. Set up admin user ID and premium channel ID in config

This documentation provides a complete reference for all commands, callbacks, and features used in the enhanced OPTRIXTRADES bot system.