"""Comprehensive security manager with rate limiting, input validation, and webhook verification"""

import hashlib
import hmac
import re
import time
import json
import ipaddress
from typing import Dict, List, Optional, Any, Tuple, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
from functools import wraps

from telegram import Update
from telegram.ext import ContextTypes

from config import BotConfig


class SecurityLevel(Enum):
    """Security levels for different operations"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RateLimitType(Enum):
    """Types of rate limiting"""
    USER = "user"
    CHAT = "chat"
    COMMAND = "command"
    GLOBAL = "global"
    IP = "ip"


@dataclass
class RateLimitConfig:
    """Rate limit configuration"""
    max_requests: int
    time_window_seconds: int
    burst_allowance: int = 0
    cooldown_seconds: int = 0


@dataclass
class RateLimitEntry:
    """Rate limit tracking entry"""
    requests: deque = field(default_factory=lambda: deque(maxlen=1000))
    last_request: datetime = field(default_factory=datetime.now)
    violation_count: int = 0
    is_blocked: bool = False
    block_until: Optional[datetime] = None


@dataclass
class SecurityEvent:
    """Security event for logging and monitoring"""
    event_type: str
    severity: SecurityLevel
    user_id: Optional[int]
    chat_id: Optional[int]
    ip_address: Optional[str]
    details: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)


class InputValidator:
    """Input validation and sanitization"""
    
    # Dangerous patterns to detect
    DANGEROUS_PATTERNS = [
        r'<script[^>]*>.*?</script>',  # Script tags
        r'javascript:',  # JavaScript URLs
        r'on\w+\s*=',  # Event handlers
        r'\beval\s*\(',  # eval() calls
        r'\bexec\s*\(',  # exec() calls
        r'\b__import__\s*\(',  # Python imports
        r'\bfile:///',  # File URLs
        r'\\x[0-9a-fA-F]{2}',  # Hex encoded chars
        r'%[0-9a-fA-F]{2}',  # URL encoded chars
    ]
    
    # SQL injection patterns
    SQL_INJECTION_PATTERNS = [
        r'\b(union|select|insert|update|delete|drop|create|alter)\b',
        r'[\'"]\s*(or|and)\s*[\'"]?\s*\d+\s*[=<>]',
        r'[\'"]\s*(or|and)\s*[\'"]?\s*[\'"]',
        r'--\s*$',
        r'/\*.*?\*/',
    ]
    
    # Command injection patterns
    COMMAND_INJECTION_PATTERNS = [
        r'[;&|`$]',  # Command separators
        r'\$\([^)]*\)',  # Command substitution
        r'`[^`]*`',  # Backtick execution
    ]
    
    @classmethod
    def validate_text_input(cls, text: str, max_length: int = 4096) -> Tuple[bool, List[str]]:
        """Validate text input for security issues"""
        issues = []
        
        # Check length
        if len(text) > max_length:
            issues.append(f"Text too long: {len(text)} > {max_length}")
        
        # Check for dangerous patterns
        for pattern in cls.DANGEROUS_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                issues.append(f"Dangerous pattern detected: {pattern}")
        
        # Check for SQL injection
        for pattern in cls.SQL_INJECTION_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                issues.append(f"Potential SQL injection: {pattern}")
        
        # Check for command injection
        for pattern in cls.COMMAND_INJECTION_PATTERNS:
            if re.search(pattern, text):
                issues.append(f"Potential command injection: {pattern}")
        
        return len(issues) == 0, issues
    
    @classmethod
    def sanitize_text(cls, text: str) -> str:
        """Sanitize text input"""
        # Remove null bytes
        text = text.replace('\x00', '')
        
        # Remove control characters except newlines and tabs
        text = ''.join(char for char in text if ord(char) >= 32 or char in '\n\t')
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    @classmethod
    def validate_user_id(cls, user_id: Any) -> bool:
        """Validate user ID format"""
        try:
            uid = int(user_id)
            return 0 < uid < 2**63  # Valid Telegram user ID range
        except (ValueError, TypeError):
            return False
    
    @classmethod
    def validate_chat_id(cls, chat_id: Any) -> bool:
        """Validate chat ID format"""
        try:
            cid = int(chat_id)
            return -2**63 < cid < 2**63  # Valid Telegram chat ID range
        except (ValueError, TypeError):
            return False
    
    @classmethod
    def validate_command(cls, command: str) -> bool:
        """Validate command format"""
        if not command.startswith('/'):
            return False
        
        # Remove bot username if present
        command = command.split('@')[0]
        
        # Check format: /command_name
        pattern = r'^/[a-zA-Z][a-zA-Z0-9_]*$'
        return bool(re.match(pattern, command))
    
    @classmethod
    def validate_callback_data(cls, data: str) -> bool:
        """Validate callback data"""
        if len(data) > 64:  # Telegram limit
            return False
        
        # Should only contain safe characters
        pattern = r'^[a-zA-Z0-9_:.-]+$'
        return bool(re.match(pattern, data))


class RateLimiter:
    """Advanced rate limiter with multiple strategies"""
    
    def __init__(self):
        self.limits: Dict[RateLimitType, RateLimitConfig] = {
            RateLimitType.USER: RateLimitConfig(max_requests=30, time_window_seconds=60, burst_allowance=5),
            RateLimitType.CHAT: RateLimitConfig(max_requests=100, time_window_seconds=60, burst_allowance=10),
            RateLimitType.COMMAND: RateLimitConfig(max_requests=10, time_window_seconds=60),
            RateLimitType.GLOBAL: RateLimitConfig(max_requests=1000, time_window_seconds=60),
            RateLimitType.IP: RateLimitConfig(max_requests=50, time_window_seconds=60)
        }
        
        self.entries: Dict[str, RateLimitEntry] = defaultdict(RateLimitEntry)
        self.blocked_users: Set[int] = set()
        self.blocked_ips: Set[str] = set()
        
        # Whitelist for admins and trusted users
        self.whitelisted_users: Set[int] = {BotConfig.ADMIN_USER_ID} if BotConfig.ADMIN_USER_ID else set()
        self.whitelisted_ips: Set[str] = set()
    
    def check_rate_limit(self, limit_type: RateLimitType, identifier: str, 
                        user_id: Optional[int] = None) -> Tuple[bool, Optional[str]]:
        """Check if request is within rate limits"""
        # Skip rate limiting for whitelisted users
        if user_id and user_id in self.whitelisted_users:
            return True, None
        
        # Check if user/IP is blocked
        if user_id and user_id in self.blocked_users:
            return False, "User is temporarily blocked"
        
        if limit_type == RateLimitType.IP and identifier in self.blocked_ips:
            return False, "IP address is temporarily blocked"
        
        config = self.limits[limit_type]
        entry = self.entries[f"{limit_type.value}:{identifier}"]
        now = datetime.now()
        
        # Check if still in cooldown period
        if entry.block_until and now < entry.block_until:
            return False, f"Rate limit exceeded. Try again in {(entry.block_until - now).seconds} seconds"
        
        # Clean old requests
        cutoff_time = now - timedelta(seconds=config.time_window_seconds)
        while entry.requests and entry.requests[0] < cutoff_time:
            entry.requests.popleft()
        
        # Check rate limit
        current_requests = len(entry.requests)
        max_allowed = config.max_requests + config.burst_allowance
        
        if current_requests >= max_allowed:
            # Rate limit exceeded
            entry.violation_count += 1
            
            # Progressive penalties
            if entry.violation_count >= 3:
                # Block for longer periods on repeated violations
                block_duration = min(300 * (2 ** (entry.violation_count - 3)), 3600)  # Max 1 hour
                entry.block_until = now + timedelta(seconds=block_duration)
                
                # Add to blocked list for faster checks
                if user_id:
                    self.blocked_users.add(user_id)
                elif limit_type == RateLimitType.IP:
                    self.blocked_ips.add(identifier)
            
            return False, f"Rate limit exceeded: {current_requests}/{config.max_requests} requests per {config.time_window_seconds}s"
        
        # Add current request
        entry.requests.append(now)
        entry.last_request = now
        
        return True, None
    
    def add_whitelist_user(self, user_id: int) -> None:
        """Add user to whitelist"""
        self.whitelisted_users.add(user_id)
        # Remove from blocked list if present
        self.blocked_users.discard(user_id)
    
    def add_whitelist_ip(self, ip_address: str) -> None:
        """Add IP to whitelist"""
        self.whitelisted_ips.add(ip_address)
        self.blocked_ips.discard(ip_address)
    
    def unblock_user(self, user_id: int) -> None:
        """Manually unblock a user"""
        self.blocked_users.discard(user_id)
        # Reset violation count
        for key in list(self.entries.keys()):
            if key.endswith(f":{user_id}"):
                self.entries[key].violation_count = 0
                self.entries[key].block_until = None
    
    def get_rate_limit_status(self, limit_type: RateLimitType, identifier: str) -> Dict[str, Any]:
        """Get current rate limit status"""
        config = self.limits[limit_type]
        entry = self.entries[f"{limit_type.value}:{identifier}"]
        now = datetime.now()
        
        # Clean old requests
        cutoff_time = now - timedelta(seconds=config.time_window_seconds)
        while entry.requests and entry.requests[0] < cutoff_time:
            entry.requests.popleft()
        
        return {
            "current_requests": len(entry.requests),
            "max_requests": config.max_requests,
            "time_window_seconds": config.time_window_seconds,
            "violation_count": entry.violation_count,
            "is_blocked": entry.block_until is not None and now < entry.block_until,
            "block_until": entry.block_until.isoformat() if entry.block_until else None,
            "requests_remaining": max(0, config.max_requests - len(entry.requests))
        }


class WebhookVerifier:
    """Webhook signature verification"""
    
    def __init__(self, secret_token: Optional[str] = None):
        self.secret_token = secret_token or BotConfig.WEBHOOK_SECRET
    
    def verify_signature(self, payload: bytes, signature: str) -> bool:
        """Verify webhook signature"""
        if not self.secret_token:
            return True  # Skip verification if no secret configured
        
        try:
            # Telegram uses HMAC-SHA256
            expected_signature = hmac.new(
                self.secret_token.encode('utf-8'),
                payload,
                hashlib.sha256
            ).hexdigest()
            
            # Compare signatures securely
            return hmac.compare_digest(signature, expected_signature)
            
        except Exception:
            return False
    
    def verify_telegram_signature(self, payload: bytes, telegram_signature: str) -> bool:
        """Verify Telegram's X-Telegram-Bot-Api-Secret-Token header"""
        if not self.secret_token:
            return True
        
        return hmac.compare_digest(telegram_signature, self.secret_token)


class IPWhitelist:
    """IP address whitelist management"""
    
    def __init__(self):
        # Telegram's IP ranges (as of 2024)
        self.telegram_ips = [
            ipaddress.ip_network('149.154.160.0/20'),
            ipaddress.ip_network('91.108.4.0/22'),
            ipaddress.ip_network('91.108.56.0/22'),
            ipaddress.ip_network('91.108.8.0/22'),
            ipaddress.ip_network('149.154.164.0/22'),
            ipaddress.ip_network('149.154.168.0/22'),
            ipaddress.ip_network('149.154.172.0/22'),
        ]
        
        self.custom_whitelist: List[ipaddress.IPv4Network] = []
        self.blacklist: List[ipaddress.IPv4Network] = []
    
    def is_telegram_ip(self, ip_address: str) -> bool:
        """Check if IP is from Telegram"""
        try:
            ip = ipaddress.ip_address(ip_address)
            return any(ip in network for network in self.telegram_ips)
        except ValueError:
            return False
    
    def is_whitelisted(self, ip_address: str) -> bool:
        """Check if IP is whitelisted"""
        try:
            ip = ipaddress.ip_address(ip_address)
            return any(ip in network for network in self.custom_whitelist)
        except ValueError:
            return False
    
    def is_blacklisted(self, ip_address: str) -> bool:
        """Check if IP is blacklisted"""
        try:
            ip = ipaddress.ip_address(ip_address)
            return any(ip in network for network in self.blacklist)
        except ValueError:
            return False
    
    def add_to_whitelist(self, ip_or_network: str) -> None:
        """Add IP or network to whitelist"""
        try:
            network = ipaddress.ip_network(ip_or_network, strict=False)
            self.custom_whitelist.append(network)
        except ValueError as e:
            raise ValueError(f"Invalid IP or network: {e}")
    
    def add_to_blacklist(self, ip_or_network: str) -> None:
        """Add IP or network to blacklist"""
        try:
            network = ipaddress.ip_network(ip_or_network, strict=False)
            self.blacklist.append(network)
        except ValueError as e:
            raise ValueError(f"Invalid IP or network: {e}")


class SecurityManager:
    """Comprehensive security manager"""
    
    def __init__(self):
        self.validator = InputValidator()
        self.rate_limiter = RateLimiter()
        self.webhook_verifier = WebhookVerifier()
        self.ip_whitelist = IPWhitelist()
        self.security_events: deque = deque(maxlen=1000)
        
        # Security policies
        self.policies = {
            "require_webhook_verification": True,
            "block_suspicious_ips": True,
            "log_all_security_events": True,
            "auto_block_repeated_violations": True,
            "validate_all_inputs": True
        }
    
    async def validate_request(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                              ip_address: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """Comprehensive request validation"""
        try:
            # Extract user and chat information
            user_id = update.effective_user.id if update.effective_user else None
            chat_id = update.effective_chat.id if update.effective_chat else None
            
            # IP address validation
            if ip_address and self.policies["block_suspicious_ips"]:
                if self.ip_whitelist.is_blacklisted(ip_address):
                    await self._log_security_event(
                        "ip_blacklisted", SecurityLevel.HIGH,
                        user_id, chat_id, ip_address,
                        {"reason": "IP address is blacklisted"}
                    )
                    return False, "Access denied"
                
                # Check IP rate limiting
                if ip_address:
                    allowed, message = self.rate_limiter.check_rate_limit(
                        RateLimitType.IP, ip_address, user_id
                    )
                    if not allowed:
                        await self._log_security_event(
                            "ip_rate_limit_exceeded", SecurityLevel.MEDIUM,
                            user_id, chat_id, ip_address,
                            {"reason": message}
                        )
                        return False, message
            
            # User rate limiting
            if user_id:
                allowed, message = self.rate_limiter.check_rate_limit(
                    RateLimitType.USER, str(user_id), user_id
                )
                if not allowed:
                    await self._log_security_event(
                        "user_rate_limit_exceeded", SecurityLevel.MEDIUM,
                        user_id, chat_id, ip_address,
                        {"reason": message}
                    )
                    return False, message
            
            # Chat rate limiting
            if chat_id:
                allowed, message = self.rate_limiter.check_rate_limit(
                    RateLimitType.CHAT, str(chat_id), user_id
                )
                if not allowed:
                    await self._log_security_event(
                        "chat_rate_limit_exceeded", SecurityLevel.MEDIUM,
                        user_id, chat_id, ip_address,
                        {"reason": message}
                    )
                    return False, message
            
            # Input validation
            if self.policies["validate_all_inputs"]:
                validation_result = await self._validate_update_content(update)
                if not validation_result[0]:
                    await self._log_security_event(
                        "input_validation_failed", SecurityLevel.HIGH,
                        user_id, chat_id, ip_address,
                        {"issues": validation_result[1]}
                    )
                    return False, "Invalid input detected"
            
            return True, None
            
        except Exception as e:
            await self._log_security_event(
                "security_validation_error", SecurityLevel.CRITICAL,
                user_id, chat_id, ip_address,
                {"error": str(e)}
            )
            return False, "Security validation failed"
    
    async def _validate_update_content(self, update: Update) -> Tuple[bool, List[str]]:
        """Validate all content in an update"""
        issues = []
        
        # Validate message text
        if update.message and update.message.text:
            valid, text_issues = self.validator.validate_text_input(update.message.text)
            if not valid:
                issues.extend(text_issues)
        
        # Validate callback data
        if update.callback_query and update.callback_query.data:
            if not self.validator.validate_callback_data(update.callback_query.data):
                issues.append("Invalid callback data format")
        
        # Validate user and chat IDs
        if update.effective_user:
            if not self.validator.validate_user_id(update.effective_user.id):
                issues.append("Invalid user ID")
        
        if update.effective_chat:
            if not self.validator.validate_chat_id(update.effective_chat.id):
                issues.append("Invalid chat ID")
        
        return len(issues) == 0, issues
    
    async def _log_security_event(self, event_type: str, severity: SecurityLevel,
                                 user_id: Optional[int], chat_id: Optional[int],
                                 ip_address: Optional[str], details: Dict[str, Any]) -> None:
        """Log security event"""
        event = SecurityEvent(
            event_type=event_type,
            severity=severity,
            user_id=user_id,
            chat_id=chat_id,
            ip_address=ip_address,
            details=details
        )
        
        self.security_events.append(event)
        
        if self.policies["log_all_security_events"]:
            # Log to structured logger
            import logging
            logger = logging.getLogger(__name__)
            
            log_data = {
                "event_type": event_type,
                "severity": severity.value,
                "user_id": user_id,
                "chat_id": chat_id,
                "ip_address": ip_address,
                "details": details,
                "timestamp": event.timestamp.isoformat()
            }
            
            if severity in [SecurityLevel.HIGH, SecurityLevel.CRITICAL]:
                logger.warning(f"Security event: {event_type}", extra=log_data)
            else:
                logger.info(f"Security event: {event_type}", extra=log_data)
    
    def get_security_summary(self) -> Dict[str, Any]:
        """Get security summary and statistics"""
        now = datetime.now()
        last_hour = now - timedelta(hours=1)
        last_day = now - timedelta(days=1)
        
        recent_events = [e for e in self.security_events if e.timestamp >= last_hour]
        daily_events = [e for e in self.security_events if e.timestamp >= last_day]
        
        return {
            "total_events": len(self.security_events),
            "events_last_hour": len(recent_events),
            "events_last_day": len(daily_events),
            "events_by_type": self._count_events_by_field(daily_events, "event_type"),
            "events_by_severity": self._count_events_by_field(daily_events, "severity"),
            "blocked_users_count": len(self.rate_limiter.blocked_users),
            "blocked_ips_count": len(self.rate_limiter.blocked_ips),
            "whitelisted_users_count": len(self.rate_limiter.whitelisted_users),
            "policies": self.policies
        }
    
    def _count_events_by_field(self, events: List[SecurityEvent], field: str) -> Dict[str, int]:
        """Count events by a specific field"""
        counts = defaultdict(int)
        for event in events:
            value = getattr(event, field)
            if hasattr(value, 'value'):  # Enum
                value = value.value
            counts[str(value)] += 1
        return dict(counts)


def security_check(security_level: SecurityLevel = SecurityLevel.MEDIUM):
    """Decorator for security checks"""
    def decorator(func):
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            # Get IP address from context if available
            ip_address = getattr(context, 'ip_address', None)
            
            # Perform security validation
            allowed, message = await security_manager.validate_request(update, context, ip_address)
            
            if not allowed:
                # Send security denial message to user
                if update.effective_message:
                    await update.effective_message.reply_text(
                        "Access denied for security reasons. Please try again later."
                    )
                return
            
            # Proceed with original function
            return await func(update, context, *args, **kwargs)
        
        return wrapper
    return decorator


# Global security manager instance
security_manager = SecurityManager()