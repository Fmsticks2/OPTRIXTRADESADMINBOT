import subprocess
import sys
import os

def install_dependencies():
    """Install required dependencies"""
    print("🔧 Installing dependencies...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "python-telegram-bot==20.7"])
        print("✅ Dependencies installed successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install dependencies: {e}")
        return False

def run_test():
    """Run the bot test"""
    print("🧪 Running bot tests...")
    try:
        result = subprocess.run([sys.executable, "fixed_test_bot.py"], 
                              capture_output=True, text=True, cwd="scripts")
        print(result.stdout)
        if result.stderr:
            print("Errors:", result.stderr)
        return result.returncode == 0
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

def main():
    print("🚀 OPTRIXTRADES Bot Setup & Test")
    print("=" * 50)
    
    # Step 1: Install dependencies
    if not install_dependencies():
        print("❌ Setup failed - could not install dependencies")
        return
    
    print()
    
    # Step 2: Run tests
    if run_test():
        print("🎉 Setup completed successfully!")
        print("Your bot is ready to use!")
    else:
        print("⚠️  Some tests failed, but basic setup is complete")
    
    print("=" * 50)
    print("📋 Manual steps to complete:")
    print("1. Create your bot with @BotFather if not done")
    print("2. Add your bot to the premium channel as admin")
    print("3. Run: python telegram_bot.py")

if __name__ == '__main__':
    main()
