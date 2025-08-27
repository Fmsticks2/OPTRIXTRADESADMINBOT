# Channel Join Request Feature

This document describes the automatic channel join request handling feature for the OPTRIXTRADES bot.

## Overview

The bot can automatically handle chat join requests for OPTRIXTRADES channels:

1. When a user requests to join a channel, the bot receives a notification
2. The bot sends a welcome message with a deep link to the user
3. The bot approves their join request (if auto-approval is enabled)
4. The bot sends a confirmation message
5. The admin is notified about the join request

## Configuration

The following environment variables control this feature:

| Variable                               | Description                                    | Default |
| -------------------------------------- | ---------------------------------------------- | ------- |
| `ENABLE_AUTO_APPROVE_JOIN_REQUESTS`    | Whether to automatically approve join requests | `true`  |
| `JOIN_REQUEST_WELCOME_MESSAGE_ENABLED` | Whether to send welcome messages to users      | `true`  |

## Requirements

For this feature to work, the bot must:

1. Be an administrator in the channel
2. Have permission to approve new members
3. Be able to send messages to users (to send the welcome message)

## Setting Up Channel Permissions

1. Open your channel in Telegram
2. Go to Channel Info > Administrators > Add Administrator
3. Add your bot as an administrator
4. Enable "Add Members" permission for the bot
5. Save the changes

## Troubleshooting

If the feature is not working:

1. Verify the bot is an administrator in the channel
2. Check that the bot has the necessary permissions
3. Ensure your webhook is properly configured to receive chat_join_request updates
4. Check the logs for any errors

## Message Customization

The welcome and confirmation messages can be customized by modifying the `handle_chat_join_request` function in the `telegram_bot/handlers/join_request_handlers.py` file.
