# Redis Queue Integration Verification

This guide explains how to verify that the messaging service properly integrates with Redis queues for asynchronous message processing.

## Overview

The messaging service supports two processing modes:

### 1. **Synchronous Processing** (Default - Not Recommended for Production)
- Messages are processed immediately in the API request
- No Redis queue involved
- Controlled by `SYNC_MESSAGE_PROCESSING=true`
- **Current Default**: `True` in `app/core/config.py`

### 2. **Asynchronous Processing** (Recommended for Production)
- Messages are queued to Redis
- Background worker processes messages from queue
- Better scalability and resilience
- Controlled by `SYNC_MESSAGE_PROCESSING=false`

## Architecture Flow

### Asynchronous Message Flow (SYNC_MESSAGE_PROCESSING=false)

```
1. Client → POST /api/v1/messages/send
2. API validates and saves message to PostgreSQL (status: pending)
3. API adds message to Redis queue: message_queue:{type}
4. API returns response immediately
5. Background worker dequeues message from Redis
6. Worker processes message through provider
7. Worker updates message status (sending → sent → delivered)
8. Database updated with final status
```

### Queue Structure

**Outbound Message Queues:**
- `message_queue:sms` - SMS messages
- `message_queue:mms` - MMS messages (messages with attachments)
- `message_queue:email` - Email messages

**Webhook Queue:**
- `webhook_queue` - Incoming webhooks (currently processed synchronously)

## How Messages Are Added to Queues

### Outbound Messages (message_queue:*)

In `app/services/message_service.py`:

```python
async def send_message(self, message_data: Dict[str, Any]) -> Message:
    # ... create message in database ...
    
    # Queue message for sending
    await self._queue_message_for_sending(message)
    
    # Process immediately if sync mode (SKIP QUEUE)
    if settings.sync_message_processing:
        await self.process_outbound_message(str(message.id))
    
    return message

async def _queue_message_for_sending(self, message: Message):
    """Queue message for sending."""
    queue_data = {
        "message_id": str(message.id),
        "retry_count": message.retry_count,
        "scheduled_at": datetime.utcnow().isoformat()
    }
    
    # Queue name based on message type
    queue_name = f"message_queue:{message.message_type.value}"
    await redis_manager.enqueue_message(queue_name, queue_data)
```

**Key Points:**
1. **Line 95**: `await self._queue_message_for_sending(message)` - Always queues the message
2. **Lines 122-127**: If `sync_message_processing=True`, immediately processes the message (bypassing worker)
3. **Line 715**: Queue name is determined by message type (sms, mms, email)

### Webhook Queue (webhook_queue)

**Current Implementation**: Webhooks are processed **synchronously**, not via queue.

In `app/api/v1/webhooks.py`:

```python
@router.post("/twilio")
async def twilio_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    # Process webhook directly (synchronous)
    service = WebhookService(db)
    result = await service.process_webhook(
        provider="twilio",
        headers=headers,
        body=data
    )
    return Response(...)
```

**Why Synchronous for Webhooks?**
- Webhook providers (Twilio, SendGrid) expect immediate response
- They may retry if response is delayed
- Processing is fast (just database insert)
- For heavy processing, use background tasks after initial response

**To Add Webhook Queuing** (if needed in future):

```python
# In webhook endpoint
await redis_manager.enqueue_message("webhook_queue", {
    "provider": "twilio",
    "headers": headers,
    "body": data
})
return Response(...)  # Return immediately

# Worker will process from queue
```

## Worker Processing

The background worker (`app/workers/message_processor.py`) runs separate tasks for each queue:

```python
async def start(self):
    self.tasks = [
        asyncio.create_task(self.process_sms_queue()),      # Processes message_queue:sms
        asyncio.create_task(self.process_email_queue()),    # Processes message_queue:email
        asyncio.create_task(self.process_retry_queue()),    # Processes retries
        asyncio.create_task(self.process_webhook_queue()),  # Processes webhook_queue
        asyncio.create_task(self.update_metrics()),         # Updates metrics
    ]
```

Each queue processor:
1. Reads messages from Redis Stream (XREAD)
2. Dequeues messages in batches
3. Processes each message
4. Updates message status in database
5. Handles errors and retries

## Verification Steps

### Step 1: Check Current Configuration

```bash
# Check if SYNC_MESSAGE_PROCESSING is set
echo $SYNC_MESSAGE_PROCESSING

# If not set or set to 'true', messages are processed synchronously
```

### Step 2: Enable Async Processing

```bash
# Set environment variable
export SYNC_MESSAGE_PROCESSING=false

# Or add to .env file
echo "SYNC_MESSAGE_PROCESSING=false" >> .env
```

### Step 3: Start Services

```bash
# Start Docker services
docker compose up -d postgres redis

# Start API with async processing
make run

# In another terminal, start worker
make worker
```

### Step 4: Run Verification Script

```bash
# Run automated verification
make verify-redis-queue

# Or directly
python3 ./bin/verify_redis_queue.py
```

### Expected Output (Async Mode)

```
═══════════════════════════════════════════════════════════════════
         Redis Queue Integration Verification
═══════════════════════════════════════════════════════════════════

ℹ Setting up connections...
✓ Connected to Redis
✓ API is healthy

═══════════════════════════════════════════════════════════════════
         Step 1: Verify Sync Processing Configuration
═══════════════════════════════════════════════════════════════════

✓ SYNC_MESSAGE_PROCESSING is set to False

═══════════════════════════════════════════════════════════════════
              Step 2: Test Message Queuing to Redis
═══════════════════════════════════════════════════════════════════

ℹ Initial queue length for message_queue:sms: 0
ℹ Sending SMS message via API...
✓ Message sent with ID: abc123...
ℹ Initial status: pending
ℹ Final queue length for message_queue:sms: 1
✓ Message added to Redis queue! (queue grew by 1)
✓ Message found in queue:
  Message ID in queue: abc123...
  Scheduled at: 2024-01-15T10:30:00

═══════════════════════════════════════════════════════════════════
                  Step 3: Check Processing Mode
═══════════════════════════════════════════════════════════════════

ℹ Checking message status immediately after send...
ℹ Message status: pending
✓ Message is in PENDING state
✓ This indicates ASYNCHRONOUS processing via queue

═══════════════════════════════════════════════════════════════════
               Step 4: Monitor Worker Processing
═══════════════════════════════════════════════════════════════════

ℹ Waiting for worker to process message (timeout: 30s)...
ℹ Status changed: pending -> sending
ℹ Status changed: sending -> sent
✓ Message processed by worker!
✓ Final status: sent
✓ Processing time: 2s

...

Test Summary
✓ PASS - Sync Processing Disabled
✓ PASS - Message Queued to Redis
✓ PASS - Async Processing Mode
✓ PASS - Worker Processed Message
✓ PASS - Webhook Integration
✓ PASS - Queue Operations

✓ All tests passed!
```

## Manual Verification

### Check Redis Queue Directly

```bash
# Connect to Redis CLI
make redis-cli

# Or
docker exec -it $(docker ps -q -f name=redis) redis-cli

# Check queue length
XLEN message_queue:sms

# View messages in queue
XRANGE message_queue:sms - + COUNT 10

# Example output:
1) 1) "1234567890-0"
   2) 1) "data"
      2) "{\"message_id\":\"abc123\",\"retry_count\":0,\"scheduled_at\":\"2024-01-15T10:30:00\"}"
```

### Monitor Worker Logs

```bash
# If worker is running in terminal, watch the output

# Example worker log:
[INFO] Starting message processor...
[INFO] Message processor started successfully
[INFO] Processing message from queue: message_queue:sms
[INFO] Successfully processed message: abc123...
[INFO] Message sent successfully, message_id=abc123, provider=twilio
```

### Check Message Status via API

```bash
# Send message
MESSAGE_ID=$(curl -s -X POST http://localhost:8080/api/v1/messages/send \
  -H "Content-Type: application/json" \
  -d '{
    "from": "+15551234567",
    "to": "+15559876543",
    "type": "sms",
    "body": "Test"
  }' | jq -r '.id')

# Check status immediately (should be 'pending' in async mode)
curl http://localhost:8080/api/v1/messages/$MESSAGE_ID | jq '.status'

# Wait a few seconds and check again (should be 'sent')
sleep 3
curl http://localhost:8080/api/v1/messages/$MESSAGE_ID | jq '.status'
```

## Troubleshooting

### Issue: Messages Not Queued

**Symptom**: Queue length doesn't increase after sending message

**Cause**: `SYNC_MESSAGE_PROCESSING=true` (synchronous mode)

**Solution**:
```bash
export SYNC_MESSAGE_PROCESSING=false
# Restart API server
```

### Issue: Messages Stay in 'pending' Forever

**Symptom**: Messages are queued but never processed

**Cause**: Background worker not running

**Solution**:
```bash
# Start the worker
make worker

# Or with Python directly
python -m app.workers.message_processor
```

### Issue: Worker Crashes Immediately

**Symptom**: Worker starts then exits with error

**Possible Causes**:
1. Database not initialized: Run `make migrate`
2. Redis not running: Run `docker compose up -d redis`
3. Configuration error: Check `.env` file

### Issue: Messages Processed Too Quickly

**Symptom**: Messages show as 'sent' immediately even with async mode

**Cause**: Worker is running AND `SYNC_MESSAGE_PROCESSING=true`

**Explanation**: When sync mode is enabled, messages are:
1. Added to queue (by `_queue_message_for_sending`)
2. Processed immediately in API (by sync processing code)
3. Worker may also process them (duplicate processing!)

**Solution**: Set `SYNC_MESSAGE_PROCESSING=false` to avoid duplicate processing

## Performance Comparison

### Synchronous Mode
- **Pros**: Simple, immediate results
- **Cons**: 
  - API response time depends on provider latency
  - Cannot scale horizontally
  - Blocks API threads
  - Single point of failure

### Asynchronous Mode (Recommended)
- **Pros**:
  - Fast API responses (~50ms vs ~2000ms)
  - Horizontal scaling (multiple workers)
  - Better error handling and retries
  - Resilient to provider outages
- **Cons**: 
  - Slightly more complex setup
  - Need to run background worker
  - Status updates are eventual, not immediate

## Production Recommendations

1. **Always use async mode** (`SYNC_MESSAGE_PROCESSING=false`)
2. **Run multiple workers** for high throughput
3. **Monitor queue depth** - alerts if queue grows too large
4. **Set up worker health checks** - restart if crashed
5. **Use Redis persistence** - messages survive restarts
6. **Configure retries** properly for provider errors

## Related Documentation

- [MESSAGE_FLOW_TESTING.md](./MESSAGE_FLOW_TESTING.md) - End-to-end flow testing
- [ARCHITECTURE.md](./ARCHITECTURE.md) - System architecture
- [RUN_GUIDE.md](./RUN_GUIDE.md) - Running services

## Summary

The messaging service queue integration works as follows:

1. **Messages are ALWAYS added to Redis queue** (`_queue_message_for_sending`)
2. **Sync mode (`SYNC_MESSAGE_PROCESSING=true`)**: 
   - Messages are processed immediately by API
   - Queue is bypassed (but message is still added)
   - **This is the current default**
3. **Async mode (`SYNC_MESSAGE_PROCESSING=false`)**:
   - Messages wait in queue for worker
   - Worker processes from queue
   - Better for production

4. **Webhooks**: Currently processed synchronously (not via queue)
   - Webhook endpoints process immediately
   - Could be changed to queue-based if needed

To verify proper async operation, use the verification script:
```bash
export SYNC_MESSAGE_PROCESSING=false
make verify-redis-queue
```

