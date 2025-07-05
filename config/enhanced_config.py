"""Enhanced configuration management with validation and hot-reloading"""

import os
import json
import yaml
import logging
from typing import Dict, Any, List, Optional, Union, Type
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import asyncio
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

logger = logging.getLogger(__name__)


class Environment(Enum):
    """Environment types"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"


class LogLevel(Enum):
    """Log level enumeration"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class ValidationRule:
    """Configuration validation rule"""
    field_name: str
    required: bool = False
    data_type: Type = str
    min_value: Optional[Union[int, float]] = None
    max_value: Optional[Union[int, float]] = None
    allowed_values: Optional[List[Any]] = None
    pattern: Optional[str] = None
    custom_validator: Optional[callable] = None


@dataclass
class ConfigSection:
    """Base configuration section"""
    pass


@dataclass
class DatabaseConfig(ConfigSection):
    """Database configuration"""
    type: str = "sqlite"
    url: str = ""
    host: str = "localhost"
    port: int = 5432
    name: str = "optrixtrades"
    user: str = "postgres"
    password: str = ""
    pool_min_size: int = 2
    pool_max_size: int = 20
    connection_timeout: int = 30
    retry_attempts: int = 3
    health_check_interval: int = 60


@dataclass
class SecurityConfig(ConfigSection):
    """Security configuration"""
    rate_limit_enabled: bool = True
    max_requests_per_minute: int = 30
    max_requests_per_hour: int = 1000
    block_suspicious_patterns: bool = True
    webhook_secret_token: str = ""
    admin_whitelist: List[str] = field(default_factory=list)
    ip_whitelist: List[str] = field(default_factory=list)
    encryption_key: str = ""
    session_timeout: int = 3600


@dataclass
class LoggingConfig(ConfigSection):
    """Logging configuration"""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file_enabled: bool = True
    console_enabled: bool = True
    file_path: str = "logs/bot.log"
    max_file_size: int = 10485760  # 10MB
    backup_count: int = 5
    structured_logging: bool = True
    correlation_id_enabled: bool = True
    performance_logging: bool = False


@dataclass
class MonitoringConfig(ConfigSection):
    """Monitoring and metrics configuration"""
    enabled: bool = True
    metrics_endpoint: str = "/metrics"
    health_endpoint: str = "/health"
    prometheus_enabled: bool = False
    sentry_dsn: str = ""
    error_rate_threshold: float = 0.05
    response_time_threshold: int = 5000
    alert_webhook: str = ""


@dataclass
class CacheConfig(ConfigSection):
    """Caching configuration"""
    enabled: bool = True
    backend: str = "memory"  # memory, redis
    redis_url: str = ""
    default_ttl: int = 3600
    max_size: int = 1000
    cleanup_interval: int = 300


@dataclass
class BotConfig(ConfigSection):
    """Bot-specific configuration"""
    token: str = ""
    webhook_url: str = ""
    webhook_port: int = 8080
    webhook_path: str = "/webhook"
    mode: str = "webhook"  # webhook, polling
    admin_user_id: str = ""
    admin_username: str = ""
    premium_channel_id: str = ""
    broker_link: str = ""
    auto_verify_enabled: bool = True
    follow_up_enabled: bool = True


class ConfigurationManager:
    """Enhanced configuration manager with validation and hot-reloading"""
    
    def __init__(self, config_dir: str = "config", environment: Optional[str] = None):
        self.config_dir = Path(config_dir)
        self.environment = Environment(environment or os.getenv('ENVIRONMENT', 'development'))
        self.config_data: Dict[str, Any] = {}
        self.validation_rules: List[ValidationRule] = []
        self.observers: List[Observer] = []
        self.reload_callbacks: List[callable] = []
        self.last_reload: Optional[datetime] = None
        self.is_valid: bool = False
        self.validation_errors: List[str] = []
        
        # Configuration sections
        self.database = DatabaseConfig()
        self.security = SecurityConfig()
        self.logging = LoggingConfig()
        self.monitoring = MonitoringConfig()
        self.cache = CacheConfig()
        self.bot = BotConfig()
        
        self._setup_validation_rules()
    
    def _setup_validation_rules(self) -> None:
        """Setup configuration validation rules"""
        self.validation_rules = [
            # Bot configuration
            ValidationRule("bot.token", required=True, pattern=r"^\d+:[A-Za-z0-9_-]+$"),
            ValidationRule("bot.admin_user_id", required=True, pattern=r"^\d+$"),
            ValidationRule("bot.webhook_port", data_type=int, min_value=1, max_value=65535),
            ValidationRule("bot.mode", allowed_values=["webhook", "polling"]),
            
            # Database configuration
            ValidationRule("database.type", allowed_values=["postgresql", "sqlite"]),
            ValidationRule("database.pool_min_size", data_type=int, min_value=1),
            ValidationRule("database.pool_max_size", data_type=int, min_value=1),
            ValidationRule("database.connection_timeout", data_type=int, min_value=1),
            
            # Security configuration
            ValidationRule("security.max_requests_per_minute", data_type=int, min_value=1),
            ValidationRule("security.session_timeout", data_type=int, min_value=60),
            
            # Logging configuration
            ValidationRule("logging.level", allowed_values=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]),
            ValidationRule("logging.max_file_size", data_type=int, min_value=1024),
            
            # Monitoring configuration
            ValidationRule("monitoring.error_rate_threshold", data_type=float, min_value=0.0, max_value=1.0),
            ValidationRule("monitoring.response_time_threshold", data_type=int, min_value=100),
        ]
    
    async def load_configuration(self) -> None:
        """Load configuration from files and environment variables"""
        try:
            # Load base configuration
            await self._load_base_config()
            
            # Load environment-specific configuration
            await self._load_environment_config()
            
            # Override with environment variables
            self._load_environment_variables()
            
            # Apply configuration to dataclass instances
            self._apply_configuration()
            
            # Validate configuration
            self.validate_configuration()
            
            self.last_reload = datetime.now()
            logger.info(f"Configuration loaded successfully for environment: {self.environment.value}")
            
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            raise
    
    async def _load_base_config(self) -> None:
        """Load base configuration file"""
        base_config_path = self.config_dir / "base.yaml"
        if base_config_path.exists():
            with open(base_config_path, 'r') as f:
                base_config = yaml.safe_load(f)
                self.config_data.update(base_config or {})
    
    async def _load_environment_config(self) -> None:
        """Load environment-specific configuration"""
        env_config_path = self.config_dir / f"{self.environment.value}.yaml"
        if env_config_path.exists():
            with open(env_config_path, 'r') as f:
                env_config = yaml.safe_load(f)
                self._deep_merge(self.config_data, env_config or {})
    
    def _load_environment_variables(self) -> None:
        """Load configuration from environment variables"""
        env_mapping = {
            # Bot configuration
            'BOT_TOKEN': 'bot.token',
            'WEBHOOK_URL': 'bot.webhook_url',
            'WEBHOOK_PORT': 'bot.webhook_port',
            'BOT_MODE': 'bot.mode',
            'ADMIN_USER_ID': 'bot.admin_user_id',
            'ADMIN_USERNAME': 'bot.admin_username',
            'PREMIUM_CHANNEL_ID': 'bot.premium_channel_id',
            'BROKER_LINK': 'bot.broker_link',
            
            # Database configuration
            'DATABASE_TYPE': 'database.type',
            'DATABASE_URL': 'database.url',
            'POSTGRES_HOST': 'database.host',
            'POSTGRES_PORT': 'database.port',
            'POSTGRES_DB': 'database.name',
            'POSTGRES_USER': 'database.user',
            'POSTGRES_PASSWORD': 'database.password',
            'DB_POOL_MIN_SIZE': 'database.pool_min_size',
            'DB_POOL_MAX_SIZE': 'database.pool_max_size',
            
            # Security configuration
            'RATE_LIMIT_ENABLED': 'security.rate_limit_enabled',
            'MAX_REQUESTS_PER_MINUTE': 'security.max_requests_per_minute',
            'WEBHOOK_SECRET_TOKEN': 'security.webhook_secret_token',
            
            # Logging configuration
            'LOG_LEVEL': 'logging.level',
            'LOG_FILE_PATH': 'logging.file_path',
            'ENABLE_FILE_LOGGING': 'logging.file_enabled',
            
            # Monitoring configuration
            'MONITORING_ENABLED': 'monitoring.enabled',
            'SENTRY_DSN': 'monitoring.sentry_dsn',
            
            # Cache configuration
            'CACHE_ENABLED': 'cache.enabled',
            'REDIS_URL': 'cache.redis_url',
        }
        
        for env_var, config_path in env_mapping.items():
            value = os.getenv(env_var)
            if value is not None:
                self._set_nested_value(self.config_data, config_path, self._convert_env_value(value))
    
    def _convert_env_value(self, value: str) -> Union[str, int, float, bool]:
        """Convert environment variable string to appropriate type"""
        # Boolean conversion
        if value.lower() in ('true', 'false'):
            return value.lower() == 'true'
        
        # Integer conversion
        try:
            return int(value)
        except ValueError:
            pass
        
        # Float conversion
        try:
            return float(value)
        except ValueError:
            pass
        
        # Return as string
        return value
    
    def _deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> None:
        """Deep merge two dictionaries"""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value
    
    def _set_nested_value(self, data: Dict[str, Any], path: str, value: Any) -> None:
        """Set nested dictionary value using dot notation"""
        keys = path.split('.')
        current = data
        
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        
        current[keys[-1]] = value
    
    def _get_nested_value(self, data: Dict[str, Any], path: str, default: Any = None) -> Any:
        """Get nested dictionary value using dot notation"""
        keys = path.split('.')
        current = data
        
        try:
            for key in keys:
                current = current[key]
            return current
        except (KeyError, TypeError):
            return default
    
    def _apply_configuration(self) -> None:
        """Apply configuration data to dataclass instances"""
        # Apply database configuration
        db_config = self.config_data.get('database', {})
        for field_name, value in db_config.items():
            if hasattr(self.database, field_name):
                setattr(self.database, field_name, value)
        
        # Apply security configuration
        security_config = self.config_data.get('security', {})
        for field_name, value in security_config.items():
            if hasattr(self.security, field_name):
                setattr(self.security, field_name, value)
        
        # Apply logging configuration
        logging_config = self.config_data.get('logging', {})
        for field_name, value in logging_config.items():
            if hasattr(self.logging, field_name):
                setattr(self.logging, field_name, value)
        
        # Apply monitoring configuration
        monitoring_config = self.config_data.get('monitoring', {})
        for field_name, value in monitoring_config.items():
            if hasattr(self.monitoring, field_name):
                setattr(self.monitoring, field_name, value)
        
        # Apply cache configuration
        cache_config = self.config_data.get('cache', {})
        for field_name, value in cache_config.items():
            if hasattr(self.cache, field_name):
                setattr(self.cache, field_name, value)
        
        # Apply bot configuration
        bot_config = self.config_data.get('bot', {})
        for field_name, value in bot_config.items():
            if hasattr(self.bot, field_name):
                setattr(self.bot, field_name, value)
    
    def validate_configuration(self) -> None:
        """Validate configuration against rules"""
        self.validation_errors = []
        
        for rule in self.validation_rules:
            value = self._get_nested_value(self.config_data, rule.field_name)
            
            # Check if required field is present
            if rule.required and value is None:
                self.validation_errors.append(f"Required field '{rule.field_name}' is missing")
                continue
            
            if value is None:
                continue
            
            # Check data type
            if rule.data_type and not isinstance(value, rule.data_type):
                try:
                    value = rule.data_type(value)
                    self._set_nested_value(self.config_data, rule.field_name, value)
                except (ValueError, TypeError):
                    self.validation_errors.append(
                        f"Field '{rule.field_name}' must be of type {rule.data_type.__name__}"
                    )
                    continue
            
            # Check min/max values
            if rule.min_value is not None and value < rule.min_value:
                self.validation_errors.append(
                    f"Field '{rule.field_name}' must be >= {rule.min_value}"
                )
            
            if rule.max_value is not None and value > rule.max_value:
                self.validation_errors.append(
                    f"Field '{rule.field_name}' must be <= {rule.max_value}"
                )
            
            # Check allowed values
            if rule.allowed_values and value not in rule.allowed_values:
                self.validation_errors.append(
                    f"Field '{rule.field_name}' must be one of: {rule.allowed_values}"
                )
            
            # Check pattern
            if rule.pattern:
                import re
                if not re.match(rule.pattern, str(value)):
                    self.validation_errors.append(
                        f"Field '{rule.field_name}' does not match required pattern"
                    )
            
            # Custom validation
            if rule.custom_validator:
                try:
                    if not rule.custom_validator(value):
                        self.validation_errors.append(
                            f"Field '{rule.field_name}' failed custom validation"
                        )
                except Exception as e:
                    self.validation_errors.append(
                        f"Field '{rule.field_name}' custom validation error: {e}"
                    )
        
        self.is_valid = len(self.validation_errors) == 0
        
        if not self.is_valid:
            error_msg = "Configuration validation failed:\n" + "\n".join(self.validation_errors)
            logger.error(error_msg)
            if self.environment == Environment.PRODUCTION:
                raise ValueError(error_msg)
        else:
            logger.info("Configuration validation passed")
    
    def enable_hot_reloading(self) -> None:
        """Enable hot-reloading of configuration files"""
        class ConfigFileHandler(FileSystemEventHandler):
            def __init__(self, config_manager):
                self.config_manager = config_manager
            
            def on_modified(self, event):
                if not event.is_directory and event.src_path.endswith(('.yaml', '.yml', '.json')):
                    logger.info(f"Configuration file changed: {event.src_path}")
                    asyncio.create_task(self.config_manager.reload_configuration())
        
        observer = Observer()
        observer.schedule(ConfigFileHandler(self), str(self.config_dir), recursive=True)
        observer.start()
        self.observers.append(observer)
        
        logger.info("Configuration hot-reloading enabled")
    
    async def reload_configuration(self) -> None:
        """Reload configuration and notify callbacks"""
        try:
            await self.load_configuration()
            
            # Notify callbacks
            for callback in self.reload_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(self)
                    else:
                        callback(self)
                except Exception as e:
                    logger.error(f"Configuration reload callback failed: {e}")
            
            logger.info("Configuration reloaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to reload configuration: {e}")
    
    def add_reload_callback(self, callback: callable) -> None:
        """Add callback to be called when configuration is reloaded"""
        self.reload_callbacks.append(callback)
    
    def get_config_summary(self) -> Dict[str, Any]:
        """Get configuration summary for debugging"""
        return {
            "environment": self.environment.value,
            "last_reload": self.last_reload.isoformat() if self.last_reload else None,
            "is_valid": self.is_valid,
            "validation_errors": self.validation_errors,
            "sections": {
                "database": {
                    "type": self.database.type,
                    "host": self.database.host,
                    "pool_size": f"{self.database.pool_min_size}-{self.database.pool_max_size}"
                },
                "security": {
                    "rate_limit_enabled": self.security.rate_limit_enabled,
                    "max_requests_per_minute": self.security.max_requests_per_minute
                },
                "logging": {
                    "level": self.logging.level,
                    "file_enabled": self.logging.file_enabled
                },
                "monitoring": {
                    "enabled": self.monitoring.enabled,
                    "sentry_enabled": bool(self.monitoring.sentry_dsn)
                },
                "bot": {
                    "mode": self.bot.mode,
                    "webhook_port": self.bot.webhook_port,
                    "auto_verify_enabled": self.bot.auto_verify_enabled
                }
            }
        }
    
    def stop_hot_reloading(self) -> None:
        """Stop hot-reloading observers"""
        for observer in self.observers:
            observer.stop()
            observer.join()
        self.observers.clear()
        logger.info("Configuration hot-reloading stopped")


# Global configuration manager instance
config_manager = ConfigurationManager()