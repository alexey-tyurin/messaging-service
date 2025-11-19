"""Unit tests for message service."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
from uuid import uuid4

from app.services.message_service import MessageService
from app.models.database import MessageType, MessageDirection, MessageStatus


@pytest.mark.asyncio
async def test_send_message_creates_conversation(async_db, sample_message_data):
    """Test that sending a message creates a conversation."""
    service = MessageService(async_db)
    
    # Send message
    message = await service.send_message(sample_message_data)
    
    # Assert message created
    assert message is not None
    assert message.from_address == sample_message_data["from"]
    assert message.to_address == sample_message_data["to"]
    assert message.body == sample_message_data["body"]
    assert message.direction == MessageDirection.OUTBOUND
    assert message.status == MessageStatus.PENDING
    assert message.message_type == MessageType.SMS
    
    # Assert conversation created
    assert message.conversation_id is not None


@pytest.mark.asyncio
async def test_send_message_validates_data(async_db):
    """Test that send_message validates input data."""
    service = MessageService(async_db)
    
    # Missing required fields
    with pytest.raises(ValueError, match="Missing required field"):
        await service.send_message({})
    
    # Missing body and attachments
    with pytest.raises(ValueError, match="Message must have body or attachments"):
        await service.send_message({
            "from": "+15551234567",
            "to": "+15559876543",
        })


@pytest.mark.asyncio
async def test_determine_message_type(async_db):
    """Test message type determination."""
    service = MessageService(async_db)
    
    # SMS type
    sms_data = {
        "from": "+15551234567",
        "to": "+15559876543",
        "body": "Test",
    }
    assert service._determine_message_type(sms_data) == MessageType.SMS
    
    # Email type
    email_data = {
        "from": "sender@example.com",
        "to": "recipient@example.com",
        "body": "Test",
    }
    assert service._determine_message_type(email_data) == MessageType.EMAIL
    
    # MMS type (with attachments)
    mms_data = {
        "from": "+15551234567",
        "to": "+15559876543",
        "body": "Test",
        "attachments": ["image.jpg"],
    }
    assert service._determine_message_type(mms_data) == MessageType.MMS


@pytest.mark.asyncio
async def test_get_message_returns_none_for_invalid_id(async_db):
    """Test that get_message returns None for invalid ID."""
    service = MessageService(async_db)
    
    message = await service.get_message(str(uuid4()))
    assert message is None


@pytest.mark.asyncio
@patch('app.services.message_service.redis_manager')
async def test_queue_message_for_sending(mock_redis, async_db, sample_message_data):
    """Test that messages are queued properly."""
    mock_redis.enqueue_message = AsyncMock(return_value="msg_123")
    mock_redis.redis_client.xlen = AsyncMock(return_value=5)
    
    service = MessageService(async_db)
    message = await service.send_message(sample_message_data)
    
    # Verify message was queued
    mock_redis.enqueue_message.assert_called_once()
    call_args = mock_redis.enqueue_message.call_args
    assert "message_queue:sms" in call_args[0]


@pytest.mark.asyncio
async def test_process_outbound_message_with_retry(async_db):
    """Test message retry logic."""
    service = MessageService(async_db)
    
    # Create a message with failed status
    message_data = {
        "from": "+15551234567",
        "to": "+15559876543",
        "body": "Test retry",
    }
    message = await service.send_message(message_data)
    
    # Mock provider failure
    with patch('app.services.message_service.ProviderSelector.select_provider') as mock_selector:
        mock_provider = AsyncMock()
        mock_provider.send_message.side_effect = Exception("Provider error")
        mock_selector.return_value = mock_provider
        
        # Process message (should fail and retry)
        result = await service.process_outbound_message(str(message.id))
        
        assert result is False
        
        # Refresh message
        updated_message = await service.get_message(str(message.id))
        assert updated_message.status == MessageStatus.RETRY
        assert updated_message.retry_count == 1


@pytest.mark.asyncio
async def test_receive_message_creates_inbound(async_db):
    """Test receiving inbound messages."""
    service = MessageService(async_db)
    
    webhook_data = {
        "provider": "twilio",
        "provider_message_id": "twilio_123",
        "from": "+15551234567",
        "to": "+15559876543",
        "type": "sms",
        "body": "Inbound message",
        "direction": "inbound",
        "timestamp": datetime.utcnow().isoformat(),
    }
    
    message = await service.receive_message("twilio", webhook_data)
    
    assert message is not None
    assert message.direction == MessageDirection.INBOUND
    assert message.status == MessageStatus.DELIVERED
    assert message.body == "Inbound message"
    assert message.provider_message_id == "twilio_123"


@pytest.mark.asyncio
async def test_receive_duplicate_message(async_db):
    """Test that duplicate messages are not created."""
    service = MessageService(async_db)
    
    webhook_data = {
        "provider": "twilio",
        "provider_message_id": "twilio_duplicate",
        "from": "+15551234567",
        "to": "+15559876543",
        "type": "sms",
        "body": "Duplicate message",
        "direction": "inbound",
        "timestamp": datetime.utcnow().isoformat(),
    }
    
    # Receive first message
    message1 = await service.receive_message("twilio", webhook_data)
    
    # Try to receive duplicate
    message2 = await service.receive_message("twilio", webhook_data)
    
    # Should return the same message
    assert message1.id == message2.id


@pytest.mark.asyncio
async def test_update_message_status(async_db, sample_message_data):
    """Test updating message status."""
    service = MessageService(async_db)
    
    # Create message
    message = await service.send_message(sample_message_data)
    
    # Update status to delivered
    success = await service.update_message_status(
        str(message.id),
        MessageStatus.DELIVERED,
        {"delivered_time": datetime.utcnow().isoformat()}
    )
    
    assert success is True
    
    # Verify status updated
    updated = await service.get_message(str(message.id))
    assert updated.status == MessageStatus.DELIVERED
    assert updated.delivered_at is not None
