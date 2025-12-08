"""
API endpoints for conversation operations.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Path
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.api.v1.models import (
    ConversationResponse, ConversationListResponse, ConversationUpdateRequest,
    ConversationSearchRequest, ConversationStatisticsResponse, MessageResponse,
    CreateConversationRequest
)
from app.services.conversation_service import ConversationService
from app.services.message_service import MessageService
from app.db.session import get_db
from app.models.database import ConversationStatus, MessageType, ConversationType
from app.core.observability import get_logger


logger = get_logger(__name__)
router = APIRouter()


@router.post("/", response_model=ConversationResponse, status_code=201)
async def create_conversation(
    request: CreateConversationRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new conversation or thread.
    
    - **Thread**: Requires title, type=thread.
    - **Direct**: Requires participants, type=direct (default).
    """
    try:
        service = ConversationService(db)
        conversation = await service.create_conversation(request)
        
        return ConversationResponse(
            id=str(conversation.id),
            participant_from=conversation.participant_from,
            participant_to=conversation.participant_to,
            channel_type=conversation.channel_type.value,
            type=conversation.type,
            status=conversation.status.value,
            title=conversation.title,
            last_message_at=conversation.last_message_at,
            message_count=conversation.message_count,
            unread_count=conversation.unread_count,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            metadata=conversation.meta_data or {}
        )
    except Exception as e:
        logger.error(f"Failed to create conversation: {e}")
        raise HTTPException(status_code=500, detail="Failed to create conversation")


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: UUID = Path(..., description="Conversation ID"),
    include_messages: bool = Query(False, description="Include messages in response"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get a specific conversation by ID.
    
    Optionally includes all messages in the conversation.
    """
    try:
        service = ConversationService(db)
        conversation = await service.get_conversation(
            str(conversation_id),
            include_messages=include_messages
        )
        
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        response = ConversationResponse(
            id=str(conversation.id),
            participant_from=conversation.participant_from,
            participant_to=conversation.participant_to,
            channel_type=conversation.channel_type.value,
            type=conversation.type,
            status=conversation.status.value,
            title=conversation.title,
            last_message_at=conversation.last_message_at,
            message_count=conversation.message_count,
            unread_count=conversation.unread_count,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            metadata=conversation.meta_data or {}
        )
        
        # Include messages if requested
        if include_messages and conversation.messages:
            response.messages = [
                MessageResponse(
                    id=str(msg.id),
                    conversation_id=str(msg.conversation_id),
                    parent_id=str(msg.parent_id) if msg.parent_id else None,
                    provider=msg.provider.value if msg.provider else None,
                    provider_message_id=msg.provider_message_id,
                    direction=msg.direction.value,
                    status=msg.status.value,
                    type=msg.message_type.value,
                    **{"from": msg.from_address},
                    to=msg.to_address,
                    body=msg.body,
                    attachments=msg.attachments or [],
                    sent_at=msg.sent_at,
                    delivered_at=msg.delivered_at,
                    created_at=msg.created_at,
                    updated_at=msg.updated_at,
                    metadata=msg.meta_data or {}
                )
                for msg in conversation.messages
            ]
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get conversation: {e}")
        raise HTTPException(status_code=500, detail="Failed to get conversation")


@router.get("/", response_model=ConversationListResponse)
async def list_conversations(
    participant: Optional[str] = Query(None, description="Filter by participant"),
    channel_type: Optional[MessageType] = Query(None, description="Filter by channel type"),
    status: Optional[ConversationStatus] = Query(None, description="Filter by status"),
    type: Optional[ConversationType] = Query(None, description="Filter by conversation type"),
    limit: int = Query(50, ge=1, le=100, description="Number of items to return"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    db: AsyncSession = Depends(get_db)
):
    """
    List conversations with optional filters.
    
    Supports filtering by participant, channel type, status, and conversation type.
    Results are paginated and ordered by last message time (newest first).
    """
    try:
        service = ConversationService(db)
        
        conversations, total = await service.list_conversations(
            participant=participant,
            channel_type=channel_type,
            status=status,
            type=type,
            limit=limit,
            offset=offset
        )
        
        # Convert to response models
        conversation_responses = []
        for conv in conversations:
            conversation_responses.append(ConversationResponse(
                id=str(conv.id),
                participant_from=conv.participant_from,
                participant_to=conv.participant_to,
                channel_type=conv.channel_type.value,
                type=conv.type,
                status=conv.status.value,
                title=conv.title,
                last_message_at=conv.last_message_at,
                message_count=conv.message_count,
                unread_count=conv.unread_count,
                created_at=conv.created_at,
                updated_at=conv.updated_at,
                metadata=conv.meta_data or {}
            ))
        
        return ConversationListResponse(
            conversations=conversation_responses,
            total=total,
            limit=limit,
            offset=offset
        )
        
    except Exception as e:
        logger.error(f"Failed to list conversations: {e}")
        raise HTTPException(status_code=500, detail="Failed to list conversations")


@router.patch("/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    conversation_id: UUID = Path(..., description="Conversation ID"),
    request: ConversationUpdateRequest = ...,
    db: AsyncSession = Depends(get_db)
):
    """
    Update conversation properties.
    
    Allows updating title, status, and metadata.
    """
    try:
        service = ConversationService(db)
        
        updates = request.dict(exclude_unset=True)
        success = await service.update_conversation(str(conversation_id), updates)
        
        if not success:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        # Get updated conversation
        conversation = await service.get_conversation(str(conversation_id))
        
        return ConversationResponse(
            id=str(conversation.id),
            participant_from=conversation.participant_from,
            participant_to=conversation.participant_to,
            channel_type=conversation.channel_type.value,
            type=conversation.type,
            status=conversation.status.value,
            title=conversation.title,
            last_message_at=conversation.last_message_at,
            message_count=conversation.message_count,
            unread_count=conversation.unread_count,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            metadata=conversation.meta_data or {}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update conversation: {e}")
        raise HTTPException(status_code=500, detail="Failed to update conversation")


@router.delete("/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: UUID = Path(..., description="Conversation ID"),
    hard_delete: bool = Query(False, description="Permanently delete conversation"),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a conversation.
    
    By default, performs a soft delete (marks as closed).
    Set hard_delete=true to permanently remove the conversation and all messages.
    """
    try:
        service = ConversationService(db)
        success = await service.delete_conversation(
            str(conversation_id),
            soft_delete=not hard_delete
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete conversation: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete conversation")


@router.post("/search", response_model=ConversationListResponse)
async def search_conversations(
    request: ConversationSearchRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Search conversations by participants or message content.
    
    Searches in participant addresses, conversation titles, and message bodies.
    """
    try:
        service = ConversationService(db)
        
        conversations, total = await service.search_conversations(
            query=request.query,
            limit=request.limit
        )
        
        # Convert to response models
        conversation_responses = []
        for conv in conversations:
            conversation_responses.append(ConversationResponse(
                id=str(conv.id),
                participant_from=conv.participant_from,
                participant_to=conv.participant_to,
                channel_type=conv.channel_type.value,
                type=conv.type,
                status=conv.status.value,
                title=conv.title,
                last_message_at=conv.last_message_at,
                message_count=conv.message_count,
                unread_count=conv.unread_count,
                created_at=conv.created_at,
                updated_at=conv.updated_at,
                metadata=conv.meta_data or {}
            ))
        
        return ConversationListResponse(
            conversations=conversation_responses,
            total=total,
            limit=request.limit,
            offset=0
        )
        
    except Exception as e:
        logger.error(f"Failed to search conversations: {e}")
        raise HTTPException(status_code=500, detail="Failed to search conversations")
