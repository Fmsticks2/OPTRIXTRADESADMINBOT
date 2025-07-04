# 🚀 OPTRIXTRADES Bot Setup Guide

## Step 1: Configure Environment Variables

### 1.1 Get Your Admin User ID
Before setting up the bot, you need your Telegram user ID:

1. Open Telegram
2. Search for `@userinfobot`
3. Start a chat and send any message
4. Copy your **User ID** (numeric value)

### 1.2 Update .env File
Open the `.env` file and update these critical values:

\`\`\`env
# REQUIRED: Replace with your actual Telegram user ID
ADMIN_USER_ID=YOUR_ACTUAL_USER_ID_HERE

# Optional: Customize these settings
AUTO_VERIFY_ENABLED=true          # Set to false for manual-only verification
MIN_UID_LENGTH=6                  # Adjust based on your broker's UID format
MAX_UID_LENGTH=20                 # Adjust based on your broker's UID format
DEBUG_MODE=false                  # Set to true for development/testing
\`\`\`

## Step 2: Install Dependencies

\`\`\`bash
pip install -r requirements.txt
\`\`\`

## Step 3: Test Configuration

```python
python -c "from config import config; print(config.get_summary())"
