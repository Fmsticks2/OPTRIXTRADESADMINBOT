# 🌐 OPTRIXTRADES Bot Webhook Setup Guide

## Why Use Webhooks?

### Polling vs Webhooks

**Polling (Current Setup):**
- ✅ Simple to set up
- ✅ Works everywhere
- ❌ Higher server load
- ❌ Slower response times
- ❌ Not suitable for serverless

**Webhooks (Recommended for Production):**
- ✅ Instant message delivery
- ✅ Lower server load
- ✅ Better for production
- ✅ Required for some platforms
- ❌ Requires public URL

## Quick Setup Options

### Option 1: Railway Deployment (Recommended)

1. **Deploy to Railway:**
   \`\`\`bash
   # Push your code to GitHub
   git add .
   git commit -m "Add webhook support"
   git push origin main
   \`\`\`

2. **Set Environment Variables in Railway:**
   \`\`\`env
   BOT_MODE=webhook
   WEBHOOK_ENABLED=true
   WEBHOOK_PORT=8000
   \`\`\`

3. **Get Your Railway URL:**
   - Railway will provide a URL like: `https://your-app.railway.app`

4. **Set Webhook:**
   \`\`\`bash
   python webhook/webhook_setup.py
   # Enter your Railway URL + /webhook/YOUR_BOT_TOKEN
   \`\`\`

### Option 2: Local Testing with Ngrok

1. **Install Ngrok:**
   \`\`\`bash
   # Download from https://ngrok.com/download
   # Or use package manager:
   brew install ngrok  # macOS
   choco install ngrok # Windows
   \`\`\`

2. **Test Locally:**
   \`\`\`bash
   python webhook/ngrok_helper.py
   \`\`\`

3. **Start Webhook Server:**
   \`\`\`bash
   python webhook/webhook_server.py
   \`\`\`

### Option 3: Manual Setup

1. **Start Webhook Server:**
   \`\`\`bash
   BOT_MODE=webhook python bot_runner.py
   \`\`\`

2. **Set Webhook URL:**
   \`\`\`bash
   python webhook/webhook_setup.py
   \`\`\`

## Environment Variables

Add to your `.env` file:

\`\`\`env
# Webhook Mode
BOT_MODE=webhook
WEBHOOK_ENABLED=true
WEBHOOK_PORT=8000
WEBHOOK_SECRET_TOKEN=your-secret-token-here

# Your webhook URL (Railway/production)
WEBHOOK_URL=https://your-domain.com
\`\`\`

## Webhook Endpoints

Your webhook server provides these endpoints:

- `GET /` - Server status
- `GET /health` - Health check
- `POST /webhook/{BOT_TOKEN}` - Telegram webhook
- `POST /admin/set_webhook` - Set webhook URL
- `DELETE /admin/delete_webhook` - Delete webhook
- `GET /admin/webhook_info` - Webhook information

## Testing Your Webhook

### 1. Health Check
\`\`\`bash
curl https://your-domain.com/health
\`\`\`

### 2. Webhook Info
\`\`\`bash
curl https://your-domain.com/admin/webhook_info
\`\`\`

### 3. Test Bot
- Send `/start` to your bot in Telegram
- Check webhook server logs

## Production Deployment

### Railway Deployment

1. **Create railway.yml:**
   \`\`\`yaml
   build:
     builder: DOCKERFILE
   deploy:
     startCommand: python webhook/webhook_server.py
   \`\`\`

2. **Set Environment Variables:**
   - `BOT_MODE=webhook`
   - `WEBHOOK_ENABLED=true`
   - All your existing bot variables

3. **Deploy:**
   - Railway auto-deploys from GitHub
   - Get your Railway URL
   - Set webhook using the setup script

### Other Platforms

**Heroku:**
\`\`\`bash
# Procfile
web: python webhook/webhook_server.py
\`\`\`

**DigitalOcean App Platform:**
\`\`\`yaml
# .do/app.yaml
name: optrixtrades-bot
services:
- name: webhook
  source_dir: /
  github:
    repo: your-username/your-repo
    branch: main
  run_command: python webhook/webhook_server.py
\`\`\`

## Security Features

### Webhook Secret Token
\`\`\`env
WEBHOOK_SECRET_TOKEN=your-random-secret-here
\`\`\`

### HTTPS Required
- Telegram requires HTTPS for webhooks
- Railway/Heroku provide HTTPS automatically
- For custom domains, ensure SSL certificate

### Rate Limiting
- Built-in rate limiting in webhook server
- Configurable via environment variables

## Troubleshooting

### Common Issues

1. **"Webhook not receiving updates"**
   - Check webhook URL is publicly accessible
   - Verify HTTPS is working
   - Check Telegram webhook info

2. **"Invalid webhook URL"**
   - Must be HTTPS
   - Must be publicly accessible
   - Check URL format

3. **"Bot not responding"**
   - Check webhook server logs
   - Verify bot token is correct
   - Test health endpoint

### Debug Commands

\`\`\`bash
# Check webhook status
python webhook/webhook_setup.py

# View server logs
tail -f webhook.log

# Test webhook URL
curl -X POST https://your-domain.com/webhook/YOUR_BOT_TOKEN \
  -H "Content-Type: application/json" \
  -d '{"update_id": 1, "message": {"message_id": 1, "date": 1234567890, "chat": {"id": 123, "type": "private"}, "from": {"id": 123, "is_bot": false, "first_name": "Test"}, "text": "/start"}}'
\`\`\`

## Performance Benefits

### Webhook vs Polling Performance

| Metric | Polling | Webhook |
|--------|---------|---------|
| Response Time | 1-3 seconds | < 100ms |
| Server Load | High | Low |
| Scalability | Limited | Excellent |
| Real-time | No | Yes |
| Resource Usage | High | Low |

## Migration from Polling

To migrate your existing bot:

1. **Update Environment:**
   \`\`\`env
   BOT_MODE=webhook
   \`\`\`

2. **Deploy Webhook Server:**
   \`\`\`bash
   python webhook/webhook_server.py
   \`\`\`

3. **Set Webhook:**
   \`\`\`bash
   python webhook/webhook_setup.py
   \`\`\`

4. **Test Functionality:**
   - All existing features work the same
   - Admin commands work identically
   - Auto-verification functions normally

Your bot is now production-ready with webhook support! 🚀
