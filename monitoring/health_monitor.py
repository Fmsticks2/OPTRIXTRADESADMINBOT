"""Comprehensive health monitoring and performance tracking system"""

import asyncio
import json
import psutil
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
from pathlib import Path
import logging

from telegram.ext import Application

from config import BotConfig
from database.connection import DatabaseManager

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health status levels"""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    DOWN = "down"


class MetricType(Enum):
    """Types of metrics"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


@dataclass
class HealthCheck:
    """Health check definition"""
    name: str
    check_function: Callable
    interval_seconds: int
    timeout_seconds: int = 30
    critical_threshold: int = 3  # Consecutive failures before critical
    enabled: bool = True


@dataclass
class HealthCheckResult:
    """Health check result"""
    name: str
    status: HealthStatus
    message: str
    response_time_ms: float
    timestamp: datetime
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Metric:
    """Performance metric"""
    name: str
    metric_type: MetricType
    value: float
    timestamp: datetime
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class Alert:
    """System alert"""
    alert_id: str
    severity: HealthStatus
    title: str
    message: str
    timestamp: datetime
    source: str
    resolved: bool = False
    resolved_at: Optional[datetime] = None


class MetricsCollector:
    """Collect and store performance metrics"""
    
    def __init__(self, max_metrics: int = 10000):
        self.metrics: deque = deque(maxlen=max_metrics)
        self.counters: Dict[str, float] = defaultdict(float)
        self.gauges: Dict[str, float] = {}
        self.histograms: Dict[str, List[float]] = defaultdict(list)
        self.timers: Dict[str, List[float]] = defaultdict(list)
    
    def increment_counter(self, name: str, value: float = 1.0, tags: Optional[Dict[str, str]] = None) -> None:
        """Increment a counter metric"""
        self.counters[name] += value
        self._add_metric(name, MetricType.COUNTER, value, tags or {})
    
    def set_gauge(self, name: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
        """Set a gauge metric"""
        self.gauges[name] = value
        self._add_metric(name, MetricType.GAUGE, value, tags or {})
    
    def add_histogram_value(self, name: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
        """Add value to histogram"""
        self.histograms[name].append(value)
        # Keep only last 1000 values
        if len(self.histograms[name]) > 1000:
            self.histograms[name] = self.histograms[name][-1000:]
        self._add_metric(name, MetricType.HISTOGRAM, value, tags or {})
    
    def record_timer(self, name: str, duration_ms: float, tags: Optional[Dict[str, str]] = None) -> None:
        """Record timer duration"""
        self.timers[name].append(duration_ms)
        # Keep only last 1000 values
        if len(self.timers[name]) > 1000:
            self.timers[name] = self.timers[name][-1000:]
        self._add_metric(name, MetricType.TIMER, duration_ms, tags or {})
    
    def _add_metric(self, name: str, metric_type: MetricType, value: float, tags: Dict[str, str]) -> None:
        """Add metric to collection"""
        metric = Metric(
            name=name,
            metric_type=metric_type,
            value=value,
            timestamp=datetime.now(),
            tags=tags
        )
        self.metrics.append(metric)
    
    def get_counter_value(self, name: str) -> float:
        """Get current counter value"""
        return self.counters.get(name, 0.0)
    
    def get_gauge_value(self, name: str) -> Optional[float]:
        """Get current gauge value"""
        return self.gauges.get(name)
    
    def get_histogram_stats(self, name: str) -> Dict[str, float]:
        """Get histogram statistics"""
        values = self.histograms.get(name, [])
        if not values:
            return {}
        
        sorted_values = sorted(values)
        count = len(sorted_values)
        
        return {
            "count": count,
            "min": min(sorted_values),
            "max": max(sorted_values),
            "mean": sum(sorted_values) / count,
            "p50": sorted_values[int(count * 0.5)],
            "p90": sorted_values[int(count * 0.9)],
            "p95": sorted_values[int(count * 0.95)],
            "p99": sorted_values[int(count * 0.99)] if count >= 100 else sorted_values[-1]
        }
    
    def get_timer_stats(self, name: str) -> Dict[str, float]:
        """Get timer statistics"""
        return self.get_histogram_stats(name)  # Same calculation
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get comprehensive metrics summary"""
        return {
            "counters": dict(self.counters),
            "gauges": dict(self.gauges),
            "histograms": {name: self.get_histogram_stats(name) for name in self.histograms.keys()},
            "timers": {name: self.get_timer_stats(name) for name in self.timers.keys()},
            "total_metrics": len(self.metrics),
            "collection_time": datetime.now().isoformat()
        }


class SystemHealthChecker:
    """System health monitoring"""
    
    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db_manager = db_manager
        self.health_checks: Dict[str, HealthCheck] = {}
        self.check_results: Dict[str, List[HealthCheckResult]] = defaultdict(list)
        self.failure_counts: Dict[str, int] = defaultdict(int)
        self.last_check_times: Dict[str, datetime] = {}
        
        # Register default health checks
        self._register_default_checks()
    
    def _register_default_checks(self) -> None:
        """Register default health checks"""
        self.register_check(HealthCheck(
            name="system_resources",
            check_function=self._check_system_resources,
            interval_seconds=60
        ))
        
        self.register_check(HealthCheck(
            name="database_connection",
            check_function=self._check_database_connection,
            interval_seconds=30
        ))
        
        self.register_check(HealthCheck(
            name="disk_space",
            check_function=self._check_disk_space,
            interval_seconds=300  # 5 minutes
        ))
        
        self.register_check(HealthCheck(
            name="memory_usage",
            check_function=self._check_memory_usage,
            interval_seconds=60
        ))
        
        self.register_check(HealthCheck(
            name="bot_responsiveness",
            check_function=self._check_bot_responsiveness,
            interval_seconds=120
        ))
    
    def register_check(self, health_check: HealthCheck) -> None:
        """Register a health check"""
        self.health_checks[health_check.name] = health_check
        logger.info(f"Registered health check: {health_check.name}")
    
    async def run_check(self, check_name: str) -> HealthCheckResult:
        """Run a specific health check"""
        if check_name not in self.health_checks:
            raise ValueError(f"Health check '{check_name}' not found")
        
        check = self.health_checks[check_name]
        start_time = time.time()
        
        try:
            # Run the check with timeout
            result = await asyncio.wait_for(
                check.check_function(),
                timeout=check.timeout_seconds
            )
            
            response_time = (time.time() - start_time) * 1000
            
            # Reset failure count on success
            self.failure_counts[check_name] = 0
            
            check_result = HealthCheckResult(
                name=check_name,
                status=result.get("status", HealthStatus.HEALTHY),
                message=result.get("message", "Check passed"),
                response_time_ms=response_time,
                timestamp=datetime.now(),
                details=result.get("details", {})
            )
            
        except asyncio.TimeoutError:
            response_time = (time.time() - start_time) * 1000
            self.failure_counts[check_name] += 1
            
            check_result = HealthCheckResult(
                name=check_name,
                status=HealthStatus.CRITICAL,
                message=f"Health check timed out after {check.timeout_seconds}s",
                response_time_ms=response_time,
                timestamp=datetime.now()
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            self.failure_counts[check_name] += 1
            
            # Determine status based on failure count
            if self.failure_counts[check_name] >= check.critical_threshold:
                status = HealthStatus.CRITICAL
            else:
                status = HealthStatus.WARNING
            
            check_result = HealthCheckResult(
                name=check_name,
                status=status,
                message=f"Health check failed: {str(e)}",
                response_time_ms=response_time,
                timestamp=datetime.now(),
                details={"error": str(e), "failure_count": self.failure_counts[check_name]}
            )
        
        # Store result
        self.check_results[check_name].append(check_result)
        # Keep only last 100 results per check
        if len(self.check_results[check_name]) > 100:
            self.check_results[check_name] = self.check_results[check_name][-100:]
        
        self.last_check_times[check_name] = datetime.now()
        
        return check_result
    
    async def run_all_checks(self) -> Dict[str, HealthCheckResult]:
        """Run all enabled health checks"""
        results = {}
        
        for check_name, check in self.health_checks.items():
            if not check.enabled:
                continue
            
            # Check if it's time to run this check
            last_check = self.last_check_times.get(check_name)
            if last_check:
                time_since_last = (datetime.now() - last_check).total_seconds()
                if time_since_last < check.interval_seconds:
                    continue
            
            try:
                result = await self.run_check(check_name)
                results[check_name] = result
            except Exception as e:
                logger.error(f"Failed to run health check {check_name}: {e}")
        
        return results
    
    async def _check_system_resources(self) -> Dict[str, Any]:
        """Check system resource usage"""
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        
        details = {
            "cpu_percent": cpu_percent,
            "memory_percent": memory.percent,
            "memory_available_gb": round(memory.available / (1024**3), 2),
            "memory_total_gb": round(memory.total / (1024**3), 2)
        }
        
        # Determine status
        if cpu_percent > 90 or memory.percent > 90:
            status = HealthStatus.CRITICAL
            message = f"High resource usage: CPU {cpu_percent}%, Memory {memory.percent}%"
        elif cpu_percent > 70 or memory.percent > 70:
            status = HealthStatus.WARNING
            message = f"Moderate resource usage: CPU {cpu_percent}%, Memory {memory.percent}%"
        else:
            status = HealthStatus.HEALTHY
            message = f"Resource usage normal: CPU {cpu_percent}%, Memory {memory.percent}%"
        
        return {
            "status": status,
            "message": message,
            "details": details
        }
    
    async def _check_database_connection(self) -> Dict[str, Any]:
        """Check database connectivity"""
        if not self.db_manager:
            return {
                "status": HealthStatus.WARNING,
                "message": "Database manager not configured"
            }
        
        try:
            # Perform a simple health check query
            start_time = time.time()
            health_result = await self.db_manager.health_check()
            query_time = (time.time() - start_time) * 1000
            
            if health_result:
                status = HealthStatus.HEALTHY
                message = f"Database connection healthy (query time: {query_time:.2f}ms)"
            else:
                status = HealthStatus.CRITICAL
                message = "Database health check failed"
            
            return {
                "status": status,
                "message": message,
                "details": {
                    "query_time_ms": round(query_time, 2),
                    "connection_pool_size": getattr(self.db_manager, 'pool_size', 'unknown')
                }
            }
            
        except Exception as e:
            return {
                "status": HealthStatus.CRITICAL,
                "message": f"Database connection failed: {str(e)}",
                "details": {"error": str(e)}
            }
    
    async def _check_disk_space(self) -> Dict[str, Any]:
        """Check available disk space"""
        try:
            disk_usage = psutil.disk_usage('/')
            free_percent = (disk_usage.free / disk_usage.total) * 100
            
            details = {
                "total_gb": round(disk_usage.total / (1024**3), 2),
                "used_gb": round(disk_usage.used / (1024**3), 2),
                "free_gb": round(disk_usage.free / (1024**3), 2),
                "free_percent": round(free_percent, 2)
            }
            
            if free_percent < 5:
                status = HealthStatus.CRITICAL
                message = f"Critical: Only {free_percent:.1f}% disk space remaining"
            elif free_percent < 15:
                status = HealthStatus.WARNING
                message = f"Warning: Only {free_percent:.1f}% disk space remaining"
            else:
                status = HealthStatus.HEALTHY
                message = f"Disk space healthy: {free_percent:.1f}% free"
            
            return {
                "status": status,
                "message": message,
                "details": details
            }
            
        except Exception as e:
            return {
                "status": HealthStatus.CRITICAL,
                "message": f"Failed to check disk space: {str(e)}",
                "details": {"error": str(e)}
            }
    
    async def _check_memory_usage(self) -> Dict[str, Any]:
        """Check detailed memory usage"""
        try:
            process = psutil.Process()
            memory_info = process.memory_info()
            memory_percent = process.memory_percent()
            
            details = {
                "rss_mb": round(memory_info.rss / (1024**2), 2),
                "vms_mb": round(memory_info.vms / (1024**2), 2),
                "percent": round(memory_percent, 2),
                "num_threads": process.num_threads(),
                "num_fds": process.num_fds() if hasattr(process, 'num_fds') else 'N/A'
            }
            
            if memory_percent > 80:
                status = HealthStatus.CRITICAL
                message = f"High memory usage: {memory_percent:.1f}%"
            elif memory_percent > 60:
                status = HealthStatus.WARNING
                message = f"Moderate memory usage: {memory_percent:.1f}%"
            else:
                status = HealthStatus.HEALTHY
                message = f"Memory usage normal: {memory_percent:.1f}%"
            
            return {
                "status": status,
                "message": message,
                "details": details
            }
            
        except Exception as e:
            return {
                "status": HealthStatus.CRITICAL,
                "message": f"Failed to check memory usage: {str(e)}",
                "details": {"error": str(e)}
            }
    
    async def _check_bot_responsiveness(self) -> Dict[str, Any]:
        """Check bot responsiveness"""
        try:
            # Simple responsiveness test
            start_time = time.time()
            
            # Simulate a lightweight operation
            await asyncio.sleep(0.001)  # 1ms delay
            
            response_time = (time.time() - start_time) * 1000
            
            if response_time > 1000:  # 1 second
                status = HealthStatus.CRITICAL
                message = f"Bot very slow to respond: {response_time:.2f}ms"
            elif response_time > 500:  # 500ms
                status = HealthStatus.WARNING
                message = f"Bot slow to respond: {response_time:.2f}ms"
            else:
                status = HealthStatus.HEALTHY
                message = f"Bot responsive: {response_time:.2f}ms"
            
            return {
                "status": status,
                "message": message,
                "details": {"response_time_ms": round(response_time, 2)}
            }
            
        except Exception as e:
            return {
                "status": HealthStatus.CRITICAL,
                "message": f"Bot responsiveness check failed: {str(e)}",
                "details": {"error": str(e)}
            }
    
    def get_overall_health(self) -> HealthStatus:
        """Get overall system health status"""
        if not self.check_results:
            return HealthStatus.WARNING
        
        # Get latest results for each check
        latest_results = {}
        for check_name, results in self.check_results.items():
            if results:
                latest_results[check_name] = results[-1]
        
        if not latest_results:
            return HealthStatus.WARNING
        
        # Determine overall status
        statuses = [result.status for result in latest_results.values()]
        
        if HealthStatus.CRITICAL in statuses:
            return HealthStatus.CRITICAL
        elif HealthStatus.WARNING in statuses:
            return HealthStatus.WARNING
        else:
            return HealthStatus.HEALTHY
    
    def get_health_summary(self) -> Dict[str, Any]:
        """Get comprehensive health summary"""
        overall_status = self.get_overall_health()
        
        # Get latest results
        latest_results = {}
        for check_name, results in self.check_results.items():
            if results:
                latest_result = results[-1]
                latest_results[check_name] = {
                    "status": latest_result.status.value,
                    "message": latest_result.message,
                    "response_time_ms": round(latest_result.response_time_ms, 2),
                    "timestamp": latest_result.timestamp.isoformat(),
                    "failure_count": self.failure_counts.get(check_name, 0)
                }
        
        return {
            "overall_status": overall_status.value,
            "checks": latest_results,
            "summary": {
                "total_checks": len(self.health_checks),
                "enabled_checks": sum(1 for check in self.health_checks.values() if check.enabled),
                "last_update": datetime.now().isoformat()
            }
        }


class AlertManager:
    """Manage system alerts and notifications"""
    
    def __init__(self, max_alerts: int = 1000):
        self.alerts: deque = deque(maxlen=max_alerts)
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_rules: List[Callable] = []
        
        # Register default alert rules
        self._register_default_rules()
    
    def _register_default_rules(self) -> None:
        """Register default alerting rules"""
        self.alert_rules.extend([
            self._check_health_status_alerts,
            self._check_resource_alerts,
            self._check_error_rate_alerts
        ])
    
    def create_alert(self, alert_id: str, severity: HealthStatus, title: str, 
                    message: str, source: str) -> Alert:
        """Create a new alert"""
        alert = Alert(
            alert_id=alert_id,
            severity=severity,
            title=title,
            message=message,
            timestamp=datetime.now(),
            source=source
        )
        
        self.alerts.append(alert)
        self.active_alerts[alert_id] = alert
        
        logger.warning(f"Alert created: {title} - {message}")
        
        return alert
    
    def resolve_alert(self, alert_id: str) -> bool:
        """Resolve an active alert"""
        if alert_id in self.active_alerts:
            alert = self.active_alerts[alert_id]
            alert.resolved = True
            alert.resolved_at = datetime.now()
            del self.active_alerts[alert_id]
            
            logger.info(f"Alert resolved: {alert.title}")
            return True
        
        return False
    
    def check_alert_rules(self, health_summary: Dict[str, Any], 
                         metrics_summary: Dict[str, Any]) -> List[Alert]:
        """Check all alert rules and create alerts if needed"""
        new_alerts = []
        
        for rule in self.alert_rules:
            try:
                alerts = rule(health_summary, metrics_summary)
                if alerts:
                    new_alerts.extend(alerts)
            except Exception as e:
                logger.error(f"Alert rule failed: {e}")
        
        return new_alerts
    
    def _check_health_status_alerts(self, health_summary: Dict[str, Any], 
                                   metrics_summary: Dict[str, Any]) -> List[Alert]:
        """Check for health status alerts"""
        alerts = []
        
        overall_status = health_summary.get("overall_status")
        
        if overall_status == HealthStatus.CRITICAL.value:
            alert_id = "system_critical"
            if alert_id not in self.active_alerts:
                alert = self.create_alert(
                    alert_id=alert_id,
                    severity=HealthStatus.CRITICAL,
                    title="System Critical",
                    message="One or more critical health checks are failing",
                    source="health_monitor"
                )
                alerts.append(alert)
        else:
            # Resolve alert if system is no longer critical
            self.resolve_alert("system_critical")
        
        return alerts
    
    def _check_resource_alerts(self, health_summary: Dict[str, Any], 
                              metrics_summary: Dict[str, Any]) -> List[Alert]:
        """Check for resource usage alerts"""
        alerts = []
        
        # Check system resources from health checks
        checks = health_summary.get("checks", {})
        system_check = checks.get("system_resources")
        
        if system_check and system_check.get("status") == HealthStatus.CRITICAL.value:
            alert_id = "high_resource_usage"
            if alert_id not in self.active_alerts:
                alert = self.create_alert(
                    alert_id=alert_id,
                    severity=HealthStatus.CRITICAL,
                    title="High Resource Usage",
                    message=system_check.get("message", "System resources critically high"),
                    source="resource_monitor"
                )
                alerts.append(alert)
        else:
            self.resolve_alert("high_resource_usage")
        
        return alerts
    
    def _check_error_rate_alerts(self, health_summary: Dict[str, Any], 
                                metrics_summary: Dict[str, Any]) -> List[Alert]:
        """Check for high error rate alerts"""
        alerts = []
        
        # Check error rate from metrics
        counters = metrics_summary.get("counters", {})
        error_count = counters.get("errors_total", 0)
        request_count = counters.get("requests_total", 1)
        
        error_rate = (error_count / request_count) * 100 if request_count > 0 else 0
        
        if error_rate > 10:  # 10% error rate threshold
            alert_id = "high_error_rate"
            if alert_id not in self.active_alerts:
                alert = self.create_alert(
                    alert_id=alert_id,
                    severity=HealthStatus.CRITICAL,
                    title="High Error Rate",
                    message=f"Error rate is {error_rate:.1f}% ({error_count}/{request_count})",
                    source="error_monitor"
                )
                alerts.append(alert)
        else:
            self.resolve_alert("high_error_rate")
        
        return alerts
    
    def get_active_alerts(self) -> List[Dict[str, Any]]:
        """Get all active alerts"""
        return [
            {
                "alert_id": alert.alert_id,
                "severity": alert.severity.value,
                "title": alert.title,
                "message": alert.message,
                "timestamp": alert.timestamp.isoformat(),
                "source": alert.source,
                "duration_minutes": round((datetime.now() - alert.timestamp).total_seconds() / 60, 1)
            }
            for alert in self.active_alerts.values()
        ]
    
    def get_alert_summary(self) -> Dict[str, Any]:
        """Get alert summary"""
        now = datetime.now()
        last_hour = now - timedelta(hours=1)
        last_day = now - timedelta(days=1)
        
        recent_alerts = [alert for alert in self.alerts if alert.timestamp >= last_hour]
        daily_alerts = [alert for alert in self.alerts if alert.timestamp >= last_day]
        
        return {
            "active_alerts": len(self.active_alerts),
            "alerts_last_hour": len(recent_alerts),
            "alerts_last_day": len(daily_alerts),
            "total_alerts": len(self.alerts),
            "active_alert_details": self.get_active_alerts()
        }


class HealthMonitor:
    """Main health monitoring coordinator"""
    
    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.metrics_collector = MetricsCollector()
        self.health_checker = SystemHealthChecker(db_manager)
        self.alert_manager = AlertManager()
        self.monitoring_active = False
        self.monitoring_task: Optional[asyncio.Task] = None
        self.monitoring_interval = 30  # seconds
    
    async def start_monitoring(self) -> None:
        """Start continuous monitoring"""
        if self.monitoring_active:
            logger.warning("Monitoring already active")
            return
        
        self.monitoring_active = True
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("Health monitoring started")
    
    async def stop_monitoring(self) -> None:
        """Stop continuous monitoring"""
        self.monitoring_active = False
        
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Health monitoring stopped")
    
    async def _monitoring_loop(self) -> None:
        """Main monitoring loop"""
        while self.monitoring_active:
            try:
                # Run health checks
                await self.health_checker.run_all_checks()
                
                # Collect system metrics
                await self._collect_system_metrics()
                
                # Check alert rules
                health_summary = self.health_checker.get_health_summary()
                metrics_summary = self.metrics_collector.get_metrics_summary()
                
                self.alert_manager.check_alert_rules(health_summary, metrics_summary)
                
                # Wait for next iteration
                await asyncio.sleep(self.monitoring_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitoring loop error: {e}")
                await asyncio.sleep(self.monitoring_interval)
    
    async def _collect_system_metrics(self) -> None:
        """Collect system-level metrics"""
        try:
            # CPU and memory metrics
            cpu_percent = psutil.cpu_percent()
            memory = psutil.virtual_memory()
            
            self.metrics_collector.set_gauge("system.cpu.percent", cpu_percent)
            self.metrics_collector.set_gauge("system.memory.percent", memory.percent)
            self.metrics_collector.set_gauge("system.memory.available_gb", memory.available / (1024**3))
            
            # Process metrics
            process = psutil.Process()
            self.metrics_collector.set_gauge("process.memory.rss_mb", process.memory_info().rss / (1024**2))
            self.metrics_collector.set_gauge("process.memory.percent", process.memory_percent())
            self.metrics_collector.set_gauge("process.threads", process.num_threads())
            
            # Disk metrics
            disk_usage = psutil.disk_usage('/')
            self.metrics_collector.set_gauge("system.disk.free_percent", (disk_usage.free / disk_usage.total) * 100)
            
        except Exception as e:
            logger.error(f"Failed to collect system metrics: {e}")
    
    def get_comprehensive_status(self) -> Dict[str, Any]:
        """Get comprehensive system status"""
        health_summary = self.health_checker.get_health_summary()
        metrics_summary = self.metrics_collector.get_metrics_summary()
        alert_summary = self.alert_manager.get_alert_summary()
        
        return {
            "timestamp": datetime.now().isoformat(),
            "monitoring_active": self.monitoring_active,
            "health": health_summary,
            "metrics": metrics_summary,
            "alerts": alert_summary,
            "uptime_hours": self._get_uptime_hours()
        }
    
    def _get_uptime_hours(self) -> float:
        """Get system uptime in hours"""
        try:
            boot_time = datetime.fromtimestamp(psutil.boot_time())
            uptime = datetime.now() - boot_time
            return round(uptime.total_seconds() / 3600, 2)
        except Exception:
            return 0.0
    
    # Convenience methods for external use
    def record_request(self, endpoint: str, duration_ms: float, status_code: int) -> None:
        """Record API request metrics"""
        self.metrics_collector.increment_counter("requests_total", tags={"endpoint": endpoint, "status": str(status_code)})
        self.metrics_collector.record_timer("request_duration_ms", duration_ms, tags={"endpoint": endpoint})
        
        if status_code >= 400:
            self.metrics_collector.increment_counter("errors_total", tags={"endpoint": endpoint, "status": str(status_code)})
    
    def record_database_operation(self, operation: str, duration_ms: float, success: bool) -> None:
        """Record database operation metrics"""
        self.metrics_collector.increment_counter("db_operations_total", tags={"operation": operation, "success": str(success)})
        self.metrics_collector.record_timer("db_operation_duration_ms", duration_ms, tags={"operation": operation})
        
        if not success:
            self.metrics_collector.increment_counter("db_errors_total", tags={"operation": operation})
    
    def record_user_interaction(self, interaction_type: str) -> None:
        """Record user interaction metrics"""
        self.metrics_collector.increment_counter("user_interactions_total", tags={"type": interaction_type})


# Global health monitor instance
health_monitor: Optional[HealthMonitor] = None


def initialize_health_monitor(db_manager: Optional[DatabaseManager] = None) -> HealthMonitor:
    """Initialize global health monitor"""
    global health_monitor
    health_monitor = HealthMonitor(db_manager)
    return health_monitor


def get_health_monitor() -> Optional[HealthMonitor]:
    """Get global health monitor instance"""
    return health_monitor