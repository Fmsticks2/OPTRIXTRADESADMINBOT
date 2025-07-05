"""Security utilities for OPTRIXTRADES Telegram Bot"""

import hashlib
import hmac
import re
import time
import logging
from typing import Dict, Any, Optional, List, Callable, Tuple
from functools import wraps
from datetime import datetime, timedelta
import json
import os
import asyncio
import ipaddress

from telegram import Update
from telegram.ext import ContextTypes

from config import BotConfig

logger = logging.getLogger(__name__)

class RateLimiter:
    """Rate limiting implementation to prevent abuse"""
    
    def __init__(self):
        self.requests = {}
        self.blocked_users = set()
        self.blocked_ips = set()
        self.suspicious_patterns = [
            r'(?i)\b(drop|delete)\s+table\b',  # SQL injection attempts
            r'(?i)\b(exec|system|eval)\s*\(',  # Command injection attempts
            r'(?i)<script[^>]*>',  # XSS attempts
            r'(?i)\b(and|or)\s+\d+=\d+',  # SQL injection
            r'(?i)\.\./',  # Path traversal
        ]
    
    def is_rate_limited(self, user_id: int) -> bool:
        """Check if a user is rate limited"""
        if not BotConfig.RATE_LIMIT_ENABLED:
            return False
        
        if user_id in self.blocked_users:
            return True
        
        current_time = time.time()
        minute_ago = current_time - 60
        
        # Initialize if this is a new user
        if user_id not in self.requests:
            self.requests[user_id] = []
        
        # Clean up old requests
        self.requests[user_id] = [t for t in self.requests[user_id] if t > minute_ago]
        
        # Check if user exceeded rate limit
        if len(self.requests[user_id]) >= BotConfig.MAX_REQUESTS_PER_MINUTE:
            logger.warning(f"User {user_id} has been rate limited")
            return True
        
        # Add current request
        self.requests[user_id].append(current_time)
        return False
    
    def block_user(self, user_id: int, duration_minutes: int = 30):
        """Block a user for a specified duration"""
        self.blocked_users.add(user_id)
        # Schedule unblock
        asyncio.create_task(self._schedule_unblock(user_id, duration_minutes))
        logger.warning(f"User {user_id} has been blocked for {duration_minutes} minutes")
    
    async def _schedule_unblock(self, user_id: int, duration_minutes: int):
        """Schedule user unblocking after duration"""
        await asyncio.sleep(duration_minutes * 60)
        if user_id in self.blocked_users:
            self.blocked_users.remove(user_id)
            logger.info(f"User {user_id} has been unblocked")
    
    def block_ip(self, ip_address: str, duration_minutes: int = 60):
        """Block an IP address for a specified duration"""
        self.blocked_ips.add(ip_address)
        # Schedule unblock
        asyncio.create_task(self._schedule_unblock_ip(ip_address, duration_minutes))
        logger.warning(f"IP {ip_address} has been blocked for {duration_minutes} minutes")
    
    async def _schedule_unblock_ip(self, ip_address: str, duration_minutes: int):
        """Schedule IP unblocking after duration"""
        await asyncio.sleep(duration_minutes * 60)
        if ip_address in self.blocked_ips:
            self.blocked_ips.remove(ip_address)
            logger.info(f"IP {ip_address} has been unblocked")
    
    def is_suspicious(self, text: str) -> bool:
        """Check if text contains suspicious patterns"""
        if not BotConfig.BLOCK_SUSPICIOUS_PATTERNS:
            return False
        
        if not text:
            return False
        
        for pattern in self.suspicious_patterns:
            if re.search(pattern, text):
                logger.warning(f"Suspicious pattern detected: {pattern}")
                return True
        
        return False


class SecurityUtils:
    """Security utilities for the bot"""
    
    @staticmethod
    def generate_hmac(data: str, secret: str) -> str:
        """Generate HMAC for data verification"""
        return hmac.new(
            secret.encode(),
            data.encode(),
            hashlib.sha256
        ).hexdigest()
    
    @staticmethod
    def verify_hmac(data: str, signature: str, secret: str) -> bool:
        """Verify HMAC signature"""
        expected = SecurityUtils.generate_hmac(data, secret)
        return hmac.compare_digest(expected, signature)
    
    @staticmethod
    def hash_password(password: str, salt: Optional[str] = None) -> Tuple[str, str]:
        """Hash a password with a salt"""
        if salt is None:
            salt = os.urandom(32).hex()
        
        hashed = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode(),
            salt.encode(),
            100000  # Number of iterations
        ).hex()
        
        return hashed, salt
    
    @staticmethod
    def verify_password(password: str, stored_hash: str, salt: str) -> bool:
        """Verify a password against a stored hash"""
        hashed, _ = SecurityUtils.hash_password(password, salt)
        return hmac.compare_digest(hashed, stored_hash)
    
    @staticmethod
    def sanitize_input(text: str) -> str:
        """Sanitize user input to prevent injection attacks"""
        if not text:
            return ""
        
        # Remove potentially dangerous characters
        sanitized = re.sub(r'[\<\>\&\;\`\|]', '', text)
        
        # Limit length
        return sanitized[:1000]  # Limit to 1000 chars
    
    @staticmethod
    def is_valid_ip(ip: str) -> bool:
        """Check if string is a valid IP address"""
        try:
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            return False
    
    @staticmethod
    def validate_webhook_request(request_data: Dict[str, Any], headers: Dict[str, str]) -> bool:
        """Validate webhook request authenticity"""
        if not BotConfig.WEBHOOK_SECRET_TOKEN:
            return True  # No validation if no token configured
        
        token = headers.get('X-Telegram-Bot-Api-Secret-Token')
        if not token:
            logger.warning("Missing secret token in webhook request")
            return False
        
        return token == BotConfig.WEBHOOK_SECRET_TOKEN


def rate_limit(func):
    """Decorator to apply rate limiting to handlers"""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if not update.effective_user:
            return await func(update, context, *args, **kwargs)
        
        user_id = update.effective_user.id
        
        # Get global rate limiter instance
        from telegram_bot.utils.security import rate_limiter
        
        # Check if user is rate limited
        if rate_limiter.is_rate_limited(user_id):
            await update.effective_message.reply_text(
                "You are sending too many requests. Please wait a moment before trying again."
            )
            return
        
        # Check for suspicious patterns in message text
        if update.effective_message and update.effective_message.text:
            if rate_limiter.is_suspicious(update.effective_message.text):
                await update.effective_message.reply_text(
                    "Your message contains suspicious patterns and has been blocked."
                )
                rate_limiter.block_user(user_id)
                return
        
        return await func(update, context, *args, **kwargs)
    
    return wrapper


def admin_only(func):
    """Decorator to restrict handler to admin users only"""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if not update.effective_user:
            return
        
        user_id = update.effective_user.id
        admin_id = BotConfig.ADMIN_USER_ID
        
        if not admin_id or str(user_id) != admin_id:
            await update.effective_message.reply_text(
                "This command is restricted to administrators."
            )
            logger.warning(f"Unauthorized admin command attempt by user {user_id}")
            return
        
        return await func(update, context, *args, **kwargs)
    
    return wrapper


# Create global instances
rate_limiter = RateLimiter()
security_utils = SecurityUtils()