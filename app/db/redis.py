"""
Redis connection management for caching, rate limiting, and message queuing.
"""

import json
import logging
from typing import Optional, Any, Dict, List
from datetime import timedelta
import redis.asyncio as redis
from redis.exceptions import RedisError
from contextlib import asynccontextmanager

from app.core.config import settings

logger = logging.getLogger(__name__)


class RedisManager:
    """Manages Redis connections and operations."""
    
    def __init__(self):
        """Initialize Redis manager."""
        self.redis_client: Optional[redis.Redis] = None
        self.pubsub: Optional[redis.client.PubSub] = None
        
    async def init_redis(self):
        """Initialize Redis connection pool."""
        try:
            # Build connection parameters
            redis_params = {
                "host": settings.redis_host,
                "port": settings.redis_port,
                "password": settings.redis_password if settings.redis_password else None,
                "db": settings.redis_db,
                "decode_responses": True,
                "max_connections": settings.redis_pool_size,
                "socket_connect_timeout": settings.redis_pool_timeout,
                "socket_keepalive": True,
            }
            
            # Only set keepalive options on Linux (they're not compatible with macOS)
            import platform
            if platform.system() == "Linux":
                redis_params["socket_keepalive_options"] = {
                    1: 1,  # TCP_KEEPIDLE
                    2: 1,  # TCP_KEEPINTVL
                    3: 3,  # TCP_KEEPCNT
                }
            
            self.redis_client = redis.Redis(**redis_params)
            
            # Test connection
            await self.redis_client.ping()
            logger.info("Redis connection initialized successfully")
            
            # Initialize pub/sub
            self.pubsub = self.redis_client.pubsub()
            
        except RedisError as e:
            logger.error(f"Failed to initialize Redis: {e}")
            raise
    
    async def close(self):
        """Close Redis connections."""
        if self.pubsub:
            await self.pubsub.close()
        if self.redis_client:
            await self.redis_client.close()
            logger.info("Redis connections closed")
    
    # Cache Operations
    async def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None
        """
        try:
            value = await self.redis_client.get(key)
            if value:
                return json.loads(value)
            return None
        except (RedisError, json.JSONDecodeError) as e:
            logger.error(f"Error getting cache key {key}: {e}")
            return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """
        Set cache value.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds
            
        Returns:
            True if successful
        """
        try:
            serialized = json.dumps(value)
            if ttl:
                await self.redis_client.setex(key, ttl, serialized)
            else:
                await self.redis_client.set(key, serialized)
            return True
        except (RedisError, json.JSONEncodeError) as e:
            logger.error(f"Error setting cache key {key}: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """
        Delete cache entry.
        
        Args:
            key: Cache key
            
        Returns:
            True if deleted
        """
        try:
            result = await self.redis_client.delete(key)
            return result > 0
        except RedisError as e:
            logger.error(f"Error deleting cache key {key}: {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        """
        Check if key exists.
        
        Args:
            key: Cache key
            
        Returns:
            True if exists
        """
        try:
            return await self.redis_client.exists(key) > 0
        except RedisError as e:
            logger.error(f"Error checking key existence {key}: {e}")
            return False
    
    # Rate Limiting
    async def check_rate_limit(
        self,
        key: str,
        limit: int,
        window: int
    ) -> tuple[bool, int]:
        """
        Check rate limit using sliding window.
        
        Args:
            key: Rate limit key
            limit: Maximum requests
            window: Time window in seconds
            
        Returns:
            Tuple of (allowed, remaining)
        """
        try:
            pipe = self.redis_client.pipeline()
            now = await self.redis_client.time()
            now_ms = now[0] * 1000 + now[1] // 1000
            window_ms = window * 1000
            
            # Remove old entries
            pipe.zremrangebyscore(key, 0, now_ms - window_ms)
            # Add current request
            pipe.zadd(key, {str(now_ms): now_ms})
            # Count requests in window
            pipe.zcard(key)
            # Set expiry
            pipe.expire(key, window + 1)
            
            results = await pipe.execute()
            count = results[2]
            
            allowed = count <= limit
            remaining = max(0, limit - count)
            
            return allowed, remaining
            
        except RedisError as e:
            logger.error(f"Error checking rate limit for {key}: {e}")
            # Fail open - allow request if Redis is down
            return True, limit
    
    # Message Queue Operations
    async def enqueue_message(
        self,
        queue: str,
        message: Dict[str, Any]
    ) -> str:
        """
        Add message to queue using Redis Streams.
        
        Args:
            queue: Queue name
            message: Message data
            
        Returns:
            Message ID
        """
        try:
            # Convert message to flat dict for Redis Streams
            flat_message = {"data": json.dumps(message)}
            message_id = await self.redis_client.xadd(queue, flat_message)
            return message_id
        except (RedisError, json.JSONEncodeError) as e:
            logger.error(f"Error enqueuing message to {queue}: {e}")
            raise
    
    async def dequeue_messages(
        self,
        queue: str,
        count: int = 10,
        block: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        Dequeue messages from Redis Stream.
        
        Args:
            queue: Queue name
            count: Number of messages to fetch
            block: Block timeout in milliseconds
            
        Returns:
            List of messages
        """
        try:
            # Read messages from stream
            messages = await self.redis_client.xread(
                {queue: "$"},
                count=count,
                block=block
            )
            
            result = []
            for stream_name, stream_messages in messages:
                for message_id, data in stream_messages:
                    # Handle both bytes and string keys (depends on decode_responses setting)
                    data_value = data.get("data") or data.get(b"data")
                    if data_value:
                        message_data = json.loads(data_value)
                        message_data["_id"] = message_id
                        result.append(message_data)
            
            return result
            
        except (RedisError, json.JSONDecodeError) as e:
            logger.error(f"Error dequeuing messages from {queue}: {e}")
            return []
    
    async def ack_message(
        self,
        queue: str,
        group: str,
        message_id: str
    ) -> bool:
        """
        Acknowledge message processing.
        
        Args:
            queue: Queue name
            group: Consumer group
            message_id: Message ID
            
        Returns:
            True if acknowledged
        """
        try:
            result = await self.redis_client.xack(queue, group, message_id)
            return result > 0
        except RedisError as e:
            logger.error(f"Error acknowledging message {message_id}: {e}")
            return False
    
    # Pub/Sub Operations
    async def publish(
        self,
        channel: str,
        message: Dict[str, Any]
    ) -> int:
        """
        Publish message to channel.
        
        Args:
            channel: Channel name
            message: Message data
            
        Returns:
            Number of subscribers that received the message
        """
        try:
            serialized = json.dumps(message)
            return await self.redis_client.publish(channel, serialized)
        except (RedisError, json.JSONEncodeError) as e:
            logger.error(f"Error publishing to channel {channel}: {e}")
            return 0
    
    async def subscribe(
        self,
        channels: List[str]
    ):
        """
        Subscribe to channels.
        
        Args:
            channels: List of channel names
        """
        try:
            await self.pubsub.subscribe(*channels)
            logger.info(f"Subscribed to channels: {channels}")
        except RedisError as e:
            logger.error(f"Error subscribing to channels: {e}")
            raise
    
    # Distributed Lock
    @asynccontextmanager
    async def lock(
        self,
        key: str,
        timeout: int = 10
    ):
        """
        Acquire distributed lock.
        
        Args:
            key: Lock key
            timeout: Lock timeout in seconds
        """
        lock_key = f"lock:{key}"
        lock_value = str(id(self))
        
        try:
            # Try to acquire lock
            acquired = await self.redis_client.set(
                lock_key,
                lock_value,
                nx=True,
                ex=timeout
            )
            
            if not acquired:
                raise Exception(f"Failed to acquire lock for {key}")
            
            yield
            
        finally:
            # Release lock if we own it
            current = await self.redis_client.get(lock_key)
            if current == lock_value:
                await self.redis_client.delete(lock_key)
    
    # Health Check
    async def health_check(self) -> bool:
        """
        Check Redis health.
        
        Returns:
            True if Redis is healthy
        """
        try:
            await self.redis_client.ping()
            return True
        except RedisError as e:
            logger.error(f"Redis health check failed: {e}")
            return False


# Global Redis manager instance
redis_manager = RedisManager()


async def init_redis():
    """Initialize Redis on application startup."""
    await redis_manager.init_redis()


async def close_redis():
    """Close Redis connections on application shutdown."""
    await redis_manager.close()
