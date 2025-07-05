"""Logging configuration for OPTRIXTRADES Telegram Bot"""

import logging
import logging.handlers
import os
import sys
from datetime import datetime
from typing import Dict, Any, Optional

from config import BotConfig


def setup_logging(log_level: str = None, log_file: str = None) -> None:
    """Configure logging for the application.
    
    Sets up logging with appropriate handlers, formatters, and log levels.
    Supports both console and file logging with different formats.
    
    Args:
        log_level: The logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to the log file (if None, uses default from config)
    """
    # Get log level from config if not provided
    if log_level is None:
        log_level = BotConfig.LOG_LEVEL
    
    # Convert string log level to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Get log file from config if not provided
    if log_file is None:
        log_dir = BotConfig.LOG_DIR or "logs"
        # Create logs directory if it doesn't exist
        os.makedirs(log_dir, exist_ok=True)
        # Default log filename includes date
        date_str = datetime.now().strftime("%Y-%m-%d")
        log_file = os.path.join(log_dir, f"bot_{date_str}.log")
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # Remove existing handlers to avoid duplicates when reconfiguring
    for handler in root_logger.handlers[:]:  
        root_logger.removeHandler(handler)
    
    # Create formatters
    console_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    file_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s"
    )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # File handler with rotation
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=10*1024*1024,  # 10 MB
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)
    
    # Set specific log levels for some noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    
    # Log startup message
    logging.info(f"Logging initialized at level {log_level}")
    logging.info(f"Log file: {log_file}")


class StructuredLogger:
    """Utility class for structured logging with consistent format."""
    
    @staticmethod
    def log_user_action(user_id: int, action: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Log user actions in a structured format.
        
        Args:
            user_id: The ID of the user performing the action
            action: The action being performed
            details: Additional details about the action
        """
        log_data = {
            "user_id": user_id,
            "action": action,
            "timestamp": datetime.now().isoformat(),
            "details": details or {}
        }
        logging.info(f"USER_ACTION: {log_data}")
    
    @staticmethod
    def log_bot_event(event_type: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Log bot events in a structured format.
        
        Args:
            event_type: The type of event
            details: Additional details about the event
        """
        log_data = {
            "event_type": event_type,
            "timestamp": datetime.now().isoformat(),
            "details": details or {}
        }
        logging.info(f"BOT_EVENT: {log_data}")
    
    @staticmethod
    def log_verification(user_id: int, status: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Log verification events in a structured format.
        
        Args:
            user_id: The ID of the user being verified
            status: The verification status (submitted, approved, rejected, etc.)
            details: Additional details about the verification
        """
        log_data = {
            "user_id": user_id,
            "status": status,
            "timestamp": datetime.now().isoformat(),
            "details": details or {}
        }
        logging.info(f"VERIFICATION: {log_data}")
    
    @staticmethod
    def log_performance(operation: str, duration_ms: float, details: Optional[Dict[str, Any]] = None) -> None:
        """Log performance metrics in a structured format.
        
        Args:
            operation: The operation being measured
            duration_ms: The duration of the operation in milliseconds
            details: Additional details about the operation
        """
        log_data = {
            "operation": operation,
            "duration_ms": duration_ms,
            "timestamp": datetime.now().isoformat(),
            "details": details or {}
        }
        logging.info(f"PERFORMANCE: {log_data}")