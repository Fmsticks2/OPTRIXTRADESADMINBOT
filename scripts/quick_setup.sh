#!/bin/bash

echo "🚀 OPTRIXTRADES Bot Quick Setup"
echo "================================"

# Install Python dependencies
echo "📦 Installing Python dependencies..."
pip install python-telegram-bot==20.7

echo ""
echo "✅ Dependencies installed!"
echo ""

# Run the test
echo "🧪 Running bot tests..."
python3 fixed_test_bot.py

echo ""
echo "🎯 Setup complete!"
echo "Next: Run 'python3 telegram_bot.py' to start your bot"
