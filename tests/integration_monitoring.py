import unittest
import asyncio
import logging
from unittest.mock import patch, MagicMock, AsyncMock
import os
import sys
import sqlite3
import tempfile
import time
from datetime import datetime, timedelta

# Add project root to path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from telegram_bot.utils.monitoring import Metrics, HealthCheck, measure_time

class IntegrationTestMonitoring(unittest.TestCase):
    """Integration tests for monitoring system"""
    
    def setUp(self):
        # Create a temporary database file
        self.db_fd, self.db_path = tempfile.mkstemp()
        
        # Set up a test database
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        
        # Create metrics table
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            metric_type TEXT NOT NULL,
            metric_name TEXT NOT NULL,
            metric_value REAL,
            context TEXT
        )
        """)
        
        # Create health_checks table
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS health_checks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            service TEXT NOT NULL,
            status TEXT NOT NULL,
            response_time REAL,
            details TEXT
        )
        """)
        
        self.conn.commit()
        
        # Configure test logger
        self.logger = logging.getLogger('test_logger')
        self.logger.setLevel(logging.DEBUG)
        self.log_capture = MagicMock()
        self.logger.addHandler(self.log_capture)
        
        # Create metrics with test database
        with patch('telegram_bot.utils.monitoring.BotConfig') as mock_config:
            mock_config.DB_PATH = self.db_path
            self.metrics = Metrics(logger=self.logger)
            self.health_check = HealthCheck(logger=self.logger)
    
    def tearDown(self):
        # Close and remove the temporary database
        self.conn.close()
        os.close(self.db_fd)
        os.unlink(self.db_path)
    
    def test_metrics_storage_and_retrieval(self):
        """Test that metrics are properly stored in the database and can be retrieved"""
        # Track various metrics
        self.metrics.track_command("start", user_id=123456)
        self.metrics.track_callback("verify_button", user_id=123456)
        self.metrics.track_verification(success=True, user_id=123456)
        self.metrics.track_error("API error", severity="medium")
        self.metrics.track_performance("api_request", 0.5)  # 500ms
        
        # Verify metrics were stored in database
        self.cursor.execute("SELECT COUNT(*) FROM metrics")
        count = self.cursor.fetchone()[0]
        self.assertEqual(count, 5)  # 5 metrics should be stored
        
        # Check command metric
        self.cursor.execute("SELECT * FROM metrics WHERE metric_type = 'command'")
        command_metric = self.cursor.fetchone()
        self.assertIsNotNone(command_metric)
        self.assertEqual(command_metric[3], "start")  # metric_name
        
        # Check performance metric
        self.cursor.execute("SELECT * FROM metrics WHERE metric_type = 'performance'")
        perf_metric = self.cursor.fetchone()
        self.assertIsNotNone(perf_metric)
        self.assertEqual(perf_metric[3], "api_request")  # metric_name
        self.assertEqual(perf_metric[4], 0.5)  # metric_value
    
    def test_metrics_report_generation(self):
        """Test metrics report generation"""
        # Add some test metrics
        for i in range(10):
            self.metrics.track_command("start", user_id=100+i)
        
        for i in range(5):
            self.metrics.track_command("help", user_id=200+i)
        
        for i in range(3):
            self.metrics.track_error("API error", severity="medium")
        
        # Generate report
        report = self.metrics.generate_report()
        
        # Verify report contents
        self.assertIn("commands", report)
        self.assertIn("errors", report)
        
        # Check command counts
        self.assertEqual(report["commands"]["start"], 10)
        self.assertEqual(report["commands"]["help"], 5)
        
        # Check error counts
        self.assertEqual(report["errors"]["API error"], 3)
        
        # Check total users
        self.assertEqual(report["total_users"], 15)  # 10 start + 5 help users
    
    @patch('telegram.Bot')
    @patch('telegram_bot.utils.monitoring.BotConfig')
    async def test_metrics_report_sending(self, mock_config, mock_bot):
        """Test sending metrics report to admins"""
        # Configure mocks
        mock_config.ADMIN_USER_IDS = [12345, 67890]
        mock_bot.send_message = AsyncMock()
        
        # Add some test metrics
        self.metrics.track_command("start", user_id=123456)
        self.metrics.track_error("API error", severity="medium")
        
        # Send report
        await self.metrics.send_report(mock_bot)
        
        # Verify bot.send_message was called for each admin
        self.assertEqual(mock_bot.send_message.call_count, 2)
        
        # Verify message content
        message_text = mock_bot.send_message.call_args_list[0][1]["text"]
        self.assertIn("Metrics Report", message_text)
        self.assertIn("start", message_text)
        self.assertIn("API error", message_text)
    
    @patch('telegram_bot.utils.monitoring.requests')
    def test_health_check_telegram_api(self, mock_requests):
        """Test health check for Telegram API"""
        # Configure mock
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True}
        mock_response.elapsed.total_seconds.return_value = 0.2
        mock_requests.get.return_value = mock_response
        
        # Run health check
        result = self.health_check.check_telegram_api()
        
        # Verify result
        self.assertTrue(result["healthy"])
        self.assertEqual(result["response_time"], 0.2)
        
        # Verify health check was stored in database
        self.cursor.execute("SELECT * FROM health_checks WHERE service = 'telegram_api'")
        health_record = self.cursor.fetchone()
        
        self.assertIsNotNone(health_record)
        self.assertEqual(health_record[3], "healthy")  # status
        self.assertEqual(health_record[4], 0.2)  # response_time
    
    def test_health_check_database(self):
        """Test health check for database"""
        # Run health check
        result = self.health_check.check_database()
        
        # Verify result
        self.assertTrue(result["healthy"])
        self.assertGreaterEqual(result["response_time"], 0)
        
        # Verify health check was stored in database
        self.cursor.execute("SELECT * FROM health_checks WHERE service = 'database'")
        health_record = self.cursor.fetchone()
        
        self.assertIsNotNone(health_record)
        self.assertEqual(health_record[3], "healthy")  # status
    
    @patch('telegram_bot.utils.monitoring.requests')
    def test_health_check_external_api(self, mock_requests):
        """Test health check for external API"""
        # Configure mock
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.elapsed.total_seconds.return_value = 0.3
        mock_requests.get.return_value = mock_response
        
        # Run health check
        result = self.health_check.check_external_api(
            "https://api.example.com", 
            "example_api"
        )
        
        # Verify result
        self.assertTrue(result["healthy"])
        self.assertEqual(result["response_time"], 0.3)
        
        # Verify health check was stored in database
        self.cursor.execute("SELECT * FROM health_checks WHERE service = 'example_api'")
        health_record = self.cursor.fetchone()
        
        self.assertIsNotNone(health_record)
        self.assertEqual(health_record[3], "healthy")  # status
        self.assertEqual(health_record[4], 0.3)  # response_time
    
    @patch('telegram_bot.utils.monitoring.requests')
    def test_health_check_unhealthy_service(self, mock_requests):
        """Test health check for unhealthy service"""
        # Configure mock to simulate failure
        mock_requests.get.side_effect = Exception("Connection error")
        
        # Run health check
        result = self.health_check.check_external_api(
            "https://api.example.com", 
            "failing_api"
        )
        
        # Verify result
        self.assertFalse(result["healthy"])
        self.assertIn("Connection error", result["details"])
        
        # Verify health check was stored in database
        self.cursor.execute("SELECT * FROM health_checks WHERE service = 'failing_api'")
        health_record = self.cursor.fetchone()
        
        self.assertIsNotNone(health_record)
        self.assertEqual(health_record[3], "unhealthy")  # status
    
    @patch('telegram.Bot')
    @patch('telegram_bot.utils.monitoring.BotConfig')
    async def test_health_check_report_sending(self, mock_config, mock_bot):
        """Test sending health check report to admins"""
        # Configure mocks
        mock_config.ADMIN_USER_IDS = [12345]
        mock_bot.send_message = AsyncMock()
        
        # Add some health checks
        self.health_check.check_database()
        
        with patch('telegram_bot.utils.monitoring.requests') as mock_requests:
            # Configure mock for API check
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"ok": True}
            mock_response.elapsed.total_seconds.return_value = 0.2
            mock_requests.get.return_value = mock_response
            
            self.health_check.check_telegram_api()
            
            # Configure mock to simulate failure
            mock_requests.get.side_effect = Exception("Connection error")
            self.health_check.check_external_api(
                "https://api.example.com", 
                "failing_api"
            )
        
        # Send report
        await self.health_check.send_report(mock_bot)
        
        # Verify bot.send_message was called
        mock_bot.send_message.assert_called_once()
        
        # Verify message content
        message_text = mock_bot.send_message.call_args[1]["text"]
        self.assertIn("Health Check Report", message_text)
        self.assertIn("database: ✅", message_text)
        self.assertIn("telegram_api: ✅", message_text)
        self.assertIn("failing_api: ❌", message_text)
    
    def test_measure_time_decorator(self):
        """Test measure_time decorator integration with metrics"""
        # Create a test function with the measure_time decorator
        @measure_time("test_function")
        def test_function():
            time.sleep(0.1)  # Sleep for 100ms
            return "result"
        
        # Set up the metrics
        with patch('telegram_bot.utils.monitoring.metrics.track_performance') as mock_track:
            # Call the decorated function
            result = test_function()
            
            # Verify result
            self.assertEqual(result, "result")
            
            # Verify performance was tracked
            mock_track.assert_called_once()
            
            # Verify the metric details
            metric_name = mock_track.call_args[0][0]
            metric_value = mock_track.call_args[0][1]
            self.assertEqual(metric_name, "test_function")
            self.assertGreaterEqual(metric_value, 0.1)  # Should be at least 100ms
    
    async def test_measure_time_decorator_async(self):
        """Test measure_time decorator with async functions"""
        # Create an async test function with the measure_time decorator
        @measure_time("async_test_function")
        async def async_test_function():
            await asyncio.sleep(0.1)  # Sleep for 100ms
            return "async result"
        
        # Set up the metrics
        with patch('telegram_bot.utils.monitoring.metrics.track_performance') as mock_track:
            # Call the decorated function
            result = await async_test_function()
            
            # Verify result
            self.assertEqual(result, "async result")
            
            # Verify performance was tracked
            mock_track.assert_called_once()
            
            # Verify the metric details
            metric_name = mock_track.call_args[0][0]
            metric_value = mock_track.call_args[0][1]
            self.assertEqual(metric_name, "async_test_function")
            self.assertGreaterEqual(metric_value, 0.1)  # Should be at least 100ms

if __name__ == '__main__':
    unittest.main()