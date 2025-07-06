# 🚄 Railway Deployment Troubleshooting Guide

## ❌ Current Issue: Missing Environment Variables

Based on your build logs, the bot is detecting Railway environment but missing required variables:

```
❌ Configuration Errors:
  - Missing required field: BOT_TOKEN
  - Missing required field: BROKER_LINK
  - Missing required field: PREMIUM_CHANNEL_ID
  - Missing required field: ADMIN_USERNAME
  - Missing required field: ADMIN_USER_ID
```

## 🔧 Solution: Set Required Variables in Railway

### Step 1: Set Core Bot Variables
Go to your Railway project → Variables tab and add these **REQUIRED** variables:

```env
BOT_TOKEN=your_bot_token_from_botfather
BROKER_LINK=your_broker_affiliate_link
PREMIUM_CHANNEL_ID=-100xxxxxxxxxx
ADMIN_USERNAME=your_telegram_username
ADMIN_USER_ID=your_telegram_user_id
```

### Step 2: PostgreSQL Connection Variables

#### Option A: Automatic (Recommended)
Railway automatically provides `DATABASE_URL` when you add a PostgreSQL service. **No manual setup needed.**

#### Option B: Manual PostgreSQL Variables (if needed)
If you need to set PostgreSQL variables manually:

```env
DATABASE_TYPE=postgresql
DATABASE_URL=postgresql://username:password@host:port/database
```

**Railway PostgreSQL Service Variables (auto-provided):**
- `DATABASE_URL` - Complete connection string
- `PGHOST` - PostgreSQL host
- `PGPORT` - PostgreSQL port
- `PGDATABASE` - Database name
- `PGUSER` - Username
- `PGPASSWORD` - Password

### Step 3: Webhook Configuration
```env
BOT_MODE=webhook
WEBHOOK_ENABLED=true
WEBHOOK_URL=https://your-app-name-production.up.railway.app
```

## 🚀 How to Add PostgreSQL Service to Railway

### Method 1: Railway Dashboard
1. Go to your Railway project
2. Click "+ New Service"
3. Select "Database" → "PostgreSQL"
4. Railway will automatically create the service and set environment variables

### Method 2: Railway CLI
```bash
railway add --plugin postgresql
```

### Method 3: railway.toml (Already configured)
Your `railway.toml` already includes PostgreSQL configuration:

```toml
[[services]]
name = "postgres"
image = "postgres:15"
variables = { POSTGRES_DB = "optrixtrades", POSTGRES_USER = "optrixtrades_user" }
```

## 🔍 Verify PostgreSQL Connection

After adding PostgreSQL service, check these variables are automatically set:

```bash
# Check if DATABASE_URL is set
railway variables | grep DATABASE_URL

# Check all PostgreSQL variables
railway variables | grep PG
```

## 📋 Complete Variable Checklist

### ✅ Required Variables (Must Set Manually)
- [ ] `BOT_TOKEN`
- [ ] `BROKER_LINK`
- [ ] `PREMIUM_CHANNEL_ID`
- [ ] `ADMIN_USERNAME`
- [ ] `ADMIN_USER_ID`

### 🤖 Webhook Variables (Recommended)
- [ ] `BOT_MODE=webhook`
- [ ] `WEBHOOK_ENABLED=true`
- [ ] `WEBHOOK_URL` (auto-detected if not set)

### 🗄️ Database Variables (Auto-provided by Railway)
- [ ] `DATABASE_URL` (set by PostgreSQL service)
- [ ] `PGHOST` (set by PostgreSQL service)
- [ ] `PGPORT` (set by PostgreSQL service)
- [ ] `PGDATABASE` (set by PostgreSQL service)
- [ ] `PGUSER` (set by PostgreSQL service)
- [ ] `PGPASSWORD` (set by PostgreSQL service)

### 🔧 System Variables (Auto-provided by Railway)
- [ ] `PORT` (set by Railway)
- [ ] `RAILWAY_PUBLIC_DOMAIN` (set by Railway)
- [ ] `RAILWAY_ENVIRONMENT` (set by Railway)

## 🛠️ Quick Fix Commands

### Set Required Variables via CLI
```bash
# Set core bot variables
railway variables set BOT_TOKEN="your_bot_token_here"
railway variables set BROKER_LINK="your_broker_link_here"
railway variables set PREMIUM_CHANNEL_ID="-100xxxxxxxxxx"
railway variables set ADMIN_USERNAME="your_username"
railway variables set ADMIN_USER_ID="your_user_id"

# Set webhook variables
railway variables set BOT_MODE="webhook"
railway variables set WEBHOOK_ENABLED="true"

# Add PostgreSQL service
railway add --plugin postgresql

# Redeploy
railway up
```

### Bulk Import from .env File
```bash
# Create .env file with your variables
echo "BOT_TOKEN=your_token" > .env
echo "BROKER_LINK=your_link" >> .env
echo "PREMIUM_CHANNEL_ID=-100xxxxxxxxxx" >> .env
echo "ADMIN_USERNAME=your_username" >> .env
echo "ADMIN_USER_ID=your_user_id" >> .env

# Import to Railway
railway variables set --from-file .env
```

## 🔍 Debugging Steps

### 1. Check Current Variables
```bash
railway variables
```

### 2. Check Service Status
```bash
railway status
```

### 3. View Deployment Logs
```bash
railway logs
```

### 4. Test Database Connection
```bash
railway shell
# Inside the shell:
python -c "import os; print('DATABASE_URL:', os.getenv('DATABASE_URL'))"
```

## 🎯 Expected Success Output

After setting all variables correctly, you should see:

```
🚄 Railway Environment Detected
📡 Webhook Mode: True
🔌 Port: 8080
🌐 Webhook URL: https://your-app-name-production.up.railway.app
✅ Configuration validation passed
✅ Database connected successfully
✅ Bot initialized successfully
```

## 🆘 Still Having Issues?

1. **Double-check variable names** - they are case-sensitive
2. **Ensure PostgreSQL service is running** - check Railway dashboard
3. **Verify bot token format** - should contain ':' (e.g., 123456:ABC-DEF...)
4. **Check channel ID format** - should start with '-100'
5. **Confirm admin user ID is numeric**

### Get Help
```bash
# Share these outputs for debugging:
railway variables
railway status
railway logs --tail 50
```

---

**Next Steps:**
1. Set the 5 required variables in Railway dashboard
2. Add PostgreSQL service if not already added
3. Redeploy your application
4. Check logs for successful connection