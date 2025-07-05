import os
from typing import List, Dict, Any
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class BotConfig:
    """Configuration class for OPTRIXTRADES bot"""
    
    # Bot Configuration
    BOT_TOKEN: str = os.getenv('BOT_TOKEN', '')
    BROKER_LINK: str = os.getenv('BROKER_LINK', '')
    PREMIUM_CHANNEL_ID: str = os.getenv('PREMIUM_CHANNEL_ID', '')
    ADMIN_USERNAME: str = os.getenv('ADMIN_USERNAME', '')
    ADMIN_USER_ID: str = os.getenv('ADMIN_USER_ID', '')
    
    # Database
    DATABASE_PATH: str = os.getenv('DATABASE_PATH', 'trading_bot.db')
    SQLITE_DATABASE_PATH: str = os.path.join(os.path.dirname(__file__), os.getenv('SQLITE_DATABASE_PATH', 'trading_bot.db'))
    DATABASE_TYPE: str = os.getenv('DATABASE_TYPE', 'postgresql' if os.getenv('DATABASE_URL') else 'sqlite')
    DATABASE_URL: str = os.getenv('DATABASE_URL', 'postgresql://postgres:lSyqidmHknVYbkBghtRweAwPISFrfMca@caboose.proxy.rlwy.net:21466/railway')
    
    # PostgreSQL specific settings
    POSTGRES_HOST: str = os.getenv('PGHOST', os.getenv('POSTGRES_HOST', 'localhost'))
    POSTGRES_PORT: int = int(os.getenv('PGPORT', os.getenv('POSTGRES_PORT', '5432')))
    POSTGRES_DB: str = os.getenv('PGDATABASE', os.getenv('POSTGRES_DB', 'railway'))
    POSTGRES_USER: str = os.getenv('PGUSER', os.getenv('POSTGRES_USER', 'postgres'))
    POSTGRES_PASSWORD: str = os.getenv('PGPASSWORD', os.getenv('POSTGRES_PASSWORD', ''))
    
    # Auto-Verification
    AUTO_VERIFY_ENABLED: bool = os.getenv('AUTO_VERIFY_ENABLED', 'true').lower() == 'true'
    MIN_UID_LENGTH: int = int(os.getenv('MIN_UID_LENGTH', '6'))
    MAX_UID_LENGTH: int = int(os.getenv('MAX_UID_LENGTH', '20'))
    AUTO_VERIFY_CONFIDENCE_THRESHOLD: float = float(os.getenv('AUTO_VERIFY_CONFIDENCE_THRESHOLD', '0.8'))
    DAILY_AUTO_APPROVAL_LIMIT: int = int(os.getenv('DAILY_AUTO_APPROVAL_LIMIT', '100'))
    REQUIRE_BOTH_UID_AND_IMAGE: bool = os.getenv('REQUIRE_BOTH_UID_AND_IMAGE', 'true').lower() == 'true'
    MANUAL_REVIEW_SUSPICIOUS: bool = os.getenv('MANUAL_REVIEW_SUSPICIOUS', 'true').lower() == 'true'
    
    # Time-Based Settings
    VERIFICATION_WINDOW_HOURS: int = int(os.getenv('VERIFICATION_WINDOW_HOURS', '24'))
    AUTO_VERIFY_BUSINESS_HOURS_ONLY: bool = os.getenv('AUTO_VERIFY_BUSINESS_HOURS_ONLY', 'false').lower() == 'true'
    BUSINESS_HOURS_START: int = int(os.getenv('BUSINESS_HOURS_START', '9'))
    BUSINESS_HOURS_END: int = int(os.getenv('BUSINESS_HOURS_END', '17'))
    TIMEZONE: str = os.getenv('TIMEZONE', 'UTC')
    
    # Admin Notifications
    ADMIN_ERROR_NOTIFICATIONS: bool = os.getenv('ADMIN_ERROR_NOTIFICATIONS', 'true').lower() == 'true'
    NOTIFY_ON_MANUAL_NEEDED: bool = os.getenv('NOTIFY_ON_MANUAL_NEEDED', 'true').lower() == 'true'
    NOTIFY_ON_AUTO_APPROVAL: bool = os.getenv('NOTIFY_ON_AUTO_APPROVAL', 'false').lower() == 'true'
    NOTIFY_ON_REJECTION: bool = os.getenv('NOTIFY_ON_REJECTION', 'true').lower() == 'true'
    DAILY_SUMMARY: bool = os.getenv('DAILY_SUMMARY', 'true').lower() == 'true'
    QUEUE_SIZE_WARNING_THRESHOLD: int = int(os.getenv('QUEUE_SIZE_WARNING_THRESHOLD', '10'))
    
    # Image Validation
    MAX_FILE_SIZE_MB: int = int(os.getenv('MAX_FILE_SIZE_MB', '10'))
    ALLOWED_IMAGE_FORMATS: List[str] = os.getenv('ALLOWED_IMAGE_FORMATS', 'jpg,jpeg,png,pdf').split(',')
    MIN_IMAGE_WIDTH: int = int(os.getenv('MIN_IMAGE_WIDTH', '200'))
    MIN_IMAGE_HEIGHT: int = int(os.getenv('MIN_IMAGE_HEIGHT', '200'))
    
    # Security
    RATE_LIMIT_ENABLED: bool = os.getenv('RATE_LIMIT_ENABLED', 'true').lower() == 'true'
    MAX_REQUESTS_PER_MINUTE: int = int(os.getenv('MAX_REQUESTS_PER_MINUTE', '30'))
    BLOCK_SUSPICIOUS_PATTERNS: bool = os.getenv('BLOCK_SUSPICIOUS_PATTERNS', 'true').lower() == 'true'
    
    # Logging
    LOG_LEVEL: str = os.getenv('LOG_LEVEL', 'INFO')
    LOG_DIR: str = os.getenv('LOG_DIR', 'logs')
    LOG_FILE_PATH: str = os.getenv('LOG_FILE_PATH', 'bot.log')
    SCHEDULER_LOG_FILE_PATH: str = os.getenv('SCHEDULER_LOG_FILE_PATH', 'scheduler.log')
    ENABLE_FILE_LOGGING: bool = os.getenv('ENABLE_FILE_LOGGING', 'true').lower() == 'true'
    ENABLE_CONSOLE_LOGGING: bool = os.getenv('ENABLE_CONSOLE_LOGGING', 'true').lower() == 'true'
    
    # Follow-up Messages
    FOLLOW_UP_ENABLED: bool = os.getenv('FOLLOW_UP_ENABLED', 'true').lower() == 'true'
    FOLLOW_UP_1_DELAY_HOURS: int = int(os.getenv('FOLLOW_UP_1_DELAY_HOURS', '6'))
    FOLLOW_UP_2_DELAY_HOURS: int = int(os.getenv('FOLLOW_UP_2_DELAY_HOURS', '23'))
    FOLLOW_UP_3_DELAY_HOURS: int = int(os.getenv('FOLLOW_UP_3_DELAY_HOURS', '22'))
    FOLLOW_UP_4_DELAY_DAYS: int = int(os.getenv('FOLLOW_UP_4_DELAY_DAYS', '1'))
    FOLLOW_UP_5_DELAY_DAYS: int = int(os.getenv('FOLLOW_UP_5_DELAY_DAYS', '1'))
    
    # Broker Settings
    BROKER_NAME: str = os.getenv('BROKER_NAME', 'IQ Option')
    MIN_DEPOSIT_AMOUNT: int = int(os.getenv('MIN_DEPOSIT_AMOUNT', '20'))
    DEPOSIT_CURRENCY: str = os.getenv('DEPOSIT_CURRENCY', 'USD')
    
    # Performance
    DATABASE_CONNECTION_TIMEOUT: int = int(os.getenv('DATABASE_CONNECTION_TIMEOUT', '30'))
    MESSAGE_RETRY_ATTEMPTS: int = int(os.getenv('MESSAGE_RETRY_ATTEMPTS', '3'))
    WEBHOOK_TIMEOUT: int = int(os.getenv('WEBHOOK_TIMEOUT', '60'))
    
    # Development
    DEBUG_MODE: bool = os.getenv('DEBUG_MODE', 'false').lower() == 'true'
    TEST_MODE: bool = os.getenv('TEST_MODE', 'false').lower() == 'true'
    MOCK_VERIFICATION: bool = os.getenv('MOCK_VERIFICATION', 'false').lower() == 'true'

    # Webhook Configuration (consolidated and Railway-optimized)
    BOT_MODE: str = os.getenv('BOT_MODE', 'webhook')  # Default to webhook for Railway
    WEBHOOK_ENABLED: bool = os.getenv('WEBHOOK_ENABLED', 'true').lower() == 'true'  # Enable by default
    WEBHOOK_URL: str = os.getenv('WEBHOOK_URL', '')
    WEBHOOK_PORT: int = int(os.getenv('PORT') or os.getenv('WEBHOOK_PORT') or '8080')  # Railway uses PORT
    WEBHOOK_SECRET_TOKEN: str = os.getenv('WEBHOOK_SECRET_TOKEN', '')
    WEBHOOK_PATH: str = os.getenv('WEBHOOK_PATH', '/webhook')

    # Ngrok Configuration (not needed for Railway)
    NGROK_ENABLED: bool = os.getenv('NGROK_ENABLED', 'false').lower() == 'true'
    NGROK_AUTH_TOKEN: str = os.getenv('NGROK_AUTH_TOKEN', '')
    
    # Optional Services
    REDIS_URL: str = os.getenv('REDIS_URL', '')
    REDIS_PASSWORD: str = os.getenv('REDIS_PASSWORD', '')
    ANALYTICS_ENABLED: bool = os.getenv('ANALYTICS_ENABLED', 'false').lower() == 'true'
    SENTRY_DSN: str = os.getenv('SENTRY_DSN', '')
    MONITORING_WEBHOOK: str = os.getenv('MONITORING_WEBHOOK', '')
    
    @classmethod
    def validate_config(cls) -> Dict[str, Any]:
        """Validate configuration and return validation results"""
        errors = []
        warnings = []
        
        # Required fields validation
        required_fields = [
            ('BOT_TOKEN', cls.BOT_TOKEN),
            ('BROKER_LINK', cls.BROKER_LINK),
            ('PREMIUM_CHANNEL_ID', cls.PREMIUM_CHANNEL_ID),
            ('ADMIN_USERNAME', cls.ADMIN_USERNAME),
            ('ADMIN_USER_ID', cls.ADMIN_USER_ID),
            ('SQLITE_DATABASE_PATH', cls.SQLITE_DATABASE_PATH)
        ]
        
        for field_name, field_value in required_fields:
            if not field_value:
                errors.append(f"Missing required field: {field_name}")
        
        # Bot token format validation
        if cls.BOT_TOKEN and ':' not in cls.BOT_TOKEN:
            errors.append("BOT_TOKEN format is invalid (should contain ':')")
        
        # Channel ID format validation
        if cls.PREMIUM_CHANNEL_ID and not cls.PREMIUM_CHANNEL_ID.startswith('-100'):
            warnings.append("PREMIUM_CHANNEL_ID should start with '-100' for supergroups")
        
        # Admin user ID validation
        if cls.ADMIN_USER_ID and not cls.ADMIN_USER_ID.isdigit():
            errors.append("ADMIN_USER_ID should be a numeric Telegram user ID")
        
        # UID length validation
        if cls.MIN_UID_LENGTH >= cls.MAX_UID_LENGTH:
            errors.append("MIN_UID_LENGTH should be less than MAX_UID_LENGTH")
        
        # Business hours validation
        if cls.BUSINESS_HOURS_START >= cls.BUSINESS_HOURS_END:
            warnings.append("BUSINESS_HOURS_START should be less than BUSINESS_HOURS_END")
        
        # Webhook validation for Railway
        if cls.BOT_MODE == 'webhook' and not cls.WEBHOOK_URL and not os.getenv('RAILWAY_ENVIRONMENT'):
            warnings.append("WEBHOOK_URL should be set when using webhook mode (auto-detected on Railway)")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }
    
    @classmethod
    def get_summary(cls) -> str:
        """Get configuration summary"""
        return f"""
🤖 OPTRIXTRADES Bot Configuration Summary
========================================

Bot Settings:
- Token: {cls.BOT_TOKEN[:10] + '...' if cls.BOT_TOKEN else 'NOT SET'}
- Mode: {cls.BOT_MODE.upper()}
- Broker: {cls.BROKER_NAME}
- Channel: {cls.PREMIUM_CHANNEL_ID}
- Admin: @{cls.ADMIN_USERNAME}

Webhook Settings:
- Enabled: {cls.WEBHOOK_ENABLED}
- Port: {cls.WEBHOOK_PORT}
- URL: {cls.WEBHOOK_URL or 'Auto-detect on Railway'}

Auto-Verification:
- Enabled: {cls.AUTO_VERIFY_ENABLED}
- UID Length: {cls.MIN_UID_LENGTH}-{cls.MAX_UID_LENGTH}
- Daily Limit: {cls.DAILY_AUTO_APPROVAL_LIMIT}

Notifications:
- Manual Review: {cls.NOTIFY_ON_MANUAL_NEEDED}
- Auto Approval: {cls.NOTIFY_ON_AUTO_APPROVAL}
- Rejections: {cls.NOTIFY_ON_REJECTION}

Follow-ups:
- Enabled: {cls.FOLLOW_UP_ENABLED}
- First: {cls.FOLLOW_UP_1_DELAY_HOURS}h
- Second: {cls.FOLLOW_UP_2_DELAY_HOURS}h

Development:
- Debug Mode: {cls.DEBUG_MODE}
- Test Mode: {cls.TEST_MODE}
========================================
        """.strip()
    
    @classmethod
    def is_railway_environment(cls) -> bool:
        """Check if running on Railway"""
        # Check for multiple Railway indicators since RAILWAY_ENVIRONMENT might not be set during build
        railway_indicators = [
            'RAILWAY_ENVIRONMENT',
            'RAILWAY_SERVICE_NAME', 
            'RAILWAY_PROJECT_ID',
            'RAILWAY_PUBLIC_DOMAIN',
            'RAILWAY_PRIVATE_DOMAIN'
        ]
        return any(os.getenv(indicator) for indicator in railway_indicators)
    
    @classmethod
    def get_webhook_url(cls) -> str:
        """Get webhook URL, auto-detect on Railway"""
        if cls.WEBHOOK_URL:
            return cls.WEBHOOK_URL
        
        # Auto-detect Railway URL
        railway_url = os.getenv('RAILWAY_PUBLIC_DOMAIN')
        if railway_url:
            return f"https://{railway_url}/webhook/{cls.BOT_TOKEN}"
        
        return ""

# Create global config instance
config = BotConfig()

# Only validate configuration if we're in a production environment or if explicitly requested
# This prevents validation errors during local development when env vars aren't set
def validate_and_report_config(force_validation=False):
    """Validate configuration and report results"""
    # Skip validation in local development unless forced
    if not force_validation and not config.is_railway_environment() and not os.getenv('VALIDATE_CONFIG'):
        return
    
    validation_result = config.validate_config()
    if not validation_result['valid']:
        print("❌ Configuration Errors:")
        for error in validation_result['errors']:
            print(f"  - {error}")
        
        # Only exit in production environments
        if config.is_railway_environment():
            print("\n🚨 Configuration errors detected in production environment!")
            print("Please check your Railway environment variables.")
    
    if validation_result['warnings']:
        print("⚠️  Configuration Warnings:")
        for warning in validation_result['warnings']:
            print(f"  - {warning}")
    
    return validation_result

# Environment-specific setup
if config.is_railway_environment():
    print(f"🚄 Railway Environment Detected")
    print(f"📡 Webhook Mode: {config.WEBHOOK_ENABLED}")
    print(f"🔌 Port: {config.WEBHOOK_PORT}")
    webhook_url = config.get_webhook_url()
    if webhook_url:
        print(f"🌐 Webhook URL: {webhook_url}")
    
    # Validate configuration in Railway environment
    validate_and_report_config(force_validation=True)
else:
    # Only show local development message if we're actually in a local environment
    # During Railway build, some variables might not be available yet
    if not any(os.getenv(var) for var in ['PORT', 'RAILWAY_STATIC_URL', 'NIXPACKS_METADATA']):
        print("🏠 Local Development Environment")
        print("💡 Set VALIDATE_CONFIG=true to enable configuration validation locally")
    # If we detect build-time Railway indicators, stay silent to avoid confusion