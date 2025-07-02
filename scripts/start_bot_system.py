import subprocess
import sys
import time
import threading

def run_main_bot():
    """Run the main bot"""
    print("🤖 Starting Main Bot...")
    try:
        subprocess.run([sys.executable, "telegram_bot.py"])
    except KeyboardInterrupt:
        print("Main bot stopped")

def run_scheduler():
    """Run the scheduler"""
    print("⏰ Starting Scheduler...")
    time.sleep(5)  # Wait 5 seconds before starting scheduler
    try:
        subprocess.run([sys.executable, "bot_scheduler.py"])
    except KeyboardInterrupt:
        print("Scheduler stopped")

def main():
    print("🚀 OPTRIXTRADES Bot System Starting...")
    print("=" * 50)
    print("This will start both:")
    print("1. Main Bot (handles user interactions)")
    print("2. Scheduler (handles follow-up messages)")
    print("=" * 50)
    
    try:
        # Start main bot in a thread
        bot_thread = threading.Thread(target=run_main_bot)
        bot_thread.daemon = True
        bot_thread.start()
        
        # Start scheduler in main thread
        run_scheduler()
        
    except KeyboardInterrupt:
        print("\n🛑 System stopped by user")
    except Exception as e:
        print(f"\n❌ System error: {e}")

if __name__ == '__main__':
    main()
