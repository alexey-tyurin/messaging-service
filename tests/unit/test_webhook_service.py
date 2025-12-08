
import pytest
from unittest.mock import Mock, AsyncMock, patch
from app.services.webhook_service import WebhookService
from app.models.database import WebhookLog

@pytest.fixture
def service(async_db):
    return WebhookService(async_db)

@pytest.mark.asyncio
async def test_process_webhook_twilio(service):
    """Test processing Twilio webhook."""
    payload = {"MessageStatus": "sent", "MessageSid": "SM123"}
    headers = {"X-Twilio-Signature": "sig"}
    
    with patch('app.services.webhook_service.redis_manager') as mock_redis, \
         patch('app.services.webhook_service.ProviderFactory') as MockFactory, \
         patch('app.services.webhook_service.MessageService') as MockMsgService:
        
        # Setup Redis mock
        mock_redis.exists = AsyncMock(return_value=False)
        mock_redis.set = AsyncMock()
        mock_redis.enqueue_job = AsyncMock()
        
        # Setup Provider mock
        mock_provider = AsyncMock()
        mock_provider.validate_webhook = AsyncMock(return_value=True)
        # return dict with direction/status as expected by _handle_status_update
        mock_provider.process_webhook = AsyncMock(return_value={
            "direction": "outbound",
            "status": "sent",
            "provider_message_id": "SM123"
        })
        MockFactory.get_provider.return_value = mock_provider
        
        # Setup MessageService mock
        mock_msg_svc = AsyncMock()
        mock_msg_svc.update_message_status = AsyncMock()
        MockMsgService.return_value = mock_msg_svc
        
        # We also need to mock DB execution for "select(Message)"
        # But service uses self.db.execute.
        # We can mock execution result.
        mock_result = Mock()
        mock_msg = Mock()
        mock_msg.id = "msg_123"
        mock_result.scalar_one_or_none.return_value = mock_msg
        service.db.execute = AsyncMock(return_value=mock_result)

        result = await service.process_webhook("twilio", headers, payload)
        
        assert result["status"] == "success"

@pytest.mark.asyncio
async def test_process_webhook_sendgrid(service):
    """Test processing SendGrid webhook."""
    payload = {"event": "delivered", "sg_message_id": "msg_123"}
    headers = {}
    
    with patch('app.services.webhook_service.redis_manager') as mock_redis, \
         patch('app.services.webhook_service.ProviderFactory') as MockFactory, \
         patch('app.services.webhook_service.MessageService') as MockMsgService:
        
        mock_redis.exists = AsyncMock(return_value=False)
        mock_redis.set = AsyncMock()
        
        mock_provider = AsyncMock()
        mock_provider.validate_webhook = AsyncMock(return_value=True)
        mock_provider.process_webhook = AsyncMock(return_value={
            "direction": "outbound",
            "status": "delivered",
            "provider_message_id": "msg_123"
        })
        MockFactory.get_provider.return_value = mock_provider
        
        mock_msg_svc = AsyncMock()
        mock_msg_svc.update_message_status = AsyncMock()
        MockMsgService.return_value = mock_msg_svc
        
        mock_result = Mock()
        mock_msg = Mock()
        mock_msg.id = "msg_123"
        mock_result.scalar_one_or_none.return_value = mock_msg
        service.db.execute = AsyncMock(return_value=mock_result)
        
        result = await service.process_webhook("sendgrid", headers, payload)
        assert result["status"] == "success"

@pytest.mark.asyncio
async def test_process_webhook_unknown_provider(service):
    """Test unknown provider name."""
    with pytest.raises(ValueError):
        await service.process_webhook("unknown", {}, {})

@pytest.mark.asyncio
async def test_validate_signature(service):
    """Test signature validation logic (if exposed or implicitly tested)."""
    # Assuming Twilio provider mocked via Factory?
    pass
