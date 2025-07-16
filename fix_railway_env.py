#!/usr/bin/env python3
"""
Quick Railway Environment Variables Setup Script
"""

import subprocess
import sys
import os
from typing import Dict, List

def run_railway_command(command: List[str]) -> bool:
    """Run a railway CLI command"""
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        print(f"✅ {' '.join(command)}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed: {' '.join(command)}")
        print(f"   Error: {e.stderr}")
        return False
    except FileNotFoundError:
        print("❌ Railway CLI not found. Please install it first:")
        print("   npm install -g @railway/cli")
        return False

def check_railway_cli() -> bool:
    """Check if Railway CLI is installed"""
    try:
        subprocess.run(['railway', '--version'], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def set_environment_variables() -> bool:
    """Set all required environment variables"""
    print("🔧 Setting Railway Environment Variables...")
    print("=" * 50)
    
    # Required variables with current values from your bot
    variables = {
        'BOT_TOKEN': '8195373457:AAGFwhtAYNQSt4vFj6BMApQo7Nd2wtrOBZI',
        'BOT_MODE': 'webhook',
        'WEBHOOK_ENABLED': 'true',
        'DATABASE_TYPE': 'postgresql',
        # These need to be set by user
        'BROKER_LINK': 'PLEASE_SET_YOUR_BROKER_LINK',
        'PREMIUM_CHANNEL_ID': 'PLEASE_SET_YOUR_CHANNEL_ID',  # Format: -1001234567890
        'ADMIN_USERNAME': 'PLEASE_SET_YOUR_USERNAME',
        'ADMIN_USER_ID': 'PLEASE_SET_YOUR_USER_ID',
    }
    
    success_count = 0
    total_count = len(variables)
    
    for var_name, var_value in variables.items():
        if var_value.startswith('PLEASE_SET_'):
            print(f"⚠️  {var_name}: {var_value}")
            print(f"   You need to manually set this variable in Railway dashboard")
            continue
            
        success = run_railway_command(['railway', 'variables', 'set', f'{var_name}={var_value}'])
        if success:
            success_count += 1
    
    print(f"\n📊 Results: {success_count}/{total_count} variables set successfully")
    return success_count > 0

def deploy_bot() -> bool:
    """Deploy the bot to Railway"""
    print("\n🚀 Deploying bot to Railway...")
    return run_railway_command(['railway', 'up'])

def check_deployment() -> bool:
    """Check deployment status"""
    print("\n📋 Checking deployment status...")
    return run_railway_command(['railway', 'status'])

def show_logs() -> bool:
    """Show recent logs"""
    print("\n📜 Recent deployment logs:")
    return run_railway_command(['railway', 'logs', '--tail', '50'])

def main():
    """Main function"""
    print("🚄 Railway Environment Setup Tool")
    print("=" * 50)
    
    # Check Railway CLI
    if not check_railway_cli():
        print("❌ Railway CLI not found!")
        print("\n📥 Install Railway CLI:")
        print("   npm install -g @railway/cli")
        print("   railway login")
        print("   railway link")
        return
    
    print("✅ Railway CLI found")
    
    # Set environment variables
    if set_environment_variables():
        print("\n✅ Basic environment variables set successfully!")
        
        # Show manual steps
        print("\n⚠️  MANUAL STEPS REQUIRED:")
        print("   1. Go to Railway Dashboard → Your Project → Variables")
        print("   2. Set these variables manually:")
        print("      - BROKER_LINK: Your broker referral link")
        print("      - PREMIUM_CHANNEL_ID: Your Telegram channel ID (format: -1001234567890)")
        print("      - ADMIN_USERNAME: Your Telegram username")
        print("      - ADMIN_USER_ID: Your Telegram user ID")
        print("   3. Ensure PostgreSQL service is added and linked")
        
        # Ask if user wants to deploy
        response = input("\n🚀 Deploy now? (y/n): ").lower().strip()
        if response == 'y':
            if deploy_bot():
                print("\n✅ Deployment initiated!")
                
                # Check status
                check_deployment()
                
                # Show logs
                input("\nPress Enter to view logs...")
                show_logs()
            else:
                print("\n❌ Deployment failed")
        else:
            print("\n📝 To deploy later, run: railway up")
    else:
        print("\n❌ Failed to set environment variables")
        print("\n🔧 Manual setup required:")
        print("   1. railway login")
        print("   2. railway link (select your project)")
        print("   3. Set variables in Railway dashboard")

if __name__ == "__main__":
    main()