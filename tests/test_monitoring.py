import unittest
import asyncio
import logging
from unittest.mock import patch, MagicMock, AsyncMock
import time
from datetime import datetime

from telegram_bot.utils.monitoring import Metrics, HealthCheck, measure_time

class TestMonitoring(unittest.TestCase):
    """Test suite for monitoring utilities"""
    
    def setUp(self):
        # Set up logging for tests
        self.logger = logging.getLogger('test_logger')
        self.logger.setLevel(logging.DEBUG)
        # Use a string IO handler to capture log output
        self.log_capture = MagicMock()
        self.logger.addHandler(self.log_capture)
    
    def test_metrics_tracking(self):
        """Test metrics tracking functionality"""
        metrics = Metrics()
        
        # Test command tracking
        metrics.track_command("start")
        metrics.track_command("help")
        metrics.track_command("start")
        
        self.assertEqual(metrics.metrics["commands"]["start"], 2)
        self.assertEqual(metrics.metrics["commands"]["help"], 1)
        
        # Test callback tracking
        metrics.track_callback("verify_button")
        metrics.track_callback("cancel_button")
        metrics.track_callback("verify_button")
        
        self.assertEqual(metrics.metrics["callbacks"]["verify_button"], 2)
        self.assertEqual(metrics.metrics["callbacks"]["cancel_button"], 1)
        
        # Test verification tracking
        metrics.track_verification("auto_approved")
        metrics.track_verification("manual_approved")
        metrics.track_verification("rejected")
        
        self.assertEqual(metrics.metrics["verifications"]["total"], 3)
        self.assertEqual(metrics.metrics["verifications"]["auto_approved"], 1)
        self.assertEqual(metrics.metrics["verifications"]["manual_approved"], 1)
        self.assertEqual(metrics.metrics["verifications"]["rejected"], 1)
        
        # Test error tracking
        metrics.track_error("DatabaseError")
        metrics.track_error("TimeoutError")
        metrics.track_error("DatabaseError")
        
        self.assertEqual(metrics.metrics["errors"]["total"], 3)
        self.assertEqual(metrics.metrics["errors"]["by_type"]["DatabaseError"], 2)
        self.assertEqual(metrics.metrics["errors"]["by_type"]["TimeoutError"], 1)
        
        # Test response time tracking
        metrics.track_response_time(0.1)
        metrics.track_response_time(0.3)
        
        self.assertEqual(metrics.metrics["performance"]["requests"], 2)
        self.assertEqual(metrics.metrics["performance"]["total_response_time"], 0.4)
        self.assertEqual(metrics.metrics["performance"]["avg_response_time"], 0.2)
        
        # Test user tracking
        metrics.track_user(is_new=True)
        metrics.track_user(is_new=True)
        metrics.track_user(is_new=False)
        
        self.assertEqual(metrics.metrics["users"]["total"], 2)
        self.assertEqual(metrics.metrics["users"]["new_today"], 2)
        self.assertEqual(metrics.metrics["users"]["active"], 3)
        
        # Test get_metrics
        metrics_data = metrics.get_metrics()
        self.assertIn("uptime", metrics_data)
        self.assertGreater(metrics_data["uptime"], 0)
        
        # Test reset_daily_metrics
        metrics.reset_daily_metrics()
        self.assertEqual(metrics.metrics["users"]["new_today"], 0)
        self.assertEqual(metrics.metrics["users"]["active"], 0)
    
    @patch('telegram_bot.utils.monitoring.aiohttp.ClientSession')
    async def test_send_metrics_report(self, mock_session):
        """Test sending metrics report"""
        # Setup mock session
        mock_session_instance = MagicMock()
        mock_session.return_value.__aenter__.return_value = mock_session_instance
        
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_session_instance.post.return_value.__aenter__.return_value = mock_response
        
        # Create metrics instance with mocked config
        metrics = Metrics()
        
        # Patch config
        with patch('telegram_bot.utils.monitoring.BotConfig') as mock_config:
            mock_config.MONITORING_WEBHOOK = "https://example.com/webhook"
            mock_config.DEBUG_MODE = False
            
            # Call send_metrics_report
            await metrics.send_metrics_report()
            
            # Verify post was called with correct data
            mock_session_instance.post.assert_called_once()
            args, kwargs = mock_session_instance.post.call_args
            
            self.assertEqual(args[0], "https://example.com/webhook")
            self.assertIn("json", kwargs)
            self.assertIn("headers", kwargs)
            
            # Verify report structure
            report = kwargs["json"]
            self.assertIn("timestamp", report)
            self.assertIn("bot_name", report)
            self.assertIn("environment", report)
            self.assertIn("metrics", report)
            self.assertEqual(report["environment"], "production")
    
    async def test_health_check(self):
        """Test health check functionality"""
        health_check = HealthCheck()
        
        # Define test service check functions
        async def healthy_service():
            return True
        
        async def unhealthy_service():
            return False
        
        async def error_service():
            raise Exception("Test error")
        
        # Register services
        health_check.register_service("healthy", healthy_service, 10)
        health_check.register_service("unhealthy", unhealthy_service, 10)
        health_check.register_service("error", error_service, 10)
        
        # Check individual services
        healthy_result = await health_check.check_service("healthy")
        unhealthy_result = await health_check.check_service("unhealthy")
        error_result = await health_check.check_service("error")
        
        self.assertEqual(healthy_result["status"], "healthy")
        self.assertEqual(unhealthy_result["status"], "unhealthy")
        self.assertEqual(error_result["status"], "error")
        
        # Check all services
        all_results = await health_check.check_all_services()
        
        self.assertIn("healthy", all_results)
        self.assertIn("unhealthy", all_results)
        self.assertIn("error", all_results)
        
        # Get overall health status
        with patch('telegram_bot.utils.monitoring.metrics') as mock_metrics:
            mock_metrics.metrics = {"start_time": time.time() - 3600}  # 1 hour uptime
            
            health_status = await health_check.get_health_status()
            
            self.assertEqual(health_status["status"], "unhealthy")
            self.assertIn("timestamp", health_status)
            self.assertIn("uptime", health_status)
            self.assertIn("services", health_status)
    
    async def test_measure_time_decorator(self):
        """Test measure_time decorator"""
        # Create a test async function with the decorator
        @measure_time
        async def test_async_function():
            await asyncio.sleep(0.1)
            return "result"
        
        # Create a test sync function with the decorator
        @measure_time
        def test_sync_function():
            time.sleep(0.1)
            return "result"
        
        # Patch the metrics instance
        with patch('telegram_bot.utils.monitoring.metrics') as mock_metrics:
            # Test async function
            result = await test_async_function()
            
            self.assertEqual(result, "result")
            mock_metrics.track_response_time.assert_called_once()
            execution_time = mock_metrics.track_response_time.call_args[0][0]
            self.assertGreaterEqual(execution_time, 0.1)
            
            # Reset mock
            mock_metrics.track_response_time.reset_mock()
            
            # Test sync function
            result = test_sync_function()
            
            self.assertEqual(result, "result")
            mock_metrics.track_response_time.assert_called_once()
            execution_time = mock_metrics.track_response_time.call_args[0][0]
            self.assertGreaterEqual(execution_time, 0.1)

if __name__ == '__main__':
    unittest.main()