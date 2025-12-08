
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime
from uuid import uuid4

from app.models.database import MessageType, ConversationStatus

@pytest.mark.asyncio
async def test_webhook_api(client):
    """Test webhook endpoint."""
    webhook_data = {
        "provider": "twilio",
        "key": "value"
    }
    
    with patch('app.api.v1.webhooks.WebhookService') as mock_service_cls:
        mock_service = AsyncMock()
        mock_service.process_webhook.return_value = {"status": "processed"}
        mock_service_cls.return_value = mock_service
        
        # Test Twilio (XML response)
        response = client.post("/api/v1/webhooks/twilio", json=webhook_data)
        assert response.status_code == 200
        assert "application/xml" in response.headers["content-type"]
        assert "<Response></Response>" in response.text

        # Test SendGrid (JSON response)
        response = client.post("/api/v1/webhooks/sendgrid", json=webhook_data)
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        
        # Test Generic (JSON response)
        response = client.post("/api/v1/webhooks/generic/custom", json=webhook_data)
        assert response.status_code == 200
        assert response.json()["status"] == "ok"



@pytest.mark.asyncio
async def test_conversation_api_list(client):
    """Test list conversations."""
    mock_conv = Mock()
    mock_conv.id = uuid4()
    mock_conv.participant_from = "+123"
    mock_conv.participant_to = "+456"
    mock_conv.channel_type = MessageType.SMS
    mock_conv.status = ConversationStatus.ACTIVE
    mock_conv.title = "Test"
    mock_conv.last_message_at = datetime.utcnow()
    mock_conv.message_count = 1
    mock_conv.unread_count = 0
    mock_conv.created_at = datetime.utcnow()
    mock_conv.updated_at = datetime.utcnow()
    mock_conv.meta_data = {}
    
    with patch('app.api.v1.conversations.ConversationService') as mock_service_cls:
        mock_service = AsyncMock()
        mock_service.list_conversations.return_value = ([mock_conv], 1)
        mock_service_cls.return_value = mock_service
        
        response = client.get("/api/v1/conversations/")
        
        if response.status_code != 200:
            print(response.text)
            
        assert response.status_code == 200
        assert len(response.json()["conversations"]) == 1

@pytest.mark.asyncio
async def test_conversation_api_get(client):
    """Test get conversation."""
    conv_id = uuid4()
    mock_conv = Mock()
    mock_conv.id = conv_id
    mock_conv.participant_from = "+123"
    mock_conv.participant_to = "+456"
    mock_conv.channel_type = MessageType.SMS
    mock_conv.status = ConversationStatus.ACTIVE
    mock_conv.title = "Test"
    mock_conv.last_message_at = datetime.utcnow()
    mock_conv.message_count = 1
    mock_conv.unread_count = 0
    mock_conv.created_at = datetime.utcnow()
    mock_conv.updated_at = datetime.utcnow()
    mock_conv.meta_data = {}
    
    with patch('app.api.v1.conversations.ConversationService') as mock_service_cls:
        mock_service = AsyncMock()
        mock_service.get_conversation.return_value = mock_conv
        mock_service_cls.return_value = mock_service
        
        response = client.get(f"/api/v1/conversations/{conv_id}")
        assert response.status_code == 200
        assert response.json()["id"] == str(conv_id)
