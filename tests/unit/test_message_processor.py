
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta

from app.workers.message_processor import MessageProcessor
from app.models.database import Message, MessageStatus

@pytest.fixture
def message_processor():
    return MessageProcessor()

@pytest.mark.asyncio
async def test_process_sms_queue(message_processor):
    """Test processing SMS queue."""
    
    # Mock redis_manager
    with patch('app.workers.message_processor.redis_manager') as mock_redis:
        mock_redis.dequeue_messages = AsyncMock(side_effect=[
            [{"message_id": "msg_123"}], # First batch
            [], # Empty batch (to simulate end of queue)
        ])
        mock_redis.redis_client.xlen = AsyncMock(return_value=0)
        
        # Mock _process_message
        message_processor._process_message = AsyncMock()
        
        # Mock running state to run only once or twice
        # We can control the loop by mocking running property or just raising exception to stop
        # Or simpler: run the logic inside the loop manually or mock `settings.queue_batch_size`?
        # The loop condition is `while self.running`.
        # We can set side_effect of mock_redis.dequeue_messages to eventually raise specific exception 
        # that we catch, OR we can start the task and cancel it.
        
        # But for unit testing the logic, we can also extract the loop body or just inject a way to break the loop.
        # Let's mock `asyncio.sleep` to stop the loop by raising CancelledError or something custom.
        
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            mock_sleep.side_effect = [None, Exception("StopLoop")]
            
            message_processor.running = True
            
            try:
                await message_processor.process_sms_queue()
            except Exception as e:
                if str(e) != "StopLoop":
                    raise
            
            # Verify processed
            message_processor._process_message.assert_called_with({"message_id": "msg_123"})
            mock_redis.dequeue_messages.assert_called()


@pytest.mark.asyncio
async def test_process_retry_queue(message_processor):
    """Test processing retry queue."""
    
    with patch('app.workers.message_processor.db_manager') as mock_db_manager, \
         patch('app.workers.message_processor.MessageService') as mock_service_cls:
        
        # Mock DB session context
        mock_db = AsyncMock()
        # Async context manager mock
        mock_db_manager.session_context.return_value.__aenter__.return_value = mock_db
        
        # Mock DB execute result
        mock_message = Mock()
        mock_message.id = "msg_retry_1"
        
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = [mock_message]
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        # Mock service
        mock_service = AsyncMock()
        mock_service_cls.return_value = mock_service
        
        # Mock sleep to stop loop
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            mock_sleep.side_effect = Exception("StopLoop")
            
            message_processor.running = True
            
            try:
                await message_processor.process_retry_queue()
            except Exception as e:
                if str(e) != "StopLoop":
                    raise
        
        # Verify
        mock_service_cls.assert_called_with(mock_db)
        mock_service.process_outbound_message.assert_called_with("msg_retry_1")


@pytest.mark.asyncio
async def test_process_message_success(message_processor):
    """Test successful message processing logic."""
    
    with patch('app.workers.message_processor.db_manager') as mock_db_manager, \
         patch('app.workers.message_processor.MessageService') as mock_service_cls:
        
        mock_db = AsyncMock()
        mock_db_manager.session_context.return_value.__aenter__.return_value = mock_db
        
        mock_service = AsyncMock()
        mock_service.process_outbound_message.return_value = True
        mock_service_cls.return_value = mock_service
        
        msg_data = {"message_id": "msg_123"}
        
        await message_processor._process_message(msg_data)
        
        mock_service.process_outbound_message.assert_called_once_with("msg_123")


@pytest.mark.asyncio
async def test_process_message_missing_id(message_processor):
    """Test validation of missing message ID."""
    
    with patch('app.workers.message_processor.db_manager') as mock_db_manager:
        # Should verify it logs error and returns
        with patch('app.workers.message_processor.logger') as mock_logger:
            await message_processor._process_message({})
            
            mock_logger.error.assert_called_with("Message ID not found in queue data")

@pytest.mark.asyncio
async def test_process_message_exception(message_processor):
    """Test exception handling during processing."""
    
    with patch('app.workers.message_processor.db_manager') as mock_db_manager:
        mock_db_manager.session_context.side_effect = Exception("DB Error")
        
        with patch('app.workers.message_processor.logger') as mock_logger:
            await message_processor._process_message({"message_id": "bad"})
            
            # verify logger.error called
            assert mock_logger.error.call_count == 1
            assert "Error processing message" in mock_logger.error.call_args[0][0]

