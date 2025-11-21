"""
Legacy API routes for backward compatibility with test_original.sh.
These routes map to the new v1 API endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any, Optional
from uuid import UUID

from app.db.session import get_db
from app.services.message_service import MessageService
from app.services.conversation_service import ConversationService
from app.services.webhook_service import WebhookService
from app.models.database import MessageType
from app.core.observability import get_logger

logger = get_logger(__name__)

# Create routers for different legacy endpoint groups
messages_router = APIRouter(prefix="/api/messages", tags=["legacy-messages"])
webhooks_router = APIRouter(prefix="/api/webhooks", tags=["legacy-webhooks"])
conversations_router = APIRouter(prefix="/api/conversations", tags=["legacy-conversations"])


@messages_router.post("/sms")
async def send_sms_message(
    request: Dict[str, Any],
    db: AsyncSession = Depends(get_db)
):
    """
    Legacy endpoint for sending SMS/MMS messages.
    Maps to /api/v1/messages/send
    """
    try:
        service = MessageService(db)
        
        # Determine if it's SMS or MMS based on type field or attachments
        message_type = request.get("type", "sms")
        if message_type not in ["sms", "mms"]:
            message_type = "mms" if request.get("attachments") else "sms"
        
        # Convert legacy format to v1 format
        message_data = {
            "from": request.get("from"),
            "to": request.get("to"),
            "type": message_type,
            "body": request.get("body"),
            "attachments": request.get("attachments") or [],
            "metadata": {"timestamp": request.get("timestamp")}
        }
        
        message = await service.send_message(message_data)
        
        return {
            "status": "success",
            "message_id": str(message.id),
            "conversation_id": str(message.conversation_id),
            "type": message.message_type.value,
            "provider": message.provider.value if message.provider else None
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to send SMS/MMS: {e}")
        raise HTTPException(status_code=500, detail="Failed to send message")


@messages_router.post("/email")
async def send_email_message(
    request: Dict[str, Any],
    db: AsyncSession = Depends(get_db)
):
    """
    Legacy endpoint for sending email messages.
    Maps to /api/v1/messages/send
    """
    try:
        service = MessageService(db)
        
        # Convert legacy format to v1 format
        message_data = {
            "from": request.get("from"),
            "to": request.get("to"),
            "type": "email",
            "body": request.get("body"),
            "attachments": request.get("attachments") or [],
            "metadata": {"timestamp": request.get("timestamp")}
        }
        
        message = await service.send_message(message_data)
        
        return {
            "status": "success",
            "message_id": str(message.id),
            "conversation_id": str(message.conversation_id),
            "type": message.message_type.value,
            "provider": message.provider.value if message.provider else None
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        raise HTTPException(status_code=500, detail="Failed to send message")


@webhooks_router.post("/sms")
async def sms_webhook(
    request: Dict[str, Any],
    db: AsyncSession = Depends(get_db)
):
    """
    Legacy endpoint for SMS/MMS webhooks.
    Maps to /api/v1/webhooks/twilio
    """
    try:
        service = WebhookService(db)
        
        # Process as Twilio webhook
        await service.process_webhook(
            provider="twilio",
            headers={},
            body=request
        )
        
        return {"status": "success", "message": "Webhook processed"}
        
    except Exception as e:
        logger.error(f"Failed to process SMS webhook: {e}")
        raise HTTPException(status_code=500, detail="Failed to process webhook")


@webhooks_router.post("/email")
async def email_webhook(
    request: Dict[str, Any],
    db: AsyncSession = Depends(get_db)
):
    """
    Legacy endpoint for email webhooks.
    Maps to /api/v1/webhooks/sendgrid
    """
    try:
        service = WebhookService(db)
        
        # Process as SendGrid webhook
        await service.process_webhook(
            provider="sendgrid",
            headers={},
            body=request
        )
        
        return {"status": "success", "message": "Webhook processed"}
        
    except Exception as e:
        logger.error(f"Failed to process email webhook: {e}")
        raise HTTPException(status_code=500, detail="Failed to process webhook")


@conversations_router.get("")
async def get_conversations(
    participant: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """
    Legacy endpoint for getting conversations.
    Maps to /api/v1/conversations/
    """
    try:
        service = ConversationService(db)
        
        conversations, total = await service.list_conversations(
            participant=participant,
            limit=limit,
            offset=offset
        )
        
        # Convert to legacy format
        result = []
        for conv in conversations:
            result.append({
                "id": str(conv.id),
                "participant_from": conv.participant_from,
                "participant_to": conv.participant_to,
                "channel_type": conv.channel_type.value,
                "status": conv.status.value,
                "message_count": conv.message_count,
                "unread_count": conv.unread_count,
                "last_message_at": conv.last_message_at.isoformat() if conv.last_message_at else None,
                "created_at": conv.created_at.isoformat() if conv.created_at else None
            })
        
        return {
            "conversations": result,
            "total": total
        }
        
    except Exception as e:
        logger.error(f"Failed to list conversations: {e}")
        raise HTTPException(status_code=500, detail="Failed to list conversations")


@conversations_router.get("/{conversation_id}/messages")
async def get_conversation_messages(
    conversation_id: str,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """
    Legacy endpoint for getting messages in a conversation.
    Maps to /api/v1/messages/?conversation_id=X
    """
    try:
        service = MessageService(db)
        
        # Try to parse as UUID, otherwise just use as string
        try:
            conv_id = str(UUID(conversation_id))
        except ValueError:
            # If not a valid UUID, return empty for now
            return {
                "messages": [],
                "total": 0,
                "conversation_id": conversation_id
            }
        
        messages, total = await service.list_messages(
            conversation_id=conv_id,
            limit=limit,
            offset=offset
        )
        
        # Convert to legacy format
        result = []
        for msg in messages:
            result.append({
                "id": str(msg.id),
                "conversation_id": str(msg.conversation_id),
                "direction": msg.direction.value,
                "type": msg.message_type.value,
                "from": msg.from_address,
                "to": msg.to_address,
                "body": msg.body,
                "status": msg.status.value,
                "provider": msg.provider.value if msg.provider else None,
                "created_at": msg.created_at.isoformat() if msg.created_at else None,
                "sent_at": msg.sent_at.isoformat() if msg.sent_at else None
            })
        
        return {
            "messages": result,
            "total": total,
            "conversation_id": conversation_id
        }
        
    except Exception as e:
        logger.error(f"Failed to get conversation messages: {e}")
        raise HTTPException(status_code=500, detail="Failed to get messages")

