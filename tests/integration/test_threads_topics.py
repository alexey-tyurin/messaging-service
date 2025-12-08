"""
Integration tests for Threads and Topics.
"""

import pytest
from fastapi import status
import uuid

def test_create_topic(client):
    """Test creating a topic conversation."""
    data = {
        "type": "topic",
        "title": "General Discussion",
        "channel_type": "email"
    }
    response = client.post("/api/v1/conversations/", json=data)
    assert response.status_code == status.HTTP_201_CREATED
    r_data = response.json()
    assert r_data["type"] == "topic"
    assert r_data["title"] == "General Discussion"
    return r_data["id"]

def test_create_topic_validation_error(client):
    """Test creating a topic without title should fail."""
    data = {
        "type": "topic",
        "channel_type": "email"
        # Missing title
    }
    response = client.post("/api/v1/conversations/", json=data)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

def test_create_direct_conversation(client):
    """Test creating a direct conversation explicitly."""
    data = {
        "type": "direct",
        "participant_from": "user1@example.com",
        "participant_to": "user2@example.com",
        "channel_type": "email"
    }
    response = client.post("/api/v1/conversations/", json=data)
    assert response.status_code == status.HTTP_201_CREATED
    r_data = response.json()
    assert r_data["type"] == "direct"
    assert r_data["participant_from"] == "user1@example.com"

def test_post_to_topic(client):
    """Test posting a message to a topic."""
    # First create topic
    topic_id = test_create_topic(client)
    
    # Post message using Topic ID as 'to' address
    msg_data = {
        "from": "user@example.com",
        "to": topic_id,
        "type": "email",
        "body": "Hello Topic!"
    }
    response = client.post("/api/v1/messages/send", json=msg_data)
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["conversation_id"] == topic_id
    assert data["to"] == topic_id
    return data

import json

def test_threaded_reply(client):
    """Test replying to a message (threading)."""
    # Create parent message in a topic
    parent_msg = test_post_to_topic(client)
    parent_id = parent_msg["id"]
    topic_id = parent_msg["conversation_id"]
    
    # Reply to that message
    reply_data = {
        "from": "another@example.com",
        "to": topic_id,
        "type": "email",
        "body": "This is a reply to the topic message",
        "parent_id": parent_id
    }
    response = client.post("/api/v1/messages/send", json=reply_data)
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["parent_id"] == parent_id
    assert data["conversation_id"] == topic_id

    # Verify hierarchy via get conversation
    resp = client.get(f"/api/v1/conversations/{topic_id}?include_messages=true")
    assert resp.status_code == status.HTTP_200_OK
    conv_data = resp.json()
    
    print(f"DEBUG: Conversation Data: {json.dumps(conv_data, indent=2)}")
    
    messages = conv_data["messages"]
    
    # Find the reply
    reply_msg = next(m for m in messages if m["id"] == data["id"])
    assert reply_msg["parent_id"] == parent_id

def test_list_conversations_filter_by_type(client):
    """Test filtering conversations by type."""
    # Create topic
    test_create_topic(client)
    # Create direct
    test_create_direct_conversation(client)
    
    # Filter topics
    resp = client.get("/api/v1/conversations/?type=topic")
    assert resp.status_code == status.HTTP_200_OK
    topics = resp.json()["conversations"]
    
    print(f"DEBUG: Topics: {json.dumps(topics, indent=2)}")
    
    assert len(topics) > 0
    assert all(c["type"] == "topic" for c in topics)
    
    # Filter direct
    resp = client.get("/api/v1/conversations/?type=direct")
    assert resp.status_code == status.HTTP_200_OK
    directs = resp.json()["conversations"]
    
    print(f"DEBUG: Directs: {json.dumps(directs, indent=2)}")
    
    assert len(directs) > 0
    assert all(c["type"] == "direct" for c in directs)


def test_invalid_parent_id(client):
    """Test replying to non-existent message."""
    test_create_topic(client)
    
    fake_id = str(uuid.uuid4())
    reply_data = {
        "from": "user@example.com",
        "to": "user2@example.com", # Doesn't matter much if parent check fails first
        "type": "email",
        "body": "Reply to nothing",
        "parent_id": fake_id
    }
    # Should probably be 400 or 422, or 500 if unhandled. 
    # Current implementation raises ValueError which triggers 422 in FastAPI usually if pydantic, 
    # but inside service it raises ValueError. 
    # app/api/v1/messages.py catches ValueError and returns 422.
    response = client.post("/api/v1/messages/send", json=reply_data)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
