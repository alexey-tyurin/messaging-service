"""
Database models for the messaging service.
Defines the core entities: Conversation, Message, MessageEvent, and related models.
"""

from sqlalchemy import (
    Column, String, DateTime, ForeignKey, Text, JSON, Enum, Index, 
    UniqueConstraint, CheckConstraint, Boolean, Integer, Float
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func
import enum
import uuid


Base = declarative_base()


class MessageType(str, enum.Enum):
    """Enumeration of message types."""
    SMS = "sms"
    MMS = "mms"
    EMAIL = "email"
    VOICE_CALL = "voice_call"
    VOICEMAIL = "voicemail"


class MessageDirection(str, enum.Enum):
    """Message direction enumeration."""
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class MessageStatus(str, enum.Enum):
    """Message status enumeration."""
    PENDING = "pending"
    QUEUED = "queued"
    SENDING = "sending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRY = "retry"


class ConversationStatus(str, enum.Enum):
    """Conversation status enumeration."""
    ACTIVE = "active"
    ARCHIVED = "archived"
    CLOSED = "closed"


class EventType(str, enum.Enum):
    """Message event types."""
    CREATED = "created"
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRY = "retry"
    WEBHOOK_RECEIVED = "webhook_received"


class Provider(str, enum.Enum):
    """Message provider enumeration."""
    TWILIO = "twilio"
    SENDGRID = "sendgrid"
    INTERNAL = "internal"
    MOCK = "mock"


class Conversation(Base):
    """
    Conversation model representing a thread of messages between participants.
    """
    __tablename__ = "conversations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    participant_from = Column(String(255), nullable=False, index=True)
    participant_to = Column(String(255), nullable=False, index=True)
    channel_type = Column(Enum(MessageType), nullable=False, index=True)
    status = Column(
        Enum(ConversationStatus), 
        default=ConversationStatus.ACTIVE,
        nullable=False,
        index=True
    )
    
    # Conversation metadata
    title = Column(String(255))
    last_message_at = Column(DateTime(timezone=True), index=True)
    message_count = Column(Integer, default=0)
    unread_count = Column(Integer, default=0)
    
    # JSON metadata for extensibility
    metadata = Column(JSON, default={})
    
    # Timestamps
    created_at = Column(
        DateTime(timezone=True), 
        server_default=func.now(),
        nullable=False,
        index=True
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
    
    # Relationships
    messages = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at"
    )
    
    # Indexes
    __table_args__ = (
        Index(
            "idx_conversation_participants",
            "participant_from",
            "participant_to",
            "channel_type"
        ),
        Index("idx_conversation_updated", "updated_at"),
        Index("idx_conversation_last_message", "last_message_at"),
        UniqueConstraint(
            "participant_from",
            "participant_to", 
            "channel_type",
            name="uq_conversation_participants"
        ),
    )
    
    def __repr__(self):
        return f"<Conversation(id={self.id}, from={self.participant_from}, to={self.participant_to})>"


class Message(Base):
    """
    Message model representing individual messages within conversations.
    """
    __tablename__ = "messages"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Provider information
    provider = Column(Enum(Provider), nullable=False, index=True)
    provider_message_id = Column(String(255), index=True)
    
    # Message details
    direction = Column(Enum(MessageDirection), nullable=False, index=True)
    status = Column(
        Enum(MessageStatus),
        default=MessageStatus.PENDING,
        nullable=False,
        index=True
    )
    message_type = Column(Enum(MessageType), nullable=False, index=True)
    
    # Content
    body = Column(Text)
    attachments = Column(JSON, default=[])
    
    # Participant information (denormalized for query performance)
    from_address = Column(String(255), nullable=False, index=True)
    to_address = Column(String(255), nullable=False, index=True)
    
    # Retry information
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    retry_after = Column(DateTime(timezone=True))
    
    # Tracking
    sent_at = Column(DateTime(timezone=True), index=True)
    delivered_at = Column(DateTime(timezone=True))
    failed_at = Column(DateTime(timezone=True))
    error_message = Column(Text)
    
    # Metadata
    metadata = Column(JSON, default={})
    headers = Column(JSON, default={})
    
    # Cost tracking (for future billing features)
    cost = Column(Float, default=0.0)
    
    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
    
    # Relationships
    conversation = relationship("Conversation", back_populates="messages")
    events = relationship(
        "MessageEvent",
        back_populates="message",
        cascade="all, delete-orphan",
        order_by="MessageEvent.created_at"
    )
    
    # Indexes
    __table_args__ = (
        Index("idx_message_conversation_created", "conversation_id", "created_at"),
        Index("idx_message_status_created", "status", "created_at"),
        Index("idx_message_provider_status", "provider", "status"),
        Index("idx_message_direction_type", "direction", "message_type"),
        UniqueConstraint(
            "provider",
            "provider_message_id",
            name="uq_provider_message"
        ),
        CheckConstraint("retry_count >= 0", name="check_retry_count_positive"),
    )
    
    def __repr__(self):
        return f"<Message(id={self.id}, type={self.message_type}, status={self.status})>"


class MessageEvent(Base):
    """
    Event sourcing table for message lifecycle events.
    """
    __tablename__ = "message_events"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id = Column(
        UUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    event_type = Column(Enum(EventType), nullable=False, index=True)
    event_data = Column(JSON, default={})
    
    # Provider tracking
    provider = Column(Enum(Provider))
    provider_event_id = Column(String(255))
    provider_timestamp = Column(DateTime(timezone=True))
    
    # Event metadata
    metadata = Column(JSON, default={})
    error_message = Column(Text)
    
    # Timestamp
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True
    )
    
    # Relationships
    message = relationship("Message", back_populates="events")
    
    # Indexes
    __table_args__ = (
        Index("idx_event_message_created", "message_id", "created_at"),
        Index("idx_event_type_created", "event_type", "created_at"),
        Index("idx_event_provider", "provider", "provider_event_id"),
    )
    
    def __repr__(self):
        return f"<MessageEvent(id={self.id}, type={self.event_type}, message_id={self.message_id})>"


class WebhookLog(Base):
    """
    Log table for incoming webhooks from providers.
    """
    __tablename__ = "webhook_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider = Column(Enum(Provider), nullable=False, index=True)
    webhook_id = Column(String(255), index=True)
    
    # Request information
    endpoint = Column(String(255))
    method = Column(String(10))
    headers = Column(JSON)
    body = Column(JSON)
    
    # Processing information
    processed = Column(Boolean, default=False, index=True)
    processed_at = Column(DateTime(timezone=True))
    error_message = Column(Text)
    
    # Timestamp
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True
    )
    
    # Indexes
    __table_args__ = (
        Index("idx_webhook_provider_created", "provider", "created_at"),
        Index("idx_webhook_processed", "processed", "created_at"),
    )
    
    def __repr__(self):
        return f"<WebhookLog(id={self.id}, provider={self.provider}, processed={self.processed})>"


class AttachmentMetadata(Base):
    """
    Store metadata for message attachments (for future media handling).
    """
    __tablename__ = "attachment_metadata"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id = Column(
        UUID(as_uuid=True),
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # File information
    file_name = Column(String(255))
    file_type = Column(String(100))
    file_size = Column(Integer)
    file_url = Column(Text)
    
    # Storage information
    storage_provider = Column(String(50))
    storage_key = Column(String(500))
    
    # Security
    scanned = Column(Boolean, default=False)
    scan_result = Column(JSON)
    
    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    expires_at = Column(DateTime(timezone=True))
    
    def __repr__(self):
        return f"<AttachmentMetadata(id={self.id}, file_name={self.file_name})>"


class RateLimitEntry(Base):
    """
    Track rate limiting per client/endpoint.
    """
    __tablename__ = "rate_limits"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(String(255), nullable=False, index=True)
    endpoint = Column(String(255), nullable=False, index=True)
    
    # Rate limit tracking
    request_count = Column(Integer, default=1)
    window_start = Column(DateTime(timezone=True), nullable=False)
    window_end = Column(DateTime(timezone=True), nullable=False)
    
    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
    
    # Indexes
    __table_args__ = (
        Index("idx_rate_limit_client_endpoint", "client_id", "endpoint"),
        Index("idx_rate_limit_window", "window_end"),
        UniqueConstraint(
            "client_id",
            "endpoint",
            "window_start",
            name="uq_rate_limit_window"
        ),
    )
    
    def __repr__(self):
        return f"<RateLimitEntry(client={self.client_id}, endpoint={self.endpoint})>"
