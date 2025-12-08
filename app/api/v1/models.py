"""
Pydantic models for API requests and responses.
"""

from pydantic import BaseModel, Field, EmailStr, validator, model_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
import re
from enum import Enum


class MessageType(str, Enum):
    """Message type enumeration."""
    SMS = "sms"
    MMS = "mms"
    EMAIL = "email"


class MessageDirection(str, Enum):
    """Message direction enumeration."""
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class MessageStatus(str, Enum):
    """Message status enumeration."""
    PENDING = "pending"
    QUEUED = "queued"
    SENDING = "sending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRY = "retry"


class ConversationStatus(str, Enum):
    """Conversation status enumeration."""
    ACTIVE = "active"
    ARCHIVED = "archived"
    CLOSED = "closed"


class SendMessageRequest(BaseModel):
    """Request model for sending a message."""
    from_: str = Field(..., alias="from", description="Sender address")
    to: str = Field(..., description="Recipient address")
    type: MessageType = Field(..., description="Message type")
    body: Optional[str] = Field(None, description="Message body")
    attachments: Optional[List[str]] = Field(default=[], description="List of attachment URLs")
    metadata: Optional[Dict[str, Any]] = Field(default={}, description="Additional metadata")
    
    @validator("body", "attachments")
    def validate_content(cls, v, values):
        """Ensure message has either body or attachments."""
        if not v and not values.get("attachments"):
            if "body" not in values or not values["body"]:
                raise ValueError("Message must have either body or attachments")
        return v

    @model_validator(mode='before')
    @classmethod
    def validate_addresses(cls, values: Any) -> Any:
        """Validate sender and recipient addresses based on message type."""
        if not isinstance(values, dict):
            return values
            
        msg_type = values.get("type")
        to_addr = values.get("to")
        from_addr = values.get("from")
        
        # If type is missing, basic Pydantic validation will catch it later, 
        # but we can't strict validate format without knowing type.
        if not msg_type:
            return values

        # E.164-ish phone number: + followed by 1-15 digits.
        phone_pattern = re.compile(r"^\+?[1-9]\d{1,14}$")
        # Simple email check
        email_pattern = re.compile(r"^[^@]+@[^@]+\.[^@]+$")

        # Check for string "sms" or enum value
        is_sms_mms = False
        # Handle both raw string and Enum
        type_str = getattr(msg_type, "value", msg_type) if hasattr(msg_type, "value") else str(msg_type)
        
        if type_str in ["sms", "mms"]:
            is_sms_mms = True
        elif type_str == "email":
            if to_addr and not email_pattern.match(to_addr):
                raise ValueError("Recipient must be a valid email address")
            if from_addr and not email_pattern.match(from_addr):
                raise ValueError("Sender must be a valid email address")

        if is_sms_mms:
             if to_addr and not phone_pattern.match(to_addr):
                 raise ValueError("Recipient must be a valid phone number for SMS/MMS")
             if from_addr and not phone_pattern.match(from_addr):
                 raise ValueError("Sender must be a valid phone number for SMS/MMS")
        
        return values
    
    class Config:
        populate_by_name = True


class MessageResponse(BaseModel):
    """Response model for a message."""
    id: str = Field(..., description="Message ID")
    conversation_id: str = Field(..., description="Conversation ID")
    provider: Optional[str] = Field(None, description="Provider used")
    provider_message_id: Optional[str] = Field(None, description="Provider's message ID")
    direction: MessageDirection = Field(..., description="Message direction")
    status: MessageStatus = Field(..., description="Message status")
    message_type: MessageType = Field(..., alias="type", description="Message type")
    from_: str = Field(..., alias="from", description="Sender address")
    to: str = Field(..., description="Recipient address")
    body: Optional[str] = Field(None, description="Message body")
    attachments: List[str] = Field(default=[], description="Attachment URLs")
    sent_at: Optional[datetime] = Field(None, description="When message was sent")
    delivered_at: Optional[datetime] = Field(None, description="When message was delivered")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    metadata: Dict[str, Any] = Field(default={}, description="Additional metadata")
    
    class Config:
        populate_by_name = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class ConversationResponse(BaseModel):
    """Response model for a conversation."""
    id: str = Field(..., description="Conversation ID")
    participant_from: str = Field(..., description="From participant")
    participant_to: str = Field(..., description="To participant")
    channel_type: MessageType = Field(..., description="Channel type")
    status: ConversationStatus = Field(..., description="Conversation status")
    title: Optional[str] = Field(None, description="Conversation title")
    last_message_at: Optional[datetime] = Field(None, description="Last message timestamp")
    message_count: int = Field(0, description="Total message count")
    unread_count: int = Field(0, description="Unread message count")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    metadata: Dict[str, Any] = Field(default={}, description="Additional metadata")
    messages: Optional[List[MessageResponse]] = Field(None, description="Messages in conversation")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class ConversationUpdateRequest(BaseModel):
    """Request model for updating a conversation."""
    title: Optional[str] = Field(None, description="Conversation title")
    status: Optional[ConversationStatus] = Field(None, description="Conversation status")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class WebhookRequest(BaseModel):
    """Request model for incoming webhooks."""
    provider: str = Field(..., description="Provider name")
    data: Dict[str, Any] = Field(..., description="Webhook data")
    headers: Optional[Dict[str, str]] = Field(default={}, description="Webhook headers")


class ErrorResponse(BaseModel):
    """Response model for errors."""
    error: str = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")


class HealthResponse(BaseModel):
    """Response model for health check."""
    status: str = Field(..., description="Health status")
    timestamp: datetime = Field(..., description="Check timestamp")
    checks: Dict[str, Dict[str, Any]] = Field(..., description="Individual check results")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class PaginationParams(BaseModel):
    """Pagination parameters."""
    limit: int = Field(50, ge=1, le=100, description="Number of items to return")
    offset: int = Field(0, ge=0, description="Number of items to skip")


class MessageListResponse(BaseModel):
    """Response model for message list."""
    messages: List[MessageResponse] = Field(..., description="List of messages")
    total: int = Field(..., description="Total number of messages")
    limit: int = Field(..., description="Current limit")
    offset: int = Field(..., description="Current offset")


class ConversationListResponse(BaseModel):
    """Response model for conversation list."""
    conversations: List[ConversationResponse] = Field(..., description="List of conversations")
    total: int = Field(..., description="Total number of conversations")
    limit: int = Field(..., description="Current limit")
    offset: int = Field(..., description="Current offset")


class ConversationSearchRequest(BaseModel):
    """Request model for searching conversations."""
    query: str = Field(..., min_length=1, description="Search query")
    limit: int = Field(20, ge=1, le=50, description="Maximum results")


class ConversationStatisticsResponse(BaseModel):
    """Response model for conversation statistics."""
    conversation_id: str = Field(..., description="Conversation ID")
    total_messages: int = Field(..., description="Total message count")
    inbound_messages: int = Field(..., description="Inbound message count")
    outbound_messages: int = Field(..., description="Outbound message count")
    failed_messages: int = Field(..., description="Failed message count")
    avg_send_time_seconds: float = Field(..., description="Average send time in seconds")


class MessageStatusUpdateRequest(BaseModel):
    """Request model for updating message status."""
    status: MessageStatus = Field(..., description="New status")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
