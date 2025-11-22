# Message Flow Integration Testing

This guide explains how to test the complete message flow through the messaging service, including Redis queue processing.

## Overview

The message flow test script validates the complete 8-step message processing flow as described in the architecture.

**Note**: The system uses **asynchronous processing by default** (`SYNC_MESSAGE_PROCESSING=false`), which means:
- Messages are queued to Redis
- Background worker processes messages from queue
- This is the production-ready configuration
- **Worker must be running** for tests to pass

### Complete Flow Tested

1. **Client sends message via REST API** - HTTP POST to `/api/v1/messages/send`
2. **Message validated and stored in PostgreSQL** - Validation and database persistence
3. **Queued in Redis for async processing** - Message added to Redis Stream queue
4. **Worker picks up message from queue** - Background worker dequeues message
5. **Provider selected based on message type** - Provider selection logic executed
6. **Message sent through provider API** - External provider API call (mocked in dev)
7. **Status updated and events recorded** - Database status updates and event logging
8. **Webhooks processed for delivery confirmations** - Inbound webhook handling

## Quick Start

### Prerequisites

The system is configured for async processing by default. All services must be running:

```bash
# Start Docker services (PostgreSQL and Redis)
docker compose up -d postgres redis

# Start the API server (uses async mode by default)
make run-bg

# Start the background worker (REQUIRED - messages won't process without it!)
make worker
```

**Important**: The background worker is **required** for message processing in async mode (the default).

### Run the Test

```bash
# Run the complete message flow test
make test-flow
```

Or directly:

```bash
./bin/test_flow.sh
```

## What Gets Tested

### Message Types

The test script sends and validates:

1. **SMS Message**
   - Simple text message
   - Phone number validation
   - Queued to `message_queue:sms`

2. **MMS Message**
   - Text message with attachments
   - Attachment URL validation
   - Queued to `message_queue:mms`

3. **Email Message**
   - HTML email content
   - Email address validation
   - Queued to `message_queue:email`

### Flow Steps Validated

For each message type, the test validates:

#### Step 1: API Send
- ✅ HTTP POST returns 201 Created
- ✅ Message ID is returned
- ✅ Initial status is "pending"
- ✅ Direction is "outbound"

#### Step 2: Database Storage
- ✅ Message can be retrieved via API
- ✅ All fields are correctly stored
- ✅ Timestamps are set
- ✅ Conversation is created/linked

#### Step 3: Redis Queue
- ✅ Message is added to correct queue
- ✅ Queue length increases
- ✅ Message data is properly serialized

#### Steps 4-7: Worker Processing
- ✅ Worker dequeues message
- ✅ Provider is selected
- ✅ Message status changes to "sending"
- ✅ Message status changes to "sent"
- ✅ Processing completes within timeout

#### Step 8: Status & Events
- ✅ Final status is verified
- ✅ Timestamps are updated (sent_at, delivered_at)
- ✅ Events are recorded
- ✅ Provider information is stored

### Webhook Testing

Additionally tests:

- **Twilio Webhook** - Inbound SMS/MMS processing
- **SendGrid Webhook** - Inbound email processing

## Test Output

The test provides detailed, color-coded output:

```
═══════════════════════════════════════════
   Message Flow Integration Test Suite   
═══════════════════════════════════════════

Testing SMS Message...
────────────────────────────────────────────

Step 1: Sending message via REST API...
  ✓ Message sent successfully
  Message ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890
  Status: pending
  Direction: outbound

Step 2: Verifying message stored in PostgreSQL...
  ✓ Message found in database
  From: +15551234567
  To: +15559876543
  Type: sms
  Created: 2024-01-15T10:30:00Z

Step 3: Checking message queued in Redis...
  ✓ Queue 'message_queue:sms' exists
  Queue length: 1
  Last message ID: 1234567890-0

Steps 4-7: Monitoring worker processing...
  Waiting for worker to process message...
  ✓ Message processed!
  Final status: sent
  Processing time: 2.34s
  Provider: twilio

Step 8: Verifying status updates and events...
  ✓ Status verified
  Current status: sent
  Created at: 2024-01-15T10:30:00Z
  Sent at: 2024-01-15T10:30:02Z
  Events recorded: 3
    - CREATED
    - SENT
    - DELIVERED
```

## Test Summary

At the end, a summary table shows all test results:

```
┌─────────────────────────────────────────────────┐
│         Message Flow Test Results               │
├─────────────┬────────┬──────────────┬───────────┤
│ Test        │ Status │ Steps Passed │ Msg ID    │
├─────────────┼────────┼──────────────┼───────────┤
│ SMS Message │   ✓    │     5/5      │ a1b2c3d4  │
│ MMS Message │   ✓    │     5/5      │ e5f6g7h8  │
│ Email Msg   │   ✓    │     5/5      │ i9j0k1l2  │
└─────────────┴────────┴──────────────┴───────────┘

✓ All tests passed!
```

## Troubleshooting

### Worker Not Running

**Symptom**: Tests timeout at Step 4-7 with message:
```
⚠ Worker processing timeout
Note: Worker might not be running
```

**Cause**: The worker is required for async processing (default mode)

**Solution**: Start the worker in a separate terminal:
```bash
make worker

# Or if using Python directly:
python -m app.workers.message_processor
```

**Why this happens**: The system uses async mode by default, which requires the worker to process messages from Redis queues.

### API Not Running

**Symptom**: Connection error when setting up
```
✗ API health check failed: Connection refused
```

**Solution**: Start the API:
```bash
make run-bg
```

### Redis Not Running

**Symptom**: Redis connection error
```
✗ Redis is not running
```

**Solution**: Start Redis:
```bash
docker compose up -d redis
```

### Database Not Initialized

**Symptom**: Database errors or messages not found
```
✗ Message not found in database
```

**Solution**: Run migrations:
```bash
make migrate
```

### Dependencies Not Installed

**Symptom**: Import errors
```
ModuleNotFoundError: No module named 'httpx'
```

**Solution**: Install dev dependencies:
```bash
pip install -r requirements-dev.txt
```

Or let the script install them automatically:
```bash
./bin/test_flow.sh
```

## Manual Testing

You can also manually test each step:

### 1. Send a Message

```bash
curl -X POST http://localhost:8080/api/v1/messages/send \
  -H "Content-Type: application/json" \
  -d '{
    "from": "+15551234567",
    "to": "+15559876543",
    "type": "sms",
    "body": "Test message"
  }'
```

### 2. Check Database

```bash
# Get message by ID
curl http://localhost:8080/api/v1/messages/{message_id}
```

### 3. Check Redis Queue

```bash
# Access Redis CLI
make redis-cli

# Check queue length
XLEN message_queue:sms

# View queue messages
XRANGE message_queue:sms - + COUNT 10
```

### 4. Monitor Worker Logs

```bash
# If worker is running in foreground
# Check the terminal output

# If using Docker
docker compose logs -f worker

# If using make worker in background
tail -f logs/worker.log
```

### 5. Check Message Status

```bash
# Poll for status changes
curl http://localhost:8080/api/v1/messages/{message_id}
```

## Advanced Usage

### Test Specific Message Type

You can modify `test_message_flow.py` to test only specific message types:

```python
test_messages = [
    {
        "name": "SMS Message Only",
        "data": {
            "from": "+15551234567",
            "to": "+15559876543",
            "type": "sms",
            "body": "Test SMS"
        }
    }
]
```

### Adjust Timeouts

Modify the timeout in the script if your worker is slow:

```python
max_wait = 60  # Wait up to 60 seconds instead of 30
```

### Monitor Redis in Real-Time

Use Redis CLI to monitor in real-time:

```bash
redis-cli MONITOR
```

Then run the test in another terminal to see all Redis operations.

## Integration with CI/CD

Add to your CI pipeline:

```yaml
# .github/workflows/test.yml
- name: Run Message Flow Tests
  run: |
    docker compose up -d
    make migrate
    make run-bg &
    make worker &
    sleep 5
    make test-flow
```

## Performance Metrics

The test tracks:

- **API Response Time**: Time to accept and queue message
- **Queue Latency**: Time message spends in queue
- **Processing Time**: Time from dequeue to sent status
- **End-to-End Time**: Total time from API call to sent status

Example output:
```
Processing time: 2.34s
Queue latency: 0.45s
API response: 0.12s
Total E2E: 2.91s
```

## See Also

- [QUICK_START.md](./QUICK_START.md) - Architecture and system design
- [ARCHITECTURE.md](./ARCHITECTURE.md) - Detailed architecture documentation
- [RUN_GUIDE.md](./RUN_GUIDE.md) - Running services guide
- [bin/test.sh](./bin/test.sh) - Simple API test script

