# OPTRIXTRADES Bot Command Reference

## User Commands

| Command | Description |
|---------|-------------|
| `/start` | Begin using the bot and start registration process |
| `/menu` | Show the main menu with available options |
| `UPGRADE` | Request premium upgrade information |
| UID + Screenshot | Send your broker UID followed by deposit screenshot for verification |

## Admin Commands

| Command | Description |
|---------|-------------|
| `/admin` | Access admin dashboard |
| `/verify <user_id>` | Approve a user's verification request |
| `/reject <user_id>` | Reject a user's verification request |
| `/queue` | View pending verification requests |
| `/stats` | View bot usage statistics |

## Flow Overview

1. **New Users**: Start with `/start` command
2. **Verification**: Send UID and deposit screenshot
3. **Premium Access**: Use `UPGRADE` command for premium features
4. **Admin Tasks**: Use admin commands to manage users and view stats

For support, contact @{config.ADMIN_USERNAME}