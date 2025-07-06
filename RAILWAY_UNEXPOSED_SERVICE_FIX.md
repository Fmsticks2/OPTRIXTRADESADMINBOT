# 🚄 Railway "Unexposed Service" Issue - Complete Fix Guide

## 🔍 What Does "Unexposed Service" Mean?

When Railway shows your service as "unexposed," it means:
- Your service is running but **not accessible from the internet**
- Railway cannot detect HTTP traffic on the expected port
- The service might be running on the wrong port or not binding correctly
- Health checks are failing or not configured

## 🎯 Root Causes & Solutions

### 1. **Port Binding Issues** (Most Common)

#### ❌ Problem:
Your app isn't binding to Railway's `PORT` environment variable.

#### ✅ Solution:
Ensure your app uses Railway's `PORT` variable:

```python
# In webhook_server.py (ALREADY FIXED)
port = int(os.environ.get("PORT", getattr(config, 'WEBHOOK_PORT', 8080)))
uvicorn.run(
    "webhook.webhook_server:app",
    host="0.0.0.0",  # MUST be 0.0.0.0, not localhost
    port=port,
    log_level=config.LOG_LEVEL.lower()
)
```

### 2. **Missing Health Check Endpoints**

#### ❌ Problem:
Railway needs HTTP endpoints to detect your service is running.

#### ✅ Solution:
Your bot already has health endpoints in `bot_runner.py`:

```python
@health_app.get('/health')
async def health_check():
    return JSONResponse(content={'status': 'healthy'})

@health_app.get('/')
async def home():
    return JSONResponse(content={'message': 'OPTRIXTRADES Bot is running'})
```

### 3. **Railway Configuration Issues**

#### Check Your `railway.toml`:
```toml
[deploy]
startCommand = "python bot_runner.py webhook"  # ✅ Correct
restartPolicyType = "ON_FAILURE"

# Make sure you have the bot service defined
[[services]]
name = "optrixtrades-bot"
source = "."
```

### 4. **Environment Variables Missing**

#### Required Variables for Webhook Mode:
```env
BOT_MODE=webhook
WEBHOOK_ENABLED=true
BOT_TOKEN=your_bot_token
BROKER_LINK=your_broker_link
PREMIUM_CHANNEL_ID=-100xxxxxxxxxx
ADMIN_USERNAME=your_username
ADMIN_USER_ID=your_user_id
```

## 🔧 Step-by-Step Fix Process

### Step 1: Verify Port Configuration

1. **Check Railway Logs:**
   ```bash
   railway logs
   ```
   Look for:
   ```
   Starting server on port 8080
   🌐 Starting combined webhook + health server on port 8080
   ```

2. **Verify PORT Variable:**
   ```bash
   railway variables | grep PORT
   ```
   Should show: `PORT=8080` (or similar)

### Step 2: Test Health Endpoints

1. **Check if your service responds:**
   ```bash
   # Replace with your Railway URL
   curl https://your-app.railway.app/health
   curl https://your-app.railway.app/
   ```

2. **Expected Response:**
   ```json
   {
     "status": "healthy",
     "service": "optrixtrades-bot",
     "mode": "webhook"
   }
   ```

### Step 3: Fix Common Issues

#### Issue A: Service Not Starting
```bash
# Check if all required variables are set
railway variables

# Set missing variables
railway variables set BOT_TOKEN="your_token"
railway variables set BROKER_LINK="your_link"
# ... etc
```

#### Issue B: Wrong Start Command
```bash
# Update railway.toml or set via CLI
railway up --detach
```

#### Issue C: Port Binding to localhost
Ensure your code uses `host="0.0.0.0"` not `host="localhost"`

### Step 4: Force Service Exposure

1. **Generate Public Domain:**
   ```bash
   railway domain
   ```

2. **Or via Dashboard:**
   - Go to your Railway project
   - Click on your service
   - Go to "Settings" → "Networking"
   - Click "Generate Domain"

## 🚨 Emergency Fixes

### Fix 1: Minimal Health Server
If webhook mode fails, force health-only mode:

```bash
# Set to run only health server
railway variables set BOT_MODE="fastapi"
railway up
```

### Fix 2: Debug Mode
Enable debug endpoint to see what's wrong:

```bash
# Visit: https://your-app.railway.app/debug
# This shows environment variables and configuration
```

### Fix 3: Restart with Logs
```bash
# Restart and watch logs
railway up --detach
railway logs --follow
```

## 📊 Verification Checklist

### ✅ Service Should Show as "Exposed" When:
- [ ] App binds to `0.0.0.0:$PORT`
- [ ] Health endpoint `/health` returns 200
- [ ] Root endpoint `/` returns 200
- [ ] All required environment variables are set
- [ ] Railway can reach your service on the assigned port

### 🔍 Debug Commands
```bash
# Check service status
railway status

# View recent logs
railway logs --tail 50

# Check variables
railway variables

# Test health endpoint
curl https://your-app.railway.app/health

# View debug info
curl https://your-app.railway.app/debug
```

## 🎯 Expected Success Indicators

When fixed, you should see:

1. **Railway Dashboard:**
   - Service status: "Active" (green)
   - Service shows as "Exposed"
   - Public URL is accessible

2. **Logs:**
   ```
   🚄 Starting bot in RAILWAY mode...
   🌐 Starting combined webhook + health server on port 8080
   ✅ Database initialized successfully
   ✅ Webhook set successfully
   ```

3. **Health Check:**
   ```bash
   $ curl https://your-app.railway.app/health
   {"status":"healthy","service":"optrixtrades-bot"}
   ```

## 🆘 Still Showing Unexposed?

### Last Resort Fixes:

1. **Redeploy from scratch:**
   ```bash
   railway up --detach
   ```

2. **Check Railway service logs:**
   ```bash
   railway logs --service optrixtrades-bot
   ```

3. **Verify network settings:**
   - Railway Dashboard → Service → Settings → Networking
   - Ensure "Generate Domain" is enabled

4. **Contact Railway Support:**
   If all else fails, Railway support can help diagnose platform-specific issues.

---

**Quick Fix Summary:**
1. Ensure `BOT_MODE=webhook` is set
2. Verify all required variables are configured
3. Check that app binds to `0.0.0.0:$PORT`
4. Test health endpoints
5. Generate public domain if needed

Your service should change from "Unexposed" to "Active" within 1-2 minutes after fixing the underlying issue.