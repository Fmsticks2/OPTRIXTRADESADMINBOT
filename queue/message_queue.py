"""Message queuing system for high-volume operations"""

import asyncio
import json
import pickle
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Callable, Union, TypeVar, Generic
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import deque
import logging
from functools import wraps
import traceback

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None

from config import BotConfig

logger = logging.getLogger(__name__)

T = TypeVar('T')


class MessagePriority(Enum):
    """Message priority levels"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


class MessageStatus(Enum):
    """Message processing status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    DEAD_LETTER = "dead_letter"


class QueueBackend(Enum):
    """Queue backend types"""
    REDIS = "redis"
    MEMORY = "memory"
    HYBRID = "hybrid"


@dataclass
class QueueMessage:
    """Queue message with metadata"""
    id: str
    queue_name: str
    payload: Any
    priority: MessagePriority = MessagePriority.NORMAL
    created_at: datetime = field(default_factory=datetime.now)
    scheduled_at: Optional[datetime] = None
    attempts: int = 0
    max_attempts: int = 3
    status: MessageStatus = MessageStatus.PENDING
    error_message: Optional[str] = None
    processing_started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    tags: List[str] = field(default_factory=list)
    timeout_seconds: int = 300  # 5 minutes default
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        data = asdict(self)
        # Convert datetime objects to ISO strings
        for key, value in data.items():
            if isinstance(value, datetime):
                data[key] = value.isoformat()
            elif isinstance(value, MessagePriority):
                data[key] = value.value
            elif isinstance(value, MessageStatus):
                data[key] = value.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'QueueMessage':
        """Create from dictionary"""
        # Convert ISO strings back to datetime objects
        for key in ['created_at', 'scheduled_at', 'processing_started_at', 'completed_at']:
            if data.get(key):
                data[key] = datetime.fromisoformat(data[key])
        
        # Convert enum values
        if 'priority' in data:
            data['priority'] = MessagePriority(data['priority'])
        if 'status' in data:
            data['status'] = MessageStatus(data['status'])
        
        return cls(**data)


@dataclass
class QueueStats:
    """Queue statistics"""
    total_messages: int = 0
    pending_messages: int = 0
    processing_messages: int = 0
    completed_messages: int = 0
    failed_messages: int = 0
    dead_letter_messages: int = 0
    average_processing_time: float = 0.0
    throughput_per_minute: float = 0.0
    error_rate: float = 0.0


class MessageHandler:
    """Base class for message handlers"""
    
    async def handle(self, message: QueueMessage) -> bool:
        """Handle a message. Return True if successful, False otherwise."""
        raise NotImplementedError
    
    async def on_error(self, message: QueueMessage, error: Exception) -> None:
        """Called when message handling fails"""
        logger.error(f"Error handling message {message.id}: {error}")
    
    async def on_retry(self, message: QueueMessage) -> bool:
        """Called before retrying a failed message. Return True to retry, False to send to dead letter."""
        return message.attempts < message.max_attempts


class MemoryQueue:
    """In-memory queue implementation"""
    
    def __init__(self, max_size: int = 10000):
        self.max_size = max_size
        self.queues: Dict[str, deque] = {}
        self.processing: Dict[str, QueueMessage] = {}
        self.dead_letter: Dict[str, List[QueueMessage]] = {}
        self.stats: Dict[str, QueueStats] = {}
        self._lock = asyncio.Lock()
        self._handlers: Dict[str, MessageHandler] = {}
        self._workers: Dict[str, List[asyncio.Task]] = {}
        self._running = False
    
    async def create_queue(self, queue_name: str, max_workers: int = 1) -> None:
        """Create a new queue"""
        async with self._lock:
            if queue_name not in self.queues:
                self.queues[queue_name] = deque()
                self.dead_letter[queue_name] = []
                self.stats[queue_name] = QueueStats()
                self._workers[queue_name] = []
                logger.info(f"Created memory queue: {queue_name}")
    
    async def delete_queue(self, queue_name: str) -> None:
        """Delete a queue"""
        async with self._lock:
            if queue_name in self.queues:
                # Stop workers
                for task in self._workers.get(queue_name, []):
                    task.cancel()
                
                # Clean up
                del self.queues[queue_name]
                del self.dead_letter[queue_name]
                del self.stats[queue_name]
                if queue_name in self._workers:
                    del self._workers[queue_name]
                if queue_name in self._handlers:
                    del self._handlers[queue_name]
                
                logger.info(f"Deleted memory queue: {queue_name}")
    
    async def enqueue(self, message: QueueMessage) -> bool:
        """Add message to queue"""
        async with self._lock:
            if message.queue_name not in self.queues:
                await self.create_queue(message.queue_name)
            
            queue = self.queues[message.queue_name]
            
            # Check size limit
            if len(queue) >= self.max_size:
                logger.warning(f"Queue {message.queue_name} is full")
                return False
            
            # Insert based on priority
            inserted = False
            for i, existing_msg in enumerate(queue):
                if message.priority.value > existing_msg.priority.value:
                    queue.insert(i, message)
                    inserted = True
                    break
            
            if not inserted:
                queue.append(message)
            
            self.stats[message.queue_name].total_messages += 1
            self.stats[message.queue_name].pending_messages += 1
            
            return True
    
    async def dequeue(self, queue_name: str) -> Optional[QueueMessage]:
        """Get next message from queue"""
        async with self._lock:
            if queue_name not in self.queues or not self.queues[queue_name]:
                return None
            
            # Check for scheduled messages
            now = datetime.now()
            queue = self.queues[queue_name]
            
            for i, message in enumerate(queue):
                if message.scheduled_at is None or message.scheduled_at <= now:
                    # Remove from queue
                    del queue[i]
                    
                    # Mark as processing
                    message.status = MessageStatus.PROCESSING
                    message.processing_started_at = now
                    self.processing[message.id] = message
                    
                    # Update stats
                    self.stats[queue_name].pending_messages -= 1
                    self.stats[queue_name].processing_messages += 1
                    
                    return message
            
            return None
    
    async def ack_message(self, message_id: str) -> bool:
        """Acknowledge successful message processing"""
        async with self._lock:
            if message_id in self.processing:
                message = self.processing[message_id]
                message.status = MessageStatus.COMPLETED
                message.completed_at = datetime.now()
                
                # Update stats
                queue_name = message.queue_name
                self.stats[queue_name].processing_messages -= 1
                self.stats[queue_name].completed_messages += 1
                
                # Calculate processing time
                if message.processing_started_at:
                    processing_time = (message.completed_at - message.processing_started_at).total_seconds()
                    current_avg = self.stats[queue_name].average_processing_time
                    completed = self.stats[queue_name].completed_messages
                    self.stats[queue_name].average_processing_time = (
                        (current_avg * (completed - 1) + processing_time) / completed
                    )
                
                del self.processing[message_id]
                return True
            
            return False
    
    async def nack_message(self, message_id: str, error_message: str = "") -> bool:
        """Negative acknowledge - message processing failed"""
        async with self._lock:
            if message_id in self.processing:
                message = self.processing[message_id]
                message.attempts += 1
                message.error_message = error_message
                
                # Check if should retry
                if message.attempts < message.max_attempts:
                    message.status = MessageStatus.RETRYING
                    # Re-queue with delay
                    delay_seconds = min(60 * (2 ** (message.attempts - 1)), 3600)  # Exponential backoff, max 1 hour
                    message.scheduled_at = datetime.now() + timedelta(seconds=delay_seconds)
                    
                    # Add back to queue
                    self.queues[message.queue_name].appendleft(message)
                    self.stats[message.queue_name].pending_messages += 1
                else:
                    # Send to dead letter
                    message.status = MessageStatus.DEAD_LETTER
                    self.dead_letter[message.queue_name].append(message)
                    self.stats[message.queue_name].dead_letter_messages += 1
                
                # Update stats
                self.stats[message.queue_name].processing_messages -= 1
                self.stats[message.queue_name].failed_messages += 1
                
                del self.processing[message_id]
                return True
            
            return False
    
    async def get_queue_size(self, queue_name: str) -> int:
        """Get queue size"""
        async with self._lock:
            return len(self.queues.get(queue_name, []))
    
    async def get_stats(self, queue_name: str) -> QueueStats:
        """Get queue statistics"""
        return self.stats.get(queue_name, QueueStats())
    
    async def purge_queue(self, queue_name: str) -> int:
        """Remove all messages from queue"""
        async with self._lock:
            if queue_name in self.queues:
                count = len(self.queues[queue_name])
                self.queues[queue_name].clear()
                self.stats[queue_name].pending_messages = 0
                return count
            return 0
    
    async def get_dead_letter_messages(self, queue_name: str) -> List[QueueMessage]:
        """Get dead letter messages"""
        return self.dead_letter.get(queue_name, [])
    
    async def requeue_dead_letter(self, queue_name: str, message_id: str) -> bool:
        """Requeue a dead letter message"""
        async with self._lock:
            dead_messages = self.dead_letter.get(queue_name, [])
            for i, message in enumerate(dead_messages):
                if message.id == message_id:
                    # Reset message
                    message.status = MessageStatus.PENDING
                    message.attempts = 0
                    message.error_message = None
                    message.scheduled_at = None
                    
                    # Move back to queue
                    self.queues[queue_name].append(message)
                    del dead_messages[i]
                    
                    # Update stats
                    self.stats[queue_name].dead_letter_messages -= 1
                    self.stats[queue_name].pending_messages += 1
                    
                    return True
            return False
    
    def register_handler(self, queue_name: str, handler: MessageHandler) -> None:
        """Register message handler for queue"""
        self._handlers[queue_name] = handler
    
    async def start_workers(self, queue_name: str, worker_count: int = 1) -> None:
        """Start worker tasks for queue"""
        if queue_name not in self.queues:
            await self.create_queue(queue_name)
        
        # Stop existing workers
        for task in self._workers.get(queue_name, []):
            task.cancel()
        
        # Start new workers
        workers = []
        for i in range(worker_count):
            task = asyncio.create_task(self._worker_loop(queue_name, i))
            workers.append(task)
        
        self._workers[queue_name] = workers
        self._running = True
        logger.info(f"Started {worker_count} workers for queue {queue_name}")
    
    async def stop_workers(self, queue_name: str) -> None:
        """Stop worker tasks for queue"""
        for task in self._workers.get(queue_name, []):
            task.cancel()
        
        self._workers[queue_name] = []
        logger.info(f"Stopped workers for queue {queue_name}")
    
    async def _worker_loop(self, queue_name: str, worker_id: int) -> None:
        """Worker loop for processing messages"""
        logger.info(f"Worker {worker_id} started for queue {queue_name}")
        
        while self._running:
            try:
                # Get next message
                message = await self.dequeue(queue_name)
                if not message:
                    await asyncio.sleep(0.1)  # Short sleep if no messages
                    continue
                
                # Get handler
                handler = self._handlers.get(queue_name)
                if not handler:
                    logger.error(f"No handler registered for queue {queue_name}")
                    await self.nack_message(message.id, "No handler registered")
                    continue
                
                # Process message with timeout
                try:
                    success = await asyncio.wait_for(
                        handler.handle(message),
                        timeout=message.timeout_seconds
                    )
                    
                    if success:
                        await self.ack_message(message.id)
                    else:
                        await self.nack_message(message.id, "Handler returned False")
                        
                except asyncio.TimeoutError:
                    await self.nack_message(message.id, "Processing timeout")
                    logger.warning(f"Message {message.id} timed out after {message.timeout_seconds}s")
                    
                except Exception as e:
                    await self.nack_message(message.id, str(e))
                    await handler.on_error(message, e)
                    logger.error(f"Error processing message {message.id}: {e}")
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker {worker_id} error: {e}")
                await asyncio.sleep(1)  # Prevent tight error loop
        
        logger.info(f"Worker {worker_id} stopped for queue {queue_name}")


class RedisQueue:
    """Redis-based queue implementation"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379", 
                 key_prefix: str = "optrixtrades:queue:"):
        self.redis_url = redis_url
        self.key_prefix = key_prefix
        self.redis_client: Optional[redis.Redis] = None
        self.connected = False
        self._handlers: Dict[str, MessageHandler] = {}
        self._workers: Dict[str, List[asyncio.Task]] = {}
        self._running = False
    
    async def connect(self) -> bool:
        """Connect to Redis"""
        if not REDIS_AVAILABLE:
            logger.warning("Redis not available")
            return False
        
        try:
            self.redis_client = redis.from_url(
                self.redis_url,
                retry_on_timeout=True,
                socket_keepalive=True
            )
            
            await self.redis_client.ping()
            self.connected = True
            logger.info(f"Connected to Redis queue at {self.redis_url}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.connected = False
            return False
    
    async def disconnect(self) -> None:
        """Disconnect from Redis"""
        self._running = False
        
        # Stop all workers
        for tasks in self._workers.values():
            for task in tasks:
                task.cancel()
        
        if self.redis_client:
            await self.redis_client.close()
            self.connected = False
            logger.info("Disconnected from Redis queue")
    
    def _make_key(self, queue_name: str, suffix: str = "") -> str:
        """Create Redis key"""
        key = f"{self.key_prefix}{queue_name}"
        if suffix:
            key += f":{suffix}"
        return key
    
    async def create_queue(self, queue_name: str, max_workers: int = 1) -> None:
        """Create a new queue (Redis lists are created automatically)"""
        if not self.connected:
            return
        
        # Initialize stats
        stats_key = self._make_key(queue_name, "stats")
        stats = QueueStats()
        await self.redis_client.hset(stats_key, mapping={
            "total_messages": 0,
            "pending_messages": 0,
            "processing_messages": 0,
            "completed_messages": 0,
            "failed_messages": 0,
            "dead_letter_messages": 0,
            "average_processing_time": 0.0
        })
        
        logger.info(f"Created Redis queue: {queue_name}")
    
    async def enqueue(self, message: QueueMessage) -> bool:
        """Add message to queue"""
        if not self.connected or not self.redis_client:
            return False
        
        try:
            # Serialize message
            message_data = json.dumps(message.to_dict())
            
            # Add to appropriate priority queue
            queue_key = self._make_key(message.queue_name, f"priority_{message.priority.value}")
            await self.redis_client.lpush(queue_key, message_data)
            
            # Update stats
            stats_key = self._make_key(message.queue_name, "stats")
            await self.redis_client.hincrby(stats_key, "total_messages", 1)
            await self.redis_client.hincrby(stats_key, "pending_messages", 1)
            
            return True
            
        except Exception as e:
            logger.error(f"Redis enqueue error: {e}")
            return False
    
    async def dequeue(self, queue_name: str) -> Optional[QueueMessage]:
        """Get next message from queue (priority order)"""
        if not self.connected or not self.redis_client:
            return None
        
        try:
            # Check priority queues in order (highest first)
            for priority in [MessagePriority.CRITICAL, MessagePriority.HIGH, 
                           MessagePriority.NORMAL, MessagePriority.LOW]:
                queue_key = self._make_key(queue_name, f"priority_{priority.value}")
                
                # Try to get message
                result = await self.redis_client.brpop(queue_key, timeout=0.1)
                if result:
                    _, message_data = result
                    message_dict = json.loads(message_data.decode('utf-8'))
                    message = QueueMessage.from_dict(message_dict)
                    
                    # Check if scheduled
                    if message.scheduled_at and datetime.now() < message.scheduled_at:
                        # Put back and continue
                        await self.redis_client.lpush(queue_key, message_data)
                        continue
                    
                    # Mark as processing
                    message.status = MessageStatus.PROCESSING
                    message.processing_started_at = datetime.now()
                    
                    # Store in processing set
                    processing_key = self._make_key(queue_name, "processing")
                    await self.redis_client.hset(processing_key, message.id, json.dumps(message.to_dict()))
                    
                    # Update stats
                    stats_key = self._make_key(queue_name, "stats")
                    await self.redis_client.hincrby(stats_key, "pending_messages", -1)
                    await self.redis_client.hincrby(stats_key, "processing_messages", 1)
                    
                    return message
            
            return None
            
        except Exception as e:
            logger.error(f"Redis dequeue error: {e}")
            return None
    
    async def ack_message(self, message_id: str) -> bool:
        """Acknowledge successful message processing"""
        if not self.connected or not self.redis_client:
            return False
        
        try:
            # Find message in processing
            for queue_name in await self._get_queue_names():
                processing_key = self._make_key(queue_name, "processing")
                message_data = await self.redis_client.hget(processing_key, message_id)
                
                if message_data:
                    message_dict = json.loads(message_data.decode('utf-8'))
                    message = QueueMessage.from_dict(message_dict)
                    
                    # Remove from processing
                    await self.redis_client.hdel(processing_key, message_id)
                    
                    # Update stats
                    stats_key = self._make_key(queue_name, "stats")
                    await self.redis_client.hincrby(stats_key, "processing_messages", -1)
                    await self.redis_client.hincrby(stats_key, "completed_messages", 1)
                    
                    # Update processing time
                    if message.processing_started_at:
                        processing_time = (datetime.now() - message.processing_started_at).total_seconds()
                        # Simple moving average (could be improved)
                        await self.redis_client.hincrbyfloat(stats_key, "average_processing_time", processing_time)
                    
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Redis ack error: {e}")
            return False
    
    async def nack_message(self, message_id: str, error_message: str = "") -> bool:
        """Negative acknowledge - message processing failed"""
        if not self.connected or not self.redis_client:
            return False
        
        try:
            # Find message in processing
            for queue_name in await self._get_queue_names():
                processing_key = self._make_key(queue_name, "processing")
                message_data = await self.redis_client.hget(processing_key, message_id)
                
                if message_data:
                    message_dict = json.loads(message_data.decode('utf-8'))
                    message = QueueMessage.from_dict(message_dict)
                    message.attempts += 1
                    message.error_message = error_message
                    
                    # Remove from processing
                    await self.redis_client.hdel(processing_key, message_id)
                    
                    if message.attempts < message.max_attempts:
                        # Retry with delay
                        delay_seconds = min(60 * (2 ** (message.attempts - 1)), 3600)
                        message.scheduled_at = datetime.now() + timedelta(seconds=delay_seconds)
                        message.status = MessageStatus.RETRYING
                        
                        # Re-queue
                        queue_key = self._make_key(queue_name, f"priority_{message.priority.value}")
                        await self.redis_client.lpush(queue_key, json.dumps(message.to_dict()))
                        
                        # Update stats
                        stats_key = self._make_key(queue_name, "stats")
                        await self.redis_client.hincrby(stats_key, "pending_messages", 1)
                    else:
                        # Send to dead letter
                        message.status = MessageStatus.DEAD_LETTER
                        dead_letter_key = self._make_key(queue_name, "dead_letter")
                        await self.redis_client.lpush(dead_letter_key, json.dumps(message.to_dict()))
                        
                        # Update stats
                        stats_key = self._make_key(queue_name, "stats")
                        await self.redis_client.hincrby(stats_key, "dead_letter_messages", 1)
                    
                    # Update stats
                    stats_key = self._make_key(queue_name, "stats")
                    await self.redis_client.hincrby(stats_key, "processing_messages", -1)
                    await self.redis_client.hincrby(stats_key, "failed_messages", 1)
                    
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Redis nack error: {e}")
            return False
    
    async def _get_queue_names(self) -> List[str]:
        """Get list of queue names"""
        if not self.connected or not self.redis_client:
            return []
        
        try:
            pattern = f"{self.key_prefix}*:stats"
            keys = await self.redis_client.keys(pattern)
            queue_names = []
            
            for key in keys:
                if isinstance(key, bytes):
                    key = key.decode('utf-8')
                # Extract queue name
                queue_name = key.replace(self.key_prefix, '').replace(':stats', '')
                queue_names.append(queue_name)
            
            return queue_names
            
        except Exception as e:
            logger.error(f"Error getting queue names: {e}")
            return []
    
    # Additional methods similar to MemoryQueue...
    # (Implementation would be similar but using Redis operations)
    
    def register_handler(self, queue_name: str, handler: MessageHandler) -> None:
        """Register message handler for queue"""
        self._handlers[queue_name] = handler
    
    async def start_workers(self, queue_name: str, worker_count: int = 1) -> None:
        """Start worker tasks for queue"""
        # Stop existing workers
        for task in self._workers.get(queue_name, []):
            task.cancel()
        
        # Start new workers
        workers = []
        for i in range(worker_count):
            task = asyncio.create_task(self._worker_loop(queue_name, i))
            workers.append(task)
        
        self._workers[queue_name] = workers
        self._running = True
        logger.info(f"Started {worker_count} Redis workers for queue {queue_name}")
    
    async def _worker_loop(self, queue_name: str, worker_id: int) -> None:
        """Worker loop for processing messages"""
        logger.info(f"Redis worker {worker_id} started for queue {queue_name}")
        
        while self._running:
            try:
                message = await self.dequeue(queue_name)
                if not message:
                    await asyncio.sleep(0.1)
                    continue
                
                handler = self._handlers.get(queue_name)
                if not handler:
                    await self.nack_message(message.id, "No handler registered")
                    continue
                
                try:
                    success = await asyncio.wait_for(
                        handler.handle(message),
                        timeout=message.timeout_seconds
                    )
                    
                    if success:
                        await self.ack_message(message.id)
                    else:
                        await self.nack_message(message.id, "Handler returned False")
                        
                except asyncio.TimeoutError:
                    await self.nack_message(message.id, "Processing timeout")
                    
                except Exception as e:
                    await self.nack_message(message.id, str(e))
                    await handler.on_error(message, e)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Redis worker {worker_id} error: {e}")
                await asyncio.sleep(1)
        
        logger.info(f"Redis worker {worker_id} stopped for queue {queue_name}")


class MessageQueue:
    """Main message queue manager"""
    
    def __init__(self, backend: QueueBackend = QueueBackend.MEMORY, 
                 redis_url: Optional[str] = None):
        self.backend = backend
        self.redis_url = redis_url or getattr(BotConfig, 'REDIS_URL', 'redis://localhost:6379')
        
        if backend == QueueBackend.REDIS:
            self.queue = RedisQueue(self.redis_url)
        elif backend == QueueBackend.MEMORY:
            self.queue = MemoryQueue()
        else:  # HYBRID - fallback to memory if Redis fails
            self.queue = RedisQueue(self.redis_url)
            self.fallback_queue = MemoryQueue()
            self.use_redis = False
    
    async def initialize(self) -> None:
        """Initialize queue manager"""
        if self.backend == QueueBackend.HYBRID:
            self.use_redis = await self.queue.connect()
            if not self.use_redis:
                logger.info("Using memory queue as fallback")
        elif hasattr(self.queue, 'connect'):
            await self.queue.connect()
        
        logger.info(f"Message queue initialized with {self.backend.value} backend")
    
    async def shutdown(self) -> None:
        """Shutdown queue manager"""
        if hasattr(self.queue, 'disconnect'):
            await self.queue.disconnect()
        
        if self.backend == QueueBackend.HYBRID and hasattr(self, 'fallback_queue'):
            # Stop fallback queue workers
            for queue_name in self.fallback_queue._workers:
                await self.fallback_queue.stop_workers(queue_name)
        
        logger.info("Message queue shutdown")
    
    def _get_active_queue(self):
        """Get the active queue (Redis or fallback)"""
        if self.backend == QueueBackend.HYBRID:
            return self.queue if self.use_redis else self.fallback_queue
        return self.queue
    
    async def send_message(self, queue_name: str, payload: Any, 
                          priority: MessagePriority = MessagePriority.NORMAL,
                          scheduled_at: Optional[datetime] = None,
                          max_attempts: int = 3,
                          timeout_seconds: int = 300,
                          tags: Optional[List[str]] = None) -> str:
        """Send a message to queue"""
        message = QueueMessage(
            id=str(uuid.uuid4()),
            queue_name=queue_name,
            payload=payload,
            priority=priority,
            scheduled_at=scheduled_at,
            max_attempts=max_attempts,
            timeout_seconds=timeout_seconds,
            tags=tags or []
        )
        
        active_queue = self._get_active_queue()
        success = await active_queue.enqueue(message)
        
        if success:
            return message.id
        else:
            raise Exception(f"Failed to enqueue message to {queue_name}")
    
    async def register_handler(self, queue_name: str, handler: MessageHandler, 
                              worker_count: int = 1) -> None:
        """Register handler and start workers for queue"""
        active_queue = self._get_active_queue()
        active_queue.register_handler(queue_name, handler)
        await active_queue.start_workers(queue_name, worker_count)
    
    async def get_queue_stats(self, queue_name: str) -> QueueStats:
        """Get queue statistics"""
        active_queue = self._get_active_queue()
        return await active_queue.get_stats(queue_name)


# Convenience decorators and functions
def queue_task(queue_name: str, priority: MessagePriority = MessagePriority.NORMAL,
              max_attempts: int = 3, timeout_seconds: int = 300):
    """Decorator to queue function execution"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if hasattr(wrapper, '_queue_manager'):
                payload = {
                    'function': func.__name__,
                    'args': args,
                    'kwargs': kwargs
                }
                
                return await wrapper._queue_manager.send_message(
                    queue_name=queue_name,
                    payload=payload,
                    priority=priority,
                    max_attempts=max_attempts,
                    timeout_seconds=timeout_seconds
                )
            else:
                # Execute directly if no queue manager
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)
        
        return wrapper
    return decorator


# Global queue manager instance
queue_manager: Optional[MessageQueue] = None


async def initialize_queue_manager(backend: QueueBackend = QueueBackend.MEMORY, 
                                  redis_url: Optional[str] = None) -> MessageQueue:
    """Initialize global queue manager"""
    global queue_manager
    queue_manager = MessageQueue(backend, redis_url)
    await queue_manager.initialize()
    return queue_manager


def get_queue_manager() -> Optional[MessageQueue]:
    """Get global queue manager instance"""
    return queue_manager


async def shutdown_queue_manager() -> None:
    """Shutdown global queue manager"""
    global queue_manager
    if queue_manager:
        await queue_manager.shutdown()
        queue_manager = None