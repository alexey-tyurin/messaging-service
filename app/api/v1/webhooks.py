"""
API endpoints for webhook operations.
"""

from fastapi import APIRouter, Depends, Request, Response, HTTPException
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
import json

from app.services.webhook_service import WebhookService
from app.db.session import get_db
from app.core.observability import get_logger


logger = get_logger(__name__)
router = APIRouter()


@router.post("/twilio")
async def twilio_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Handle Twilio webhooks for SMS/MMS messages.
    
    Processes incoming messages and delivery status updates.
    """
    try:
        # Get request data
        headers = dict(request.headers)
        body = await request.body()
        
        # Parse body based on content type
        content_type = headers.get("content-type", "")
        if "application/json" in content_type:
            data = json.loads(body)
        elif "application/x-www-form-urlencoded" in content_type:
            # Parse form data
            from urllib.parse import parse_qs
            data = {k: v[0] if len(v) == 1 else v 
                   for k, v in parse_qs(body.decode()).items()}
        else:
            data = {"raw": body.decode()}
        
        # Process webhook
        service = WebhookService(db)
        result = await service.process_webhook(
            provider="twilio",
            headers=headers,
            body=data
        )
        
        # Return appropriate response for Twilio
        return Response(
            content="<Response></Response>",
            media_type="application/xml",
            status_code=200
        )
        
    except Exception as e:
        logger.error(f"Failed to process Twilio webhook: {e}")
        # Return error response that Twilio understands
        return Response(
            content="<Response></Response>",
            media_type="application/xml",
            status_code=500
        )


@router.post("/sendgrid")
async def sendgrid_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Handle SendGrid webhooks for email messages.
    
    Processes incoming emails and delivery events.
    """
    try:
        # Get request data
        headers = dict(request.headers)
        body = await request.body()
        
        # Parse JSON body
        data = json.loads(body)
        
        # SendGrid sends events as array
        if isinstance(data, list):
            # Process each event
            for event in data:
                service = WebhookService(db)
                await service.process_webhook(
                    provider="sendgrid",
                    headers=headers,
                    body=event
                )
        else:
            # Single event
            service = WebhookService(db)
            await service.process_webhook(
                provider="sendgrid",
                headers=headers,
                body=data
            )
        
        # Return success response for SendGrid
        return {"status": "ok"}
        
    except Exception as e:
        logger.error(f"Failed to process SendGrid webhook: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/generic/{provider}")
async def generic_webhook(
    provider: str,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Generic webhook handler for any provider.
    
    Can be used for testing or new provider integrations.
    """
    try:
        # Get request data
        headers = dict(request.headers)
        body = await request.body()
        
        # Try to parse as JSON
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            data = {"raw": body.decode()}
        
        # Process webhook
        service = WebhookService(db)
        result = await service.process_webhook(
            provider=provider,
            headers=headers,
            body=data
        )
        
        return {"status": "ok", "result": result}
        
    except Exception as e:
        logger.error(f"Failed to process {provider} webhook: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/status/{provider}")
async def webhook_status(
    provider: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Check webhook configuration status for a provider.
    
    Returns whether webhooks are properly configured and recent activity.
    """
    try:
        from sqlalchemy import select, func, and_
        from app.models.database import WebhookLog, Provider as ProviderEnum
        from datetime import datetime, timedelta
        
        # Get recent webhook stats
        recent_time = datetime.utcnow() - timedelta(hours=24)
        
        # Query for webhook statistics
        stats_query = select(
            func.count(WebhookLog.id).label("total_webhooks"),
            func.count(WebhookLog.id).filter(
                WebhookLog.processed == True
            ).label("processed_webhooks"),
            func.count(WebhookLog.id).filter(
                WebhookLog.error_message != None
            ).label("error_webhooks"),
            func.max(WebhookLog.created_at).label("last_webhook_at")
        ).where(
            and_(
                WebhookLog.provider == ProviderEnum(provider),
                WebhookLog.created_at >= recent_time
            )
        )
        
        result = await db.execute(stats_query)
        stats = result.one()
        
        return {
            "provider": provider,
            "status": "configured",
            "statistics": {
                "total_webhooks_24h": stats.total_webhooks or 0,
                "processed_webhooks_24h": stats.processed_webhooks or 0,
                "error_webhooks_24h": stats.error_webhooks or 0,
                "last_webhook_at": stats.last_webhook_at.isoformat() if stats.last_webhook_at else None
            }
        }
        
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")
    except Exception as e:
        logger.error(f"Failed to get webhook status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
