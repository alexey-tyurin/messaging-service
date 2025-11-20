"""
Webhook service for processing incoming webhooks from message providers.
"""

from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
import hashlib
import hmac
import asyncio

from app.models.database import WebhookLog, Provider
from app.providers.base import ProviderFactory
from app.services.message_service import MessageService
from app.core.observability import get_logger, trace_operation, monitor_performance
from app.core.config import settings
from app.db.redis import redis_manager


logger = get_logger(__name__)


class WebhookService:
    """Service for handling webhook operations."""
    
    def __init__(self, db_session: AsyncSession):
        """
        Initialize webhook service.
        
        Args:
            db_session: Database session
        """
        self.db = db_session
    
    @trace_operation("process_webhook")
    @monitor_performance("process_webhook")
    async def process_webhook(
        self,
        provider: str,
        headers: Dict[str, str],
        body: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process incoming webhook from provider.
        
        Args:
            provider: Provider name
            headers: Request headers
            body: Webhook body
            
        Returns:
            Processing result
        """
        try:
            # Log webhook
            webhook_log = await self._log_webhook(provider, headers, body)
            
            # Check for duplicate processing
            if await self._is_duplicate(provider, body):
                logger.warning(
                    "Duplicate webhook detected",
                    provider=provider,
                    webhook_id=webhook_log.id
                )
                return {"status": "duplicate", "message": "Webhook already processed"}
            
            # Get provider instance
            try:
                from app.models.database import MessageType
                # Map provider name to message type for factory
                provider_map = {
                    "twilio": MessageType.SMS,
                    "sendgrid": MessageType.EMAIL
                }
                message_type = provider_map.get(provider)
                if not message_type:
                    raise ValueError(f"Unknown provider: {provider}")
                provider_instance = ProviderFactory.get_provider(message_type)
            except Exception:
                raise ValueError(f"Unknown provider: {provider}")
            
            # Validate webhook signature
            if not await provider_instance.validate_webhook(headers, body):
                logger.warning(
                    "Invalid webhook signature",
                    provider=provider,
                    webhook_id=webhook_log.id
                )
                webhook_log.error_message = "Invalid signature"
                await self.db.commit()
                return {"status": "error", "message": "Invalid webhook signature"}
            
            # Process webhook based on type
            webhook_data = await provider_instance.process_webhook(body)
            result = await self._handle_webhook_type(provider, webhook_data)
            
            # Mark as processed
            webhook_log.processed = True
            webhook_log.processed_at = datetime.utcnow()
            await self.db.commit()
            
            logger.info(
                "Webhook processed successfully",
                provider=provider,
                webhook_id=webhook_log.id
            )
            
            return {
                "status": "success",
                "webhook_id": str(webhook_log.id),
                "result": result
            }
            
        except Exception as e:
            logger.error(
                f"Failed to process webhook: {e}",
                provider=provider,
                body=body
            )
            
            # Update webhook log with error
            if webhook_log:
                webhook_log.error_message = str(e)
                await self.db.commit()
            
            raise
    
    async def _log_webhook(
        self,
        provider: str,
        headers: Dict[str, str],
        body: Dict[str, Any]
    ) -> WebhookLog:
        """
        Log incoming webhook.
        
        Args:
            provider: Provider name
            headers: Request headers
            body: Webhook body
            
        Returns:
            WebhookLog instance
        """
        webhook_log = WebhookLog(
            provider=Provider(provider),
            webhook_id=body.get("id") or body.get("message_id"),
            endpoint=f"/webhooks/{provider}",
            method="POST",
            headers=headers,
            body=body
        )
        
        self.db.add(webhook_log)
        await self.db.flush()
        
        return webhook_log
    
    async def _is_duplicate(
        self,
        provider: str,
        body: Dict[str, Any]
    ) -> bool:
        """
        Check if webhook is duplicate.
        
        Args:
            provider: Provider name
            body: Webhook body
            
        Returns:
            True if duplicate
        """
        # Create unique key for webhook
        webhook_key = self._generate_webhook_key(provider, body)
        
        # Check in Redis cache (with 1 hour TTL)
        if await redis_manager.exists(f"webhook:{webhook_key}"):
            return True
        
        # Set in cache to prevent duplicates
        await redis_manager.set(f"webhook:{webhook_key}", True, ttl=3600)
        
        return False
    
    def _generate_webhook_key(
        self,
        provider: str,
        body: Dict[str, Any]
    ) -> str:
        """
        Generate unique key for webhook.
        
        Args:
            provider: Provider name
            body: Webhook body
            
        Returns:
            Unique key
        """
        # Use provider and message ID to create unique key
        message_id = (
            body.get("id") or
            body.get("message_id") or
            body.get("messaging_provider_id") or
            body.get("xillio_id")
        )
        
        if message_id:
            return f"{provider}:{message_id}"
        
        # Fallback to hash of body
        body_str = str(sorted(body.items()))
        return f"{provider}:{hashlib.md5(body_str.encode()).hexdigest()}"
    
    async def _handle_webhook_type(
        self,
        provider: str,
        webhook_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle different webhook types.
        
        Args:
            provider: Provider name
            webhook_data: Processed webhook data
            
        Returns:
            Processing result
        """
        # Determine webhook type
        direction = webhook_data.get("direction")
        
        if direction == "inbound":
            # Process inbound message
            return await self._handle_inbound_message(provider, webhook_data)
        else:
            # Handle status update
            return await self._handle_status_update(provider, webhook_data)
    
    async def _handle_inbound_message(
        self,
        provider: str,
        webhook_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle inbound message webhook.
        
        Args:
            provider: Provider name
            webhook_data: Webhook data
            
        Returns:
            Processing result
        """
        message_service = MessageService(self.db)
        
        # Receive message
        message = await message_service.receive_message(provider, webhook_data)
        
        return {
            "type": "inbound_message",
            "message_id": str(message.id),
            "conversation_id": str(message.conversation_id)
        }
    
    async def _handle_status_update(
        self,
        provider: str,
        webhook_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle message status update webhook.
        
        Args:
            provider: Provider name
            webhook_data: Webhook data
            
        Returns:
            Processing result
        """
        message_service = MessageService(self.db)
        
        # Get message by provider ID
        from sqlalchemy import select
        from app.models.database import Message, MessageStatus
        
        result = await self.db.execute(
            select(Message).where(
                Message.provider == Provider(provider),
                Message.provider_message_id == webhook_data.get("provider_message_id")
            )
        )
        message = result.scalar_one_or_none()
        
        if not message:
            logger.warning(
                "Message not found for status update",
                provider=provider,
                provider_message_id=webhook_data.get("provider_message_id")
            )
            return {
                "type": "status_update",
                "status": "message_not_found"
            }
        
        # Update message status
        status_map = {
            "delivered": MessageStatus.DELIVERED,
            "failed": MessageStatus.FAILED,
            "sent": MessageStatus.SENT
        }
        
        new_status = status_map.get(webhook_data.get("status"))
        if new_status:
            await message_service.update_message_status(
                str(message.id),
                new_status,
                webhook_data
            )
        
        return {
            "type": "status_update",
            "message_id": str(message.id),
            "new_status": new_status.value if new_status else None
        }
    
    @staticmethod
    def validate_webhook_signature(
        provider: str,
        signature: str,
        body: bytes
    ) -> bool:
        """
        Validate webhook signature.
        
        Args:
            provider: Provider name
            signature: Signature from headers
            body: Request body
            
        Returns:
            True if valid
        """
        # Get provider-specific secret
        secret = settings.webhook_secret
        
        # Calculate expected signature
        expected = hmac.new(
            secret.encode(),
            body,
            hashlib.sha256
        ).hexdigest()
        
        # Compare signatures
        return hmac.compare_digest(signature, expected)


class WebhookProcessor:
    """Background processor for webhook queue."""
    
    def __init__(self, db_session: AsyncSession):
        """
        Initialize webhook processor.
        
        Args:
            db_session: Database session
        """
        self.db = db_session
        self.service = WebhookService(db_session)
    
    async def process_queue(self):
        """
        Process webhooks from queue.
        """
        while True:
            try:
                # Get webhooks from queue
                webhooks = await redis_manager.dequeue_messages(
                    "webhook_queue",
                    count=10,
                    block=1000
                )
                
                for webhook_data in webhooks:
                    try:
                        await self.service.process_webhook(
                            webhook_data["provider"],
                            webhook_data["headers"],
                            webhook_data["body"]
                        )
                        
                        # Acknowledge processing
                        await redis_manager.ack_message(
                            "webhook_queue",
                            "webhook_processors",
                            webhook_data["_id"]
                        )
                        
                    except Exception as e:
                        logger.error(f"Failed to process queued webhook: {e}")
                
            except Exception as e:
                logger.error(f"Error in webhook processor: {e}")
                await asyncio.sleep(5)
