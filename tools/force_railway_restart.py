#!/usr/bin/env python3
"""
Force Railway restart by making a deployment trigger change
"""

import os
import requests
from datetime import datetime

def check_current_deployment():
    """Check current Railway deployment"""
    print("=== Checking Current Railway Deployment ===")
    
    try:
        # Test the health endpoint
        response = requests.get("https://web-production-54a4.up.railway.app/health", timeout=10)
        print(f"Health endpoint status: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ Railway service is running")
        else:
            print(f"❌ Railway service returned: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Railway service check failed: {e}")

def create_deployment_trigger():
    """Create a file change to trigger redeployment"""
    print("\n=== Creating Deployment Trigger ===")
    
    # Create a timestamp file to force redeployment
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    trigger_content = f"# Deployment trigger - {timestamp}\n# This file forces Railway to redeploy\nDEPLOYMENT_TIMESTAMP = '{timestamp}'\n"
    
    try:
        with open('deployment_trigger.py', 'w') as f:
            f.write(trigger_content)
        print(f"✅ Created deployment_trigger.py with timestamp: {timestamp}")
        return True
    except Exception as e:
        print(f"❌ Failed to create trigger file: {e}")
        return False

def main():
    print("🚀 Force Railway Restart Script")
    print("=" * 50)
    
    # Check current deployment
    check_current_deployment()
    
    # Create trigger file
    if create_deployment_trigger():
        print("\n📝 Next Steps:")
        print("1. Run: git add deployment_trigger.py")
        print("2. Run: git commit -m 'Force redeploy - trigger restart'")
        print("3. Run: git push origin main")
        print("4. Wait 2-3 minutes for Railway to redeploy")
        print("5. Test the bot again with a UID")
        
        print("\n⚠️  The error 'update_user_data() takes 1 positional argument but 2 were given'")
        print("    should disappear after the redeployment completes.")
    else:
        print("\n❌ Failed to create deployment trigger")

if __name__ == "__main__":
    main()