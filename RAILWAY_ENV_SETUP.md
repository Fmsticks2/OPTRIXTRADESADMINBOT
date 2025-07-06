# Railway Environment Variables Setup Guide

This guide explains how to configure all necessary environment variables for deploying the OPTRIXTRADES bot on Railway.

## 🚄 Railway Deployment Overview

Railway automatically handles:
- **PORT**: Set automatically by Railway
- **DATABASE_URL**: PostgreSQL connection string (when PostgreSQL service is added)
- **RAILWAY_PUBLIC_DOMAIN**: Your app's public domain
- **RAILWAY_ENVIRONMENT**: Set to 'production'

## 📋 Required Environment Variables

Set these variables in your Railway project's environment variables section:

### 🤖 Bot Configuration (Required)
```
BOT_TOKEN=your_bot_token_from_botfather
BROKER_LINK=your_broker_affiliate_link
PREMIUM_CHANNEL_ID=-100xxxxxxxxxx
ADMIN_USERNAME=your_telegram_username
ADMIN_USER_ID=your_telegram_user_id
```

### 🌐 Webhook Configuration
```
BOT_MODE=webhook
WEBHOOK_ENABLED=true
WEBHOOK_URL=https://your-app-name-production.up.railway.app
WEBHOOK_SECRET_TOKEN=your_optional_secret_token
WEBHOOK_PATH=/webhook
```

### 🗄️ Database Configuration
```
DATABASE_TYPE=postgresql
# DATABASE_URL is automatically set by Railway PostgreSQL service
```

## 🔧 Optional Configuration Variables

### Auto-Verification Settings
```
AUTO_VERIFY_ENABLED=true
MIN_UID_LENGTH=6
MAX_UID_LENGTH=20
AUTO_VERIFY_CONFIDENCE_THRESHOLD=0.8
DAILY_AUTO_APPROVAL_LIMIT=100
REQUIRE_BOTH_UID_AND_IMAGE=true
MANUAL_REVIEW_SUSPICIOUS=true
```

### Time-Based Settings
```
VERIFICATION_WINDOW_HOURS=24
AUTO_VERIFY_BUSINESS_HOURS_ONLY=false
BUSINESS_HOURS_START=9
BUSINESS_HOURS_END=17
TIMEZONE=UTC
```

### Notification Settings
```
ADMIN_ERROR_NOTIFICATIONS=true
NOTIFY_ON_MANUAL_NEEDED=true
NOTIFY_ON_AUTO_APPROVAL=false
NOTIFY_ON_REJECTION=true
DAILY_SUMMARY=true
QUEUE_SIZE_WARNING_THRESHOLD=10
```

### Follow-up Messages
```
FOLLOW_UP_ENABLED=true
FOLLOW_UP_1_DELAY_HOURS=6
FOLLOW_UP_2_DELAY_HOURS=23
FOLLOW_UP_3_DELAY_HOURS=22
FOLLOW_UP_4_DELAY_DAYS=1
FOLLOW_UP_5_DELAY_DAYS=1
```

### Security Settings
```
RATE_LIMIT_ENABLED=true
MAX_REQUESTS_PER_MINUTE=30
BLOCK_SUSPICIOUS_PATTERNS=true
```

### Logging Configuration
```
LOG_LEVEL=INFO
ENABLE_FILE_LOGGING=true
ENABLE_CONSOLE_LOGGING=true
```

### Broker Settings
```
BROKER_NAME=IQ Option
MIN_DEPOSIT_AMOUNT=20
DEPOSIT_CURRENCY=USD
```

### Performance Settings
```
DATABASE_CONNECTION_TIMEOUT=30
MESSAGE_RETRY_ATTEMPTS=3
WEBHOOK_TIMEOUT=60
```

## 🚀 How to Set Environment Variables on Railway

### Method 1: Railway Dashboard
1. Go to your Railway project dashboard
2. Click on your service
3. Navigate to the "Variables" tab
4. Click "+ New Variable"
5. Add each variable name and value
6. Click "Deploy" to apply changes

### Method 2: Railway CLI
```bash
# Set individual variables
railway variables set BOT_TOKEN=your_bot_token
railway variables set BROKER_LINK=your_broker_link
railway variables set PREMIUM_CHANNEL_ID=-100xxxxxxxxxx

# Set multiple variables from file
railway variables set --from-file .env
```

### Method 3: Bulk Import
1. Create a `.env` file with all your variables
2. In Railway dashboard, go to Variables tab
3. Click "Import from .env"
4. Upload your `.env` file

## 🔍 Variable Validation

The bot automatically validates required variables on startup. Check the logs for:
- ✅ Configuration validation passed
- ❌ Missing required variables
- ⚠️ Configuration warnings

## 🐛 Troubleshooting

### Common Issues

1. **Bot Token Invalid**
   - Ensure BOT_TOKEN contains ':' (format: 123456:ABC-DEF...)
   - Get token from @BotFather on Telegram

2. **Channel ID Format**
   - Premium channel ID should start with '-100'
   - Use @userinfobot to get correct channel ID

3. **Admin User ID**
   - Should be numeric (e.g., 123456789)
   - Use @userinfobot to get your user ID

4. **Webhook URL**
   - Auto-detected on Railway if not set
   - Should be https://your-app-name-production.up.railway.app
   - Don't include /webhook path in WEBHOOK_URL

### Checking Configuration

```bash
# View current variables
railway variables

# Check application logs
railway logs

# Get service status
railway status
```

## 🔒 Security Best Practices

1. **Never commit sensitive variables to Git**
2. **Use Railway's built-in secret management**
3. **Set WEBHOOK_SECRET_TOKEN for webhook security**
4. **Enable RATE_LIMIT_ENABLED to prevent abuse**
5. **Use strong, unique tokens and passwords**

## 📚 Additional Resources

- [Railway Documentation](https://docs.railway.app/)
- [Telegram Bot API](https://core.telegram.org/bots/api)
- [Bot Configuration Guide](./docs/CONFIGURATION.md)
- [Webhook Setup Guide](./docs/WEBHOOK_GUIDE.md)

## 🆘 Getting Help

If you encounter issues:
1. Check Railway logs: `railway logs`
2. Verify all required variables are set
3. Ensure PostgreSQL service is running
4. Test webhook URL accessibility
5. Check bot permissions in Telegram channel