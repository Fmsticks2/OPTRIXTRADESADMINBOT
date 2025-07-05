"""Enhanced error handling with structured logging, correlation IDs, and metrics"""

import html
import json
import logging
import traceback
import time
import uuid
from functools import wraps
from typing import Callable, Dict, Any, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from config import BotConfig

logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """Error severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Error categories for classification"""
    TELEGRAM_API = "telegram_api"
    DATABASE = "database"
    VALIDATION = "validation"
    AUTHENTICATION = "authentication"
    RATE_LIMIT = "rate_limit"
    EXTERNAL_API = "external_api"
    BUSINESS_LOGIC = "business_logic"
    SYSTEM = "system"
    UNKNOWN = "unknown"


@dataclass
class ErrorMetrics:
    """Error metrics tracking"""
    total_errors: int = 0
    errors_by_category: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    errors_by_severity: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    errors_by_hour: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    recent_errors: deque = field(default_factory=lambda: deque(maxlen=100))
    error_rate_per_minute: float = 0.0
    avg_response_time: float = 0.0
    last_reset: datetime = field(default_factory=datetime.now)


@dataclass
class ErrorContext:
    """Enhanced error context with correlation tracking"""
    correlation_id: str
    timestamp: datetime
    error_type: str
    error_message: str
    severity: ErrorSeverity
    category: ErrorCategory
    user_id: Optional[int] = None
    chat_id: Optional[int] = None
    command: Optional[str] = None
    function_name: Optional[str] = None
    traceback: Optional[str] = None
    additional_data: Dict[str, Any] = field(default_factory=dict)
    response_time_ms: Optional[float] = None


class StructuredLogger:
    """Structured logger with correlation ID support"""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.correlation_id: Optional[str] = None
    
    def set_correlation_id(self, correlation_id: str) -> None:
        """Set correlation ID for current context"""
        self.correlation_id = correlation_id
    
    def _format_message(self, message: str, extra_data: Optional[Dict[str, Any]] = None) -> str:
        """Format message with correlation ID and structured data"""
        structured_data = {
            "correlation_id": self.correlation_id,
            "timestamp": datetime.now().isoformat(),
        }
        
        if extra_data:
            structured_data.update(extra_data)
        
        return f"{message} | {json.dumps(structured_data, default=str)}"
    
    def debug(self, message: str, extra_data: Optional[Dict[str, Any]] = None) -> None:
        self.logger.debug(self._format_message(message, extra_data))
    
    def info(self, message: str, extra_data: Optional[Dict[str, Any]] = None) -> None:
        self.logger.info(self._format_message(message, extra_data))
    
    def warning(self, message: str, extra_data: Optional[Dict[str, Any]] = None) -> None:
        self.logger.warning(self._format_message(message, extra_data))
    
    def error(self, message: str, extra_data: Optional[Dict[str, Any]] = None, exc_info: bool = False) -> None:
        self.logger.error(self._format_message(message, extra_data), exc_info=exc_info)
    
    def critical(self, message: str, extra_data: Optional[Dict[str, Any]] = None) -> None:
        self.logger.critical(self._format_message(message, extra_data))


class ErrorClassifier:
    """Classify errors by category and severity"""
    
    @staticmethod
    def classify_error(error: Exception, context: Optional[Dict[str, Any]] = None) -> tuple[ErrorCategory, ErrorSeverity]:
        """Classify error by category and severity"""
        error_type = type(error).__name__
        error_message = str(error).lower()
        
        # Category classification
        category = ErrorCategory.UNKNOWN
        
        if "telegram" in error_message or "bot" in error_message:
            category = ErrorCategory.TELEGRAM_API
        elif "database" in error_message or "sql" in error_message or "connection" in error_message:
            category = ErrorCategory.DATABASE
        elif "validation" in error_message or "invalid" in error_message:
            category = ErrorCategory.VALIDATION
        elif "auth" in error_message or "permission" in error_message:
            category = ErrorCategory.AUTHENTICATION
        elif "rate" in error_message or "limit" in error_message:
            category = ErrorCategory.RATE_LIMIT
        elif "http" in error_message or "api" in error_message:
            category = ErrorCategory.EXTERNAL_API
        elif "timeout" in error_message or "network" in error_message:
            category = ErrorCategory.SYSTEM
        else:
            category = ErrorCategory.BUSINESS_LOGIC
        
        # Severity classification
        severity = ErrorSeverity.MEDIUM
        
        critical_keywords = ["critical", "fatal", "crash", "corruption", "security"]
        high_keywords = ["timeout", "connection", "database", "authentication"]
        low_keywords = ["validation", "input", "format"]
        
        if any(keyword in error_message for keyword in critical_keywords):
            severity = ErrorSeverity.CRITICAL
        elif any(keyword in error_message for keyword in high_keywords):
            severity = ErrorSeverity.HIGH
        elif any(keyword in error_message for keyword in low_keywords):
            severity = ErrorSeverity.LOW
        
        return category, severity


class EnhancedErrorHandler:
    """Enhanced error handler with comprehensive tracking and metrics"""
    
    def __init__(self):
        self.metrics = ErrorMetrics()
        self.structured_logger = StructuredLogger(__name__)
        self.classifier = ErrorClassifier()
        self.alert_thresholds = {
            "error_rate_per_minute": 10,
            "critical_errors_per_hour": 5,
            "database_errors_per_hour": 20
        }
        self.last_alert_times: Dict[str, datetime] = {}
        self.alert_cooldown = timedelta(minutes=15)
    
    async def handle_error(self, update: object, context: ContextTypes.DEFAULT_TYPE, 
                          function_name: Optional[str] = None) -> None:
        """Enhanced error handler with comprehensive logging and metrics"""
        start_time = time.time()
        correlation_id = str(uuid.uuid4())[:8]
        self.structured_logger.set_correlation_id(correlation_id)
        
        try:
            # Extract error information
            error = context.error
            category, severity = self.classifier.classify_error(error)
            
            # Create error context
            error_context = ErrorContext(
                correlation_id=correlation_id,
                timestamp=datetime.now(),
                error_type=type(error).__name__,
                error_message=str(error),
                severity=severity,
                category=category,
                function_name=function_name,
                traceback=traceback.format_exc(),
                response_time_ms=(time.time() - start_time) * 1000
            )
            
            # Extract user and chat information
            if isinstance(update, Update):
                if update.effective_user:
                    error_context.user_id = update.effective_user.id
                if update.effective_chat:
                    error_context.chat_id = update.effective_chat.id
                if update.effective_message and update.effective_message.text:
                    # Extract command if present
                    text = update.effective_message.text
                    if text.startswith('/'):
                        error_context.command = text.split()[0]
            
            # Update metrics
            self._update_metrics(error_context)
            
            # Log error with structured data
            self._log_structured_error(error_context)
            
            # Check for alerts
            await self._check_and_send_alerts(error_context)
            
            # Notify admin if configured
            await self._notify_admin(error_context, update, context)
            
            # Handle user response
            await self._handle_user_response(error_context, update, context)
            
        except Exception as handler_error:
            # Fallback error handling
            logger.error(f"Error handler itself failed: {handler_error}", exc_info=True)
    
    def _update_metrics(self, error_context: ErrorContext) -> None:
        """Update error metrics"""
        self.metrics.total_errors += 1
        self.metrics.errors_by_category[error_context.category.value] += 1
        self.metrics.errors_by_severity[error_context.severity.value] += 1
        
        # Track errors by hour
        hour_key = error_context.timestamp.strftime("%Y-%m-%d-%H")
        self.metrics.errors_by_hour[hour_key] += 1
        
        # Add to recent errors
        self.metrics.recent_errors.append(error_context)
        
        # Calculate error rate per minute
        recent_minute_errors = sum(
            1 for err in self.metrics.recent_errors
            if (datetime.now() - err.timestamp).total_seconds() <= 60
        )
        self.metrics.error_rate_per_minute = recent_minute_errors
        
        # Update average response time
        if error_context.response_time_ms:
            total_response_time = self.metrics.avg_response_time * (self.metrics.total_errors - 1)
            self.metrics.avg_response_time = (total_response_time + error_context.response_time_ms) / self.metrics.total_errors
    
    def _log_structured_error(self, error_context: ErrorContext) -> None:
        """Log error with structured data"""
        log_data = {
            "error_type": error_context.error_type,
            "category": error_context.category.value,
            "severity": error_context.severity.value,
            "user_id": error_context.user_id,
            "chat_id": error_context.chat_id,
            "command": error_context.command,
            "function_name": error_context.function_name,
            "response_time_ms": error_context.response_time_ms
        }
        
        log_message = f"Error occurred: {error_context.error_message}"
        
        if error_context.severity == ErrorSeverity.CRITICAL:
            self.structured_logger.critical(log_message, log_data)
        elif error_context.severity == ErrorSeverity.HIGH:
            self.structured_logger.error(log_message, log_data, exc_info=True)
        elif error_context.severity == ErrorSeverity.MEDIUM:
            self.structured_logger.warning(log_message, log_data)
        else:
            self.structured_logger.info(log_message, log_data)
    
    async def _check_and_send_alerts(self, error_context: ErrorContext) -> None:
        """Check thresholds and send alerts if necessary"""
        now = datetime.now()
        
        # Check error rate threshold
        if self.metrics.error_rate_per_minute >= self.alert_thresholds["error_rate_per_minute"]:
            await self._send_alert(
                "high_error_rate",
                f"High error rate detected: {self.metrics.error_rate_per_minute} errors/minute",
                error_context
            )
        
        # Check critical errors threshold
        critical_errors_last_hour = sum(
            1 for err in self.metrics.recent_errors
            if err.severity == ErrorSeverity.CRITICAL and 
               (now - err.timestamp).total_seconds() <= 3600
        )
        
        if critical_errors_last_hour >= self.alert_thresholds["critical_errors_per_hour"]:
            await self._send_alert(
                "critical_errors",
                f"Multiple critical errors: {critical_errors_last_hour} in the last hour",
                error_context
            )
        
        # Check database errors threshold
        db_errors_last_hour = sum(
            1 for err in self.metrics.recent_errors
            if err.category == ErrorCategory.DATABASE and 
               (now - err.timestamp).total_seconds() <= 3600
        )
        
        if db_errors_last_hour >= self.alert_thresholds["database_errors_per_hour"]:
            await self._send_alert(
                "database_errors",
                f"High database error rate: {db_errors_last_hour} errors in the last hour",
                error_context
            )
    
    async def _send_alert(self, alert_type: str, message: str, error_context: ErrorContext) -> None:
        """Send alert with cooldown"""
        now = datetime.now()
        last_alert = self.last_alert_times.get(alert_type)
        
        if last_alert and (now - last_alert) < self.alert_cooldown:
            return  # Skip alert due to cooldown
        
        self.last_alert_times[alert_type] = now
        
        alert_data = {
            "alert_type": alert_type,
            "message": message,
            "correlation_id": error_context.correlation_id,
            "timestamp": now.isoformat(),
            "metrics": {
                "total_errors": self.metrics.total_errors,
                "error_rate_per_minute": self.metrics.error_rate_per_minute,
                "avg_response_time": self.metrics.avg_response_time
            }
        }
        
        self.structured_logger.critical(f"ALERT: {message}", alert_data)
        
        # Send to external monitoring system if configured
        # This could be Slack, Discord, PagerDuty, etc.
        # Implementation depends on your monitoring setup
    
    async def _notify_admin(self, error_context: ErrorContext, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Notify admin of errors based on severity"""
        if not BotConfig.ADMIN_USER_ID:
            return
        
        # Only notify for medium severity and above
        if error_context.severity in [ErrorSeverity.LOW]:
            return
        
        try:
            # Format admin notification
            severity_emoji = {
                ErrorSeverity.LOW: "ℹ️",
                ErrorSeverity.MEDIUM: "⚠️",
                ErrorSeverity.HIGH: "🚨",
                ErrorSeverity.CRITICAL: "🔥"
            }
            
            message = f"{severity_emoji[error_context.severity]} <b>Error Alert</b>\n\n"
            message += f"<b>Correlation ID:</b> <code>{error_context.correlation_id}</code>\n"
            message += f"<b>Category:</b> {error_context.category.value}\n"
            message += f"<b>Severity:</b> {error_context.severity.value}\n"
            message += f"<b>Type:</b> {error_context.error_type}\n"
            message += f"<b>Message:</b> {html.escape(error_context.error_message[:200])}\n"
            
            if error_context.user_id:
                message += f"<b>User ID:</b> {error_context.user_id}\n"
            if error_context.command:
                message += f"<b>Command:</b> {error_context.command}\n"
            if error_context.function_name:
                message += f"<b>Function:</b> {error_context.function_name}\n"
            
            message += f"<b>Time:</b> {error_context.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n"
            
            # Add metrics summary for critical errors
            if error_context.severity == ErrorSeverity.CRITICAL:
                message += f"\n<b>Current Metrics:</b>\n"
                message += f"• Error rate: {self.metrics.error_rate_per_minute}/min\n"
                message += f"• Total errors: {self.metrics.total_errors}\n"
                message += f"• Avg response time: {self.metrics.avg_response_time:.2f}ms\n"
            
            # Truncate if too long
            if len(message) > 4000:
                message = message[:3900] + "...\n\n<i>Message truncated</i>"
            
            await context.bot.send_message(
                chat_id=BotConfig.ADMIN_USER_ID,
                text=message,
                parse_mode=ParseMode.HTML
            )
            
        except Exception as e:
            logger.error(f"Failed to send admin notification: {e}")
    
    async def _handle_user_response(self, error_context: ErrorContext, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle user response based on error type"""
        if not isinstance(update, Update):
            return
        
        try:
            # Answer callback query if present
            if update.callback_query:
                await update.callback_query.answer(
                    "An error occurred. Please try again later."
                )
            
            # Send user message based on error category
            if update.effective_message:
                user_message = self._get_user_friendly_message(error_context)
                await update.effective_message.reply_text(user_message)
                
        except Exception as e:
            logger.error(f"Failed to handle user response: {e}")
    
    def _get_user_friendly_message(self, error_context: ErrorContext) -> str:
        """Get user-friendly error message based on category"""
        messages = {
            ErrorCategory.TELEGRAM_API: "Sorry, there's a temporary issue with the messaging service. Please try again in a moment.",
            ErrorCategory.DATABASE: "We're experiencing some technical difficulties. Please try again later.",
            ErrorCategory.VALIDATION: "Please check your input and try again.",
            ErrorCategory.AUTHENTICATION: "Authentication failed. Please contact an administrator.",
            ErrorCategory.RATE_LIMIT: "You're sending requests too quickly. Please wait a moment and try again.",
            ErrorCategory.EXTERNAL_API: "External service is temporarily unavailable. Please try again later.",
            ErrorCategory.BUSINESS_LOGIC: "Unable to process your request. Please contact support if the issue persists.",
            ErrorCategory.SYSTEM: "System is temporarily unavailable. Please try again later.",
            ErrorCategory.UNKNOWN: "An unexpected error occurred. Our team has been notified."
        }
        
        base_message = messages.get(error_context.category, messages[ErrorCategory.UNKNOWN])
        
        if error_context.severity == ErrorSeverity.CRITICAL:
            base_message += " We're working to resolve this issue as quickly as possible."
        
        return base_message
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get comprehensive metrics summary"""
        now = datetime.now()
        
        # Calculate error rates for different time periods
        last_hour_errors = sum(
            1 for err in self.metrics.recent_errors
            if (now - err.timestamp).total_seconds() <= 3600
        )
        
        last_day_errors = sum(
            1 for err in self.metrics.recent_errors
            if (now - err.timestamp).total_seconds() <= 86400
        )
        
        return {
            "total_errors": self.metrics.total_errors,
            "error_rate_per_minute": self.metrics.error_rate_per_minute,
            "errors_last_hour": last_hour_errors,
            "errors_last_day": last_day_errors,
            "avg_response_time_ms": round(self.metrics.avg_response_time, 2),
            "errors_by_category": dict(self.metrics.errors_by_category),
            "errors_by_severity": dict(self.metrics.errors_by_severity),
            "uptime_hours": round((now - self.metrics.last_reset).total_seconds() / 3600, 2),
            "last_reset": self.metrics.last_reset.isoformat()
        }
    
    def reset_metrics(self) -> None:
        """Reset error metrics"""
        self.metrics = ErrorMetrics()
        logger.info("Error metrics reset")


def enhanced_error_handler_decorator(func: Callable) -> Callable:
    """Enhanced decorator for error handling with correlation tracking"""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        correlation_id = str(uuid.uuid4())[:8]
        start_time = time.time()
        
        # Set correlation ID in context for downstream use
        if not hasattr(context, 'user_data'):
            context.user_data = {}
        context.user_data['correlation_id'] = correlation_id
        
        try:
            result = await func(update, context, *args, **kwargs)
            
            # Log successful execution
            execution_time = (time.time() - start_time) * 1000
            logger.debug(f"Function {func.__name__} executed successfully in {execution_time:.2f}ms [correlation_id: {correlation_id}]")
            
            return result
            
        except Exception as e:
            # Create enhanced error context
            error_context = context
            error_context.error = e
            
            # Handle error with enhanced handler
            await enhanced_error_handler.handle_error(update, error_context, func.__name__)
            
            # Re-raise for upstream handling if needed
            raise
    
    return wrapper


# Global enhanced error handler instance
enhanced_error_handler = EnhancedErrorHandler()

# Alias for backward compatibility
error_handler = enhanced_error_handler_decorator