
import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
from tenacity import RetryError

from app.providers.base import (
    ProviderFactory, ProviderSelector, TwilioProvider, SendGridProvider,
    ProviderRateLimitError, ProviderServerError
)
from app.models.database import MessageType, Provider
from app.core.config import settings

@pytest.fixture
async def cleanup_providers():
    yield
    await ProviderFactory.close_providers()

@pytest.mark.asyncio
async def test_provider_factory_registration(cleanup_providers):
    """Test provider registration."""
    mock_provider = AsyncMock()
    ProviderFactory.register_provider("test_provider", mock_provider)
    
    assert ProviderFactory._providers.get("test_provider") == mock_provider

@pytest.mark.asyncio
async def test_provider_factory_get_provider(cleanup_providers):
    """Test getting provider by type."""
    await ProviderFactory.init_providers()
    
    sms_provider = ProviderFactory.get_provider(MessageType.SMS)
    assert isinstance(sms_provider, TwilioProvider)
    
    email_provider = ProviderFactory.get_provider(MessageType.EMAIL)
    assert isinstance(email_provider, SendGridProvider)
    
    with pytest.raises(ValueError):
        ProviderFactory.get_provider("invalid_type")

@pytest.mark.asyncio
async def test_twilio_provider_send_message():
    """Test Twilio provider send_message."""
    provider = TwilioProvider()
    
    message_data = {
        "from": "+1234567890",
        "to": "+0987654321",
        "type": "sms",
        "body": "Test"
    }
    
    # Test success
    response = await provider.send_message(message_data)
    assert response["status"] == "sent"
    assert "provider_message_id" in response
    
    # Test error simulation (if configured)
    # We can patch settings to force errors
    with patch("app.core.config.settings.provider_error_rate", 1.0), \
         patch("app.core.config.settings.provider_429_rate", 1.0):
        
        # Depending on configuration, it might raise ProviderRateLimitError directly or wrapped in RetryError
        with pytest.raises((ProviderRateLimitError, RetryError)):
             await provider.send_message(message_data)

@pytest.mark.asyncio
async def test_sendgrid_provider_send_message():
    """Test SendGrid provider send_message."""
    provider = SendGridProvider()
    
    message_data = {
        "from": "from@example.com",
        "to": "to@example.com",
        "body": "Test"
    }
    
    response = await provider.send_message(message_data)
    assert response["status"] == "sent"
    assert "provider_message_id" in response

@pytest.mark.asyncio
async def test_provider_methods():
    """Test other provider methods."""
    provider = TwilioProvider()
    
    # health check
    assert await provider.health_check() is True
    
    # status
    status = await provider.get_message_status("id")
    assert status["status"] == "delivered"
    
    # webhook
    assert await provider.validate_webhook({}, {}) is True
    
    # process webhook
    result = await provider.process_webhook({"messaging_provider_id": "123", "type": "sms"})
    assert result["provider"] == "twilio"

@pytest.mark.asyncio
async def test_provider_selector():
    """Test ProviderSelector logic."""
    # Ensure providers initialized
    await ProviderFactory.init_providers()
    
    # SMS
    provider = await ProviderSelector.select_provider(MessageType.SMS)
    assert isinstance(provider, TwilioProvider)
    
    # Email
    provider = await ProviderSelector.select_provider(MessageType.EMAIL)
    assert isinstance(provider, SendGridProvider)
