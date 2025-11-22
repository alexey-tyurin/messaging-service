# Test Scripts Guide

This directory contains various test scripts for the messaging service.

## Quick Reference

| Command | Script | What It Tests | Duration |
|---------|--------|---------------|----------|
| `make test-flow` | `test_flow.sh` | **Complete message flow through Redis queues** | 10-15s |
| `make test` | `test.sh` | Basic API endpoints with curl | 5-10s |
| `make test-unit` | pytest | Unit tests | 1-2s |
| `make test-integration` | pytest | API integration tests | 3-5s |

## Message Flow Test (Recommended)

### Purpose
Tests the complete 8-step message flow as described in QUICK_START.md:
1. Client sends message via REST API
2. Message validated and stored in PostgreSQL
3. Queued in Redis for async processing
4. Worker picks up message from queue
5. Provider selected based on message type
6. Message sent through provider API
7. Status updated and events recorded
8. Webhooks processed for delivery confirmations

### Usage

```bash
# Run complete flow test
make test-flow
```

### Prerequisites

All services must be running:
```bash
docker compose up -d postgres redis  # Start DB and Redis
make run-bg                          # Start API
make worker                          # Start worker (IMPORTANT!)
```

### What It Tests

- ✅ SMS message flow
- ✅ MMS message flow
- ✅ Email message flow
- ✅ Redis queue operations (enqueue/dequeue)
- ✅ Worker processing
- ✅ Status transitions (pending → sending → sent)
- ✅ Event recording
- ✅ Twilio webhooks
- ✅ SendGrid webhooks

### Output

Beautiful, color-coded output with:
- ✓ Green checkmarks for success
- ✗ Red X for failures
- ⚠ Yellow warnings
- Progress bars for monitoring
- Summary table at the end

### Documentation
- Full guide: [../MESSAGE_FLOW_TESTING.md](../MESSAGE_FLOW_TESTING.md)
- Example output: [FLOW_TEST_EXAMPLE.md](./FLOW_TEST_EXAMPLE.md)

---

## Basic API Test

### Purpose
Quick smoke tests for API endpoints using curl.

### Usage

```bash
# Run API tests
make test

# Or directly
./bin/test.sh
```

### What It Tests

- Health endpoints
- Send message endpoints (SMS/MMS/Email)
- List messages
- Get specific message
- List conversations
- Search conversations
- Webhook endpoints
- Rate limiting
- Metrics endpoint

### Output
Simple pass/fail for each endpoint test.

---

## Unit Tests

### Purpose
Test individual functions and classes in isolation.

### Usage

```bash
# Run all unit tests
make test-unit

# Run specific test file
pytest tests/unit/test_message_service.py -v

# Run with coverage
pytest tests/unit -v --cov=app --cov-report=html
```

### What It Tests
- Service layer business logic
- Database models
- Redis operations
- Provider selection
- Message validation

---

## Integration Tests

### Purpose
Test API endpoints with real database.

### Usage

```bash
# Run all integration tests
make test-integration

# Run specific test
pytest tests/integration/test_api.py::test_send_message_endpoint -v
```

### What It Tests
- Complete API workflows
- Database interactions
- Request/response validation
- Error handling

---

## Choosing the Right Test

### When to Use Message Flow Test (`make test-flow`)

✅ Use when you want to:
- Validate complete end-to-end flow
- Test Redis queue integration
- Verify worker processing
- Check status transitions over time
- Test the full message lifecycle
- Debug production-like issues

**Example scenarios:**
- "Is the worker picking up messages from the queue?"
- "How long does it take for a message to be sent?"
- "Are webhooks being processed correctly?"

### When to Use API Test (`make test`)

✅ Use when you want to:
- Quick smoke test of API
- Verify endpoints are responding
- Test without worker
- Check basic functionality

**Example scenarios:**
- "Is the API up and responding?"
- "Can I send a message?"
- "Are the endpoints configured correctly?"

### When to Use Unit Tests (`make test-unit`)

✅ Use when you want to:
- Test specific functions
- Verify business logic
- Check error handling
- Fast feedback during development

**Example scenarios:**
- "Does the provider selection logic work?"
- "Is message validation correct?"
- "Do my database queries work?"

### When to Use Integration Tests (`make test-integration`)

✅ Use when you want to:
- Test API with database
- Verify request/response formats
- Check authorization
- Test multiple related operations

**Example scenarios:**
- "Does the message creation workflow work?"
- "Can I retrieve a conversation?"
- "Is pagination working?"

---

## Test Comparison Matrix

| Feature | Flow Test | API Test | Unit Test | Integration Test |
|---------|-----------|----------|-----------|------------------|
| Tests Redis queues | ✅ | ❌ | ❌ | ❌ |
| Tests worker | ✅ | ❌ | ❌ | ❌ |
| Tests status transitions | ✅ | ❌ | ❌ | ❌ |
| Tests API endpoints | ✅ | ✅ | ❌ | ✅ |
| Tests business logic | ✅ | ❌ | ✅ | ✅ |
| Needs worker running | ✅ | ❌ | ❌ | ❌ |
| Needs API running | ✅ | ✅ | ❌ | ❌ |
| Speed | Medium | Fast | Fastest | Fast |
| Coverage | E2E | API | Functions | API+DB |

---

## Running All Tests

### Development Workflow

```bash
# 1. Fast feedback during development
make test-unit

# 2. Test API changes
make test-integration

# 3. Quick smoke test
make test

# 4. Complete validation before commit
make test-flow
```

### Before Committing

```bash
# Run all tests
make test-unit && make test-integration && make test && make test-flow

# Also run linting
make lint
```

### CI/CD Pipeline

```yaml
# .github/workflows/test.yml
- name: Unit Tests
  run: make test-unit

- name: Integration Tests
  run: make test-integration

- name: Message Flow Tests
  run: |
    make run-bg &
    make worker &
    sleep 5
    make test-flow
```

---

## Troubleshooting

### "Worker processing timeout"

**Problem**: Message flow test times out waiting for worker.

**Solution**:
```bash
# Check if worker is running
pgrep -f message_processor

# If not, start it
make worker
```

### "API connection failed"

**Problem**: Cannot connect to API.

**Solution**:
```bash
# Check if API is running
curl http://localhost:8080/health

# If not, start it
make run-bg
```

### "Redis connection failed"

**Problem**: Cannot connect to Redis.

**Solution**:
```bash
# Check if Redis is running
redis-cli ping

# If not, start it
docker compose up -d redis
```

### "Import errors in tests"

**Problem**: Missing dependencies.

**Solution**:
```bash
# Install dev dependencies
pip install -r requirements-dev.txt
```

### "Database errors"

**Problem**: Database not initialized or migrations not run.

**Solution**:
```bash
# Run migrations
make migrate

# Or reset database
make db-reset
```

---

## Tips

### Monitor Tests in Real-Time

Open multiple terminals:

**Terminal 1**: Run test
```bash
make test-flow
```

**Terminal 2**: Watch API logs
```bash
make app-logs
```

**Terminal 3**: Monitor Redis
```bash
redis-cli MONITOR
```

**Terminal 4**: Check database
```bash
make db-shell
```

### Debug Failed Tests

```bash
# Run with more verbose output
pytest tests/ -vv

# Run specific test
pytest tests/unit/test_message_service.py::test_send_message -vv

# Run with debugger on failure
pytest tests/ --pdb
```

### Performance Testing

```bash
# Measure test performance
time make test-flow

# Profile Python tests
pytest tests/ --profile
```

---

## File Structure

```
bin/
├── README_TESTS.md           # This file
├── test_flow.sh              # Message flow test (bash wrapper)
├── test_message_flow.py      # Message flow test (Python implementation)
├── test.sh                   # Basic API test
├── FLOW_TEST_EXAMPLE.md      # Example output from flow test
├── start.sh                  # Start application
└── stop.sh                   # Stop application

tests/
├── unit/                     # Unit tests
│   ├── test_message_service.py
│   └── test_redis_caching.py
├── integration/              # Integration tests
│   └── test_api.py
└── conftest.py              # Pytest fixtures
```

---

## See Also

- [MESSAGE_FLOW_TESTING.md](../MESSAGE_FLOW_TESTING.md) - Complete flow testing guide
- [QUICK_START.md](../QUICK_START.md) - Getting started guide
- [RUN_GUIDE.md](../RUN_GUIDE.md) - Running and managing services
- [ARCHITECTURE.md](../ARCHITECTURE.md) - System architecture

