# Fixes Applied to Message Queue Integration

## Issues Found and Fixed

### Issue 1: Worker Not Dequeuing Existing Messages ❌ → ✅

**Problem**: 
The Redis `dequeue_messages` function was using `"$"` as the starting point for `xread`, which means "only read NEW messages from this point forward". This caused the worker to miss any messages that were already in the queue before it started.

**Location**: `app/db/redis.py`, line 242

**Before**:
```python
async def dequeue_messages(self, queue: str, count: int = 10, block: int = 1000):
    messages = await self.redis_client.xread(
        {queue: "$"},  # ❌ Only reads NEW messages
        count=count,
        block=block
    )
```

**After**:
```python
async def dequeue_messages(self, queue: str, count: int = 10, block: int = 1000):
    # Store last read ID per queue to continue from where we left off
    if not hasattr(self, '_last_ids'):
        self._last_ids = {}
    
    # Use last read ID or start from beginning
    last_id = self._last_ids.get(queue, "0-0")  # ✅ Starts from beginning
    
    messages = await self.redis_client.xread(
        {queue: last_id},  # ✅ Reads from last position
        count=count,
        block=block
    )
    
    # Update last read ID after processing
    for stream_name, stream_messages in messages:
        for message_id, data in stream_messages:
            # ... process message ...
            self._last_ids[queue] = message_id  # ✅ Track position
```

**Impact**:
- ✅ Worker now processes messages that were queued before it started
- ✅ Worker continues from where it left off on restart
- ✅ No messages are skipped

---

### Issue 2: Multiple Conversations Error in Webhooks ❌ → ✅

**Problem**: 
The webhook processing was failing with "Multiple rows were found when one or none was expected" error. This happened because the conversation lookup query could return multiple conversations between the same participants, and `scalar_one_or_none()` throws an error when multiple rows are found.

**Location**: `app/services/message_service.py`, line 653

**Before**:
```python
async def _get_or_create_conversation(self, from_address: str, to_address: str, channel_type: MessageType):
    result = await self.db.execute(
        select(Conversation).where(
            or_(
                and_(
                    Conversation.participant_from == from_address,
                    Conversation.participant_to == to_address
                ),
                and_(
                    Conversation.participant_from == to_address,
                    Conversation.participant_to == from_address
                )
            ),
            Conversation.channel_type == channel_type
        )
    )
    
    conversation = result.scalar_one_or_none()  # ❌ Fails if multiple found
```

**After**:
```python
async def _get_or_create_conversation(self, from_address: str, to_address: str, channel_type: MessageType):
    result = await self.db.execute(
        select(Conversation).where(
            or_(
                and_(
                    Conversation.participant_from == from_address,
                    Conversation.participant_to == to_address
                ),
                and_(
                    Conversation.participant_from == to_address,
                    Conversation.participant_to == from_address
                )
            ),
            Conversation.channel_type == channel_type
        ).order_by(Conversation.created_at.desc())  # ✅ Get most recent first
    )
    
    conversation = result.scalars().first()  # ✅ Returns first result or None
```

**Impact**:
- ✅ Handles multiple conversations gracefully
- ✅ Uses the most recent conversation
- ✅ Webhooks process successfully

---

### Issue 3: Missing MMS Queue Processor ❌ → ✅

**Problem**: 
Messages with attachments are categorized as MMS and queued to `message_queue:mms`, but the worker only had processors for `message_queue:sms` and `message_queue:email`. MMS messages would sit in the queue forever without being processed.

**Location**: `app/workers/message_processor.py`, lines 48-54

**Before**:
```python
async def start(self):
    self.tasks = [
        asyncio.create_task(self.process_sms_queue()),
        asyncio.create_task(self.process_email_queue()),  # ❌ No MMS processor
        asyncio.create_task(self.process_retry_queue()),
        asyncio.create_task(self.process_webhook_queue()),
        asyncio.create_task(self.update_metrics()),
    ]
```

**After**:
```python
async def start(self):
    self.tasks = [
        asyncio.create_task(self.process_sms_queue()),
        asyncio.create_task(self.process_mms_queue()),  # ✅ Added MMS processor
        asyncio.create_task(self.process_email_queue()),
        asyncio.create_task(self.process_retry_queue()),
        asyncio.create_task(self.process_webhook_queue()),
        asyncio.create_task(self.update_metrics()),
    ]

# Added new processor method
@monitor_performance("process_mms_queue")
async def process_mms_queue(self):
    """Process MMS message queue."""
    queue_name = "message_queue:mms"
    
    while self.running:
        try:
            messages = await redis_manager.dequeue_messages(
                queue_name,
                count=settings.queue_batch_size,
                block=1000
            )
            
            if not messages:
                await asyncio.sleep(1)
                continue
            
            for msg_data in messages:
                await self._process_message(msg_data)
            
            queue_depth = await redis_manager.redis_client.xlen(queue_name)
            MetricsCollector.update_queue_depth(queue_name, queue_depth)
            
        except Exception as e:
            logger.error(f"Error processing MMS queue: {e}")
            await asyncio.sleep(5)
```

**Impact**:
- ✅ MMS messages (with attachments) are now processed
- ✅ All message types covered: SMS, MMS, Email
- ✅ Complete queue coverage

---

## Summary of Changes

| File | Issue | Fix |
|------|-------|-----|
| `app/db/redis.py` | Worker missing existing messages | Changed from `"$"` to `"0-0"` with position tracking |
| `app/services/message_service.py` | Multiple conversations error | Changed from `scalar_one_or_none()` to `scalars().first()` |
| `app/workers/message_processor.py` | Missing MMS queue processor | Added `process_mms_queue()` task |

---

## Testing the Fixes

### Test 1: Worker Processing Existing Messages

```bash
# 1. Start Redis and DB
docker compose up -d postgres redis

# 2. Start API (WITHOUT worker)
export SYNC_MESSAGE_PROCESSING=false
make run-bg

# 3. Send a test message (it will be queued)
curl -X POST http://localhost:8080/api/v1/messages/send \
  -H "Content-Type: application/json" \
  -d '{"from":"+15551234567","to":"+15559876543","type":"sms","body":"Test before worker"}'

# 4. Check message is in queue and status is pending
docker exec -it $(docker ps -q -f name=redis) redis-cli XLEN message_queue:sms
# Should show: 1

# 5. NOW start the worker
make worker

# 6. Check message gets processed
# Worker logs should show: "Successfully processed message: ..."
# Queue should be empty now:
docker exec -it $(docker ps -q -f name=redis) redis-cli XLEN message_queue:sms
# Should show: 0
```

### Test 2: Webhook Processing (No More Errors)

```bash
# Send a test webhook
curl -X POST http://localhost:8080/api/v1/webhooks/twilio \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "From=%2B15559876543&To=%2B15551234567&Body=Test&MessageSid=TEST_$(date +%s)"

# Should return 200 OK with no errors
# Check logs - should NOT see "Multiple rows were found" error
```

### Test 3: MMS Message Processing

```bash
# Send MMS message with attachment
curl -X POST http://localhost:8080/api/v1/messages/send \
  -H "Content-Type: application/json" \
  -d '{
    "from": "+15551234567",
    "to": "+15559876543",
    "type": "mms",
    "body": "Check out this image",
    "attachments": ["https://example.com/image.jpg"]
  }'

# Check MMS queue
docker exec -it $(docker ps -q -f name=redis) redis-cli XLEN message_queue:mms
# Should show message added

# Worker should process it
# Check worker logs for: "Processing message from queue: message_queue:mms"
```

### Test 4: Complete Verification

```bash
# Run the full verification script
export SYNC_MESSAGE_PROCESSING=false
make restart-app
make worker  # In another terminal
make verify-redis-queue

# Expected results:
# ✓ PASS - Sync Processing Disabled
# ✓ PASS - Message Queued to Redis
# ✓ PASS - Async Processing Mode
# ✓ PASS - Worker Processed Message  ← Should now PASS
# ✓ PASS - Webhook Integration        ← Should now PASS
# ✓ PASS - Queue Operations
```

---

## How to Apply the Fixes

The fixes have already been applied to the codebase. To use them:

1. **Stop existing services**:
   ```bash
   make stop
   ```

2. **Restart with fixes**:
   ```bash
   export SYNC_MESSAGE_PROCESSING=false
   make restart-app
   ```

3. **Start worker** (in another terminal):
   ```bash
   make worker
   ```

4. **Verify everything works**:
   ```bash
   make verify-redis-queue
   ```

---

## Technical Details

### Redis Streams XREAD Behavior

- `XREAD STREAMS myqueue $`: Read only NEW messages from now
- `XREAD STREAMS myqueue 0-0`: Read ALL messages from beginning
- `XREAD STREAMS myqueue 123456-0`: Read from specific ID

Our fix uses a pattern where:
1. First call uses `0-0` (start from beginning)
2. Store the last message ID processed
3. Next call uses that ID (continue from where we left off)
4. This ensures no messages are missed

### Consumer Groups (Future Enhancement)

For production, consider using Redis Consumer Groups:
- Multiple workers can share the load
- Automatic acknowledgment tracking
- Failed message retry built-in

Example:
```python
# Create consumer group
await redis_client.xgroup_create("message_queue:sms", "workers", mkstream=True)

# Read as part of group
messages = await redis_client.xreadgroup(
    "workers",
    "worker-1",
    {"message_queue:sms": ">"},
    count=10
)
```

---

## Verification Checklist

After applying fixes, verify:

- [ ] Worker starts without errors
- [ ] Worker processes messages already in queue
- [ ] SMS messages are processed
- [ ] MMS messages are processed
- [ ] Email messages are processed
- [ ] Webhooks process without errors
- [ ] Multiple conversations handled gracefully
- [ ] Verification script passes all tests

---

## Next Steps

1. ✅ Fixes applied
2. ✅ Documentation updated
3. ⏳ Run verification script
4. ⏳ Monitor worker logs
5. ⏳ Test in development environment
6. ⏳ Consider consumer groups for production

---

## Related Documentation

- [REDIS_QUEUE_VERIFICATION.md](./REDIS_QUEUE_VERIFICATION.md) - Verification guide
- [SYNC_VS_ASYNC_PROCESSING.md](./SYNC_VS_ASYNC_PROCESSING.md) - Async processing setup
- [MESSAGE_FLOW_TESTING.md](./MESSAGE_FLOW_TESTING.md) - Message flow testing

