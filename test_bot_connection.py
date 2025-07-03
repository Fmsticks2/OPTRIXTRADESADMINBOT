#!/usr/bin/env python3
"""
Quick bot connection and webhook test script
Use this to verify your bot configuration is working
"""

import asyncio
import sys
from webhook.webhook_setup import test_bot_token, WebhookManager
from config import config

async def main():
    """Main test function"""
    print("🔧 OPTRIXTRADES Bot Connection Test")
    print("=" * 40)
    
    # Test 1: Configuration validation
    print("\n1️⃣ Testing Configuration...")
    validation_result = config.validate_config()
    
    if validation_result['valid']:
        print("   ✅ Configuration is valid")
    else:
        print("   ❌ Configuration has errors:")
        for error in validation_result['errors']:
            print(f"      - {error}")
    
    if validation_result['warnings']:
        print("   ⚠️  Warnings:")
        for warning in validation_result['warnings']:
            print(f"      - {warning}")
    
    # Test 2: Bot token validation
    print("\n2️⃣ Testing Bot Token...")
    token_valid = await test_bot_token()
    
    if not token_valid:
        print("\n❌ Bot token test failed. Cannot proceed with webhook tests.")
        return False
    
    # Test 3: Webhook information
    print("\n3️⃣ Testing Webhook Status...")
    try:
        manager = WebhookManager()
        webhook_info = await manager.get_webhook_info()
        
        if webhook_info:
            if webhook_info.url:
                print("   ✅ Webhook is configured")
                if webhook_info.last_error_message:
                    print(f"   ⚠️  Last error: {webhook_info.last_error_message}")
            else:
                print("   ℹ️  No webhook configured (polling mode)")
        else:
            print("   ❌ Could not retrieve webhook information")
            
    except Exception as e:
        print(f"   ❌ Webhook test failed: {e}")
    
    # Summary
    print("\n📊 Test Summary:")
    print(f"   Bot Token: {'✅ Valid' if token_valid else '❌ Invalid'}")
    print(f"   Configuration: {'✅ Valid' if validation_result['valid'] else '❌ Invalid'}")
    
    if token_valid and validation_result['valid']:
        print("\n🎉 Your bot is ready to use!")
        return True
    else:
        print("\n⚠️  Please fix the issues above before using the bot.")
        return False

if __name__ == '__main__':
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⏹️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        sys.exit(1)