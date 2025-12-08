"""
Integration tests for 1:1 Threads.
"""

import pytest
from fastapi import status
import uuid
import json

def test_start_thread_via_message(client):
    """Test starting a thread by sending a message with conversation_type=THREAD."""
    msg_data = {
        "from": "user1@example.com",
        "to": "user2@example.com",
        "type": "email",
        "body": "Starting a new thread",
        "conversation_type": "thread"
    }
    response = client.post("/api/v1/messages/send", json=msg_data)
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    
    assert data["type"] == "email"
    conversation_id = data["conversation_id"]
    assert conversation_id is not None
    
    # Verify conversation type
    conv_resp = client.get(f"/api/v1/conversations/{conversation_id}")
    assert conv_resp.status_code == status.HTTP_200_OK
    conv_data = conv_resp.json()
    assert conv_data["type"] == "thread"
    assert conv_data["participant_from"] == "user1@example.com"
    assert conv_data["participant_to"] == "user2@example.com"
    
    return data

def test_threaded_reply_flow(client):
    """Test full thread flow: Start -> Reply -> Reply back."""
    # 1. Start Thread
    start_msg_data = {
        "from": "alice@example.com",
        "to": "bob@example.com",
        "type": "email",
        "body": "Thread root",
        "conversation_type": "thread"
    }
    resp1 = client.post("/api/v1/messages/send", json=start_msg_data)
    assert resp1.status_code == status.HTTP_201_CREATED
    msg1 = resp1.json()
    thread_id = msg1["conversation_id"]
    
    # 2. Reply (Bob -> Alice)
    reply1_data = {
        "from": "bob@example.com",
        "to": "alice@example.com",
        "type": "email",
        "body": "First reply",
        "parent_id": msg1["id"]
    }
    resp2 = client.post("/api/v1/messages/send", json=reply1_data)
    assert resp2.status_code == status.HTTP_201_CREATED
    msg2 = resp2.json()
    
    assert msg2["conversation_id"] == thread_id
    assert msg2["parent_id"] == msg1["id"]
    
    # 3. Reply to Reply (Alice -> Bob)
    reply2_data = {
        "from": "alice@example.com",
        "to": "bob@example.com",
        "type": "email",
        "body": "Second reply",
        "parent_id": msg2["id"] # Threading off the last message? Or always root? Use case says "User 2 reply to reply 2 (that is reply 3, parent message is reply 2)"
    }
    resp3 = client.post("/api/v1/messages/send", json=reply2_data)
    assert resp3.status_code == status.HTTP_201_CREATED
    msg3 = resp3.json()
    
    assert msg3["conversation_id"] == thread_id
    assert msg3["parent_id"] == msg2["id"]
    
    # 4. Fetch messages by parent_id (Get replies to Root)
    # The requirement says "Get / add parent_id => Get all messages for this parent id". 
    # If I filter by parent_id=msg1['id'], I should see msg2.
    resp_list = client.get(f"/api/v1/messages/?parent_id={msg1['id']}")
    assert resp_list.status_code == status.HTTP_200_OK
    list_data = resp_list.json()
    messages = list_data["messages"]
    
    # Should contain msg2
    assert any(m["id"] == msg2["id"] for m in messages)
    
    # Test strict addressing validation (No UUIDs allowed in 'to')
    invalid_data = {
        "from": "alice@example.com",
        "to": str(uuid.uuid4()), # UUID
        "type": "email",
        "body": "Should fail",
        "conversation_type": "thread"
    }
    resp_fail = client.post("/api/v1/messages/send", json=invalid_data)
    # Expect 422 Validation Error
    assert resp_fail.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

def test_start_multiple_threads(client):
    """Test that starting multiple threads creates NEW conversations."""
    # Thread 1
    resp1 = client.post("/api/v1/messages/send", json={
        "from": "u1@e.com", "to": "u2@e.com", "type": "email", "body": "T1", "conversation_type": "thread"
    })
    assert resp1.status_code == status.HTTP_201_CREATED
    id1 = resp1.json()["conversation_id"]
    
    # Thread 2 (same pair)
    resp2 = client.post("/api/v1/messages/send", json={
        "from": "u1@e.com", "to": "u2@e.com", "type": "email", "body": "T2", "conversation_type": "thread"
    })
    assert resp2.status_code == status.HTTP_201_CREATED
    id2 = resp2.json()["conversation_id"]
    
    assert id1 != id2

def test_thread_creation_precedence(client):
    """
    Test that if BOTH conversation_type='thread' AND parent_id are present,
    we link to the parent conversation instead of creating a new one.
    """
    # 1. Start a thread
    resp1 = client.post("/api/v1/messages/send", json={
        "from": "u1@e.com", "to": "u2@e.com", "type": "email", "body": "Root", "conversation_type": "thread"
    })
    data1 = resp1.json()
    thread_id = data1["conversation_id"]
    msg1_id = data1["id"]
    
    # 2. Reply with explicit conversation_type='thread' (which should be ignored in favor of parent_id)
    resp2 = client.post("/api/v1/messages/send", json={
        "from": "u2@e.com", "to": "u1@e.com", "type": "email", "body": "Reply", 
        "conversation_type": "thread",
        "parent_id": msg1_id
    })
    assert resp2.status_code == status.HTTP_201_CREATED
    data2 = resp2.json()
    
    # Assert it joined the EXISTING thread
    assert data2["conversation_id"] == thread_id
    assert data2["parent_id"] == msg1_id
