#!/usr/bin/env python3
"""
Configuration validation script for OPTRIXTRADES bot
Run this before deploying to catch configuration issues
"""

import os
import sys
from config import config

def main():
    print("🔧 OPTRIXTRADES Bot Configuration Validator")
    print("=" * 50)
    
    # Run validation
    validation_result = config.validate_config()
    
    # Display results
    if validation_result['valid']:
        print("✅ Configuration is valid!")
    else:
        print("❌ Configuration has errors:")
        for error in validation_result['errors']:
            print(f"  - {error}")
    
    if validation_result['warnings']:
        print("\n⚠️  Warnings:")
        for warning in validation_result['warnings']:
            print(f"  - {warning}")
    
    # Display configuration summary
    print("\n" + config.get_summary())
    
    # Check critical settings
    print("\n🔍 Critical Settings Check:")
    
    critical_checks = [
        ("Bot Token", bool(config.BOT_TOKEN and ':' in config.BOT_TOKEN)),
        ("Admin User ID", bool(config.ADMIN_USER_ID and config.ADMIN_USER_ID.isdigit())),
        ("Broker Link", bool(config.BROKER_LINK and config.BROKER_LINK.startswith('https://'))),
        ("Premium Channel", bool(config.PREMIUM_CHANNEL_ID)),
        ("Auto-Verification", config.AUTO_VERIFY_ENABLED),
        ("Database Path", bool(config.DATABASE_PATH))
    ]
    
    for check_name, check_result in critical_checks:
        status = "✅" if check_result else "❌"
        print(f"  {status} {check_name}")
    
    # Environment-specific recommendations
    print("\n💡 Recommendations:")
    
    if config.DEBUG_MODE:
        print("  - Set DEBUG_MODE=false for production")
    
    if config.AUTO_VERIFY_ENABLED and config.DAILY_AUTO_APPROVAL_LIMIT > 500:
        print("  - Consider lowering DAILY_AUTO_APPROVAL_LIMIT for security")
    
    if not config.RATE_LIMIT_ENABLED:
        print("  - Enable RATE_LIMIT_ENABLED for production")
    
    if config.ADMIN_USER_ID == "123456789":
        print("  - ⚠️  CRITICAL: Update ADMIN_USER_ID with your actual Telegram user ID")
    
    # Exit with appropriate code
    if not validation_result['valid']:
        print("\n❌ Fix configuration errors before deploying!")
        sys.exit(1)
    else:
        print("\n🎉 Configuration is ready for deployment!")
        sys.exit(0)

if __name__ == '__main__':
    main()
