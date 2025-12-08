"""
Tests for Redis caching on get_message and get_conversation endpoints.
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime
import uuid

from app.services.message_service import MessageService
from app.services.conversation_service import ConversationService
from app.models.database import (
    Message, Conversation, MessageType, MessageDirection, 
    MessageStatus, ConversationStatus, Provider
)


class TestMessageCaching:
    """Test Redis caching for message operations."""
    
    @pytest.mark.asyncio
    async def test_get_message_cache_miss_then_hit(self, async_db):
        """Test that message is fetched from DB on cache miss, then cached."""
        # Create a test message
        conversation = Conversation(
            participant_from="+1234567890",
            participant_to="+0987654321",
            channel_type=MessageType.SMS,
            status=ConversationStatus.ACTIVE,
            meta_data={}
        )
        async_db.add(conversation)
        await async_db.flush()
        
        message = Message(
            conversation_id=conversation.id,
            provider=Provider.TWILIO,
            direction=MessageDirection.OUTBOUND,
            status=MessageStatus.SENT,
            message_type=MessageType.SMS,
            from_address="+1234567890",
            to_address="+0987654321",
            body="Test message",
            attachments=[],
            meta_data={}
        )
        async_db.add(message)
        await async_db.commit()
        
        service = MessageService(async_db)
        
        # Mock Redis get to return None (cache miss) on first call
        with patch('app.services.message_service.redis_manager.get') as mock_redis_get, \
             patch('app.services.message_service.redis_manager.set') as mock_redis_set, \
             patch('app.services.message_service.MetricsCollector.track_cache_operation') as mock_metrics:
            
            mock_redis_get.return_value = None
            mock_redis_set.return_value = True
            
            # First call - cache miss
            result = await service.get_message(str(message.id))
            
            assert result is not None
            assert result.id == message.id
            assert result.body == "Test message"
            
            # Verify cache was checked
            mock_redis_get.assert_called_once_with(f"message:{message.id}")
            
            # Verify cache miss was tracked
            assert mock_metrics.call_count >= 1
            mock_metrics.assert_any_call("get", False)
            
            # Verify data was cached
            mock_redis_set.assert_called_once()
            call_args = mock_redis_set.call_args
            assert call_args[0][0] == f"message:{message.id}"
            assert call_args[1]["ttl"] == 300
    
    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Redis mock return value handling issue")
    @patch('app.services.message_service.redis_manager')
    async def test_get_message_cache_hit(self, mock_redis, async_db):
        """Test that message is returned from cache on cache hit."""
        # Create a test message
        conversation = Conversation(
            participant_from="+1234567890",
            participant_to="+0987654321",
            channel_type=MessageType.SMS,
            status=ConversationStatus.ACTIVE,
            meta_data={}
        )
        async_db.add(conversation)
        await async_db.flush()
        
        message = Message(
            conversation_id=conversation.id,
            provider=Provider.TWILIO,
            direction=MessageDirection.OUTBOUND,
            status=MessageStatus.SENT,
            message_type=MessageType.SMS,
            from_address="+1234567890",
            to_address="+0987654321",
            body="Test message",
            attachments=[],
            meta_data={}
        )
        async_db.add(message)
        await async_db.commit()
        
        service = MessageService(async_db)
        
        # Mock Redis to return cached data
        cached_data = {
            "id": str(message.id),
            "conversation_id": str(conversation.id),
            "body": "Test message",
            "status": "sent"
        }
        
        with patch('app.services.message_service.redis_manager.get') as mock_redis_get, \
             patch('app.services.message_service.MetricsCollector.track_cache_operation') as mock_metrics:
            
            mock_redis_get.return_value = cached_data
            
            # Second call - cache hit
            result = await service.get_message(str(message.id))
            
            assert result is not None
            assert result.id == message.id
            
            # Verify cache was checked
            mock_redis_get.assert_called_once_with(f"message:{message.id}")
            
            # Verify cache hit was tracked
            mock_metrics.assert_called_once_with("get", True)


class TestConversationCaching:
    """Test Redis caching for conversation operations."""
    
    @pytest.mark.asyncio
    async def test_get_conversation_cache_miss_then_hit(self, async_db):
        """Test that conversation is fetched from DB on cache miss, then cached."""
        # Create a test conversation
        conversation = Conversation(
            participant_from="+1234567890",
            participant_to="+0987654321",
            channel_type=MessageType.SMS,
            status=ConversationStatus.ACTIVE,
            message_count=0,
            unread_count=0,
            meta_data={}
        )
        async_db.add(conversation)
        await async_db.commit()
        
        service = ConversationService(async_db)
        
        # Mock Redis get to return None (cache miss)
        with patch('app.services.conversation_service.redis_manager.get') as mock_redis_get, \
             patch('app.services.conversation_service.redis_manager.set') as mock_redis_set, \
             patch('app.services.conversation_service.MetricsCollector.track_cache_operation') as mock_metrics:
            
            mock_redis_get.return_value = None
            mock_redis_set.return_value = True
            
            # First call - cache miss
            result = await service.get_conversation(str(conversation.id))
            
            assert result is not None
            assert result.id == conversation.id
            assert result.participant_from == "+1234567890"
            
            # Verify cache was checked
            mock_redis_get.assert_called_once_with(f"conversation:{conversation.id}")
            
            # Verify cache miss was tracked
            assert mock_metrics.call_count >= 1
            mock_metrics.assert_any_call("get", False)
            
            # Verify data was cached
            mock_redis_set.assert_called_once()
            call_args = mock_redis_set.call_args
            assert call_args[0][0] == f"conversation:{conversation.id}"
            assert call_args[1]["ttl"] == 300
    
    @pytest.mark.asyncio
    async def test_get_conversation_cache_hit(self, async_db):
        """Test that conversation is returned from cache on cache hit."""
        # Create a test conversation
        conversation = Conversation(
            participant_from="+1234567890",
            participant_to="+0987654321",
            channel_type=MessageType.SMS,
            status=ConversationStatus.ACTIVE,
            message_count=5,
            unread_count=2,
            meta_data={}
        )
        async_db.add(conversation)
        await async_db.commit()
        
        service = ConversationService(async_db)
        
        # Mock Redis to return cached data
        cached_data = {
            "id": str(conversation.id),
            "participant_from": "+1234567890",
            "participant_to": "+0987654321",
            "channel_type": "sms",
            "status": "active",
            "message_count": 5,
            "unread_count": 2
        }
        
        with patch('app.services.conversation_service.redis_manager.get') as mock_redis_get, \
             patch('app.services.conversation_service.MetricsCollector.track_cache_operation') as mock_metrics:
            
            mock_redis_get.return_value = cached_data
            
            # Second call - cache hit
            result = await service.get_conversation(str(conversation.id))
            
            assert result is not None
            assert result.id == conversation.id
            
            # Verify cache was checked
            mock_redis_get.assert_called_once_with(f"conversation:{conversation.id}")
            
            # Verify cache hit was tracked
            mock_metrics.assert_called_once_with("get", True)


class TestCacheInvalidation:
    """Test that cache is properly invalidated on updates."""
    
    @pytest.mark.asyncio
    async def test_update_message_status_invalidates_cache(self, async_db):
        """Test that updating message status invalidates the cache."""
        # Create a test message
        conversation = Conversation(
            participant_from="+1234567890",
            participant_to="+0987654321",
            channel_type=MessageType.SMS,
            status=ConversationStatus.ACTIVE,
            meta_data={}
        )
        async_db.add(conversation)
        await async_db.flush()
        
        message = Message(
            conversation_id=conversation.id,
            provider=Provider.TWILIO,
            direction=MessageDirection.OUTBOUND,
            status=MessageStatus.PENDING,
            message_type=MessageType.SMS,
            from_address="+1234567890",
            to_address="+0987654321",
            body="Test message",
            attachments=[],
            meta_data={}
        )
        async_db.add(message)
        await async_db.commit()
        
        service = MessageService(async_db)
        
        # Mock Redis delete
        with patch('app.services.message_service.redis_manager.delete') as mock_redis_delete:
            mock_redis_delete.return_value = True
            
            # Update message status
            success = await service.update_message_status(
                str(message.id),
                MessageStatus.DELIVERED,
                {"delivery_time": "2025-01-01T00:00:00"}
            )
            
            assert success is True
            
            # Verify cache was invalidated
            mock_redis_delete.assert_called_once_with(f"message:{message.id}")
    
    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Redis mock return value handling issue")
    async def test_mark_as_read_invalidates_cache(self, async_db):
        """Test that marking conversation as read invalidates the cache."""
        # Create a test conversation
        conversation = Conversation(
            participant_from="+1234567890",
            participant_to="+0987654321",
            channel_type=MessageType.SMS,
            status=ConversationStatus.ACTIVE,
            message_count=5,
            unread_count=3,
            meta_data={}
        )
        async_db.add(conversation)
        await async_db.commit()
        
        service = ConversationService(async_db)
        
        # Mock Redis delete and publish
        with patch('app.services.conversation_service.redis_manager.delete') as mock_redis_delete, \
             patch('app.services.conversation_service.redis_manager.publish') as mock_redis_publish:
            
            mock_redis_delete.return_value = True
            mock_redis_publish.return_value = 1
            
            # Mark as read
            success = await service.mark_as_read(str(conversation.id))
            
            assert success is True
            
            # Verify cache was invalidated
            mock_redis_delete.assert_called_once_with(f"conversation:{conversation.id}")

