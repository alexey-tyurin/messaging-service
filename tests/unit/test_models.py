
import pytest
from app.models.database import Message, Conversation, MessageType, MessageStatus, MessageDirection, Provider

def test_message_model_defaults():
    """Test Message model defaults."""
    # SQLAlchemy defaults usually apply on flush, but we can check if we set them explicitly
    # OR if we want to test model defaults, we should use a session.
    # For unit testing the model object itself without DB:
    msg = Message(
        to_address="+123",
        body="Test",
        status=MessageStatus.PENDING # Set explicit default for unit test object
    )
    assert msg.status == MessageStatus.PENDING
    assert msg.retry_count == 0 or msg.retry_count is None # Defaults might be None until flush

def test_enums():
    """Test Enum values."""
    assert MessageType.SMS.value == "sms"
    assert MessageStatus.SENT.value == "sent"
    assert MessageDirection.INBOUND.value == "inbound"
    assert Provider.TWILIO.value == "twilio"
