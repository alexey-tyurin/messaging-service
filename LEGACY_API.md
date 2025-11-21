# Legacy API Endpoints

This document describes the legacy API endpoints that provide backward compatibility with the original test script (`test_original.sh`).

## Overview

The messaging service supports two API endpoint structures:

1. **New API** (`/api/v1/*`) - Modern, RESTful endpoints with comprehensive features
2. **Legacy API** (`/api/*`) - Original endpoints for backward compatibility

Both APIs use the same underlying services and database, ensuring consistent behavior.

## Endpoint Mapping

### Message Sending

#### Legacy: POST /api/messages/sms
**Purpose**: Send SMS or MMS messages

**Request Body**:
```json
{
  "from": "+12016661234",
  "to": "+18045551234",
  "type": "sms",  // or "mms"
  "body": "Hello! This is a test SMS message.",
  "attachments": null,  // or ["url1", "url2"] for MMS
  "timestamp": "2024-11-01T14:00:00Z"
}
```

**Response**:
```json
{
  "status": "success",
  "message_id": "uuid",
  "conversation_id": "uuid",
  "type": "sms",
  "provider": "twilio"
}
```

**Maps to**: `POST /api/v1/messages/send`

---

#### Legacy: POST /api/messages/email
**Purpose**: Send email messages

**Request Body**:
```json
{
  "from": "user@usehatchapp.com",
  "to": "contact@gmail.com",
  "body": "Hello! This is a test email with <b>HTML</b>.",
  "attachments": ["https://example.com/document.pdf"],
  "timestamp": "2024-11-01T14:00:00Z"
}
```

**Response**:
```json
{
  "status": "success",
  "message_id": "uuid",
  "conversation_id": "uuid",
  "type": "email",
  "provider": "sendgrid"
}
```

**Maps to**: `POST /api/v1/messages/send`

---

### Webhooks

#### Legacy: POST /api/webhooks/sms
**Purpose**: Receive incoming SMS/MMS webhooks

**Request Body**:
```json
{
  "from": "+18045551234",
  "to": "+12016661234",
  "type": "sms",  // or "mms"
  "messaging_provider_id": "message-1",
  "body": "This is an incoming SMS message",
  "attachments": null,
  "timestamp": "2024-11-01T14:00:00Z"
}
```

**Response**:
```json
{
  "status": "success",
  "message": "Webhook processed"
}
```

**Maps to**: `POST /api/v1/webhooks/twilio`

---

#### Legacy: POST /api/webhooks/email
**Purpose**: Receive incoming email webhooks

**Request Body**:
```json
{
  "from": "contact@gmail.com",
  "to": "user@usehatchapp.com",
  "xillio_id": "message-3",
  "body": "<html><body>HTML content</body></html>",
  "attachments": ["https://example.com/document.pdf"],
  "timestamp": "2024-11-01T14:00:00Z"
}
```

**Response**:
```json
{
  "status": "success",
  "message": "Webhook processed"
}
```

**Maps to**: `POST /api/v1/webhooks/sendgrid`

---

### Conversations

#### Legacy: GET /api/conversations
**Purpose**: List all conversations

**Query Parameters**:
- `participant` (optional): Filter by participant
- `limit` (optional): Max results (default: 50)
- `offset` (optional): Skip results (default: 0)

**Response**:
```json
{
  "conversations": [
    {
      "id": "uuid",
      "participant_from": "+12016661234",
      "participant_to": "+18045551234",
      "channel_type": "sms",
      "status": "active",
      "message_count": 5,
      "unread_count": 2,
      "last_message_at": "2024-11-01T14:00:00Z",
      "created_at": "2024-11-01T12:00:00Z"
    }
  ],
  "total": 1
}
```

**Maps to**: `GET /api/v1/conversations/`

---

#### Legacy: GET /api/conversations/{id}/messages
**Purpose**: Get messages for a specific conversation

**Path Parameters**:
- `id`: Conversation ID (UUID or integer)

**Query Parameters**:
- `limit` (optional): Max results (default: 50)
- `offset` (optional): Skip results (default: 0)

**Response**:
```json
{
  "messages": [
    {
      "id": "uuid",
      "conversation_id": "uuid",
      "direction": "outbound",
      "type": "sms",
      "from": "+12016661234",
      "to": "+18045551234",
      "body": "Message text",
      "status": "sent",
      "provider": "twilio",
      "created_at": "2024-11-01T14:00:00Z",
      "sent_at": "2024-11-01T14:00:01Z"
    }
  ],
  "total": 1,
  "conversation_id": "uuid"
}
```

**Maps to**: `GET /api/v1/messages/?conversation_id={id}`

---

## Key Differences

### Legacy API vs New API

| Feature | Legacy API | New API |
|---------|-----------|---------|
| **Endpoint Structure** | Type-specific routes | Unified routes |
| **Send SMS** | `POST /api/messages/sms` | `POST /api/v1/messages/send` |
| **Send Email** | `POST /api/messages/email` | `POST /api/v1/messages/send` |
| **Webhooks** | Type-specific (`/sms`, `/email`) | Provider-specific (`/twilio`, `/sendgrid`) |
| **Response Format** | Simple status objects | Full resource objects |
| **Error Handling** | Basic HTTP errors | Detailed error responses |
| **Pagination** | Basic offset/limit | Full pagination metadata |
| **Filtering** | Limited | Comprehensive filters |

## Testing

### Run Legacy API Tests

```bash
# Make sure the application is running
make run

# Run the original test script
./bin/test_original.sh
```

**Expected Output**:
```
=== Testing Messaging Service Endpoints ===
1. Testing SMS send...
Status: 200
✓ Success

2. Testing MMS send...
Status: 200
✓ Success

3. Testing Email send...
Status: 200
✓ Success

... (all tests pass)

=== Test script completed ===
```

### Run New API Tests

```bash
# Run the comprehensive test suite
make test
```

Both test suites should pass successfully.

## Migration Guide

If you're using the legacy API and want to migrate to the new API:

### 1. Message Sending

**Before (Legacy)**:
```bash
# SMS
curl -X POST http://localhost:8080/api/messages/sms \
  -H "Content-Type: application/json" \
  -d '{"from": "+1234567890", "to": "+0987654321", "type": "sms", "body": "Hello"}'

# Email
curl -X POST http://localhost:8080/api/messages/email \
  -H "Content-Type: application/json" \
  -d '{"from": "user@example.com", "to": "contact@example.com", "body": "Hello"}'
```

**After (New API)**:
```bash
# Single endpoint for all types
curl -X POST http://localhost:8080/api/v1/messages/send \
  -H "Content-Type: application/json" \
  -d '{"from": "+1234567890", "to": "+0987654321", "type": "sms", "body": "Hello"}'

curl -X POST http://localhost:8080/api/v1/messages/send \
  -H "Content-Type: application/json" \
  -d '{"from": "user@example.com", "to": "contact@example.com", "type": "email", "body": "Hello"}'
```

### 2. Webhooks

**Before (Legacy)**:
```bash
POST /api/webhooks/sms    # For SMS/MMS
POST /api/webhooks/email  # For email
```

**After (New API)**:
```bash
POST /api/v1/webhooks/twilio    # For SMS/MMS
POST /api/v1/webhooks/sendgrid  # For email
```

### 3. Conversations

**Before (Legacy)**:
```bash
GET /api/conversations
GET /api/conversations/1/messages
```

**After (New API)**:
```bash
GET /api/v1/conversations/
GET /api/v1/messages/?conversation_id=uuid
```

## Implementation Details

The legacy API endpoints are implemented in `app/api/legacy_routes.py` and use the same underlying services as the new API:

- **MessageService** - Handles message sending and retrieval
- **ConversationService** - Manages conversations
- **WebhookService** - Processes incoming webhooks

This ensures:
- ✅ Consistent business logic
- ✅ Same data validation
- ✅ Identical error handling
- ✅ Single source of truth
- ✅ Easy maintenance

## Deprecation Notice

⚠️ **The legacy API endpoints are provided for backward compatibility only.**

**Recommendations**:
1. Use the new API (`/api/v1/*`) for new integrations
2. Migrate existing integrations when possible
3. The legacy API may be removed in a future major version

## Support

For questions or issues:
- Check the main API documentation: http://localhost:8080/docs
- Review ARCHITECTURE.md for system design
- See ERROR_HANDLING.md for error handling details

