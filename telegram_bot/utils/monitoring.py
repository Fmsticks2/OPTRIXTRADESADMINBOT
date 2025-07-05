"""Monitoring and metrics utilities for OPTRIXTRADES Telegram Bot"""

import time
import logging
import asyncio
from typing import Dict, Any, Optional, List, Callable
from functools import wraps
from datetime import datetime, timedelta
import json
import os
import aiohttp

from config import BotConfig

logger = logging.getLogger(__name__)

class Metrics:
    """Metrics collection and reporting for the bot"""
    
    def __init__(self):
        self.metrics = {
            "commands": {},
            "callbacks": {},
            "verifications": {
                "total": 0,
                "auto_approved": 0,
                "manual_approved": 0,
                "rejected": 0,
                "pending": 0
            },
            "errors": {
                "total": 0,
                "by_type": {}
            },
            "performance": {
                "avg_response_time": 0,
                "total_response_time": 0,
                "requests": 0
            },
            "users": {
                "total": 0,
                "active": 0,
                "new_today": 0
            },
            "uptime": 0,
            "start_time": time.time()
        }
        self.last_report_time = time.time()
        self.reporting_interval = 3600  # 1 hour in seconds
        self._setup_periodic_reporting()
    
    def _setup_periodic_reporting(self):
        """Set up periodic reporting task"""
        if BotConfig.MONITORING_WEBHOOK:
            asyncio.create_task(self._periodic_reporting())
    
    async def _periodic_reporting(self):
        """Periodically send metrics reports"""
        while True:
            await asyncio.sleep(self.reporting_interval)
            await self.send_metrics_report()
    
    def track_command(self, command_name: str):
        """Track command usage"""
        if command_name not in self.metrics["commands"]:
            self.metrics["commands"][command_name] = 0
        self.metrics["commands"][command_name] += 1
    
    def track_callback(self, callback_name: str):
        """Track callback query usage"""
        if callback_name not in self.metrics["callbacks"]:
            self.metrics["callbacks"][callback_name] = 0
        self.metrics["callbacks"][callback_name] += 1
    
    def track_verification(self, status: str):
        """Track verification status"""
        self.metrics["verifications"]["total"] += 1
        if status in self.metrics["verifications"]:
            self.metrics["verifications"][status] += 1
    
    def track_error(self, error_type: str):
        """Track error occurrences"""
        self.metrics["errors"]["total"] += 1
        if error_type not in self.metrics["errors"]["by_type"]:
            self.metrics["errors"]["by_type"][error_type] = 0
        self.metrics["errors"]["by_type"][error_type] += 1
    
    def track_response_time(self, response_time: float):
        """Track response time for performance metrics"""
        metrics = self.metrics["performance"]
        metrics["requests"] += 1
        metrics["total_response_time"] += response_time
        metrics["avg_response_time"] = metrics["total_response_time"] / metrics["requests"]
    
    def track_user(self, is_new: bool = False, is_active: bool = True):
        """Track user metrics"""
        if is_new:
            self.metrics["users"]["total"] += 1
            self.metrics["users"]["new_today"] += 1
        if is_active:
            self.metrics["users"]["active"] += 1
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics"""
        # Update uptime
        self.metrics["uptime"] = time.time() - self.metrics["start_time"]
        return self.metrics
    
    def reset_daily_metrics(self):
        """Reset daily metrics (called at midnight)"""
        self.metrics["users"]["new_today"] = 0
        self.metrics["users"]["active"] = 0
    
    async def send_metrics_report(self):
        """Send metrics report to monitoring webhook"""
        if not BotConfig.MONITORING_WEBHOOK:
            return
        
        try:
            metrics = self.get_metrics()
            report = {
                "timestamp": datetime.now().isoformat(),
                "bot_name": "OPTRIXTRADES",
                "environment": "production" if not BotConfig.DEBUG_MODE else "development",
                "metrics": metrics
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    BotConfig.MONITORING_WEBHOOK,
                    json=report,
                    headers={"Content-Type": "application/json"}
                ) as response:
                    if response.status != 200:
                        logger.warning(f"Failed to send metrics report: {response.status}")
                    else:
                        logger.debug("Metrics report sent successfully")
        except Exception as e:
            logger.error(f"Error sending metrics report: {e}")


def measure_time(func):
    """Decorator to measure execution time of functions"""
    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        start_time = time.time()
        result = await func(*args, **kwargs)
        execution_time = time.time() - start_time
        # Get global metrics instance
        from telegram_bot.utils.monitoring import metrics
        metrics.track_response_time(execution_time)
        return result
    
    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        execution_time = time.time() - start_time
        # Get global metrics instance
        from telegram_bot.utils.monitoring import metrics
        metrics.track_response_time(execution_time)
        return result
    
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    return sync_wrapper


class HealthCheck:
    """Health check utilities for the bot"""
    
    def __init__(self):
        self.services = {}
        self.last_check = {}
        self.status = {}
    
    def register_service(self, name: str, check_func: Callable, interval_seconds: int = 60):
        """Register a service for health checking"""
        self.services[name] = {
            "check_func": check_func,
            "interval": interval_seconds
        }
        self.last_check[name] = 0
        self.status[name] = {"status": "unknown", "last_checked": None, "details": None}
    
    async def check_service(self, name: str) -> Dict[str, Any]:
        """Check a specific service's health"""
        if name not in self.services:
            return {"status": "unknown", "error": "Service not registered"}
        
        try:
            service = self.services[name]
            result = await service["check_func"]() if asyncio.iscoroutinefunction(service["check_func"]) else service["check_func"]()
            status = {"status": "healthy" if result else "unhealthy", "last_checked": datetime.now().isoformat()}
            self.status[name] = status
            self.last_check[name] = time.time()
            return status
        except Exception as e:
            status = {
                "status": "error",
                "last_checked": datetime.now().isoformat(),
                "error": str(e)
            }
            self.status[name] = status
            self.last_check[name] = time.time()
            return status
    
    async def check_all_services(self) -> Dict[str, Dict[str, Any]]:
        """Check all registered services"""
        results = {}
        for name in self.services:
            current_time = time.time()
            # Only check if interval has passed
            if current_time - self.last_check.get(name, 0) >= self.services[name]["interval"]:
                results[name] = await self.check_service(name)
            else:
                results[name] = self.status.get(name, {"status": "unknown"})
        return results
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Get overall health status"""
        services = await self.check_all_services()
        overall_status = "healthy"
        
        for service_name, service_status in services.items():
            if service_status.get("status") in ["unhealthy", "error"]:
                overall_status = "unhealthy"
                break
        
        return {
            "status": overall_status,
            "timestamp": datetime.now().isoformat(),
            "uptime": time.time() - metrics.metrics["start_time"],
            "services": services
        }


# Create global instances
metrics = Metrics()
health_check = HealthCheck()

# Register basic health checks
async def check_database():
    """Check database connection"""
    try:
        from database.connection import get_connection
        conn = await get_connection()
        return conn is not None
    except Exception:
        return False

async def check_telegram_api():
    """Check Telegram API connection"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://api.telegram.org/bot{BotConfig.BOT_TOKEN}/getMe") as response:
                return response.status == 200
    except Exception:
        return False

# Register health checks
health_check.register_service("database", check_database, 300)  # Check every 5 minutes
health_check.register_service("telegram_api", check_telegram_api, 600)  # Check every 10 minutes