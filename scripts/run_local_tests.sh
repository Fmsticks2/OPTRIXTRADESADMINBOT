#!/bin/bash

echo "🧪 OPTRIXTRADES Local Testing Suite"
echo "=================================="

# Set environment for testing
export DEBUG_MODE=true
export TEST_MODE=true

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    if [ $2 -eq 0 ]; then
        echo -e "${GREEN}✅ $1${NC}"
    else
        echo -e "${RED}❌ $1${NC}"
    fi
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

# Check Python version
echo "🐍 Checking Python version..."
python3 --version
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Python 3 not found${NC}"
    exit 1
fi

# Check if virtual environment is activated
if [[ "$VIRTUAL_ENV" != "" ]]; then
    echo -e "${GREEN}✅ Virtual environment active: $VIRTUAL_ENV${NC}"
else
    print_warning "No virtual environment detected. Consider using one."
fi

# Install/check dependencies
echo ""
echo "📦 Checking dependencies..."
pip install -r requirements.txt > /dev/null 2>&1
print_status "Dependencies installed" $?

# Check environment variables
echo ""
echo "🌍 Checking environment variables..."
if [ -f ".env" ]; then
    echo -e "${GREEN}✅ .env file found${NC}"
else
    echo -e "${RED}❌ .env file not found${NC}"
    echo "Create .env file with required variables"
    exit 1
fi

# Run configuration validation
echo ""
echo "🔧 Validating configuration..."
python3 -c "from config import config; result = config.validate_config(); exit(0 if result['valid'] else 1)"
print_status "Configuration validation" $?

# Run comprehensive system tests
echo ""
echo "🧪 Running comprehensive system tests..."
python3 tests/test_system_comprehensive.py
TEST_RESULT=$?
print_status "System tests" $TEST_RESULT

# Run database tests specifically
echo ""
echo "🗄️  Testing database operations..."
python3 -c "
import asyncio
from database import db_manager

async def test_db():
    try:
        await db_manager.initialize()
        health = await db_manager.health_check()
        print(f'Database: {health[\"status\"]} ({db_manager.db_type})')
        await db_manager.close()
        return health['status'] == 'healthy'
    except Exception as e:
        print(f'Database error: {e}')
        return False

result = asyncio.run(test_db())
exit(0 if result else 1)
"
print_status "Database connection" $?

# Test bot token
echo ""
echo "🤖 Testing bot token..."
python3 -c "
import asyncio
from telegram import Bot
from config import config

async def test_bot():
    try:
        bot = Bot(token=config.BOT_TOKEN)
        info = await bot.get_me()
        print(f'Bot: @{info.username} ({info.first_name})')
        return True
    except Exception as e:
        print(f'Bot token error: {e}')
        return False

result = asyncio.run(test_bot())
exit(0 if result else 1)
"
print_status "Bot token validation" $?

# Test webhook configuration (if enabled)
if grep -q "BOT_MODE=webhook" .env; then
    echo ""
    echo "🌐 Testing webhook configuration..."
    python3 -c "
from config import config
valid = config.WEBHOOK_ENABLED and config.WEBHOOK_PORT and config.WEBHOOK_SECRET_TOKEN
print(f'Webhook config: {\"valid\" if valid else \"invalid\"}')
exit(0 if valid else 1)
"
    print_status "Webhook configuration" $?
fi

# Summary
echo ""
echo "📊 Test Summary"
echo "==============="

if [ $TEST_RESULT -eq 0 ]; then
    echo -e "${GREEN}🎉 All tests passed! System is ready for development.${NC}"
    echo ""
    echo "🚀 Next steps:"
    echo "1. Run: python3 scripts/local_development.py"
    echo "2. Or run: python3 bot_runner.py"
    echo "3. Test your bot in Telegram"
else
    echo -e "${RED}❌ Some tests failed. Check the output above.${NC}"
    echo ""
    echo "🔧 Common fixes:"
    echo "1. Check .env file configuration"
    echo "2. Ensure database is running"
    echo "3. Verify bot token is correct"
    echo "4. Install missing dependencies"
fi

echo ""
echo "📝 Logs available in:"
echo "   - bot.log (main bot logs)"
echo "   - errors.log (error logs)"
echo "   - database.log (database logs)"

exit $TEST_RESULT
