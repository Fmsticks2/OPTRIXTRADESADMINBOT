#!/usr/bin/env python3
"""
Railway Debug Script - Diagnose deployment issues
"""

import os
import sys
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def check_environment():
    """Check Railway environment and configuration"""
    print("🔍 Railway Environment Debug")
    print("=" * 40)
    
    # Check if running on Railway
    is_railway = os.environ.get('RAILWAY_ENVIRONMENT') is not None
    print(f"🚄 Railway Environment: {is_railway}")
    
    if is_railway:
        print(f"📍 Railway Environment: {os.environ.get('RAILWAY_ENVIRONMENT')}")
        print(f"🔌 Port: {os.environ.get('PORT', 'Not set')}")
        print(f"🌐 Railway Public Domain: {os.environ.get('RAILWAY_PUBLIC_DOMAIN', 'Not set')}")
    
    # Check critical environment variables
    critical_vars = [
        'BOT_TOKEN',
        'BROKER_LINK', 
        'PREMIUM_CHANNEL_ID',
        'ADMIN_USERNAME',
        'ADMIN_USER_ID',
        'DATABASE_URL'
    ]
    
    print("\n🔑 Critical Environment Variables:")
    missing_vars = []
    for var in critical_vars:
        value = os.environ.get(var)
        if value:
            # Mask sensitive values
            if 'TOKEN' in var or 'URL' in var:
                display_value = f"{value[:10]}..." if len(value) > 10 else "***"
            else:
                display_value = value
            print(f"  ✅ {var}: {display_value}")
        else:
            print(f"  ❌ {var}: Not set")
            missing_vars.append(var)
    
    # Check webhook configuration
    print("\n🌐 Webhook Configuration:")
    webhook_vars = ['BOT_MODE', 'WEBHOOK_ENABLED', 'WEBHOOK_URL', 'WEBHOOK_PORT']
    for var in webhook_vars:
        value = os.environ.get(var, 'Not set')
        print(f"  📡 {var}: {value}")
    
    # Check Python path and imports
    print("\n🐍 Python Environment:")
    print(f"  📁 Current Working Directory: {os.getcwd()}")
    print(f"  📂 Script Directory: {os.path.dirname(os.path.abspath(__file__))}")
    print(f"  🔍 Python Path: {sys.path[:3]}...")  # Show first 3 entries
    
    # Test imports
    print("\n📦 Import Tests:")
    try:
        from config import config
        print("  ✅ config module imported successfully")
        print(f"  🤖 Bot Token (masked): {config.BOT_TOKEN[:10] if config.BOT_TOKEN else 'Not set'}...")
    except Exception as e:
        print(f"  ❌ Failed to import config: {e}")
    
    try:
        from webhook.webhook_server import run_webhook_server
        print("  ✅ webhook_server module imported successfully")
    except Exception as e:
        print(f"  ❌ Failed to import webhook_server: {e}")
    
    try:
        from database.connection import DatabaseManager
        print("  ✅ database module imported successfully")
    except Exception as e:
        print(f"  ❌ Failed to import database: {e}")
    
    # Summary
    print("\n📊 Summary:")
    if missing_vars:
        print(f"  ❌ Missing {len(missing_vars)} critical variables: {', '.join(missing_vars)}")
        print("  🔧 Action Required: Set missing environment variables in Railway")
        return False
    else:
        print("  ✅ All critical environment variables are set")
        print("  🚀 Environment appears ready for deployment")
        return True

def test_webhook_server():
    """Test webhook server startup"""
    print("\n🌐 Testing Webhook Server Startup...")
    try:
        from webhook.webhook_server import run_webhook_server
        print("  ✅ Webhook server import successful")
        print("  🚀 Ready to start webhook server")
        return True
    except Exception as e:
        print(f"  ❌ Webhook server test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main debug function"""
    print("🚀 OPTRIXTRADES Railway Debug Tool")
    print("=" * 50)
    
    # Check environment
    env_ok = check_environment()
    
    # Test webhook server if environment is OK
    if env_ok:
        webhook_ok = test_webhook_server()
        
        if webhook_ok:
            print("\n🎉 All checks passed! Bot should work on Railway.")
            print("\n🔧 If bot still doesn't work, check Railway logs for runtime errors.")
        else:
            print("\n❌ Webhook server test failed. Check import errors above.")
    else:
        print("\n❌ Environment check failed. Fix missing variables first.")
    
    print("\n" + "=" * 50)

if __name__ == "__main__":
    main()