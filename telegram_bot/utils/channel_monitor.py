"""Channel member count monitoring for OPTRIXTRADES Telegram Bot"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import json
from telegram import Bot
from telegram.error import TelegramError

from config import BotConfig
from telegram_bot.utils.monitoring import metrics

logger = logging.getLogger(__name__)

class ChannelMemberMonitor:
    """Monitor channel member count and detect new joins"""
    
    def __init__(self, bot: Bot):
        self.bot = bot
        self.channel_id = BotConfig.PREMIUM_CHANNEL_ID
        self.monitoring_active = False
        self.monitoring_task: Optional[asyncio.Task] = None
        self.check_interval = 300  # 5 minutes
        self.last_member_count = 0
        self.member_count_history = []
        self.max_history_size = 288  # 24 hours of 5-minute intervals
        
    async def start_monitoring(self) -> None:
        """Start channel member count monitoring"""
        if self.monitoring_active:
            logger.warning("Channel monitoring already active")
            return
            
        if not self.channel_id:
            logger.error("PREMIUM_CHANNEL_ID not configured")
            return
            
        self.monitoring_active = True
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info(f"Channel member monitoring started for channel {self.channel_id}")
        
    async def stop_monitoring(self) -> None:
        """Stop channel member count monitoring"""
        self.monitoring_active = False
        
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
                
        logger.info("Channel member monitoring stopped")
        
    async def _monitoring_loop(self) -> None:
        """Main monitoring loop"""
        while self.monitoring_active:
            try:
                await self._check_member_count()
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Channel monitoring error: {e}")
                await asyncio.sleep(self.check_interval)
                
    async def _check_member_count(self) -> None:
        """Check current member count and detect changes"""
        try:
            # Get current member count
            chat = await self.bot.get_chat(self.channel_id)
            current_count = chat.member_count or 0
            
            # Record the count with timestamp
            timestamp = datetime.now()
            self.member_count_history.append({
                'timestamp': timestamp.isoformat(),
                'count': current_count
            })
            
            # Maintain history size
            if len(self.member_count_history) > self.max_history_size:
                self.member_count_history.pop(0)
                
            # Check for new members
            if self.last_member_count > 0 and current_count > self.last_member_count:
                new_members = current_count - self.last_member_count
                logger.info(f"Detected {new_members} new channel members")
                
                # Track the metric
                metrics.track_user(is_new=True, is_active=True)
                
                # Log the event
                await self._log_member_increase(new_members, current_count)
                
            self.last_member_count = current_count
            
            logger.debug(f"Channel member count: {current_count}")
            
        except TelegramError as e:
            logger.error(f"Failed to get channel member count: {e}")
        except Exception as e:
            logger.error(f"Unexpected error checking member count: {e}")
            
    async def _log_member_increase(self, new_members: int, total_count: int) -> None:
        """Log member increase event"""
        event_data = {
            'event': 'channel_member_increase',
            'new_members': new_members,
            'total_members': total_count,
            'timestamp': datetime.now().isoformat(),
            'channel_id': self.channel_id
        }
        
        logger.info(f"Channel member increase: {json.dumps(event_data)}")
        
        # Send to monitoring webhook if configured
        if BotConfig.MONITORING_WEBHOOK:
            try:
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    await session.post(
                        BotConfig.MONITORING_WEBHOOK,
                        json=event_data,
                        timeout=aiohttp.ClientTimeout(total=10)
                    )
            except Exception as e:
                logger.error(f"Failed to send member increase event to webhook: {e}")
                
    def get_member_count_stats(self) -> Dict[str, Any]:
        """Get member count statistics"""
        if not self.member_count_history:
            return {
                'current_count': self.last_member_count,
                'history_available': False
            }
            
        # Calculate statistics
        counts = [entry['count'] for entry in self.member_count_history]
        
        # Get counts from different time periods
        now = datetime.now()
        hour_ago = now - timedelta(hours=1)
        day_ago = now - timedelta(days=1)
        
        hour_ago_count = None
        day_ago_count = None
        
        for entry in reversed(self.member_count_history):
            entry_time = datetime.fromisoformat(entry['timestamp'])
            
            if hour_ago_count is None and entry_time <= hour_ago:
                hour_ago_count = entry['count']
                
            if day_ago_count is None and entry_time <= day_ago:
                day_ago_count = entry['count']
                break
                
        return {
            'current_count': self.last_member_count,
            'min_count': min(counts) if counts else 0,
            'max_count': max(counts) if counts else 0,
            'hour_change': (self.last_member_count - hour_ago_count) if hour_ago_count else 0,
            'day_change': (self.last_member_count - day_ago_count) if day_ago_count else 0,
            'history_entries': len(self.member_count_history),
            'monitoring_active': self.monitoring_active,
            'last_check': self.member_count_history[-1]['timestamp'] if self.member_count_history else None
        }
        
    async def send_welcome_message(self, user_id: int) -> bool:
        """Send welcome message to a user who joined the channel"""
        try:
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            
            welcome_text = (
                "🎉 You have successfully joined the channel, click start to continue registration."
            )
            
            # Create inline keyboard with start button
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🚀 Start", url=f"https://t.me/{self.bot.username}?start=welcome")]
            ])
            
            await self.bot.send_message(
                chat_id=user_id,
                text=welcome_text,
                reply_markup=keyboard,
                parse_mode='HTML'
            )
            
            logger.info(f"Welcome message sent to user {user_id}")
            return True
            
        except TelegramError as e:
            logger.error(f"Failed to send welcome message to user {user_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending welcome message to user {user_id}: {e}")
            return False

# Global instance
channel_monitor: Optional[ChannelMemberMonitor] = None

def initialize_channel_monitor(bot: Bot) -> ChannelMemberMonitor:
    """Initialize the global channel monitor instance"""
    global channel_monitor
    channel_monitor = ChannelMemberMonitor(bot)
    return channel_monitor

def get_channel_monitor() -> Optional[ChannelMemberMonitor]:
    """Get the global channel monitor instance"""
    return channel_monitor