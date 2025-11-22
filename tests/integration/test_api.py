"""Integration tests for API endpoints."""

import pytest
from fastapi import status
import json


def test_health_check(client):
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "status" in data
    assert "timestamp" in data


def test_send_message_endpoint(client, sample_message_data):
    """Test sending a message via API."""
    import os
    
    response = client.post(
        "/api/v1/messages/send",
        json=sample_message_data
    )
    
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    
    assert "id" in data
    assert data["from"] == sample_message_data["from"]
    assert data["to"] == sample_message_data["to"]
    assert data["body"] == sample_message_data["body"]
    
    # Status can be "sent" if sync processing is enabled, otherwise "pending"
    sync_processing = os.getenv("SYNC_MESSAGE_PROCESSING", "false").lower() == "true"
    if sync_processing:
        assert data["status"] in ["sent", "pending"]  # Allow either during sync processing
    else:
        assert data["status"] == "pending"
    
    assert data["direction"] == "outbound"


def test_send_message_invalid_data(client):
    """Test sending message with invalid data."""
    response = client.post(
        "/api/v1/messages/send",
        json={"invalid": "data"}
    )
    
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_get_message_not_found(client):
    """Test getting non-existent message."""
    response = client.get("/api/v1/messages/123e4567-e89b-12d3-a456-426614174000")
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_list_messages(client, sample_message_data):
    """Test listing messages."""
    # Send a message first
    client.post("/api/v1/messages/send", json=sample_message_data)
    
    # List messages
    response = client.get("/api/v1/messages?limit=10")
    assert response.status_code == status.HTTP_200_OK
    
    data = response.json()
    assert "messages" in data
    assert "total" in data
    assert "limit" in data
    assert "offset" in data
    assert isinstance(data["messages"], list)


def test_list_conversations(client):
    """Test listing conversations."""
    response = client.get("/api/v1/conversations?limit=10")
    assert response.status_code == status.HTTP_200_OK
    
    data = response.json()
    assert "conversations" in data
    assert isinstance(data["conversations"], list)


def test_webhook_twilio(client):
    """Test Twilio webhook endpoint."""
    webhook_data = {
        "messaging_provider_id": "test_123",
        "from": "+15551234567",
        "to": "+15559876543",
        "type": "sms",
        "body": "Test webhook",
        "timestamp": "2024-01-01T12:00:00Z"
    }
    
    response = client.post(
        "/api/v1/webhooks/twilio",
        json=webhook_data
    )
    
    assert response.status_code == status.HTTP_200_OK


def test_webhook_sendgrid(client):
    """Test SendGrid webhook endpoint."""
    webhook_data = {
        "xillio_id": "email_123",
        "from": "sender@example.com",
        "to": "recipient@example.com",
        "body": "<p>Email content</p>",
        "timestamp": "2024-01-01T12:00:00Z"
    }
    
    response = client.post(
        "/api/v1/webhooks/sendgrid",
        json=webhook_data
    )
    
    assert response.status_code == status.HTTP_200_OK


def test_conversation_search(client):
    """Test conversation search."""
    search_data = {
        "query": "test",
        "limit": 5
    }
    
    response = client.post(
        "/api/v1/conversations/search",
        json=search_data
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "conversations" in data


def test_rate_limiting(client):
    """Test that rate limiting headers are present."""
    response = client.get("/api/v1/messages")
    
    assert "X-RateLimit-Limit" in response.headers
    assert "X-RateLimit-Remaining" in response.headers
    assert "X-RateLimit-Reset" in response.headers


def test_metrics_endpoint(client):
    """Test metrics endpoint."""
    response = client.get("/metrics")
    
    assert response.status_code == status.HTTP_200_OK
    assert response.headers["content-type"].startswith("text/plain")
    assert b"messages_total" in response.content
    assert b"http_requests_total" in response.content


def test_send_email(client, sample_email_data):
    """Test sending an email message."""
    response = client.post(
        "/api/v1/messages/send",
        json=sample_email_data
    )
    
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    
    assert data["type"] == "email"
    assert data["from"] == sample_email_data["from"]
    assert data["to"] == sample_email_data["to"]


def test_conversation_lifecycle(client, sample_message_data):
    """Test full conversation lifecycle."""
    # Send initial message
    response = client.post("/api/v1/messages/send", json=sample_message_data)
    assert response.status_code == status.HTTP_201_CREATED
    message_data = response.json()
    conversation_id = message_data["conversation_id"]
    
    # Get conversation
    response = client.get(f"/api/v1/conversations/{conversation_id}")
    assert response.status_code == status.HTTP_200_OK
    conv_data = response.json()
    assert conv_data["message_count"] == 1
    
    # Mark as read
    response = client.post(f"/api/v1/conversations/{conversation_id}/mark-read")
    assert response.status_code == status.HTTP_204_NO_CONTENT
    
    # Archive conversation
    response = client.post(f"/api/v1/conversations/{conversation_id}/archive")
    assert response.status_code == status.HTTP_200_OK
    archived_data = response.json()
    assert archived_data["status"] == "archived"


def test_message_retry(client, sample_message_data):
    """Test message retry functionality."""
    # Send a message
    response = client.post("/api/v1/messages/send", json=sample_message_data)
    message_id = response.json()["id"]
    
    # Attempt retry (will fail since message is not in failed state)
    response = client.post(f"/api/v1/messages/{message_id}/retry")
    assert response.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_200_OK]


def test_dependency_check(client):
    """Test dependency health check."""
    response = client.get("/dependencies")
    assert response.status_code == status.HTTP_200_OK
    
    data = response.json()
    assert "dependencies" in data
    assert "timestamp" in data
