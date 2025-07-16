# 🚄 Railway Bot Fix Guide - Complete Solution

## 🔍 Problem Identified

Your bot is failing on Railway because **critical environment variables are missing**. The debug script shows:

❌ **Missing Variables:**
- `BOT_TOKEN`
- `BROKER_LINK` 
- `PREMIUM_CHANNEL_ID`
- `ADMIN_USERNAME`
- `ADMIN_USER_ID`
- `DATABASE_URL`

## 🔧 Complete Fix Steps

### Step 1: Set Environment Variables in Railway

1. **Go to Railway Dashboard:**
   - Open [railway.app](https://railway.app)
   - Navigate to your project
   - Click on your service
   - Go to **Variables** tab

2. **Add Required Variables:**

```env
# Bot Configuration
BOT_TOKEN=8195373457:AAGFwhtAYNQSt4vFj6BMApQo7Nd2wtrOBZI
BROKER_LINK=your_broker_link_here
PREMIUM_CHANNEL_ID=-1001234567890
ADMIN_USERNAME=your_admin_username
ADMIN_USER_ID=your_admin_user_id

# Webhook Configuration
BOT_MODE=webhook
WEBHOOK_ENABLED=true
WEBHOOK_URL=https://your-app-name-production.up.railway.app

# Database (if using PostgreSQL)
DATABASE_TYPE=postgresql
DATABASE_URL=${{Postgres.DATABASE_URL}}
```

### Step 2: Update Railway Configuration

Your `railway.toml` should include all variables:

```toml
[build]
builder = "nixpacks"
buildCommand = "pip install -r requirements.txt"

[deploy]
startCommand = "python bot_runner.py webhook"
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 3

[environments.production]
variables = { 
    BOT_MODE = "webhook", 
    WEBHOOK_ENABLED = "true",
    BOT_TOKEN = "${{BOT_TOKEN}}",
    BROKER_LINK = "${{BROKER_LINK}}",
    PREMIUM_CHANNEL_ID = "${{PREMIUM_CHANNEL_ID}}",
    ADMIN_USERNAME = "${{ADMIN_USERNAME}}",
    ADMIN_USER_ID = "${{ADMIN_USER_ID}}",
    DATABASE_TYPE = "postgresql",
    DATABASE_URL = "${{Postgres.DATABASE_URL}}",
    WEBHOOK_PORT = "${{PORT}}"
}
```

### Step 3: Verify Database Service

1. **Check PostgreSQL Service:**
   - In Railway dashboard, ensure you have a PostgreSQL service
   - If not, add one: **+ New** → **Database** → **PostgreSQL**

2. **Link Database:**
   - The `DATABASE_URL` should automatically reference your PostgreSQL service
   - Format: `${{Postgres.DATABASE_URL}}`

### Step 4: Deploy and Test

1. **Trigger Redeploy:**
   - After setting variables, Railway will automatically redeploy
   - Or manually trigger: **Deploy** → **Redeploy**

2. **Check Logs:**
   ```bash
   railway logs
   ```

3. **Expected Success Output:**
   ```
   🚄 Railway Environment Detected
   📡 Webhook Mode: True
   🔌 Port: 8080
   ✅ Configuration validation passed
   ✅ Database connected successfully
   🌐 Webhook set successfully
   ```

## 🛠️ Quick Fix Commands

If you have Railway CLI installed:

```bash
# Set variables via CLI
railway variables set BOT_TOKEN="8195373457:AAGFwhtAYNQSt4vFj6BMApQo7Nd2wtrOBZI"
railway variables set BROKER_LINK="your_broker_link"
railway variables set PREMIUM_CHANNEL_ID="-1001234567890"
railway variables set ADMIN_USERNAME="your_username"
railway variables set ADMIN_USER_ID="your_user_id"
railway variables set BOT_MODE="webhook"
railway variables set WEBHOOK_ENABLED="true"

# Redeploy
railway up
```

## 🔍 Debug on Railway

To debug issues on Railway, you can temporarily change the start command to:

```
startCommand = "python railway_debug.py"
```

This will run the debug script and show you exactly what's missing.

## ✅ Verification Checklist

- [ ] All environment variables set in Railway dashboard
- [ ] PostgreSQL service created and linked
- [ ] Bot token is valid (contains `:` character)
- [ ] Channel ID starts with `-100`
- [ ] Admin user ID is numeric
- [ ] Webhook URL matches your Railway domain
- [ ] Deployment logs show successful startup
- [ ] Bot responds to `/start` command

## 🆘 Still Not Working?

1. **Check Railway Logs:**
   ```bash
   railway logs --tail
   ```

2. **Test Webhook URL:**
   - Visit: `https://your-app-name-production.up.railway.app/health`
   - Should return: `{"status": "healthy"}`

3. **Verify Bot Token:**
   - Test with @BotFather on Telegram
   - Ensure bot is not used elsewhere

4. **Check Channel Permissions:**
   - Bot must be admin in premium channel
   - Channel ID format: `-1001234567890`

## 📞 Support

If you continue having issues:
1. Share Railway deployment logs
2. Confirm all environment variables are set
3. Test the debug script output

---

**Note:** Replace placeholder values with your actual bot token, channel ID, and other credentials.