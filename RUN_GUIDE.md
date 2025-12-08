# Running the Messaging Service - Detailed Operations Guide

This guide provides detailed instructions for running, managing, and troubleshooting the messaging service in different environments.

---

## Table of Contents

- [Overview](#overview)
- [System Requirements](#system-requirements)
- [Starting the System](#starting-the-system)
- [Running Modes](#running-modes)
- [Stopping the System](#stopping-the-system)
- [Common Scenarios](#common-scenarios)
- [Management Commands](#management-commands)
- [Monitoring & Logs](#monitoring--logs)
- [Troubleshooting](#troubleshooting)
- [Synchronous Mode](#synchronous-mode-not-recommended)
- [Production Deployment](#production-deployment)

---

## Overview

### Two Services Required

The messaging service requires **both** components to function:

1. **API Server** (`make run`)
   - Accepts HTTP requests
   - Validates and stores messages in PostgreSQL
   - Queues messages to Redis
   - Returns immediately (~50ms response time)

2. **Background Worker** (`make worker`) **← REQUIRED!**
   - Polls Redis queues for new messages
   - Processes messages through providers (Twilio, SendGrid)
   - Updates message status in database
   - Handles retries and errors

**Default Configuration:**
- Uses **async processing** (`SYNC_MESSAGE_PROCESSING=false`)
- Messages queued to Redis for worker processing
- Production-ready out of the box
- Worker is **mandatory** for messages to be sent

### Architecture Flow

```
Client Request
     ↓
API Server (validates, saves, queues)
     ↓
Redis Queue (message_queue:sms/mms/email)
     ↓
Background Worker (dequeues, processes)
     ↓
Provider (Twilio/SendGrid)
     ↓
Database Update (status: pending → sending → sent)
```

---

## System Requirements

### Software
- Python 3.11+ with conda environment (`py311`)
- Docker and Docker Compose
- PostgreSQL 15+ (via Docker)
- Redis 7+ (via Docker)

### Ports
- **8080** - API Server
- **5432** - PostgreSQL
- **6379** - Redis
- **9090** - Prometheus (optional)
- **3000** - Grafana (optional)

---

## Starting the System

### Complete Startup Sequence

```bash
# 1. Activate conda environment
conda activate py311

# 2. Navigate to project
cd messaging-service

# 3. Start Docker services
docker compose up -d postgres redis

# 4. Verify Docker services are healthy
docker compose ps
# Expected: Both show "Up (healthy)"

# 5. Run database migrations (first time only)
make migrate

# 6. Start API server
make run-bg  # Background mode

# 7. Start worker (REQUIRED!)
make worker &  # Background mode

# 8. Verify everything is running
make status
curl http://localhost:8080/health
```

### Alternative: Docker Everything

```bash
# Start all services in Docker containers
docker compose up -d

# This starts:
# - PostgreSQL
# - Redis
# - API (in container)
# - Worker (in container)
# - Prometheus
# - Grafana
```

---

## Running Modes

### Foreground Mode (Recommended for Development)

**Advantages:**
- See logs in real-time
- Easy to stop (Ctrl+C)
- Good for debugging

**Setup:**

Terminal 1 (API):
```bash
conda activate py311
make run
```

Terminal 2 (Worker):
```bash
conda activate py311
make worker
```

Terminal 3 (Commands):
```bash
conda activate py311
# Run your commands here
curl http://localhost:8080/health
make test
```

### Background Mode (For Testing/Scripting)

**Advantages:**
- Frees up terminal
- Can run multiple commands
- Good for automated testing

**Setup:**

```bash
conda activate py311

# Start API in background
make run-bg

# Start worker in background
make worker &

# Now terminal is free
curl http://localhost:8080/health
make test

# View logs when needed
make logs

# Stop when done
make stop
```

### Docker Mode (Production-Like)

**Advantages:**
- Closest to production
- Isolated environment
- Easy cleanup

**Setup:**

```bash
# Start everything
docker compose up -d

# View logs
docker compose logs -f app worker

# Stop everything
docker compose down
```

---

## Stopping the System

### Using Make (Recommended)

```bash
# Stops both API and worker
make stop
```

This will:
- Kill all processes on port 8080
- Stop uvicorn processes
- Stop worker processes
- Stop gunicorn processes (if any)

### Manual Stop (Foreground Mode)

If running in foreground, press `Ctrl+C` in each terminal:
- Terminal 1 (API): `Ctrl+C`
- Terminal 2 (Worker): `Ctrl+C`

### Direct Script

```bash
./bin/stop.sh
```

### Emergency Stop

If `make stop` doesn't work:

```bash
# Kill everything on port 8080
kill -9 $(lsof -ti:8080)

# Or stop all Python services
pkill -f "uvicorn|app.main|message_processor"

# Or nuclear option
killall -9 python
```

---

## Common Scenarios

### Scenario 1: Active Development (3 Terminals)

**Best for:** Writing code, seeing logs, running commands

```bash
# Terminal 1: API (foreground)
conda activate py311
make run

# Terminal 2: Worker (foreground)
conda activate py311
make worker

# Terminal 3: Development
conda activate py311
# Edit code, run tests, make API calls
make test
curl http://localhost:8080/api/v1/messages/
```

**Workflow:**
1. Make code changes
2. Save file (auto-reloads with --reload flag)
3. Test changes in Terminal 3
4. See logs in Terminal 1 & 2

### Scenario 2: Quick Testing (1 Terminal)

**Best for:** Running tests, scripting, CI/CD

```bash
conda activate py311

# Start everything in background
docker compose up -d postgres redis
make run-bg
make worker &

# Run tests
make test
make test-flow

# Check results
curl http://localhost:8080/api/v1/messages/

# Stop when done
make stop
```

### Setup Integration Testing
**Prerequisites:**
Before running integration tests, make sure you have the following services running via Docker Compose:
- PostgreSQL
- Redis

For full integration verification (ensuring the background worker processes messages), you should also run the service and worker:
```bash
# Start API
make run-bg
# Start Worker
make worker &
```

**Configuration:**
By default, the `TEST_ENV` variable is set to `integration` in `app/core/config.py`. This means tests will attempt to connect to the real services provided by Docker Compose. If you wish to run unit tests with an in-memory database, you can override this by setting `TEST_ENV=unit`.

**Running Tests:**
To run integration tests (default behavior):
```bash
# Ensure services are up
docker compose up -d postgres redis

# Run tests
pytest tests/integration/test_api.py
```

To run unit tests (using in-memory SQLite):
```bash
TEST_ENV=unit pytest tests/unit/
```

### Scenario 3: Integration Testing

**Best for:** Testing complete message flow

```bash
# Terminal 1: Start services in background
conda activate py311
docker compose up -d postgres redis
make run-bg
make worker &

# Terminal 2: Run integration tests
conda activate py311
make test-flow

# This validates:
# - API accepts message
# - Message queued to Redis
# - Worker processes message
# - Status changes (pending → sent)
# - Database updated correctly
```

### Scenario 4: Production Simulation

**Best for:** Testing deployment, load testing

```bash
# Use Docker for everything
docker compose up -d

# Run load tests
locust -f tests/load/locustfile.py --host=http://localhost:8080

# Monitor metrics
open http://localhost:9090  # Prometheus
open http://localhost:3000  # Grafana

# View logs
docker compose logs -f app worker

# Stop when done
docker compose down
```

---

## Management Commands

### Starting Services

| Command | Description | Mode | Blocks Terminal? |
|---------|-------------|------|------------------|
| `make run` | Start API | Foreground | ✅ Yes |
| `make run-bg` | Start API | Background | ❌ No |
| `make worker` | Start worker | Foreground | ✅ Yes |
| `make worker &` | Start worker | Background | ❌ No |
| `./bin/start.sh` | Start API | Foreground | ✅ Yes |
| `docker compose up -d` | Start all | Docker | ❌ No |

### Stopping Services

| Command | Description | What It Stops |
|---------|-------------|---------------|
| `make stop` | Stop all services | API + Worker + All Python |
| `./bin/stop.sh` | Stop all services | API + Worker + All Python |
| `docker compose down` | Stop Docker services | All Docker containers |
| `Ctrl+C` | Stop foreground process | Current process only |

### Management

| Command | Description | Output                            |
|---------|-------------|-----------------------------------|
| `make status` | Check API status | PID and port info                 |
| `make logs` | View application logs | Real-time logs                    |
| `make restart-app` | Restart API only | Stops and starts API              |
| `make migrate` | Run DB migrations | Creates/updates tables            |
| `make db-reset` | Reset DB | Drops schema / Creates new schema |
| `make test` | Run all tests | Test results                      |
| `make test-flow` | Run flow tests | Flow validation results           |

### Docker Management

| Command | Description |
|---------|-------------|
| `make docker-up` | Start Docker services |
| `make docker-down` | Stop Docker services |
| `make docker-logs` | View Docker logs |
| `docker compose ps` | Check Docker status |
| `docker compose logs -f app` | Follow API logs |
| `docker compose logs -f worker` | Follow worker logs |

---

## Monitoring & Logs

### Viewing Logs

**Application Logs:**
```bash
# Real-time logs (all)
make logs

# Or directly
tail -f logs/app.log

# Worker logs (if running in background)
tail -f logs/worker.log

# Docker logs
docker compose logs -f app
docker compose logs -f worker
```

**Filter Logs:**
```bash
# Only errors
tail -f logs/app.log | grep ERROR

# Only specific message ID
tail -f logs/app.log | grep "message_id=abc123"

# Only requests
tail -f logs/app.log | grep "Request"
```

### Health Checks

```bash
# Basic health
curl http://localhost:8080/health
# Expected: {"status":"healthy","timestamp":"..."}

# Readiness check (includes dependencies)
curl http://localhost:8080/ready

# Metrics
curl http://localhost:8080/metrics
```

### Monitoring Services

**Check if services are running:**
```bash
# API status
make status

# Check port 8080
lsof -i:8080

# Check all Python processes
ps aux | grep -E "uvicorn|message_processor"

# Docker services
docker compose ps
```

**Redis Queue Monitoring:**
```bash
# Access Redis CLI
docker exec -it $(docker ps -q -f name=redis) redis-cli

# Check queue lengths
XLEN message_queue:sms
XLEN message_queue:mms
XLEN message_queue:email

# View messages in queue
XRANGE message_queue:sms - + COUNT 10

# Monitor in real-time
MONITOR
```

**Database Monitoring:**
```bash
# Access PostgreSQL
docker exec -it $(docker ps -q -f name=postgres) psql -U messaging_user -d messaging_service

# Check message count
SELECT COUNT(*) FROM messages;

# Check pending messages
SELECT COUNT(*) FROM messages WHERE status = 'pending';

# Check recent messages
SELECT id, status, created_at FROM messages ORDER BY created_at DESC LIMIT 10;
```

### Metrics

**Prometheus:**
- URL: http://localhost:9090
- Query examples:
  - `message_sent_total` - Total messages sent
  - `message_failed_total` - Total failures
  - `api_request_duration_seconds` - Request latency

**Grafana:**
- URL: http://localhost:3000
- Username: admin
- Password: admin

---

## Troubleshooting

### Messages Stuck in "pending"

**Symptoms:**
- Messages never change from "pending" status
- Queue length keeps growing
- No worker logs appearing

**Cause:** Worker is not running

**Solution:**
```bash

# Check if worker is running
ps aux | grep message_processor

# If not running, start it
make worker

# If running but not processing, restart it
make stop
make run-bg
make worker &
```

**Verification:**
```bash
# Check worker logs
tail -f logs/worker.log

# Should see:
# [INFO] Starting message processor...
# [INFO] Processing message from queue: message_queue:sms
```

### "Address already in use" (Port 8080)

**Symptoms:**
- Error starting API: "Address already in use"
- `make run` fails immediately

**Solution:**
```bash
# Stop existing services
make stop

# Verify port is free
lsof -i:8080
# Should return nothing

# Start again
make run
```

**Alternative:**
```bash
# Force kill everything on port 8080
kill -9 $(lsof -ti:8080)

# Start again
make run
```

### PostgreSQL Connection Failed

**Symptoms:**
- "PostgreSQL is not available"
- "Connection refused"
- Database errors

**Solutions:**

1. **Check if PostgreSQL is running:**
   ```bash
   docker compose ps postgres
   # Should show "Up (healthy)"
   ```

2. **Start PostgreSQL:**
   ```bash
   docker compose up -d postgres
   
   # Wait for it to be healthy
   watch docker compose ps postgres
   ```

3. **Check logs:**
   ```bash
   docker compose logs postgres
   ```

4. **Check port:**
   ```bash
   lsof -i:5432
   # Should show docker process
   ```

5. **Restart if needed:**
   ```bash
   docker compose restart postgres
   ```

### Redis Connection Failed

**Symptoms:**
- "Redis is not available"
- "Connection refused"
- Queue errors

**Solutions:**

1. **Check if Redis is running:**
   ```bash
   docker compose ps redis
   # Should show "Up (healthy)"
   ```

2. **Start Redis:**
   ```bash
   docker compose up -d redis
   ```

3. **Test connection:**
   ```bash
   docker exec -it $(docker ps -q -f name=redis) redis-cli PING
   # Should return "PONG"
   ```

4. **Check port:**
   ```bash
   lsof -i:6379
   ```

### "FastAPI not found" or Import Errors

**Symptoms:**
- "ModuleNotFoundError: No module named 'fastapi'"
- Import errors when starting

**Solutions:**

1. **Activate conda environment:**
   ```bash
   conda activate py311
   ```

2. **Verify environment:**
   ```bash
   which python
   # Should show conda py311 path
   
   python --version
   # Should show Python 3.11+
   ```

3. **Reinstall dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

### API Returns 500 Errors

**Symptoms:**
- API responds with 500 Internal Server Error
- Errors in logs

**Debugging:**

1. **Check logs:**
   ```bash
   tail -f logs/app.log
   ```

2. **Check database connection:**
   ```bash
   docker compose ps postgres
   ```

3. **Check Redis connection:**
   ```bash
   docker compose ps redis
   ```

4. **Run migrations:**
   ```bash
   make migrate
   ```

5. **Restart services:**
   ```bash
   make stop
   docker compose restart postgres redis
   make run-bg
   make worker &
   ```

### Worker Crashes Immediately

**Symptoms:**
- Worker starts then exits
- No worker logs

**Debugging:**

1. **Run worker in foreground to see errors:**
   ```bash
   python -m app.workers.message_processor
   ```

2. **Common causes:**
   - Database not initialized: `make migrate`
   - Redis not running: `docker compose up -d redis`
   - Configuration error: Check environment variables
   - Port conflict: Check other services

3. **Check dependencies:**
   ```bash
   pip list | grep -E "fastapi|sqlalchemy|redis"
   ```

### Want to start with messages in queue from scratch

**Solution:**
```bash
# Clean up not processed messages
docker exec -it $(docker ps -q -f name=redis) redis-cli FLUSHALL
```
---

## ⚠️ Synchronous Mode (Not Recommended)

By default, the system uses **async processing** (production-ready). You can enable sync mode for **quick debugging only**.

### When to Use Sync Mode

**✅ Acceptable use cases:**
- Quick debugging when you don't want to run the worker
- Testing API validation logic only
- Rapid iteration on API endpoint logic

**❌ Do NOT use sync mode for:**
- **Integration tests** - Must test the real queue flow!
- **Production deployments** - Slow, doesn't scale, single point of failure
- **Load testing** - Cannot scale horizontally
- **CI/CD pipelines** - Should test production architecture
- **Any scenario requiring scalability** - Can't add workers

### How to Enable Sync Mode

```bash
# Set environment variable
export SYNC_MESSAGE_PROCESSING=true

# Restart API
make restart-app

# Now messages are processed immediately in API
# Worker is not needed in sync mode (but system is not production-ready)
```

### Behavior Differences

| Aspect | Async Mode (Default) | Sync Mode (Debug Only) |
|--------|---------------------|------------------------|
| **Processing** | Worker from queue | Immediate in API |
| **API Response Time** | ~50ms | ~2000ms |
| **Initial Status** | pending | sent |
| **Worker Required** | ✅ Yes | ❌ No |
| **Scalability** | Horizontal | None |
| **Production Ready** | ✅ Yes | ❌ No |
| **Integration Tests** | ✅ Tests real flow | ❌ Bypasses queue |

### Returning to Async Mode

**Always return to async mode after debugging:**

```bash
# Unset the variable
unset SYNC_MESSAGE_PROCESSING

# Restart API
make restart-app

# Start worker (REQUIRED!)
make worker
```

### Verification

**Check current mode:**
```bash
python3 -c "from app.core.config import settings; print(f'Async mode: {not settings.sync_message_processing}')"
```

**Expected behavior in async mode:**
```bash
# Send message
curl -X POST http://localhost:8080/api/v1/messages/send \
  -H "Content-Type: application/json" \
  -d '{"from":"+15551234567","to":"+15559876543","type":"sms","body":"Test"}'

# Response should show status: "pending" (not "sent"!)
# After 2-3 seconds, status should change to "sent"
```

See [SYNC_VS_ASYNC_PROCESSING.md](./SYNC_VS_ASYNC_PROCESSING.md) for detailed comparison.

---

## Production Deployment

### Docker Compose (Recommended)

```bash
# Production configuration
docker compose -f docker-compose.yml up -d

# This starts:
# - PostgreSQL (with persistence)
# - Redis (with persistence)
# - API (multiple instances behind load balancer)
# - Worker (multiple instances)
# - Prometheus (monitoring)
# - Grafana (dashboards)
```

### Environment Configuration

**Production environment variables:**
```bash
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO

# Database
POSTGRES_HOST=production-db.example.com
POSTGRES_PASSWORD=<strong-password>

# Redis
REDIS_HOST=production-redis.example.com

# Processing (keep async!)
SYNC_MESSAGE_PROCESSING=false

# Security
SECRET_KEY=<strong-secret-key>
ALLOWED_HOSTS=api.example.com

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_PERIOD=60
```

**Testing Rate Limiting:**
```bash
# Run the rate limiting test script
python tests/integration/test_rate_limiting.py

# Manual test with curl
for i in {1..110}; do
  curl -i http://localhost:8080/health 2>/dev/null | grep -E "HTTP|X-RateLimit"
done
```

**Rate Limit Response Headers:**
```
X-RateLimit-Limit: 100          # Max requests allowed
X-RateLimit-Remaining: 47       # Requests remaining in window
X-RateLimit-Reset: 60           # Window duration in seconds
```

**When Rate Limited (HTTP 429):**
```json
{
  "error": "Rate limit exceeded",
  "message": "Too many requests. Please try again later."
}
```

**Customizing Rate Limits:**
```bash
# More restrictive (10 requests per 10 seconds)
export RATE_LIMIT_REQUESTS=10
export RATE_LIMIT_PERIOD=10

# More permissive (1000 requests per 5 minutes)
export RATE_LIMIT_REQUESTS=1000
export RATE_LIMIT_PERIOD=300

# Disable rate limiting (not recommended for production)
export RATE_LIMIT_ENABLED=false
```

**Implementation Details:**
- Algorithm: Sliding window counter using Redis sorted sets
- Granularity: Per client IP + endpoint
- Distributed: Works across multiple API instances
- Resilient: Fails open if Redis unavailable
- Monitoring: Tracked in Prometheus metrics (`rate_limit_hits_total`)

### Scaling

**Horizontal scaling:**
```bash
# Scale API instances
docker compose up -d --scale app=3

# Scale worker instances
docker compose up -d --scale worker=5
```

### Monitoring

**Health checks:**
- Kubernetes: Use `/health` and `/ready` endpoints
- Docker: HEALTHCHECK in Dockerfile
- Load balancer: Health check on `/health`

**Metrics:**
- Prometheus scrapes `/metrics` endpoint
- Grafana dashboards for visualization
- Alerts on queue depth, error rate, latency

---

## Quick Reference

### Essential Commands

```bash
# Start everything (development)
conda activate py311
docker compose up -d postgres redis
make run-bg && make worker &

# Check status
make status
curl http://localhost:8080/health

# View logs
make logs

# Run tests
make test
make test-flow

# Stop everything
make stop
```

### Troubleshooting Checklist

- [ ] Conda environment activated (`conda activate py311`)
- [ ] Docker services running (`docker compose ps`)
- [ ] Database migrated (`make migrate`)
- [ ] API started (`make run` or `make run-bg`)
- [ ] **Worker started (`make worker`)** ← Most important!
- [ ] Health check passes (`curl http://localhost:8080/health`)
- [ ] No port conflicts (`lsof -i:8080`)

---

## Related Documentation

- [QUICK_START.md](./QUICK_START.md) - Quick start guide
- [SYNC_VS_ASYNC_PROCESSING.md](./SYNC_VS_ASYNC_PROCESSING.md) - Processing modes explained
- [MESSAGE_FLOW_TESTING.md](./MESSAGE_FLOW_TESTING.md) - Testing message flow
- [REDIS_QUEUE_VERIFICATION.md](./REDIS_QUEUE_VERIFICATION.md) - Queue verification
- [ARCHITECTURE.md](./ARCHITECTURE.md) - System architecture
- [PRD.md](./PRD.md) - Product requirements

---

**Remember: Always run both API and Worker!** 🚀
