"""
API endpoints for message operations.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Path
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.api.v1.models import (
    SendMessageRequest, MessageResponse, MessageListResponse,
    MessageStatusUpdateRequest, PaginationParams
)
from app.services.message_service import MessageService
from app.db.session import get_db
from app.models.database import MessageStatus, MessageDirection, MessageType
from app.core.observability import get_logger


logger = get_logger(__name__)
router = APIRouter()


@router.post("/send", response_model=MessageResponse, status_code=201)
async def send_message(
    request: SendMessageRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Send a new message.
    
    Automatically detects message type if not specified.
    Queues message for delivery through appropriate provider.
    """
    try:
        service = MessageService(db)
        
        # Convert Pydantic model to dict
        message_data = request.dict(by_alias=True)
        
        # Send message
        message = await service.send_message(message_data)
        
        # Convert to response model
        return MessageResponse(
            id=str(message.id),
            conversation_id=str(message.conversation_id),
            provider=message.provider.value if message.provider else None,
            provider_message_id=message.provider_message_id,
            direction=message.direction.value,
            status=message.status.value,
            type=message.message_type.value,
            **{"from": message.from_address},
            to=message.to_address,
            body=message.body,
            attachments=message.attachments or [],
            sent_at=message.sent_at,
            delivered_at=message.delivered_at,
            created_at=message.created_at,
            updated_at=message.updated_at,
            metadata=message.meta_data or {}
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to send message: {e}")
        raise HTTPException(status_code=500, detail="Failed to send message")


@router.get("/{message_id}", response_model=MessageResponse)
async def get_message(
    message_id: UUID = Path(..., description="Message ID"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get a specific message by ID.
    
    Returns message details including status and conversation information.
    """
    try:
        service = MessageService(db)
        message = await service.get_message(str(message_id))
        
        if not message:
            raise HTTPException(status_code=404, detail="Message not found")
        
        return MessageResponse(
            id=str(message.id),
            conversation_id=str(message.conversation_id),
            provider=message.provider.value if message.provider else None,
            provider_message_id=message.provider_message_id,
            direction=message.direction.value,
            status=message.status.value,
            type=message.message_type.value,
            **{"from": message.from_address},
            to=message.to_address,
            body=message.body,
            attachments=message.attachments or [],
            sent_at=message.sent_at,
            delivered_at=message.delivered_at,
            created_at=message.created_at,
            updated_at=message.updated_at,
            metadata=message.meta_data or {}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get message: {e}")
        raise HTTPException(status_code=500, detail="Failed to get message")


@router.get("/", response_model=MessageListResponse)
async def list_messages(
    conversation_id: Optional[UUID] = Query(None, description="Filter by conversation ID"),
    status: Optional[MessageStatus] = Query(None, description="Filter by status"),
    direction: Optional[MessageDirection] = Query(None, description="Filter by direction"),
    limit: int = Query(50, ge=1, le=100, description="Number of items to return"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    db: AsyncSession = Depends(get_db)
):
    """
    List messages with optional filters.
    
    Supports filtering by conversation, status, and direction.
    Results are paginated and ordered by creation time (newest first).
    """
    try:
        service = MessageService(db)
        
        messages, total = await service.list_messages(
            conversation_id=str(conversation_id) if conversation_id else None,
            status=status,
            direction=direction,
            limit=limit,
            offset=offset
        )
        
        # Convert to response models
        message_responses = []
        for msg in messages:
            message_responses.append(MessageResponse(
                id=str(msg.id),
                conversation_id=str(msg.conversation_id),
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
            ))
        
        return MessageListResponse(
            messages=message_responses,
            total=total,
            limit=limit,
            offset=offset
        )
        
    except Exception as e:
        logger.error(f"Failed to list messages: {e}")
        raise HTTPException(status_code=500, detail="Failed to list messages")


@router.patch("/{message_id}/status", response_model=MessageResponse)
async def update_message_status(
    message_id: UUID = Path(..., description="Message ID"),
    request: MessageStatusUpdateRequest = ...,
    db: AsyncSession = Depends(get_db)
):
    """
    Update message status.
    
    Used primarily for webhook callbacks to update delivery status.
    """
    try:
        service = MessageService(db)
        
        success = await service.update_message_status(
            str(message_id),
            request.status,
            request.metadata
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Message not found")
        
        # Get updated message
        message = await service.get_message(str(message_id))
        
        return MessageResponse(
            id=str(message.id),
            conversation_id=str(message.conversation_id),
            provider=message.provider.value if message.provider else None,
            provider_message_id=message.provider_message_id,
            direction=message.direction.value,
            status=message.status.value,
            type=message.message_type.value,
            **{"from": message.from_address},
            to=message.to_address,
            body=message.body,
            attachments=message.attachments or [],
            sent_at=message.sent_at,
            delivered_at=message.delivered_at,
            created_at=message.created_at,
            updated_at=message.updated_at,
            metadata=message.meta_data or {}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update message status: {e}")
        raise HTTPException(status_code=500, detail="Failed to update message status")


@router.post("/{message_id}/retry", response_model=MessageResponse)
async def retry_message(
    message_id: UUID = Path(..., description="Message ID"),
    db: AsyncSession = Depends(get_db)
):
    """
    Retry sending a failed message.
    
    Requeues the message for delivery if it failed or is in retry status.
    """
    try:
        service = MessageService(db)
        
        # Get message
        message = await service.get_message(str(message_id))
        if not message:
            raise HTTPException(status_code=404, detail="Message not found")
        
        # Check if message can be retried
        if message.status not in [MessageStatus.FAILED, MessageStatus.RETRY]:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot retry message with status: {message.status}"
            )
        
        # Reset retry count and requeue
        message.retry_count = 0
        message.status = MessageStatus.PENDING
        await db.commit()
        
        # Process message
        success = await service.process_outbound_message(str(message_id))
        
        # Get updated message
        message = await service.get_message(str(message_id))
        
        return MessageResponse(
            id=str(message.id),
            conversation_id=str(message.conversation_id),
            provider=message.provider.value if message.provider else None,
            provider_message_id=message.provider_message_id,
            direction=message.direction.value,
            status=message.status.value,
            type=message.message_type.value,
            **{"from": message.from_address},
            to=message.to_address,
            body=message.body,
            attachments=message.attachments or [],
            sent_at=message.sent_at,
            delivered_at=message.delivered_at,
            created_at=message.created_at,
            updated_at=message.updated_at,
            metadata=message.meta_data or {}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retry message: {e}")
        raise HTTPException(status_code=500, detail="Failed to retry message")
