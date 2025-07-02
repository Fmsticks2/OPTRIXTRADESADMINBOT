"""
Comprehensive system testing for OPTRIXTRADES bot with PostgreSQL
Tests all components including database, webhook, and bot functionality
"""

import asyncio
import pytest
import logging
import os
import sys
from datetime import datetime
from typing import Dict, Any

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import config
from database import db_manager, get_user_data, create_user, update_user_data, log_interaction
from utils.error_handler import error_handler_instance

# Configure test logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SystemTester:
    """Comprehensive system testing class"""
    
    def __init__(self):
        self.test_results = {}
        self.test_user_id = 999999999
        self.failed_tests = []
        self.passed_tests = []
    
    async def run_all_tests(self) -> Dict[str, Any]:
        """Run all system tests"""
        logger.info("🧪 Starting Comprehensive System Tests")
        logger.info("=" * 60)
        
        test_methods = [
            self.test_configuration,
            self.test_database_connection,
            self.test_database_operations,
            self.test_database_migrations,
            self.test_user_operations,
            self.test_verification_queue,
            self.test_error_handling,
            self.test_bot_token,
            self.test_webhook_configuration,
            self.test_environment_variables,
            self.test_logging_system,
            self.test_database_performance
        ]
        
        for test_method in test_methods:
            try:
                await test_method()
                self.passed_tests.append(test_method.__name__)
            except Exception as e:
                logger.error(f"❌ {test_method.__name__} failed: {e}")
                self.failed_tests.append((test_method.__name__, str(e)))
        
        return self._generate_test_report()
    
    async def test_configuration(self):
        """Test configuration validation"""
        logger.info("🔧 Testing Configuration...")
        
        # Test required environment variables
        required_vars = [
            'BOT_TOKEN', 'BROKER_LINK', 'PREMIUM_CHANNEL_ID', 
            'ADMIN_USERNAME', 'ADMIN_USER_ID'
        ]
        
        for var in required_vars:
            value = getattr(config, var, None)
            assert value, f"Missing required config: {var}"
        
        # Test bot token format
        assert ':' in config.BOT_TOKEN, "Invalid bot token format"
        
        # Test database configuration
        if config.DATABASE_TYPE == 'postgresql':
            assert config.DATABASE_URL or (config.POSTGRES_HOST and config.POSTGRES_DB), "Missing PostgreSQL configuration"
        
        logger.info("   ✅ Configuration validation passed")
    
    async def test_database_connection(self):
        """Test database connection"""
        logger.info("🗄️  Testing Database Connection...")
        
        # Initialize database
        await db_manager.initialize()
        
        # Test health check
        health = await db_manager.health_check()
        assert health['status'] == 'healthy', f"Database health check failed: {health}"
        
        logger.info(f"   ✅ Database connection successful ({db_manager.db_type})")
        logger.info(f"   📊 Response time: {health.get('response_time_ms', 'N/A')}ms")
    
    async def test_database_operations(self):
        """Test basic database operations"""
        logger.info("📝 Testing Database Operations...")
        
        # Test simple query
        if db_manager.db_type == 'postgresql':
            result = await db_manager.execute_query("SELECT 1 as test", fetch='one')
        else:
            result = await db_manager.execute_query("SELECT 1 as test", fetch='one')
        
        assert result['test'] == 1, "Basic query failed"
        
        # Test parameterized query
        if db_manager.db_type == 'postgresql':
            result = await db_manager.execute_query("SELECT $1 as value", (42,), fetch='one')
        else:
            result = await db_manager.execute_query("SELECT ? as value", (42,), fetch='one')
        
        assert result['value'] == 42, "Parameterized query failed"
        
        logger.info("   ✅ Database operations working correctly")
    
    async def test_database_migrations(self):
        """Test database migrations"""
        logger.info("🔄 Testing Database Migrations...")
        
        # Check if all tables exist
        if db_manager.db_type == 'postgresql':
            tables_query = """
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            """
        else:
            tables_query = "SELECT name FROM sqlite_master WHERE type='table'"
        
        tables = await db_manager.execute_query(tables_query, fetch='all')
        table_names = [t['table_name'] if 'table_name' in t else t['name'] for t in tables]
        
        required_tables = ['users', 'user_interactions', 'verification_queue', 'error_logs', 'bot_metrics', 'migrations']
        
        for table in required_tables:
            assert table in table_names, f"Missing table: {table}"
        
        logger.info(f"   ✅ All {len(required_tables)} required tables exist")
    
    async def test_user_operations(self):
        """Test user-related database operations"""
        logger.info("👤 Testing User Operations...")
        
        # Clean up test user first
        await self._cleanup_test_user()
        
        # Test user creation
        success = await create_user(self.test_user_id, "testuser", "Test User")
        assert success, "User creation failed"
        
        # Test user retrieval
        user_data = await get_user_data(self.test_user_id)
        assert user_data is not None, "User retrieval failed"
        assert user_data['user_id'] == self.test_user_id, "User ID mismatch"
        assert user_data['username'] == "testuser", "Username mismatch"
        
        # Test user update
        success = await update_user_data(self.test_user_id, current_flow='test_flow', deposit_confirmed=True)
        assert success, "User update failed"
        
        # Verify update
        updated_user = await get_user_data(self.test_user_id)
        assert updated_user['current_flow'] == 'test_flow', "User update verification failed"
        assert updated_user['deposit_confirmed'] == True, "Boolean update failed"
        
        # Test interaction logging
        success = await log_interaction(self.test_user_id, "test_interaction", "test_data")
        assert success, "Interaction logging failed"
        
        logger.info("   ✅ User operations working correctly")
    
    async def test_verification_queue(self):
        """Test verification queue operations"""
        logger.info("🔍 Testing Verification Queue...")
        
        # Add test entry to verification queue
        if db_manager.db_type == 'postgresql':
            query = """
                INSERT INTO verification_queue (user_id, uid, screenshot_file_id, auto_verified)
                VALUES ($1, $2, $3, $4)
            """
        else:
            query = """
                INSERT INTO verification_queue (user_id, uid, screenshot_file_id, auto_verified)
                VALUES (?, ?, ?, ?)
            """
        
        await db_manager.execute_query(query, (self.test_user_id, "TEST123456", "test_file_id", True))
        
        # Query verification queue
        if db_manager.db_type == 'postgresql':
            queue_query = "SELECT * FROM verification_queue WHERE user_id = $1"
        else:
            queue_query = "SELECT * FROM verification_queue WHERE user_id = ?"
        
        queue_entry = await db_manager.execute_query(queue_query, (self.test_user_id,), fetch='one')
        assert queue_entry is not None, "Verification queue entry not found"
        assert queue_entry['uid'] == "TEST123456", "UID mismatch in queue"
        
        logger.info("   ✅ Verification queue operations working correctly")
    
    async def test_error_handling(self):
        """Test error handling system"""
        logger.info("⚠️  Testing Error Handling...")
        
        # Test error logging
        test_error = ValueError("Test error for system testing")
        error_handler_instance.log_error(
            error=test_error,
            context="system_test",
            user_id=self.test_user_id,
            extra_data={"test": True}
        )
        
        # Wait for async error storage
        await asyncio.sleep(1)
        
        # Check if error was stored in database
        if db_manager.db_type == 'postgresql':
            error_query = "SELECT * FROM error_logs WHERE context = $1 ORDER BY created_at DESC LIMIT 1"
        else:
            error_query = "SELECT * FROM error_logs WHERE context = ? ORDER BY created_at DESC LIMIT 1"
        
        error_log = await db_manager.execute_query(error_query, ("system_test",), fetch='one')
        assert error_log is not None, "Error not logged to database"
        assert error_log['error_type'] == "ValueError", "Error type mismatch"
        
        logger.info("   ✅ Error handling system working correctly")
    
    async def test_bot_token(self):
        """Test bot token validity"""
        logger.info("🤖 Testing Bot Token...")
        
        try:
            from telegram import Bot
            bot = Bot(token=config.BOT_TOKEN)
            bot_info = await bot.get_me()
            
            assert bot_info.is_bot, "Token does not belong to a bot"
            assert bot_info.username, "Bot username not found"
            
            logger.info(f"   ✅ Bot token valid - @{bot_info.username}")
            
        except Exception as e:
            raise AssertionError(f"Bot token validation failed: {e}")
    
    async def test_webhook_configuration(self):
        """Test webhook configuration"""
        logger.info("🌐 Testing Webhook Configuration...")
        
        if config.BOT_MODE == 'webhook':
            assert config.WEBHOOK_ENABLED, "Webhook mode enabled but WEBHOOK_ENABLED is False"
            assert config.WEBHOOK_PORT, "Webhook port not configured"
            assert config.WEBHOOK_SECRET_TOKEN, "Webhook secret token not configured"
            
            logger.info("   ✅ Webhook configuration valid")
        else:
            logger.info("   ℹ️  Polling mode - webhook tests skipped")
    
    async def test_environment_variables(self):
        """Test environment variables"""
        logger.info("🌍 Testing Environment Variables...")
        
        # Test critical environment variables
        critical_vars = {
            'BOT_TOKEN': config.BOT_TOKEN,
            'DATABASE_TYPE': config.DATABASE_TYPE,
            'ADMIN_USER_ID': config.ADMIN_USER_ID,
            'AUTO_VERIFY_ENABLED': config.AUTO_VERIFY_ENABLED
        }
        
        for var_name, var_value in critical_vars.items():
            assert var_value is not None, f"Critical environment variable {var_name} is None"
        
        # Test database-specific variables
        if config.DATABASE_TYPE == 'postgresql':
            postgres_vars = [config.DATABASE_URL, config.POSTGRES_HOST, config.POSTGRES_DB]
            assert any(postgres_vars), "PostgreSQL configuration incomplete"
        
        logger.info("   ✅ Environment variables configured correctly")
    
    async def test_logging_system(self):
        """Test logging system"""
        logger.info("📝 Testing Logging System...")
        
        # Test different log levels
        test_logger = logging.getLogger('system_test')
        
        test_logger.info("Test info message")
        test_logger.warning("Test warning message")
        test_logger.error("Test error message")
        
        # Check if log files are being created
        if config.ENABLE_FILE_LOGGING:
            log_files = [config.LOG_FILE_PATH, 'errors.log']
            for log_file in log_files:
                if os.path.exists(log_file):
                    assert os.path.getsize(log_file) > 0, f"Log file {log_file} is empty"
        
        logger.info("   ✅ Logging system working correctly")
    
    async def test_database_performance(self):
        """Test database performance"""
        logger.info("⚡ Testing Database Performance...")
        
        start_time = datetime.now()
        
        # Perform multiple operations
        for i in range(10):
            if db_manager.db_type == 'postgresql':
                await db_manager.execute_query("SELECT $1 as iteration", (i,), fetch='one')
            else:
                await db_manager.execute_query("SELECT ? as iteration", (i,), fetch='one')
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        assert duration < 5.0, f"Database performance too slow: {duration}s for 10 queries"
        
        logger.info(f"   ✅ Database performance acceptable ({duration:.2f}s for 10 queries)")
    
    async def _cleanup_test_user(self):
        """Clean up test user data"""
        try:
            # Delete from all tables
            tables_and_queries = [
                ('verification_queue', 'user_id'),
                ('user_interactions', 'user_id'),
                ('users', 'user_id')
            ]
            
            for table, column in tables_and_queries:
                if db_manager.db_type == 'postgresql':
                    query = f"DELETE FROM {table} WHERE {column} = $1"
                else:
                    query = f"DELETE FROM {table} WHERE {column} = ?"
                
                await db_manager.execute_query(query, (self.test_user_id,))
                
        except Exception as e:
            logger.warning(f"Cleanup warning: {e}")
    
    def _generate_test_report(self) -> Dict[str, Any]:
        """Generate comprehensive test report"""
        total_tests = len(self.passed_tests) + len(self.failed_tests)
        success_rate = (len(self.passed_tests) / total_tests * 100) if total_tests > 0 else 0
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'total_tests': total_tests,
            'passed_tests': len(self.passed_tests),
            'failed_tests': len(self.failed_tests),
            'success_rate': round(success_rate, 2),
            'database_type': db_manager.db_type,
            'bot_mode': config.BOT_MODE,
            'auto_verification': config.AUTO_VERIFY_ENABLED,
            'passed_test_names': self.passed_tests,
            'failed_test_details': self.failed_tests
        }
        
        return report

async def main():
    """Main test function"""
    tester = SystemTester()
    
    try:
        report = await tester.run_all_tests()
        
        # Print results
        print("\n" + "=" * 60)
        print("🎯 COMPREHENSIVE SYSTEM TEST RESULTS")
        print("=" * 60)
        print(f"📊 Total Tests: {report['total_tests']}")
        print(f"✅ Passed: {report['passed_tests']}")
        print(f"❌ Failed: {report['failed_tests']}")
        print(f"📈 Success Rate: {report['success_rate']}%")
        print(f"🗄️ Database: {report['database_type'].upper()}")
        print(f"🤖 Bot Mode: {report['bot_mode'].upper()}")
        print(f"🔍 Auto-Verification: {'Enabled' if report['auto_verification'] else 'Disabled'}")
        
        if report['failed_tests'] > 0:
            print("\n❌ FAILED TESTS:")
            for test_name, error in report['failed_test_details']:
                print(f"   - {test_name}: {error}")
        
        print("\n✅ PASSED TESTS:")
        for test_name in report['passed_test_names']:
            print(f"   - {test_name}")
        
        print("=" * 60)
        
        if report['success_rate'] == 100:
            print("🎉 ALL TESTS PASSED! System is ready for deployment.")
        elif report['success_rate'] >= 80:
            print("⚠️  Most tests passed. Review failed tests before deployment.")
        else:
            print("❌ Multiple test failures. System needs attention before deployment.")
        
        return report['success_rate'] == 100
        
    except Exception as e:
        logger.error(f"Test suite failed: {e}")
        return False
    finally:
        # Cleanup
        await tester._cleanup_test_user()
        await db_manager.close()

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
