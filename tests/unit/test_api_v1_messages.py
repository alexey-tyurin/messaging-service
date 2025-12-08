
import pytest
from unittest.mock import Mock, AsyncMock, patch
from uuid import uuid4
from datetime import datetime

from app.models.database import MessageStatus, MessageDirection, MessageType

@pytest.mark.asyncio
async def test_api_send_message(client):
    """Test send message endpoint."""
    message_data = {
        "from": "+15551234567",
        "to": "+15559876543",
        "body": "Test API",
        "type": "sms"
    }
    
    mock_message = Mock()
    mock_message.id = uuid4()
    mock_message.conversation_id = uuid4()
    mock_message.provider.value = "twilio"
    mock_message.provider_message_id = "msg_123"
    mock_message.direction = MessageDirection.OUTBOUND
    mock_message.status = MessageStatus.PENDING
    mock_message.message_type = MessageType.SMS
    mock_message.from_address = message_data["from"]
    mock_message.to_address = message_data["to"]
    mock_message.body = message_data["body"]
    mock_message.attachments = []
    mock_message.sent_at = None
    mock_message.delivered_at = None
    mock_message.created_at = datetime.utcnow()
    mock_message.updated_at = datetime.utcnow()
    mock_message.meta_data = {}
    
    with patch('app.api.v1.messages.MessageService') as mock_service_cls:
        mock_service = AsyncMock()
        mock_service.send_message.return_value = mock_message
        mock_service_cls.return_value = mock_service
        
        response = client.post("/api/v1/messages/send", json=message_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["id"] == str(mock_message.id)
        assert data["status"] == "pending"

@pytest.mark.asyncio
async def test_api_get_message(client):
    """Test get message endpoint."""
    msg_id = uuid4()
    mock_message = Mock()
    mock_message.id = msg_id
    mock_message.conversation_id = uuid4()
    mock_message.status = MessageStatus.DELIVERED
    # properties needed for response model
    mock_message.provider.value = "twilio"
    mock_message.provider_message_id = "msg_123"
    mock_message.direction = MessageDirection.OUTBOUND
    mock_message.message_type = MessageType.SMS
    mock_message.from_address = "+123"
    mock_message.to_address = "+456"
    mock_message.body = "Body"
    mock_message.attachments = []
    mock_message.sent_at = None
    mock_message.delivered_at = None
    mock_message.created_at = datetime.utcnow()
    mock_message.updated_at = datetime.utcnow()
    mock_message.meta_data = {}

    with patch('app.api.v1.messages.MessageService') as mock_service_cls:
        mock_service = AsyncMock()
        mock_service.get_message.return_value = mock_message
        mock_service_cls.return_value = mock_service
        
        response = client.get(f"/api/v1/messages/{msg_id}")
        
        assert response.status_code == 200
        assert response.json()["id"] == str(msg_id)

@pytest.mark.asyncio
async def test_api_list_messages(client):
    """Test list messages endpoint."""
    mock_message = Mock()
    mock_message.id = uuid4()
    # Fill required fields...
    mock_message.conversation_id = uuid4()
    mock_message.status = MessageStatus.DELIVERED
    mock_message.provider.value = "twilio"
    mock_message.provider_message_id = "msg_123"
    mock_message.direction = MessageDirection.OUTBOUND
    mock_message.message_type = MessageType.SMS
    mock_message.from_address = "+123"
    mock_message.to_address = "+456"
    mock_message.body = "Body"
    mock_message.attachments = []
    mock_message.sent_at = None
    mock_message.delivered_at = None
    mock_message.created_at = datetime.utcnow()
    mock_message.updated_at = datetime.utcnow()
    mock_message.meta_data = {}
    
    with patch('app.api.v1.messages.MessageService') as mock_service_cls:
        mock_service = AsyncMock()
        mock_service.list_messages.return_value = ([mock_message], 1)
        mock_service_cls.return_value = mock_service
        
        response = client.get("/api/v1/messages/")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["messages"]) == 1

@pytest.mark.asyncio
async def test_api_update_message_status(client):
    """Test update status endpoint."""
    msg_id = uuid4()
    mock_message = Mock()
    mock_message.id = msg_id
    mock_message.status = MessageStatus.DELIVERED
    # ... required fields ...
    mock_message.conversation_id = uuid4()
    mock_message.provider.value = "twilio"
    mock_message.provider_message_id = "msg_123"
    mock_message.direction = MessageDirection.OUTBOUND
    mock_message.message_type = MessageType.SMS
    mock_message.from_address = "+123"
    mock_message.to_address = "+456"
    mock_message.body = "Body"
    mock_message.attachments = []
    mock_message.sent_at = None
    mock_message.delivered_at = None
    mock_message.created_at = datetime.utcnow()
    mock_message.updated_at = datetime.utcnow()
    mock_message.meta_data = {}

    with patch('app.api.v1.messages.MessageService') as mock_service_cls:
        mock_service = AsyncMock()
        mock_service.update_message_status.return_value = True
        mock_service.get_message.return_value = mock_message
        mock_service_cls.return_value = mock_service
        
        response = client.patch(
            f"/api/v1/messages/{msg_id}/status",
            json={"status": "delivered"}
        )
        
        assert response.status_code == 200
        assert response.json()["status"] == "delivered"

@pytest.mark.asyncio
async def test_api_retry_message(client):
    """Test retry message endpoint."""
    msg_id = uuid4()
    mock_message = Mock()
    mock_message.id = msg_id
    mock_message.status = MessageStatus.FAILED # Retryable
    # ... required fields ...
    mock_message.conversation_id = uuid4()
    mock_message.provider.value = "twilio"
    mock_message.provider_message_id = "msg_123"
    mock_message.direction = MessageDirection.OUTBOUND
    mock_message.message_type = MessageType.SMS
    mock_message.from_address = "+123"
    mock_message.to_address = "+456"
    mock_message.body = "Body"
    mock_message.attachments = []
    mock_message.sent_at = None
    mock_message.delivered_at = None
    mock_message.created_at = datetime.utcnow()
    mock_message.updated_at = datetime.utcnow()
    mock_message.meta_data = {}

    with patch('app.api.v1.messages.MessageService') as mock_service_cls:
        mock_service = AsyncMock()
        mock_service.get_message.return_value = mock_message
        mock_service.process_outbound_message.return_value = True
        mock_service_cls.return_value = mock_service
        
        response = client.post(f"/api/v1/messages/{msg_id}/retry")
        
        assert response.status_code == 200
