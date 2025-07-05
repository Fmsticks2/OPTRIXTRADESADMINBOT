#!/usr/bin/env python3
"""
Deploy Bot Fixes to Railway
This script helps deploy the UID verification fixes to Railway.
"""

import subprocess
import sys
import os
import requests
from datetime import datetime

def check_git_status():
    """Check if we're in a git repository and have changes"""
    try:
        result = subprocess.run(['git', 'status', '--porcelain'], 
                              capture_output=True, text=True, cwd=os.getcwd())
        if result.returncode == 0:
            return True, result.stdout.strip()
        return False, "Not a git repository"
    except FileNotFoundError:
        return False, "Git not installed"

def deploy_via_git():
    """Deploy using git push"""
    try:
        print("📦 Adding files to git...")
        subprocess.run(['git', 'add', '.'], check=True, cwd=os.getcwd())
        
        print("💾 Committing changes...")
        commit_msg = f"Fix UID verification flow - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        subprocess.run(['git', 'commit', '-m', commit_msg], check=True, cwd=os.getcwd())
        
        print("🚀 Pushing to Railway...")
        subprocess.run(['git', 'push', 'origin', 'main'], check=True, cwd=os.getcwd())
        
        print("✅ Deployment initiated via git push!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Git deployment failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def check_railway_cli():
    """Check if Railway CLI is available"""
    try:
        result = subprocess.run(['railway', '--version'], 
                              capture_output=True, text=True)
        return result.returncode == 0
    except FileNotFoundError:
        return False

def deploy_via_railway_cli():
    """Deploy using Railway CLI"""
    try:
        print("🚀 Deploying via Railway CLI...")
        result = subprocess.run(['railway', 'deploy'], 
                              capture_output=True, text=True, cwd=os.getcwd())
        
        if result.returncode == 0:
            print("✅ Railway CLI deployment successful!")
            print(result.stdout)
            return True
        else:
            print(f"❌ Railway CLI deployment failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Railway CLI error: {e}")
        return False

def show_manual_deployment_guide():
    """Show manual deployment instructions"""
    print("""
🔧 MANUAL DEPLOYMENT REQUIRED

Since automatic deployment isn't available, please deploy manually:

📋 Option 1: Railway Web Interface (Recommended)
1. Go to: https://railway.app/dashboard
2. Find your OPTRIXTRADES project
3. Click on your service
4. Go to "Deployments" tab
5. Click "Deploy" or "Redeploy" button
6. Wait for deployment to complete

📋 Option 2: GitHub Integration
If your project is connected to GitHub:
1. Push changes to your GitHub repository
2. Railway will automatically deploy

📋 Option 3: Install Railway CLI
1. Install: npm install -g @railway/cli
2. Login: railway login
3. Link: railway link
4. Deploy: railway deploy

🎯 After deployment, test with a UID like: ABC123456
""")

def main():
    print("🚀 OPTRIXTRADES Bot Deployment")
    print("=" * 50)
    print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Check if fixes are in place
    if not os.path.exists('main.py'):
        print("❌ main.py not found. Are you in the right directory?")
        return False
    
    print("✅ Bot files found")
    
    # Try different deployment methods
    deployed = False
    
    # Method 1: Git deployment
    git_available, git_status = check_git_status()
    if git_available:
        print("\n🔍 Git repository detected")
        if git_status:
            print(f"📝 Changes detected: {len(git_status.splitlines())} files")
            if deploy_via_git():
                deployed = True
        else:
            print("ℹ️  No changes to commit")
    
    # Method 2: Railway CLI
    if not deployed and check_railway_cli():
        print("\n🛤️  Railway CLI detected")
        if deploy_via_railway_cli():
            deployed = True
    
    # Method 3: Manual instructions
    if not deployed:
        show_manual_deployment_guide()
    
    print("\n" + "=" * 50)
    if deployed:
        print("🎉 Deployment completed! Test your bot now.")
        print("\n🧪 Test by sending a UID like: ABC123456")
        print("Expected response: ✅ UID Received: ABC123456")
    else:
        print("⚠️  Manual deployment required. Follow the guide above.")
    
    return deployed

if __name__ == "__main__":
    main()