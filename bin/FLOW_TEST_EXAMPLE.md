# Message Flow Test - Example Output

This document shows example output from running `make test-flow`.

## Successful Test Run

```
=========================================
Message Flow Integration Test
=========================================

Checking dependencies...
✓ Dependencies OK

Checking services...
✓ API is running
✓ Redis is running

Running message flow tests...

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
  Created: 2024-01-15T10:30:00.123456Z

Step 3: Checking message queued in Redis...
  ✓ Queue 'message_queue:sms' exists
  Queue length: 1
  Last message ID: 1705318200000-0

Steps 4-7: Monitoring worker processing...
  Monitoring for up to 30 seconds...
  Waiting for worker to process message... ━━━━━━━━━━━━━━━━━━━ 100% 
  ✓ Message processed!
  Final status: sent
  Processing time: 2.34s
  Provider: twilio
  Queue length changed: 1 → 0

Step 8: Verifying status updates and events...
  ✓ Status verified
  Current status: sent
  Created at: 2024-01-15T10:30:00.123456Z
  Sent at: 2024-01-15T10:30:02.456789Z
  Delivered at: None
  Events recorded: 3
    - CREATED
    - SENT
    - DELIVERED

Testing MMS Message...
────────────────────────────────────────────

Step 1: Sending message via REST API...
  ✓ Message sent successfully
  Message ID: b2c3d4e5-f6g7-8901-bcde-f12345678901
  Status: pending
  Direction: outbound

Step 2: Verifying message stored in PostgreSQL...
  ✓ Message found in database
  From: +15551234567
  To: +15559876543
  Type: mms
  Created: 2024-01-15T10:30:05.123456Z

Step 3: Checking message queued in Redis...
  ✓ Queue 'message_queue:mms' exists
  Queue length: 1
  Last message ID: 1705318205000-0

Steps 4-7: Monitoring worker processing...
  Monitoring for up to 30 seconds...
  Waiting for worker to process message... ━━━━━━━━━━━━━━━━━━━ 100%
  ✓ Message processed!
  Final status: sent
  Processing time: 2.12s
  Provider: twilio
  Queue length changed: 1 → 0

Step 8: Verifying status updates and events...
  ✓ Status verified
  Current status: sent
  Created at: 2024-01-15T10:30:05.123456Z
  Sent at: 2024-01-15T10:30:07.234567Z
  Delivered at: None
  Events recorded: 3
    - CREATED
    - SENT
    - DELIVERED

Testing Email Message...
────────────────────────────────────────────

Step 1: Sending message via REST API...
  ✓ Message sent successfully
  Message ID: c3d4e5f6-g7h8-9012-cdef-012345678901
  Status: pending
  Direction: outbound

Step 2: Verifying message stored in PostgreSQL...
  ✓ Message found in database
  From: sender@example.com
  To: recipient@example.com
  Type: email
  Created: 2024-01-15T10:30:10.123456Z

Step 3: Checking message queued in Redis...
  ✓ Queue 'message_queue:email' exists
  Queue length: 1
  Last message ID: 1705318210000-0

Steps 4-7: Monitoring worker processing...
  Monitoring for up to 30 seconds...
  Waiting for worker to process message... ━━━━━━━━━━━━━━━━━━━ 100%
  ✓ Message processed!
  Final status: sent
  Processing time: 1.98s
  Provider: sendgrid
  Queue length changed: 1 → 0

Step 8: Verifying status updates and events...
  ✓ Status verified
  Current status: sent
  Created at: 2024-01-15T10:30:10.123456Z
  Sent at: 2024-01-15T10:30:12.123456Z
  Delivered at: None
  Events recorded: 3
    - CREATED
    - SENT
    - DELIVERED

Testing Webhook Flow...
────────────────────────────────────────────

Testing Twilio webhook...
  ✓ Twilio webhook processed
  Response: {'status': 'success', 'message_id': 'd4e5f6g7-h8i9-0123-defg-123456789012'}

Testing SendGrid webhook...
  ✓ SendGrid webhook processed
  Response: {'status': 'success', 'message_id': 'e5f6g7h8-i9j0-1234-efgh-234567890123'}

═══════════════════════════════════════════
           Test Summary                   
═══════════════════════════════════════════

╭─────────────────────────────────────────────────────────╮
│           Message Flow Test Results                     │
├──────────────┬──────────┬──────────────┬────────────────┤
│ Test         │ Status   │ Steps Passed │ Message ID     │
├──────────────┼──────────┼──────────────┼────────────────┤
│ SMS Message  │    ✓     │     5/5      │ a1b2c3d4       │
│ MMS Message  │    ✓     │     5/5      │ b2c3d4e5       │
│ Email Msg    │    ✓     │     5/5      │ c3d4e5f6       │
└──────────────┴──────────┴──────────────┴────────────────┘

✓ All tests passed!

Check logs for more details: logs/app.log

=========================================
Message Flow Tests Complete!
=========================================

Additional commands:
  make worker          - Start background worker
  make app-logs        - View application logs
  make redis-cli       - Access Redis CLI
  make db-shell        - Access PostgreSQL shell
```

## Test Run With Worker Not Running

```
=========================================
Message Flow Integration Test
=========================================

Checking dependencies...
✓ Dependencies OK

Checking services...
✓ API is running
✓ Redis is running
⚠ Worker may not be running
  For full flow testing, start worker with: make worker
  (Tests will still run but may timeout on worker processing steps)

Running message flow tests...

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
  Created: 2024-01-15T10:30:00.123456Z

Step 3: Checking message queued in Redis...
  ✓ Queue 'message_queue:sms' exists
  Queue length: 1
  Last message ID: 1705318200000-0

Steps 4-7: Monitoring worker processing...
  Monitoring for up to 30 seconds...
  Waiting for worker (status: pending)... ━━━━━━━━━━━━━━━━━━━ 100%
  ⚠ Worker processing timeout
  Note: Worker might not be running

Step 8: Verifying status updates and events...
  ✓ Status verified
  Current status: pending
  Created at: 2024-01-15T10:30:00.123456Z
  Sent at: None
  Delivered at: None
  Events recorded: 1
    - CREATED

[Similar output for MMS and Email...]

═══════════════════════════════════════════
           Test Summary                   
═══════════════════════════════════════════

╭─────────────────────────────────────────────────────────╮
│           Message Flow Test Results                     │
├──────────────┬──────────┬──────────────┬────────────────┤
│ Test         │ Status   │ Steps Passed │ Message ID     │
├──────────────┼──────────┼──────────────┼────────────────┤
│ SMS Message  │    ✗     │     4/5      │ a1b2c3d4       │
│ MMS Message  │    ✗     │     4/5      │ b2c3d4e5       │
│ Email Msg    │    ✗     │     4/5      │ c3d4e5f6       │
└──────────────┴──────────┴──────────────┴────────────────┘

⚠ Some tests failed or timed out

Common issues:
  • Worker not running: Start with 'make worker' or 'python -m app.workers.message_processor'
  • Database not initialized: Run 'make migrate'
  • Redis not running: Start with 'docker compose up -d redis'

Check logs for more details: logs/app.log

=========================================
Some tests failed or timed out
=========================================

Additional commands:
  make worker          - Start background worker
  make app-logs        - View application logs
  make redis-cli       - Access Redis CLI
  make db-shell        - Access PostgreSQL shell
```

## Usage

```bash
# Run the test
make test-flow

# Or directly
./bin/test_flow.sh

# Or just the Python script
python3 ./bin/test_message_flow.py
```

## What to Look For

### ✅ Successful Test Indicators

1. All steps show ✓ green checkmarks
2. Message status changes from `pending` → `sending` → `sent`
3. Processing time is reasonable (1-5 seconds)
4. Queue length changes (increases then decreases)
5. Events are recorded for each state transition
6. Final summary shows all tests passed

### ⚠️ Warning Indicators

1. Worker processing timeout
   - **Cause**: Worker not running or slow
   - **Fix**: Start worker with `make worker`

2. Queue length doesn't decrease
   - **Cause**: Worker not processing queue
   - **Fix**: Check worker logs, restart worker

3. Message stuck in "pending" status
   - **Cause**: Not queued or worker not picking up
   - **Fix**: Check Redis connection and worker

### ❌ Failure Indicators

1. API connection failed
   - **Fix**: Start API with `make run-bg`

2. Redis connection failed
   - **Fix**: Start Redis with `docker compose up -d redis`

3. Database errors
   - **Fix**: Run migrations with `make migrate`

4. HTTP 500 errors
   - **Fix**: Check API logs with `make app-logs`

## Monitoring During Test

### Terminal 1: Run Test
```bash
make test-flow
```

### Terminal 2: Watch API Logs
```bash
make app-logs
```

### Terminal 3: Watch Worker Logs
```bash
# If worker running via make worker
tail -f logs/worker.log

# If worker in Docker
docker compose logs -f worker
```

### Terminal 4: Monitor Redis
```bash
redis-cli MONITOR
```

This gives you a complete view of the message flow in real-time!

