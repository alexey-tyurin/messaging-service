"""
Conversation service for managing message conversations.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid
from sqlalchemy import select, and_, or_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.database import (
    Conversation, Message, ConversationStatus, MessageType, ConversationType
)
from app.db.redis import redis_manager
from app.core.observability import get_logger, MetricsCollector, trace_operation

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.api.v1.models import CreateConversationRequest


logger = get_logger(__name__)


class ConversationService:
    """Service for handling conversation operations."""
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    @trace_operation("create_conversation")
    async def create_conversation(
        self,
        request: "CreateConversationRequest"
    ) -> Conversation:
        """
        Create a new conversation or topic.
        
        Args:
            request: Creation request
            
        Returns:
            Created Conversation
        """
        try:
            # For DIRECT, check if exists
            if request.type == ConversationType.DIRECT:
                existing = await self._find_direct_conversation(
                    request.participant_from,
                    request.participant_to,
                    request.channel_type
                )
                if existing:
                    return existing


            
            conversation = Conversation(
                type=request.type,
                participant_from=request.participant_from,
                participant_to=request.participant_to,
                channel_type=request.channel_type,
                title=request.title,
                status=ConversationStatus.ACTIVE,
                meta_data=request.metadata or {}
            )
            
            self.db.add(conversation)
            await self.db.flush()
            
            logger.info(
                "Conversation created",
                conversation_id=str(conversation.id),
                type=request.type.value
            )
            
            return conversation
            
        except Exception as e:
            logger.error(f"Error creating conversation: {e}")
            await self.db.rollback()
            raise

    async def _find_direct_conversation(
        self, 
        participant_from: str, 
        participant_to: str, 
        channel_type: MessageType
    ) -> Optional[Conversation]:
        """Find existing direct conversation."""
        # Normalize participants order for consistent lookup
        p1, p2 = sorted([participant_from, participant_to])
        
        query = select(Conversation).where(
            and_(
                Conversation.type == ConversationType.DIRECT,
                Conversation.participant_from == p1,
                Conversation.participant_to == p2,
                Conversation.channel_type == channel_type,
                Conversation.status != ConversationStatus.CLOSED
            )
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    

    
    @trace_operation("get_conversation")
    async def get_conversation(
        self,
        conversation_id: str,
        include_messages: bool = False
    ) -> Optional[Conversation]:
        """
        Get conversation by ID.
        
        Args:
            conversation_id: Conversation ID
            include_messages: Include messages in response
            
        Returns:
            Conversation object or None
        """
        try:
            # Check Redis cache first
            cache_key = f"conversation:{conversation_id}"
            cached_data = await redis_manager.get(cache_key)
            
            if cached_data:
                logger.debug(f"Conversation cache hit: {conversation_id}")
                MetricsCollector.track_cache_operation("get", True)
                
                # If messages are not needed, reconstruct from cache without DB query
                if not include_messages:
                    # Create a detached Conversation object from cached data
                    from datetime import datetime
                    
                    conversation = Conversation(
                        id=uuid.UUID(cached_data["id"]),
                        participant_from=cached_data.get("participant_from"),
                        participant_to=cached_data.get("participant_to"),
                        channel_type=MessageType(cached_data["channel_type"]),
                        # Default to DIRECT if not in cache (backwards compat)
                        type=ConversationType(cached_data.get("type", "direct")),
                        status=ConversationStatus(cached_data["status"]),
                        message_count=cached_data["message_count"],
                        unread_count=cached_data["unread_count"],
                        title=cached_data.get("title"),
                        last_message_at=datetime.fromisoformat(cached_data["last_message_at"]) if cached_data.get("last_message_at") else None,
                        created_at=datetime.fromisoformat(cached_data["created_at"]) if cached_data.get("created_at") else None,
                        updated_at=datetime.fromisoformat(cached_data["updated_at"]) if cached_data.get("updated_at") else None,
                        meta_data=cached_data.get("meta_data", {})
                    )
                    logger.debug(f"Returned conversation from cache without DB query: {conversation_id}")
                    return conversation
                else:
                    # Messages needed - query DB with relationships
                    logger.debug(f"Cache hit but loading messages from DB: {conversation_id}")
                    query = select(Conversation).where(Conversation.id == conversation_id)
                    query = query.options(selectinload(Conversation.messages))
                    result = await self.db.execute(query)
                    return result.scalar_one_or_none()
            
            # Cache miss - fetch from database
            logger.debug(f"Conversation cache miss: {conversation_id}")
            MetricsCollector.track_cache_operation("get", False)
            
            query = select(Conversation).where(Conversation.id == conversation_id)
            
            if include_messages:
                query = query.options(selectinload(Conversation.messages))
            
            result = await self.db.execute(query)
            conversation = result.scalar_one_or_none()
            
            if conversation:
                # Cache conversation metadata
                cache_data = {
                    "id": str(conversation.id),
                    "participant_from": conversation.participant_from,
                    "participant_to": conversation.participant_to,
                    "channel_type": conversation.channel_type.value,
                    "type": conversation.type.value,
                    "status": conversation.status.value,
                    "message_count": conversation.message_count,
                    "unread_count": conversation.unread_count,
                    "title": conversation.title,
                    "last_message_at": conversation.last_message_at.isoformat() if conversation.last_message_at else None,
                    "created_at": conversation.created_at.isoformat() if conversation.created_at else None,
                    "updated_at": conversation.updated_at.isoformat() if conversation.updated_at else None,
                    "meta_data": conversation.meta_data or {}
                }
                
                await redis_manager.set(cache_key, cache_data, ttl=300)  # 5 minutes
                MetricsCollector.track_cache_operation("set", True)
                logger.debug(f"Cached conversation: {conversation_id}")
            
            return conversation
            
        except Exception as e:
            logger.error(f"Failed to get conversation: {e}", exc_info=True)
            return None
    
    @trace_operation("list_conversations")
    async def list_conversations(
        self,
        participant: Optional[str] = None,
        channel_type: Optional[MessageType] = None,
        status: Optional[ConversationStatus] = None,
        type: Optional[ConversationType] = None,
        limit: int = 50,
        offset: int = 0
    ) -> tuple[List[Conversation], int]:
        """
        List conversations with filters.
        
        Args:
            participant: Filter by participant (from or to)
            channel_type: Filter by channel type
            status: Filter by status
            type: Filter by conversation type
            limit: Max results
            offset: Skip results
            
        Returns:
            Tuple of (list of conversations, total count)
        """
        try:
            query = select(Conversation)
            
            if participant:
                query = query.where(
                    or_(
                        Conversation.participant_from == participant,
                        Conversation.participant_to == participant
                    )
                )
            
            if channel_type:
                query = query.where(Conversation.channel_type == channel_type)
            
            if status:
                query = query.where(Conversation.status == status)

            if type:
                query = query.where(Conversation.type == type)
            
            # Get total count before pagination
            count_query = select(func.count()).select_from(Conversation)
            if participant:
                count_query = count_query.where(
                    or_(
                        Conversation.participant_from == participant,
                        Conversation.participant_to == participant
                    )
                )
            if channel_type:
                count_query = count_query.where(Conversation.channel_type == channel_type)
            if status:
                count_query = count_query.where(Conversation.status == status)
            if type:
                count_query = count_query.where(Conversation.type == type)
            
            count_result = await self.db.execute(count_query)
            total = count_result.scalar() or 0
            
            # Order by last message and paginate
            query = query.order_by(desc(Conversation.last_message_at))
            query = query.limit(limit).offset(offset)
            
            result = await self.db.execute(query)
            conversations = result.scalars().all()
            
            return conversations, total
            
        except Exception as e:
            logger.error(f"Failed to list conversations: {e}")
            return [], 0
    
    @trace_operation("update_conversation")
    async def update_conversation(
        self,
        conversation_id: str,
        updates: Dict[str, Any]
    ) -> bool:
        """
        Update conversation properties.
        
        Args:
            conversation_id: Conversation ID
            updates: Fields to update
            
        Returns:
            True if updated
        """
        try:
            conversation = await self.db.get(Conversation, conversation_id)
            if not conversation:
                logger.warning(f"Conversation not found: {conversation_id}")
                return False
            
            # Update allowed fields
            allowed_fields = ["title", "status", "metadata"]
            for field, value in updates.items():
                if field in allowed_fields:
                    setattr(conversation, field, value)
            
            conversation.updated_at = datetime.utcnow()
            
            await self.db.commit()
            
            # Invalidate cache
            await redis_manager.delete(f"conversation:{conversation_id}")
            
            logger.info(
                "Conversation updated",
                conversation_id=conversation_id,
                updates=updates
            )
            
            return True
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to update conversation: {e}")
            return False

    
    @trace_operation("delete_conversation")
    async def delete_conversation(
        self,
        conversation_id: str,
        soft_delete: bool = True
    ) -> bool:
        """
        Delete a conversation.
        
        Args:
            conversation_id: Conversation ID
            soft_delete: If True, mark as closed; if False, hard delete
            
        Returns:
            True if deleted
        """
        try:
            conversation = await self.db.get(Conversation, conversation_id)
            if not conversation:
                return False
            
            if soft_delete:
                # Soft delete - mark as closed
                conversation.status = ConversationStatus.CLOSED
                conversation.updated_at = datetime.utcnow()
            else:
                # Hard delete - remove from database
                # Messages will be cascade deleted
                await self.db.delete(conversation)
            
            await self.db.commit()
            
            # Clean up cache
            await redis_manager.delete(f"conversation:{conversation_id}")
            
            logger.info(
                f"Conversation {'closed' if soft_delete else 'deleted'}",
                conversation_id=conversation_id
            )
            
            return True
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to delete conversation: {e}")
            return False
    
    @trace_operation("search_conversations")
    async def search_conversations(
        self,
        query: str,
        limit: int = 20
    ) -> tuple[List[Conversation], int]:
        """
        Search conversations by participants or message content.
        
        Args:
            query: Search query
            limit: Max results
            
        Returns:
            Tuple of (list of matching conversations, total count)
        """
        try:
            # Search by participants
            conversations_query = select(Conversation).where(
                or_(
                    Conversation.participant_from.ilike(f"%{query}%"),
                    Conversation.participant_to.ilike(f"%{query}%"),
                    Conversation.title.ilike(f"%{query}%") if Conversation.title else False
                )
            ).limit(limit)
            
            result = await self.db.execute(conversations_query)
            conversations = result.scalars().all()
            
            # Also search in message content (limited for performance)
            if len(conversations) < limit:
                messages_query = select(Message.conversation_id).distinct().where(
                    Message.body.ilike(f"%{query}%")
                ).limit(limit - len(conversations))
                
                message_result = await self.db.execute(messages_query)
                conversation_ids = message_result.scalars().all()
                
                if conversation_ids:
                    additional_query = select(Conversation).where(
                        Conversation.id.in_(conversation_ids)
                    )
                    additional_result = await self.db.execute(additional_query)
                    conversations.extend(additional_result.scalars().all())
            
            final_conversations = conversations[:limit]
            return final_conversations, len(final_conversations)
            
        except Exception as e:
            logger.error(f"Failed to search conversations: {e}")
            return [], 0

