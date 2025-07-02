import subprocess
import sys
import os

def install_package(package):
    """Install a Python package using pip"""
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        return True
    except subprocess.CalledProcessError:
        return False

def main():
    print("🔧 Installing OPTRIXTRADES Bot Dependencies...")
    print("=" * 50)
    
    # List of required packages
    packages = [
        "python-telegram-bot==20.7",
        "asyncio",
        "sqlite3"  # This is built-in, but we'll check it
    ]
    
    success_count = 0
    
    for package in packages:
        print(f"📦 Installing {package}...")
        if package == "sqlite3":
            # sqlite3 is built-in, just check if it's available
            try:
                import sqlite3
                print(f"   ✅ {package} - Already available (built-in)")
                success_count += 1
            except ImportError:
                print(f"   ❌ {package} - Not available")
        elif package == "asyncio":
            # asyncio is built-in in Python 3.7+
            try:
                import asyncio
                print(f"   ✅ {package} - Already available (built-in)")
                success_count += 1
            except ImportError:
                print(f"   ❌ {package} - Not available")
        else:
            if install_package(package):
                print(f"   ✅ {package} - Installed successfully")
                success_count += 1
            else:
                print(f"   ❌ {package} - Installation failed")
    
    print("=" * 50)
    if success_count == len(packages):
        print("🎉 All dependencies installed successfully!")
        print("✅ Ready to run the bot!")
    else:
        print(f"⚠️  {len(packages) - success_count} dependencies failed to install")
        print("Please install them manually:")
        print("pip install python-telegram-bot==20.7")
    
    print("=" * 50)

if __name__ == '__main__':
    main()
