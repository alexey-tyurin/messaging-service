"""
Conversation service for managing message conversations.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy import select, and_, or_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.database import (
    Conversation, Message, ConversationStatus, MessageType
)
from app.db.redis import redis_manager
from app.core.observability import get_logger, MetricsCollector, trace_operation


logger = get_logger(__name__)


class ConversationService:
    """Service for handling conversation operations."""
    
    def __init__(self, db_session: AsyncSession):
        """
        Initialize conversation service.
        
        Args:
            db_session: Database session
        """
        self.db = db_session
    
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
            query = select(Conversation).where(Conversation.id == conversation_id)
            
            if include_messages:
                query = query.options(selectinload(Conversation.messages))
            
            result = await self.db.execute(query)
            conversation = result.scalar_one_or_none()
            
            if conversation:
                # Cache conversation metadata
                await redis_manager.set(
                    f"conversation:{conversation_id}",
                    {
                        "id": str(conversation.id),
                        "participant_from": conversation.participant_from,
                        "participant_to": conversation.participant_to,
                        "channel_type": conversation.channel_type.value,
                        "status": conversation.status.value,
                        "message_count": conversation.message_count,
                        "unread_count": conversation.unread_count
                    },
                    ttl=300  # 5 minutes
                )
                
                MetricsCollector.track_cache_operation("set", True)
            
            return conversation
            
        except Exception as e:
            logger.error(f"Failed to get conversation: {e}")
            return None
    
    @trace_operation("list_conversations")
    async def list_conversations(
        self,
        participant: Optional[str] = None,
        channel_type: Optional[MessageType] = None,
        status: Optional[ConversationStatus] = None,
        limit: int = 50,
        offset: int = 0
    ) -> tuple[List[Conversation], int]:
        """
        List conversations with filters.
        
        Args:
            participant: Filter by participant (from or to)
            channel_type: Filter by channel type
            status: Filter by status
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
            
            count_result = await self.db.execute(count_query)
            total = count_result.scalar() or 0
            
            # Order by last message and paginate
            query = query.order_by(desc(Conversation.last_message_at))
            query = query.limit(limit).offset(offset)
            
            result = await self.db.execute(query)
            conversations = result.scalars().all()
            
            # Update metrics
            if not offset:  # Only count on first page
                for channel in MessageType:
                    metrics_query = select(func.count()).select_from(Conversation)
                    metrics_query = metrics_query.where(
                        and_(
                            Conversation.channel_type == channel,
                            Conversation.status == ConversationStatus.ACTIVE
                        )
                    )
                    metrics_result = await self.db.execute(metrics_query)
                    count = metrics_result.scalar()
                    MetricsCollector.update_conversation_count(channel.value, count)
            
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
    
    @trace_operation("mark_as_read")
    async def mark_as_read(self, conversation_id: str) -> bool:
        """
        Mark conversation as read.
        
        Args:
            conversation_id: Conversation ID
            
        Returns:
            True if marked as read
        """
        try:
            conversation = await self.db.get(Conversation, conversation_id)
            if not conversation:
                return False
            
            conversation.unread_count = 0
            conversation.updated_at = datetime.utcnow()
            
            await self.db.commit()
            
            # Publish event
            await redis_manager.publish(
                f"conversation:{conversation_id}",
                {
                    "type": "marked_read",
                    "conversation_id": conversation_id,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
            
            return True
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to mark conversation as read: {e}")
            return False
    
    @trace_operation("archive_conversation")
    async def archive_conversation(self, conversation_id: str) -> bool:
        """
        Archive a conversation.
        
        Args:
            conversation_id: Conversation ID
            
        Returns:
            True if archived
        """
        return await self.update_conversation(
            conversation_id,
            {"status": ConversationStatus.ARCHIVED}
        )
    
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
    
    @trace_operation("get_conversation_statistics")
    async def get_conversation_statistics(
        self,
        conversation_id: str
    ) -> Dict[str, Any]:
        """
        Get conversation statistics.
        
        Args:
            conversation_id: Conversation ID
            
        Returns:
            Statistics dictionary
        """
        try:
            # Get message statistics
            stats_query = select(
                func.count(Message.id).label("total_messages"),
                func.count(Message.id).filter(
                    Message.direction == "inbound"
                ).label("inbound_messages"),
                func.count(Message.id).filter(
                    Message.direction == "outbound"
                ).label("outbound_messages"),
                func.count(Message.id).filter(
                    Message.status == "failed"
                ).label("failed_messages"),
                func.avg(
                    func.extract("epoch", Message.sent_at - Message.created_at)
                ).label("avg_send_time")
            ).where(Message.conversation_id == conversation_id)
            
            result = await self.db.execute(stats_query)
            stats = result.one()
            
            return {
                "total_messages": stats.total_messages or 0,
                "inbound_messages": stats.inbound_messages or 0,
                "outbound_messages": stats.outbound_messages or 0,
                "failed_messages": stats.failed_messages or 0,
                "avg_send_time_seconds": float(stats.avg_send_time) if stats.avg_send_time else 0
            }
            
        except Exception as e:
            logger.error(f"Failed to get conversation statistics: {e}")
            return {}
    
    @trace_operation("merge_conversations")
    async def merge_conversations(
        self,
        source_id: str,
        target_id: str
    ) -> bool:
        """
        Merge two conversations.
        
        Args:
            source_id: Source conversation ID
            target_id: Target conversation ID
            
        Returns:
            True if merged
        """
        try:
            source = await self.db.get(Conversation, source_id)
            target = await self.db.get(Conversation, target_id)
            
            if not source or not target:
                logger.warning("Conversation not found for merge")
                return False
            
            # Move messages from source to target
            update_query = (
                select(Message)
                .where(Message.conversation_id == source_id)
            )
            result = await self.db.execute(update_query)
            messages = result.scalars().all()
            
            for message in messages:
                message.conversation_id = target.id
            
            # Update target conversation stats
            target.message_count += source.message_count
            target.unread_count += source.unread_count
            
            if source.last_message_at and (
                not target.last_message_at or 
                source.last_message_at > target.last_message_at
            ):
                target.last_message_at = source.last_message_at
            
            # Delete source conversation
            await self.db.delete(source)
            
            await self.db.commit()
            
            logger.info(
                "Conversations merged",
                source_id=source_id,
                target_id=target_id
            )
            
            return True
            
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to merge conversations: {e}")
            return False
