"""
Provider abstraction layer implementing strategy pattern for different message providers.
Supports SMS/MMS (Twilio), Email (SendGrid), and extensible for Voice/Voicemail.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from datetime import datetime
import asyncio
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential
from circuitbreaker import circuit

from app.core.observability import get_logger, MetricsCollector, trace_operation
from app.models.database import MessageType, MessageStatus, Provider
from app.core.config import settings


logger = get_logger(__name__)


class MessageProvider(ABC):
    """Abstract base class for message providers."""
    
    @abstractmethod
    async def send_message(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """Send a message through the provider."""
        pass
    
    @abstractmethod
    async def get_message_status(self, message_id: str) -> Dict[str, Any]:
        """Get message status from provider."""
        pass
    
    @abstractmethod
    async def validate_webhook(self, headers: Dict, body: Any) -> bool:
        """Validate incoming webhook."""
        pass
    
    @abstractmethod
    async def process_webhook(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process incoming webhook data."""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check provider health."""
        pass


class TwilioProvider(MessageProvider):
    """
    Twilio provider for SMS/MMS messages.
    
    NOTE: This is a MOCK implementation that returns hardcoded responses.
    No actual API calls are made to Twilio.
    """
    
    def __init__(self):
        self.name = Provider.TWILIO
        self.base_url = "https://api.twilio.com"  # Not actually used (mock)
        self.timeout = settings.sms_provider_timeout
        self.client = httpx.AsyncClient(timeout=self.timeout)
        
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    @circuit(failure_threshold=5, recovery_timeout=60)
    @trace_operation("twilio_send_message")
    async def send_message(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send SMS/MMS through Twilio (MOCK).
        
        This is a mock implementation that returns hardcoded success responses.
        No actual Twilio API calls are made.
        
        Args:
            message_data: Message details (from, to, type, body, attachments)
            
        Returns:
            Mock provider response with provider_message_id, status, timestamp, cost
        """
        try:
            with MetricsCollector.track_duration(
                message_data["type"],
                self.name.value
            ):
                # MOCK: Simulate network delay (no actual API call)
                # In production, this would make actual API call
                await asyncio.sleep(0.1)

            # MOCK: Return hardcoded success response
                response = {
                    "provider_message_id": f"twilio_{datetime.utcnow().timestamp()}",
                    "status": "sent",
                    "timestamp": datetime.utcnow().isoformat(),
                    "cost": 0.01 if message_data["type"] == "sms" else 0.02
                }
                
                MetricsCollector.track_message(
                    direction="outbound",
                    msg_type=message_data["type"],
                    status="sent",
                    provider=self.name.value
                )
                
                logger.info(
                    "Message sent via Twilio (MOCK)",
                    provider=self.name.value,
                    message_id=response["provider_message_id"]
                )
                
                return response
                
        except Exception as e:
            MetricsCollector.track_provider_error(
                self.name.value,
                type(e).__name__
            )
            logger.error(
                "Failed to send message via Twilio (MOCK)",
                error=str(e),
                message_data=message_data
            )
            raise
    
    async def get_message_status(self, message_id: str) -> Dict[str, Any]:
        """
        Get message status from Twilio (MOCK).
        
        Returns hardcoded delivered status without making actual API calls.
        """
        try:
            # MOCK: Simulate API delay
            await asyncio.sleep(0.05)
            # MOCK: Return hardcoded delivered status
            return {
                "status": "delivered",
                "delivered_at": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Failed to get status from Twilio (MOCK): {e}")
            raise
    
    async def validate_webhook(self, headers: Dict, body: Any) -> bool:
        """
        Validate Twilio webhook signature (MOCK).
        
        Always returns True. In production, would validate X-Twilio-Signature.
        """
        # MOCK: Always accept webhooks
        return True
    
    async def process_webhook(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process Twilio webhook data (MOCK).
        
        Normalizes webhook data to internal format.
        """
        try:
            # Normalize Twilio webhook to internal format
            return {
                "provider": self.name.value,
                "provider_message_id": data.get("messaging_provider_id"),
                "from": data.get("from"),
                "to": data.get("to"),
                "type": data.get("type", "sms"),
                "body": data.get("body"),
                "attachments": data.get("attachments", []),
                "timestamp": data.get("timestamp"),
                "direction": "inbound"
            }
        except Exception as e:
            logger.error(f"Failed to process Twilio webhook (MOCK): {e}")
            raise
    
    async def health_check(self) -> bool:
        """
        Check Twilio API health (MOCK).
        
        Always returns True indicating provider is healthy.
        """
        try:
            # MOCK: Simulate health check
            await asyncio.sleep(0.01)
            return True
        except Exception:
            return False
    
    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()


class SendGridProvider(MessageProvider):
    """
    SendGrid provider for email messages.
    
    NOTE: This is a MOCK implementation that returns hardcoded responses.
    No actual API calls are made to SendGrid.
    """
    
    def __init__(self):
        self.name = Provider.SENDGRID
        self.base_url = "https://api.sendgrid.com"  # Not actually used (mock)
        self.timeout = settings.email_provider_timeout
        self.client = httpx.AsyncClient(timeout=self.timeout)
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    @circuit(failure_threshold=5, recovery_timeout=60)
    @trace_operation("sendgrid_send_message")
    async def send_message(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send email through SendGrid (MOCK).
        
        This is a mock implementation that returns hardcoded success responses.
        No actual SendGrid API calls are made.
        
        Args:
            message_data: Message details (from, to, body, attachments)
            
        Returns:
            Mock provider response with provider_message_id, status, timestamp, cost
        """
        try:
            with MetricsCollector.track_duration("email", self.name.value):
                # MOCK: Simulate network delay (no actual API call)
                await asyncio.sleep(0.15)
                
                # MOCK: Return hardcoded success response
                response = {
                    "provider_message_id": f"sendgrid_{datetime.utcnow().timestamp()}",
                    "status": "sent",
                    "timestamp": datetime.utcnow().isoformat(),
                    "cost": 0.001
                }
                
                MetricsCollector.track_message(
                    direction="outbound",
                    msg_type="email",
                    status="sent",
                    provider=self.name.value
                )
                
                logger.info(
                    "Email sent via SendGrid (MOCK)",
                    provider=self.name.value,
                    message_id=response["provider_message_id"]
                )
                
                return response
                
        except Exception as e:
            MetricsCollector.track_provider_error(
                self.name.value,
                type(e).__name__
            )
            logger.error(
                "Failed to send email via SendGrid (MOCK)",
                error=str(e),
                message_data=message_data
            )
            raise
    
    async def get_message_status(self, message_id: str) -> Dict[str, Any]:
        """
        Get message status from SendGrid (MOCK).
        
        Returns hardcoded delivered status without making actual API calls.
        """
        try:
            # MOCK: Simulate API delay
            await asyncio.sleep(0.05)
            # MOCK: Return hardcoded delivered status
            return {
                "status": "delivered",
                "delivered_at": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Failed to get status from SendGrid (MOCK): {e}")
            raise
    
    async def validate_webhook(self, headers: Dict, body: Any) -> bool:
        """
        Validate SendGrid webhook (MOCK).
        
        Always returns True. In production, would validate webhook signature.
        """
        # MOCK: Always accept webhooks
        return True
    
    async def process_webhook(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process SendGrid webhook data (MOCK).
        
        Normalizes webhook data to internal format.
        """
        try:
            # Normalize SendGrid webhook to internal format
            return {
                "provider": self.name.value,
                "provider_message_id": data.get("xillio_id"),
                "from": data.get("from"),
                "to": data.get("to"),
                "type": "email",
                "body": data.get("body"),
                "attachments": data.get("attachments", []),
                "timestamp": data.get("timestamp"),
                "direction": "inbound"
            }
        except Exception as e:
            logger.error(f"Failed to process SendGrid webhook (MOCK): {e}")
            raise
    
    async def health_check(self) -> bool:
        """
        Check SendGrid API health (MOCK).
        
        Always returns True indicating provider is healthy.
        """
        try:
            # MOCK: Simulate health check
            await asyncio.sleep(0.01)
            return True
        except Exception:
            return False
    
    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()


class ProviderFactory:
    """Factory for creating message providers."""
    
    _providers: Dict[str, MessageProvider] = {}
    
    @classmethod
    def register_provider(cls, provider_type: str, provider: MessageProvider):
        """Register a provider."""
        cls._providers[provider_type] = provider
        logger.info(f"Registered provider: {provider_type}")
    
    @classmethod
    def get_provider(cls, message_type: MessageType) -> MessageProvider:
        """
        Get appropriate provider for message type.
        
        Args:
            message_type: Type of message
            
        Returns:
            Message provider instance
        """
        provider_map = {
            MessageType.SMS: "twilio",
            MessageType.MMS: "twilio",
            MessageType.EMAIL: "sendgrid"
        }
        
        provider_type = provider_map.get(message_type)
        if not provider_type:
            raise ValueError(f"No provider for message type: {message_type}")
        
        provider = cls._providers.get(provider_type)
        if not provider:
            raise ValueError(f"Provider not registered: {provider_type}")
        
        return provider
    
    @classmethod
    async def init_providers(cls):
        """Initialize all providers."""
        # Register providers
        cls.register_provider("twilio", TwilioProvider())
        cls.register_provider("sendgrid", SendGridProvider())
        
        logger.info("All providers initialized")
    
    @classmethod
    async def close_providers(cls):
        """Close all provider connections."""
        for provider_type, provider in cls._providers.items():
            if hasattr(provider, "close"):
                await provider.close()
                logger.info(f"Closed provider: {provider_type}")


class ProviderSelector:
    """Selects best provider based on various factors."""
    
    @staticmethod
    async def select_provider(
        message_type: MessageType,
        metadata: Optional[Dict[str, Any]] = None
    ) -> MessageProvider:
        """
        Select optimal provider for message.
        
        Args:
            message_type: Type of message
            metadata: Additional selection criteria
            
        Returns:
            Selected provider
        """
        # For now, use default provider mapping
        # In production, could implement:
        # - Load balancing
        # - Cost optimization
        # - Geographic routing
        # - Provider health checks
        
        provider = ProviderFactory.get_provider(message_type)
        
        # Check provider health
        if not await provider.health_check():
            logger.warning(f"Provider unhealthy: {provider.name}")
            # In production, fallback to backup provider
        
        return provider
