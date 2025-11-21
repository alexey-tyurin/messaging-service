"""
Core message service handling business logic for sending and receiving messages.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import uuid
from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.database import (
    Message, Conversation, MessageEvent, WebhookLog,
    MessageType, MessageDirection, MessageStatus, EventType,
    ConversationStatus, Provider
)
from app.providers.base import ProviderFactory, ProviderSelector
from app.db.redis import redis_manager
from app.core.observability import get_logger, MetricsCollector, trace_operation, monitor_performance
from app.core.config import settings


logger = get_logger(__name__)


class MessageService:
    """Service for handling message operations."""
    
    def __init__(self, db_session: AsyncSession):
        """
        Initialize message service.
        
        Args:
            db_session: Database session
        """
        self.db = db_session
    
    @trace_operation("send_message")
    @monitor_performance("send_message")
    async def send_message(self, message_data: Dict[str, Any]) -> Message:
        """
        Send a message through appropriate provider.
        
        Args:
            message_data: Message details including from, to, body, type
            
        Returns:
            Created message object
        """
        try:
            # Validate message data
            self._validate_message_data(message_data)
            
            # Determine message type
            message_type = self._determine_message_type(message_data)
            
            # Select provider based on message type
            provider = await ProviderSelector.select_provider(
                message_type,
                message_data.get("metadata", {})
            )
            
            # Get or create conversation
            conversation = await self._get_or_create_conversation(
                from_address=message_data["from"],
                to_address=message_data["to"],
                channel_type=message_type
            )
            
            # Create message record with provider assigned
            message = Message(
                conversation_id=conversation.id,
                provider=Provider(provider.name),
                direction=MessageDirection.OUTBOUND,
                status=MessageStatus.PENDING,
                message_type=message_type,
                from_address=message_data["from"],
                to_address=message_data["to"],
                body=message_data.get("body"),
                attachments=message_data.get("attachments", []),
                meta_data=message_data.get("metadata", {})
            )
            
            self.db.add(message)
            await self.db.flush()
            
            # Create initial event
            await self._create_message_event(
                message.id,
                EventType.CREATED,
                {"source": "api"}
            )
            
            # Queue message for sending
            await self._queue_message_for_sending(message)
            
            # Update conversation
            conversation.last_message_at = message.created_at
            conversation.message_count += 1
            
            await self.db.commit()
            
            # Invalidate conversation cache after update
            await redis_manager.delete(f"conversation:{conversation.id}")
            logger.debug(f"Invalidated conversation cache: {conversation.id}")
            
            # Track metrics
            MetricsCollector.track_message(
                direction="outbound",
                msg_type=message_type.value,
                status="pending",
                provider="unknown"
            )
            
            logger.info(
                "Message created and queued",
                message_id=str(message.id),
                conversation_id=str(conversation.id)
            )
            
            # Process message immediately if sync processing is enabled
            if settings.sync_message_processing:
                logger.info(f"Processing message synchronously: {message.id}")
                await self.process_outbound_message(str(message.id))
                # Refresh message to get updated status
                await self.db.refresh(message)
            
            return message
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to send message: {e}", message_data=message_data)
            raise
    
    @trace_operation("process_outbound_message")
    async def process_outbound_message(self, message_id: str) -> bool:
        """
        Process outbound message from queue.
        
        Args:
            message_id: Message ID
            
        Returns:
            True if successful
        """
        try:
            # Get message with conversation
            message = await self.db.get(Message, message_id)
            if not message:
                logger.error(f"Message not found: {message_id}")
                return False
            
            # Check retry count
            if message.retry_count >= message.max_retries:
                message.status = MessageStatus.FAILED
                message.failed_at = datetime.utcnow()
                message.error_message = "Max retries exceeded"
                await self._create_message_event(
                    message.id,
                    EventType.FAILED,
                    {"reason": "max_retries"}
                )
                await self.db.commit()
                
                # Invalidate message cache after failure
                await redis_manager.delete(f"message:{message.id}")
                logger.debug(f"Invalidated message cache after failure: {message.id}")
                
                return False
            
            # Select provider
            provider = await ProviderSelector.select_provider(
                message.message_type,
                message.meta_data
            )
            
            # Update message status
            message.status = MessageStatus.SENDING
            message.provider = Provider(provider.name)
            await self.db.flush()
            
            # Send through provider
            try:
                response = await provider.send_message({
                    "from": message.from_address,
                    "to": message.to_address,
                    "type": message.message_type.value,
                    "body": message.body,
                    "attachments": message.attachments
                })
                
                # Update message with provider response
                message.provider_message_id = response["provider_message_id"]
                message.status = MessageStatus.SENT
                message.sent_at = datetime.utcnow()
                message.cost = response.get("cost", 0)
                
                await self._create_message_event(
                    message.id,
                    EventType.SENT,
                    response
                )
                
                await self.db.commit()
                
                # Invalidate message cache after status update
                await redis_manager.delete(f"message:{message.id}")
                logger.debug(f"Invalidated message cache: {message.id}")
                
                logger.info(
                    "Message sent successfully",
                    message_id=str(message.id),
                    provider=provider.name
                )
                
                return True
                
            except Exception as e:
                # Import provider exceptions
                from app.providers.base import ProviderRateLimitError, ProviderServerError
                
                # Handle different error types with different strategies
                retry_delay = settings.queue_retry_delay * message.retry_count
                
                if isinstance(e, ProviderRateLimitError):
                    # 429 Rate Limit: Use provider's retry_after or exponential backoff
                    retry_delay = max(e.retry_after, retry_delay * 2)
                    error_type = "rate_limit_429"
                    logger.warning(
                        f"Provider rate limit hit (429), retry after {retry_delay}s",
                        message_id=str(message.id),
                        provider=provider.name,
                        retry_after=e.retry_after
                    )
                elif isinstance(e, ProviderServerError):
                    # 500 Server Error: Standard exponential backoff
                    retry_delay = retry_delay * 1.5
                    error_type = "server_error_500"
                    logger.warning(
                        f"Provider server error (500), retry after {retry_delay}s",
                        message_id=str(message.id),
                        provider=provider.name
                    )
                else:
                    # Other errors: Standard retry
                    error_type = "unknown_error"
                    logger.warning(
                        f"Provider error: {type(e).__name__}",
                        message_id=str(message.id),
                        provider=provider.name,
                        error=str(e)
                    )
                
                # Update message for retry
                message.retry_count += 1
                message.status = MessageStatus.RETRY
                message.retry_after = datetime.utcnow() + timedelta(seconds=retry_delay)
                message.error_message = str(e)
                
                await self._create_message_event(
                    message.id,
                    EventType.RETRY,
                    {
                        "error": str(e),
                        "error_type": error_type,
                        "retry_count": message.retry_count,
                        "retry_delay": retry_delay
                    }
                )
                
                # Re-queue for retry
                await self._queue_message_for_sending(message)
                
                await self.db.commit()
                
                # Invalidate message cache after retry update
                await redis_manager.delete(f"message:{message.id}")
                logger.debug(f"Invalidated message cache after retry: {message.id}")
                
                logger.info(
                    f"Message queued for retry",
                    message_id=str(message.id),
                    retry_count=message.retry_count,
                    retry_delay=retry_delay,
                    error_type=error_type
                )
                
                return False
                
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to process outbound message: {e}")
            return False
    
    @trace_operation("receive_message")
    async def receive_message(
        self,
        provider: str,
        webhook_data: Dict[str, Any]
    ) -> Message:
        """
        Process incoming message from webhook.
        
        Args:
            provider: Provider name
            webhook_data: Normalized webhook data
            
        Returns:
            Created message object
        """
        try:
            # Check for duplicate
            existing = await self.db.execute(
                select(Message).where(
                    and_(
                        Message.provider == Provider(provider),
                        Message.provider_message_id == webhook_data.get("provider_message_id")
                    )
                )
            )
            if existing.scalar_one_or_none():
                logger.warning(
                    "Duplicate message received",
                    provider=provider,
                    provider_message_id=webhook_data.get("provider_message_id")
                )
                return existing.scalar_one()
            
            # Determine message type
            message_type = MessageType(webhook_data["type"])
            
            # Get or create conversation
            conversation = await self._get_or_create_conversation(
                from_address=webhook_data["from"],
                to_address=webhook_data["to"],
                channel_type=message_type
            )
            
            # Create message
            message = Message(
                conversation_id=conversation.id,
                provider=Provider(provider),
                provider_message_id=webhook_data.get("provider_message_id"),
                direction=MessageDirection.INBOUND,
                status=MessageStatus.DELIVERED,
                message_type=message_type,
                from_address=webhook_data["from"],
                to_address=webhook_data["to"],
                body=webhook_data.get("body"),
                attachments=webhook_data.get("attachments", []),
                delivered_at=datetime.utcnow(),
                meta_data=webhook_data.get("metadata", {})
            )
            
            self.db.add(message)
            await self.db.flush()
            
            # Create event
            await self._create_message_event(
                message.id,
                EventType.WEBHOOK_RECEIVED,
                webhook_data
            )
            
            # Update conversation
            conversation.last_message_at = message.created_at
            conversation.message_count += 1
            conversation.unread_count += 1
            
            await self.db.commit()
            
            # Invalidate conversation cache after update
            await redis_manager.delete(f"conversation:{conversation.id}")
            logger.debug(f"Invalidated conversation cache: {conversation.id}")
            
            # Publish to real-time channel
            await redis_manager.publish(
                f"conversation:{conversation.id}",
                {
                    "type": "new_message",
                    "message_id": str(message.id),
                    "conversation_id": str(conversation.id)
                }
            )
            
            # Track metrics
            MetricsCollector.track_message(
                direction="inbound",
                msg_type=message_type.value,
                status="delivered",
                provider=provider
            )
            
            logger.info(
                "Inbound message processed",
                message_id=str(message.id),
                conversation_id=str(conversation.id),
                provider=provider
            )
            
            return message
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to receive message: {e}", webhook_data=webhook_data)
            raise
    
    async def get_message(
        self, 
        message_id: str,
        include_relationships: bool = True
    ) -> Optional[Message]:
        """
        Get message by ID.
        
        Args:
            message_id: Message ID
            include_relationships: If False, skip loading conversation and events (faster with cache)
            
        Returns:
            Message object or None
        """
        try:
            # Check Redis cache first
            cache_key = f"message:{message_id}"
            cached_data = await redis_manager.get(cache_key)
            
            if cached_data:
                logger.debug(f"Message cache hit: {message_id}")
                MetricsCollector.track_cache_operation("get", True)
                
                # If relationships are not needed, reconstruct from cache without DB query
                if not include_relationships:
                    # Create a detached Message object from cached data
                    # Parse datetime strings back to datetime objects
                    from datetime import datetime
                    
                    message = Message(
                        id=uuid.UUID(cached_data["id"]),
                        conversation_id=uuid.UUID(cached_data["conversation_id"]),
                        provider=Provider(cached_data["provider"]) if cached_data.get("provider") else None,
                        provider_message_id=cached_data.get("provider_message_id"),
                        direction=MessageDirection(cached_data["direction"]),
                        status=MessageStatus(cached_data["status"]),
                        message_type=MessageType(cached_data["message_type"]),
                        from_address=cached_data["from_address"],
                        to_address=cached_data["to_address"],
                        body=cached_data.get("body"),
                        attachments=cached_data.get("attachments", []),
                        sent_at=datetime.fromisoformat(cached_data["sent_at"]) if cached_data.get("sent_at") else None,
                        delivered_at=datetime.fromisoformat(cached_data["delivered_at"]) if cached_data.get("delivered_at") else None,
                        created_at=datetime.fromisoformat(cached_data["created_at"]) if cached_data.get("created_at") else None,
                        updated_at=datetime.fromisoformat(cached_data["updated_at"]) if cached_data.get("updated_at") else None,
                        meta_data=cached_data.get("meta_data", {})
                    )
                    logger.debug(f"Returned message from cache without DB query: {message_id}")
                    return message
                else:
                    # Relationships needed - query DB but data exists (faster query)
                    logger.debug(f"Cache hit but loading relationships from DB: {message_id}")
                    result = await self.db.execute(
                        select(Message)
                        .options(selectinload(Message.conversation))
                        .options(selectinload(Message.events))
                        .where(Message.id == message_id)
                    )
                    return result.scalar_one_or_none()
            
            # Cache miss - fetch from database
            logger.debug(f"Message cache miss: {message_id}")
            MetricsCollector.track_cache_operation("get", False)
            
            query = select(Message).where(Message.id == message_id)
            
            if include_relationships:
                query = query.options(selectinload(Message.conversation))
                query = query.options(selectinload(Message.events))
            
            result = await self.db.execute(query)
            message = result.scalar_one_or_none()
            
            if message:
                # Cache the message data
                cache_data = {
                    "id": str(message.id),
                    "conversation_id": str(message.conversation_id),
                    "provider": message.provider.value if message.provider else None,
                    "provider_message_id": message.provider_message_id,
                    "direction": message.direction.value,
                    "status": message.status.value,
                    "message_type": message.message_type.value,
                    "from_address": message.from_address,
                    "to_address": message.to_address,
                    "body": message.body,
                    "attachments": message.attachments or [],
                    "sent_at": message.sent_at.isoformat() if message.sent_at else None,
                    "delivered_at": message.delivered_at.isoformat() if message.delivered_at else None,
                    "created_at": message.created_at.isoformat() if message.created_at else None,
                    "updated_at": message.updated_at.isoformat() if message.updated_at else None,
                    "meta_data": message.meta_data or {}
                }
                
                await redis_manager.set(cache_key, cache_data, ttl=300)  # 5 minutes TTL
                MetricsCollector.track_cache_operation("set", True)
                logger.debug(f"Cached message: {message_id}")
            
            return message
            
        except Exception as e:
            logger.error(f"Failed to get message: {e}", exc_info=True)
            return None
    
    async def list_messages(
        self,
        conversation_id: Optional[str] = None,
        status: Optional[MessageStatus] = None,
        direction: Optional[MessageDirection] = None,
        limit: int = 50,
        offset: int = 0
    ) -> tuple[List[Message], int]:
        """
        List messages with filters.
        
        Args:
            conversation_id: Filter by conversation
            status: Filter by status
            direction: Filter by direction
            limit: Max results
            offset: Skip results
            
        Returns:
            Tuple of (list of messages, total count)
        """
        try:
            query = select(Message).options(selectinload(Message.conversation))
            
            if conversation_id:
                query = query.where(Message.conversation_id == conversation_id)
            if status:
                query = query.where(Message.status == status)
            if direction:
                query = query.where(Message.direction == direction)
            
            # Get total count before pagination
            count_query = select(func.count()).select_from(Message)
            if conversation_id:
                count_query = count_query.where(Message.conversation_id == conversation_id)
            if status:
                count_query = count_query.where(Message.status == status)
            if direction:
                count_query = count_query.where(Message.direction == direction)
            
            count_result = await self.db.execute(count_query)
            total = count_result.scalar() or 0
            
            # Get paginated messages
            query = query.order_by(Message.created_at.desc())
            query = query.limit(limit).offset(offset)
            
            result = await self.db.execute(query)
            messages = result.scalars().all()
            
            return messages, total
            
        except Exception as e:
            logger.error(f"Failed to list messages: {e}")
            return [], 0
    
    async def update_message_status(
        self,
        message_id: str,
        status: MessageStatus,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Update message status.
        
        Args:
            message_id: Message ID
            status: New status
            metadata: Additional metadata
            
        Returns:
            True if updated
        """
        try:
            message = await self.db.get(Message, message_id)
            if not message:
                return False
            
            message.status = status
            
            if status == MessageStatus.DELIVERED:
                message.delivered_at = datetime.utcnow()
            elif status == MessageStatus.FAILED:
                message.failed_at = datetime.utcnow()
            
            if metadata:
                message.meta_data.update(metadata)
            
            await self._create_message_event(
                message.id,
                EventType.DELIVERED if status == MessageStatus.DELIVERED else EventType.FAILED,
                metadata or {}
            )
            
            await self.db.commit()
            
            # Invalidate cache after update
            await redis_manager.delete(f"message:{message_id}")
            logger.debug(f"Invalidated message cache: {message_id}")
            
            return True
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to update message status: {e}")
            return False
    
    # Helper methods
    def _validate_message_data(self, message_data: Dict[str, Any]):
        """Validate message data."""
        required_fields = ["from", "to"]
        for field in required_fields:
            if field not in message_data:
                raise ValueError(f"Missing required field: {field}")
        
        if not message_data.get("body") and not message_data.get("attachments"):
            raise ValueError("Message must have body or attachments")
    
    def _determine_message_type(self, message_data: Dict[str, Any]) -> MessageType:
        """Determine message type from data."""
        if "type" in message_data:
            return MessageType(message_data["type"])
        
        # Auto-detect based on address format
        to_address = message_data["to"]
        if "@" in to_address:
            return MessageType.EMAIL
        elif message_data.get("attachments"):
            return MessageType.MMS
        else:
            return MessageType.SMS
    
    async def _get_or_create_conversation(
        self,
        from_address: str,
        to_address: str,
        channel_type: MessageType
    ) -> Conversation:
        """Get or create conversation."""
        # Try to find existing conversation
        result = await self.db.execute(
            select(Conversation).where(
                or_(
                    and_(
                        Conversation.participant_from == from_address,
                        Conversation.participant_to == to_address
                    ),
                    and_(
                        Conversation.participant_from == to_address,
                        Conversation.participant_to == from_address
                    )
                ),
                Conversation.channel_type == channel_type
            )
        )
        
        conversation = result.scalar_one_or_none()
        
        if not conversation:
            # Create new conversation
            conversation = Conversation(
                participant_from=from_address,
                participant_to=to_address,
                channel_type=channel_type,
                status=ConversationStatus.ACTIVE,
                meta_data={}
            )
            self.db.add(conversation)
            await self.db.flush()
            
            logger.info(
                "Created new conversation",
                conversation_id=str(conversation.id),
                from_address=from_address,
                to_address=to_address
            )
        
        return conversation
    
    async def _create_message_event(
        self,
        message_id: uuid.UUID,
        event_type: EventType,
        event_data: Dict[str, Any]
    ):
        """Create message event."""
        event = MessageEvent(
            message_id=message_id,
            event_type=event_type,
            event_data=event_data,
            meta_data={}
        )
        self.db.add(event)
    
    async def _queue_message_for_sending(self, message: Message):
        """Queue message for sending."""
        queue_data = {
            "message_id": str(message.id),
            "retry_count": message.retry_count,
            "scheduled_at": datetime.utcnow().isoformat()
        }
        
        queue_name = f"message_queue:{message.message_type.value}"
        await redis_manager.enqueue_message(queue_name, queue_data)
        
        # Update queue depth metric
        MetricsCollector.update_queue_depth(
            queue_name,
            await redis_manager.redis_client.xlen(queue_name)
        )
