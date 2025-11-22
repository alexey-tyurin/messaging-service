# Sync vs Async Message Processing

## Overview

The messaging service has a configuration variable `SYNC_MESSAGE_PROCESSING` that controls whether messages are processed:
- **Synchronously** (immediately in the API request)
- **Asynchronously** (via Redis queue and background worker)

**Current Default**: `SYNC_MESSAGE_PROCESSING=False` (asynchronous processing via Redis queue)

This means the system uses **async processing by default**, leveraging Redis queues and background workers for optimal performance and scalability.

## Code Location

In `app/core/config.py` (line 95):

```python
# Processing Mode
sync_message_processing: bool = Field(default=False, env="SYNC_MESSAGE_PROCESSING")
```

In `app/services/message_service.py` (lines 94-127):

```python
async def send_message(self, message_data: Dict[str, Any]) -> Message:
    # ...
    
    # Queue message for sending (line 95)
    await self._queue_message_for_sending(message)
    
    # ...
    
    # Process message immediately if sync processing is enabled (line 122-127)
    if settings.sync_message_processing:
        logger.info(f"Processing message synchronously: {message.id}")
        await self.process_outbound_message(str(message.id))
        # Refresh message to get updated status
        await self.db.refresh(message)
    
    return message
```

## How It Works

### Synchronous Mode (SYNC_MESSAGE_PROCESSING=True)

**NOT RECOMMENDED FOR PRODUCTION**

```
1. API receives request
2. Message saved to database (status: pending)
3. Message added to Redis queue ✓
4. Message processed IMMEDIATELY (status: pending → sending → sent)
5. Message returned with final status (sent)
6. Worker may also process it from queue (potential duplicate!)
```

**Problems:**
- Redis queue is effectively bypassed
- Worker may cause duplicate processing
- API response is slow (waits for provider)
- Can't scale horizontally
- Single point of failure

### Asynchronous Mode (SYNC_MESSAGE_PROCESSING=False)

**CURRENT DEFAULT - RECOMMENDED FOR PRODUCTION**

```
1. API receives request
2. Message saved to database (status: pending)
3. Message added to Redis queue ✓
4. API returns immediately with status: pending ✓
5. Worker picks up from queue
6. Worker processes (status: pending → sending → sent)
7. Client polls for status updates
```

**Benefits:**
- Fast API responses (~50ms)
- True async processing
- Worker can scale horizontally
- Better resilience and fault tolerance
- Follows documented architecture
- Industry best practice

## Configuration

The default is already set to async mode in `app/core/config.py` (line 95):

```python
# Processing Mode
sync_message_processing: bool = Field(default=False, env="SYNC_MESSAGE_PROCESSING")
```

### To Enable Synchronous Mode (Not Recommended)

If you need synchronous processing for debugging or testing:

**Option 1: Set Environment Variable**

```bash
# In terminal before starting services
export SYNC_MESSAGE_PROCESSING=true

# Or in .env file
echo "SYNC_MESSAGE_PROCESSING=true" >> .env
```

**Option 2: Docker Compose**

Add to `docker-compose.yml`:

```yaml
services:
  app:
    environment:
      - SYNC_MESSAGE_PROCESSING=true
```

## Verification

### Async Mode (Default Behavior)

```bash
# Send message  
curl -X POST http://localhost:8080/api/v1/messages/send \
  -H "Content-Type: application/json" \
  -d '{"from":"+15551234567","to":"+15559876543","type":"sms","body":"Test"}'

# Response (immediate, status is 'pending'):
{
  "id": "abc123...",
  "status": "pending",  # ← Waiting for worker!
  "sent_at": null
}

# Check Redis queue
redis-cli XLEN message_queue:sms
# Output: 1 (message waiting for worker)

# Wait a few seconds, then check status
curl http://localhost:8080/api/v1/messages/abc123...
# Response:
{
  "id": "abc123...",
  "status": "sent",  # ← Now processed by worker!
  "sent_at": "2024-01-15T10:30:02Z"
}
```

### Sync Mode (If Enabled)

```bash
# Send message  
curl -X POST http://localhost:8080/api/v1/messages/send \
  -H "Content-Type: application/json" \
  -d '{"from":"+15551234567","to":"+15559876543","type":"sms","body":"Test"}'

# Response (immediate, status is 'pending'):
{
  "id": "abc123...",
  "status": "pending",  # ← Waiting for worker!
  "sent_at": null
}

# Check Redis queue
redis-cli XLEN message_queue:sms
# Output: 1 (message waiting for worker)

# Wait a few seconds, then check status
curl http://localhost:8080/api/v1/messages/abc123...
# Response:
{
  "id": "abc123...",
  "status": "sent",  # ← Now processed by worker!
  "sent_at": "2024-01-15T10:30:02Z"
}
```

## Testing

### Automated Verification

```bash
# Start services (async mode is default)
docker compose up -d postgres redis
make run-bg
make worker  # Required for async processing!

# Run verification script
make verify-redis-queue
```

Expected output:
```
✓ PASS - Async Processing Enabled (Default)
✓ PASS - Message Queued to Redis
✓ PASS - Message Status: Pending (Async)
✓ PASS - Worker Processed Message
```

### Manual Testing

1. **Check current setting:**
   ```bash
   python3 -c "from app.core.config import settings; print(f'Sync mode: {settings.sync_message_processing}')"
   ```

2. **Send test message and observe:**
   ```bash
   # Send message
   MESSAGE_ID=$(curl -s -X POST http://localhost:8080/api/v1/messages/send \
     -H "Content-Type: application/json" \
     -d '{"from":"+15551234567","to":"+15559876543","type":"sms","body":"Test"}' \
     | jq -r '.id')
   
   # Immediately check status (should be 'pending' in async mode)
   curl -s http://localhost:8080/api/v1/messages/$MESSAGE_ID | jq '.status'
   
   # Check Redis queue
   docker exec -it $(docker ps -q -f name=redis) redis-cli XLEN message_queue:sms
   
   # Wait and check again
   sleep 3
   curl -s http://localhost:8080/api/v1/messages/$MESSAGE_ID | jq '.status'
   ```

## Recommendation

**The system is already configured correctly!**

The default setting (`SYNC_MESSAGE_PROCESSING=false`) is optimal for:
1. Production deployments
2. Documented architecture compliance
3. Performance and scalability
4. Proper separation of concerns
5. Horizontal scaling capability
6. Industry best practices

**For Development**: 
- **Use default (async mode)** - Tests the real production flow
- **Only use sync mode** for quick debugging when you don't want to run the worker

## Worker Management

When using async mode, **you must run the worker**:

```bash
# Terminal 1: API server
make run

# Terminal 2: Background worker
make worker

# Or in Docker
docker compose up -d  # Includes worker service if configured
```

Worker logs will show:
```
[INFO] Starting message processor...
[INFO] Message processor started successfully
[INFO] Processing message from queue: message_queue:sms
[INFO] Successfully processed message: abc123...
```

## Summary

| Aspect | Sync Mode (True) | Async Mode (False) |
|--------|------------------|-------------------|
| **Queue Used** | No (bypassed) | Yes ✓ |
| **Worker Needed** | No | Yes (required) |
| **API Response** | Slow (~2s) | Fast (~50ms) |
| **Status After Send** | sent | pending |
| **Scalability** | Poor | Excellent |
| **Production Ready** | No | Yes ✓ |
| **Current Default** | No | **Yes** ✓ |

**Configuration Status**: ✅ System is already configured for async processing (production-ready).

## Related Files

- `app/core/config.py` - Configuration setting
- `app/services/message_service.py` - Processing logic
- `app/workers/message_processor.py` - Background worker
- `MESSAGE_FLOW_TESTING.md` - Flow documentation
- `REDIS_QUEUE_VERIFICATION.md` - Verification guide
- `bin/verify_redis_queue.py` - Verification script

