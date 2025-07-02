"""
Railway deployment helper script
Automates Railway deployment with PostgreSQL setup
"""

import os
import sys
import subprocess
import json
import time
from typing import Dict, Any, Optional

class RailwayDeployer:
    """Railway deployment automation"""
    
    def __init__(self):
        self.project_name = "optrixtrades-bot"
        self.service_name = "optrixtrades-bot"
        self.postgres_service = "postgres"
    
    def deploy_to_railway(self):
        """Complete Railway deployment process"""
        print("🚀 OPTRIXTRADES Railway Deployment")
        print("=" * 50)
        
        # Step 1: Check Railway CLI
        self.check_railway_cli()
        
        # Step 2: Login to Railway
        self.railway_login()
        
        # Step 3: Create/connect project
        self.setup_railway_project()
        
        # Step 4: Add PostgreSQL service
        self.add_postgresql_service()
        
        # Step 5: Set environment variables
        self.set_environment_variables()
        
        # Step 6: Deploy application
        self.deploy_application()
        
        # Step 7: Set webhook URL
        self.setup_webhook()
        
        print("\n🎉 Deployment completed successfully!")
        self.print_deployment_info()
    
    def check_railway_cli(self):
        """Check if Railway CLI is installed"""
        print("🔧 Checking Railway CLI...")
        
        try:
            result = subprocess.run(['railway', '--version'], 
                                  capture_output=True, text=True, check=True)
            print(f"   ✅ Railway CLI found: {result.stdout.strip()}")
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("   ❌ Railway CLI not found")
            print("\n💡 Install Railway CLI:")
            print("   npm install -g @railway/cli")
            print("   or")
            print("   curl -fsSL https://railway.app/install.sh | sh")
            sys.exit(1)
    
    def railway_login(self):
        """Login to Railway"""
        print("\n🔐 Railway Authentication...")
        
        try:
            # Check if already logged in
            result = subprocess.run(['railway', 'whoami'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                print(f"   ✅ Already logged in: {result.stdout.strip()}")
                return
        except:
            pass
        
        print("   🌐 Opening Railway login...")
        try:
            subprocess.run(['railway', 'login'], check=True)
            print("   ✅ Login successful")
        except subprocess.CalledProcessError:
            print("   ❌ Login failed")
            sys.exit(1)
    
    def setup_railway_project(self):
        """Create or connect to Railway project"""
        print("\n📁 Setting up Railway project...")
        
        try:
            # Try to link existing project
            subprocess.run(['railway', 'link'], input='y\n', 
                         text=True, capture_output=True)
            print("   ✅ Connected to existing project")
        except:
            # Create new project
            try:
                subprocess.run(['railway', 'init', self.project_name], 
                             check=True, capture_output=True)
                print(f"   ✅ Created new project: {self.project_name}")
            except subprocess.CalledProcessError:
                print("   ❌ Failed to create project")
                sys.exit(1)
    
    def add_postgresql_service(self):
        """Add PostgreSQL service to Railway project"""
        print("\n🗄️  Adding PostgreSQL service...")
        
        try:
            # Add PostgreSQL plugin
            result = subprocess.run([
                'railway', 'add', '--plugin', 'postgresql'
            ], capture_output=True, text=True, check=True)
            
            print("   ✅ PostgreSQL service added")
            
            # Wait for service to be ready
            print("   ⏳ Waiting for PostgreSQL to initialize...")
            time.sleep(10)
            
        except subprocess.CalledProcessError as e:
            print(f"   ⚠️  PostgreSQL service may already exist: {e}")
    
    def set_environment_variables(self):
        """Set environment variables in Railway"""
        print("\n🌍 Setting environment variables...")
        
        # Read current .env file
        env_vars = self.read_env_file()
        
        # Railway-specific variables
        railway_vars = {
            'BOT_MODE': 'webhook',
            'WEBHOOK_ENABLED': 'true',
            'DATABASE_TYPE': 'postgresql',
            'AUTO_MIGRATE_ON_START': 'true',
            'RAILWAY_ENVIRONMENT': 'production'
        }
        
        # Combine variables
        all_vars = {**env_vars, **railway_vars}
        
        # Set each variable
        for key, value in all_vars.items():
            if key and value and not key.startswith('#'):
                try:
                    subprocess.run([
                        'railway', 'variables', 'set', f'{key}={value}'
                    ], check=True, capture_output=True)
                    print(f"   ✅ Set {key}")
                except subprocess.CalledProcessError:
                    print(f"   ⚠️  Failed to set {key}")
        
        print(f"   📊 Set {len(all_vars)} environment variables")
    
    def read_env_file(self) -> Dict[str, str]:
        """Read environment variables from .env file"""
        env_vars = {}
        
        if not os.path.exists('.env'):
            print("   ⚠️  .env file not found")
            return env_vars
        
        with open('.env', 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip()
        
        return env_vars
    
    def deploy_application(self):
        """Deploy the application to Railway"""
        print("\n🚀 Deploying application...")
        
        try:
            # Deploy using Railway
            result = subprocess.run([
                'railway', 'up', '--detach'
            ], capture_output=True, text=True, check=True)
            
            print("   ✅ Application deployed successfully")
            print(f"   📝 Deployment output: {result.stdout.strip()}")
            
            # Wait for deployment to complete
            print("   ⏳ Waiting for deployment to complete...")
            time.sleep(30)
            
        except subprocess.CalledProcessError as e:
            print(f"   ❌ Deployment failed: {e}")
            print(f"   📝 Error output: {e.stderr}")
            sys.exit(1)
    
    def setup_webhook(self):
        """Setup webhook URL after deployment"""
        print("\n🌐 Setting up webhook...")
        
        try:
            # Get Railway domain
            result = subprocess.run([
                'railway', 'domain'
            ], capture_output=True, text=True, check=True)
            
            domain = result.stdout.strip()
            if domain:
                webhook_url = f"https://{domain}"
                print(f"   ✅ Railway domain: {webhook_url}")
                
                # Set webhook URL environment variable
                subprocess.run([
                    'railway', 'variables', 'set', f'WEBHOOK_URL={webhook_url}'
                ], check=True, capture_output=True)
                
                print("   ✅ Webhook URL configured")
            else:
                print("   ⚠️  Could not get Railway domain")
                
        except subprocess.CalledProcessError:
            print("   ⚠️  Could not setup webhook automatically")
            print("   💡 Set webhook manually after deployment")
    
    def print_deployment_info(self):
        """Print deployment information"""
        print("\n📋 Deployment Information")
        print("=" * 50)
        
        try:
            # Get project info
            result = subprocess.run([
                'railway', 'status'
            ], capture_output=True, text=True, check=True)
            
            print("🚀 Railway Status:")
            print(result.stdout)
            
        except:
            pass
        
        print("\n🔧 Next Steps:")
        print("1. Check Railway dashboard for deployment status")
        print("2. Monitor logs: railway logs")
        print("3. Test your bot in Telegram")
        print("4. Set webhook URL if not done automatically")
        print("5. Add bot to your premium channel as admin")
        
        print("\n📊 Useful Commands:")
        print("   railway logs          - View application logs")
        print("   railway status        - Check deployment status")
        print("   railway variables     - View environment variables")
        print("   railway domain        - Get application URL")
        print("   railway shell         - Access application shell")

def main():
    """Main deployment function"""
    deployer = RailwayDeployer()
    
    try:
        # Confirm deployment
        print("🚀 OPTRIXTRADES Railway Deployment")
        print("=" * 50)
        print("This will deploy your bot to Railway with PostgreSQL.")
        print("Make sure you have:")
        print("✅ Railway CLI installed")
        print("✅ .env file configured")
        print("✅ Bot tested locally")
        print()
        
        confirm = input("Proceed with deployment? (y/N): ").strip().lower()
        if confirm != 'y':
            print("Deployment cancelled.")
            return
        
        deployer.deploy_to_railway()
        
    except KeyboardInterrupt:
        print("\n🛑 Deployment interrupted")
    except Exception as e:
        print(f"\n❌ Deployment failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
