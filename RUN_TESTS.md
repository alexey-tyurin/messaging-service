# How to Run the Verification Tests

## The Fix Applied

✅ **Changed default to async processing** in `app/core/config.py`:
```python
sync_message_processing: bool = Field(default=False, ...)  # Now defaults to False
```

## Steps to Test

### Step 1: Stop Everything

```bash
make stop
```

### Step 2: Restart the API Server

The API server needs to be restarted to pick up the new default:

```bash
make run-bg
```

**Wait for it to start** (about 3-5 seconds), then verify it's running:

```bash
curl http://localhost:8080/health
# Should return: {"status":"healthy"}
```

### Step 3: Start the Worker

**In a NEW terminal window**, start the worker:

```bash
make worker
```

You should see output like:
```
INFO:app.workers.message_processor:Starting message processor...
INFO:app.workers.message_processor:Message processor started successfully
```

**Keep this terminal open** - the worker needs to keep running.

### Step 4: Run Verification

**In the first terminal**, run the verification:

```bash
make verify-redis-queue
```

## Expected Results

```
═══════════════════════════════════════════════════════════════════
         Redis Queue Integration Verification
═══════════════════════════════════════════════════════════════════

Test Summary
✓ PASS - Sync Processing Disabled
✓ PASS - Message Queued to Redis
✓ PASS - Async Processing Mode
✓ PASS - Worker Processed Message
✓ PASS - Webhook Integration
✓ PASS - Queue Operations

✓ All tests passed!
```

## Troubleshooting

### If "Async Processing Mode" still fails:

The API might still be running with the old code. Try:

```bash
# Kill all Python processes (careful!)
pkill -f uvicorn
pkill -f "python.*app.main"

# Wait a moment
sleep 3

# Restart
make restart-app
```

### If "Worker Processed Message" fails:

Check if the worker is actually running:

```bash
ps aux | grep message_processor
```

If not running, start it:

```bash
make worker
```

### If "Webhook Integration" fails:

Check the API logs for errors:

```bash
tail -50 logs/app.log | grep -i error
```

## Manual Quick Test

To quickly verify async mode is working:

```bash
# Send a message
MESSAGE_ID=$(curl -s -X POST http://localhost:8080/api/v1/messages/send \
  -H "Content-Type: application/json" \
  -d '{"from":"+15551234567","to":"+15559876543","type":"sms","body":"Test"}' \
  | jq -r '.id')

# Immediately check status (should be "pending")
curl -s http://localhost:8080/api/v1/messages/$MESSAGE_ID | jq '.status'

# Output should be: "pending"
# If it's "sent", then sync mode is still enabled

# Check Redis queue
docker exec -it $(docker ps -q -f name=redis) redis-cli XLEN message_queue:sms

# Output should be: 1 (message in queue)

# Wait a few seconds for worker to process
sleep 3

# Check again
curl -s http://localhost:8080/api/v1/messages/$MESSAGE_ID | jq '.status'

# Output should now be: "sent"
```

## Summary of Changes

1. ✅ **Fixed Redis dequeue** - Worker now reads existing messages (not just new ones)
2. ✅ **Fixed webhook errors** - Handles multiple conversations gracefully  
3. ✅ **Added MMS queue processor** - All message types now covered
4. ✅ **Changed default to async** - `sync_message_processing=False` by default

## Files Modified

- `app/core/config.py` - Changed default to `False`
- `app/db/redis.py` - Fixed dequeue to read from beginning
- `app/services/message_service.py` - Fixed conversation lookup
- `app/workers/message_processor.py` - Added MMS queue processor

All tests should now pass! 🎉

