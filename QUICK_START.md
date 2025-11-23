# Messaging Service - Quick Start Guide

A production-ready, distributed messaging service supporting SMS, MMS, Email, and extensible for Voice/Voicemail. Built with FastAPI, PostgreSQL, Redis, and designed for horizontal scalability.

## 🏗️ Architecture Highlights

- **Event-driven architecture** with async message processing via Redis queues
- **Microservices-ready** design with clear service boundaries
- **Provider abstraction** using Strategy pattern
- **Comprehensive observability** with metrics, logging, and tracing
- **Rate limiting** and circuit breakers for resilience
- **PostgreSQL** with proper indexing and migrations
- **Docker-ready** with multi-stage builds

## 📋 Core Features

### Messaging
- ✅ Unified API for SMS, MMS, and Email
- ✅ Automatic conversation threading
- ✅ Provider failover and retry logic
- ✅ Webhook processing for inbound messages
- ✅ Message status tracking and events
- ✅ Rate limiting per client
- ✅ Idempotency for message sending

### Production Ready
- ✅ Health checks and readiness probes
- ✅ Prometheus metrics integration
- ✅ Structured JSON logging
- ✅ OpenTelemetry tracing support
- ✅ Database connection pooling
- ✅ Redis connection management
- ✅ Graceful shutdown handling

---

## ⚠️ Important: Async Processing by Default

The system uses **asynchronous processing by default** (`SYNC_MESSAGE_PROCESSING=false`):
- Messages are queued to Redis
- Background worker processes messages from queues
- **Both API and Worker must be running**
- This is production-ready configuration

**Required Services:**
1. **API Server** - Accepts and queues messages
2. **Background Worker** - Processes messages from queues (**REQUIRED!**)

---

## 🚀 Quick Start (5 Steps)

### Prerequisites
- Python 3.11+ with conda environment (`py311`)
- Docker and Docker Compose
- PostgreSQL 15+ (via Docker)
- Redis 7+ (via Docker)

### Step 1: Activate Environment & Start Docker

```bash
# Activate conda environment
conda activate py311

# Navigate to project
cd messaging-service

# Start Docker services
docker compose up -d postgres redis

# Verify they're healthy
docker compose ps
# Should show postgres and redis as "Up (healthy)"
```

### Step 2: Run Database Migrations

```bash
make migrate
```

This creates all necessary database tables and indexes.

### Step 3: Start the API Server

```bash
# Foreground (recommended for development - see logs in terminal)
make run

# OR Background (frees terminal)
make run-bg
```

The API will start on http://localhost:8080

### Step 4: Start the Background Worker (REQUIRED!)

**⚠️ CRITICAL:** The worker is required for message processing!

```bash
# In a separate terminal
conda activate py311
cd messaging-service
make worker
```

**Or in background:**
```bash
make worker &
```

### Step 5: Verify Everything is Working

```bash
# Check API health
curl http://localhost:8080/health
# Expected: {"status":"healthy","timestamp":"..."}

# Send a test message
curl -X POST http://localhost:8080/api/v1/messages/send \
  -H "Content-Type: application/json" \
  -d '{
    "from": "+15551234567",
    "to": "+15559876543",
    "type": "sms",
    "body": "Hello from Hatch!"
  }'

# Should return status: "pending"
# Wait 2-3 seconds, message status will change to "sent"
```

---

## 📡 Available Endpoints

Once running, access:
- **API Documentation**: http://localhost:8080/docs
- **Health Check**: http://localhost:8080/health
- **Metrics**: http://localhost:8080/metrics
- **Prometheus**: http://localhost:9090 (if started via docker compose)
- **Grafana**: http://localhost:3000 (admin/admin)

---

## 🛑 Stopping the Service

```bash
# Stop all services (API + worker)
make stop
```

Or if running in foreground, press `Ctrl+C` in each terminal.

---

## 🔄 Restarting

```bash
# Restart API only (worker keeps running)
make restart-app
```

---

## 🧪 Testing

### Quick API Test
```bash
# Simple API smoke test
make test
```

### Complete Flow Test (Requires Worker!)
```bash
# Ensure worker is running first!
# Terminal 1: make worker

# Terminal 2: Run flow test
make test-flow
```

This validates the complete 8-step message flow:
1. API receives request
2. Message stored in PostgreSQL (status: pending)
3. Message queued to Redis
4. API returns immediately
5. Worker picks up from queue
6. Worker processes through provider
7. Status updated (pending → sending → sent)
8. Delivery confirmations processed

See [MESSAGE_FLOW_TESTING.md](./MESSAGE_FLOW_TESTING.md) for details.

### Unit Tests
```bash
pytest tests/unit -v --cov=app
```

### Integration Tests
```bash
pytest tests/integration -v
```

### Rate Limiting Tests
```bash
# Automated rate limiting test
make test-rate-limit

# Manual test
for i in {1..110}; do curl -i http://localhost:8080/health 2>/dev/null | grep -E "HTTP|X-RateLimit"; done
```

---

## ⚠️ Troubleshooting

### Messages Stuck in "pending"

**Symptom:** Messages never change from "pending" status

**Cause:** Worker is not running

**Solution:**
```bash
make worker  # Run in separate terminal
```

### "Address already in use" (Port 8080)

**Solution:**
```bash
make stop
make run
```

### "PostgreSQL is not available"

**Solution:**
```bash
docker compose up -d postgres
docker compose ps postgres  # Check status
```

### "Redis is not available"

**Solution:**
```bash
docker compose up -d redis
docker compose ps redis  # Check status
```

### "FastAPI not found"

**Solution:**
```bash
# Activate conda environment
conda activate py311
make run
```

For more troubleshooting, see [RUN_GUIDE.md](./RUN_GUIDE.md)

---

## 📊 Message Flow (Async Mode - Default)

```
1. Client → POST /api/v1/messages/send
2. API validates and saves to PostgreSQL (status: pending)
3. API adds message to Redis queue
4. API returns immediately (~50ms) with status: pending
5. Background worker dequeues message
6. Worker selects provider based on message type
7. Worker sends through provider API (Twilio/SendGrid)
8. Worker updates status (pending → sending → sent → delivered)
9. Webhooks processed for delivery confirmations
```

**Note:** Worker must be running for steps 5-8!

---

## 🔧 Configuration

### Environment Variables

The application uses environment variables for configuration:

```bash
# Database
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=messaging_user
POSTGRES_PASSWORD=messaging_password
POSTGRES_DB=messaging_service

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# Processing Mode (default: async)
SYNC_MESSAGE_PROCESSING=false  # async processing (recommended)

# Rate Limiting (default: enabled)
RATE_LIMIT_ENABLED=true        # enable/disable rate limiting
RATE_LIMIT_REQUESTS=100        # max requests per window
RATE_LIMIT_PERIOD=60           # time window in seconds

# Application
ENVIRONMENT=development
DEBUG=true
```

These are automatically set by the startup script when running locally.

---

## ⚠️ Synchronous Mode (Not Recommended)

By default, the system uses async processing (production-ready). You can enable sync mode for **quick debugging only**:

```bash
export SYNC_MESSAGE_PROCESSING=true
make restart-app
```

**⚠️ Important Limitations:**
- **Only for quick debugging** - messages processed immediately in API
- **NOT for integration tests** - doesn't test the real production flow
- **NOT for production** - slow (~2s API response), doesn't scale, single point of failure
- API responses are slow instead of fast
- Cannot scale horizontally
- Worker not needed (but system is not production-ready)

**When to use sync mode:**
- ✅ Quick debugging when you don't want to run the worker
- ✅ Testing API validation logic only

**When NOT to use sync mode:**
- ❌ Integration tests (must test the queue flow!)
- ❌ Production deployments
- ❌ Load testing
- ❌ CI/CD pipelines
- ❌ Any scenario requiring scalability

**Return to async mode:**
```bash
unset SYNC_MESSAGE_PROCESSING
make restart-app
make worker  # Remember to start worker!
```

See [SYNC_VS_ASYNC_PROCESSING.md](./SYNC_VS_ASYNC_PROCESSING.md) for detailed comparison.

---

## 📝 Development Commands

```bash
make run          # Start API (foreground)
make run-bg       # Start API (background)
make worker       # Start worker (REQUIRED!)
make stop         # Stop all services
make restart-app  # Restart API
make status       # Check API status
make logs         # View logs

make test         # Run tests
make test-flow    # Run complete flow tests
make lint         # Check code quality
make migrate      # Run database migrations
make db-reset     # Reset database: drop schema, create new schema

make docker-up    # Start all Docker services
make docker-down  # Stop all Docker services
```

### Essential Development Workflow

```bash
# Terminal 1: API
conda activate py311
make run

# Terminal 2: Worker (REQUIRED!)
conda activate py311
make worker

# Terminal 3: Development/Testing
conda activate py311
make test
curl http://localhost:8080/health
```

---

## 🐳 Docker Development (Full Stack)

Start everything in containers:

```bash
# Start all services (API, worker, PostgreSQL, Redis, Prometheus, Grafana)
docker compose up -d

# View logs
docker compose logs -f

# Stop all services
docker compose down
```

This is the closest to production deployment.

---

## 🎯 Performance Targets

- API Latency: p99 < 100ms
- Message Delivery: < 5 seconds end-to-end
- Throughput: 10,000 messages/second per instance
- Availability: 99.99% uptime
- Error Rate: < 0.1%

---


## 🔒 Rate Limiting

The service includes built-in API rate limiting using Redis for distributed rate limiting across multiple instances.

### How It Works

- **Algorithm**: Sliding window counter using Redis sorted sets
- **Granularity**: Per client IP + endpoint
- **Default Limits**: 100 requests per 60 seconds (per client/endpoint)
- **Response Headers**: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`
- **HTTP 429**: Returns when rate limit exceeded

### Configuration

Rate limiting can be configured via environment variables:

```bash
# Enable/disable rate limiting
RATE_LIMIT_ENABLED=true

# Number of requests allowed
RATE_LIMIT_REQUESTS=100

# Time window in seconds
RATE_LIMIT_PERIOD=60
```

### Testing Rate Limiting

```bash
# Run the rate limiting test script
python bin/test_rate_limiting.py

# Or test manually with curl
for i in {1..110}; do
  curl -w "\n" http://localhost:8080/health
done
```

After 100 requests, you should see HTTP 429 responses.

### Rate Limit Headers

All responses include rate limit information:

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 60
```

When rate limited (HTTP 429):

```json
{
  "error": "Rate limit exceeded",
  "message": "Too many requests. Please try again later."
}
```


## 📚 Documentation

- **Detailed Operations**: [RUN_GUIDE.md](./RUN_GUIDE.md)
- **Architecture**: [ARCHITECTURE.md](./ARCHITECTURE.md)
- **Sync vs Async**: [SYNC_VS_ASYNC_PROCESSING.md](./SYNC_VS_ASYNC_PROCESSING.md)
- **Message Flow Testing**: [MESSAGE_FLOW_TESTING.md](./MESSAGE_FLOW_TESTING.md)
- **Redis Queue Verification**: [REDIS_QUEUE_VERIFICATION.md](./REDIS_QUEUE_VERIFICATION.md)
- **Product Requirements**: [PRD.md](./PRD.md)

---

## 🆘 Need Help?

1. Check [RUN_GUIDE.md](./RUN_GUIDE.md) for detailed operational guide
2. Check [ARCHITECTURE.md](./ARCHITECTURE.md) for system design
3. Check logs: `make logs` or `tail -f logs/app.log`
4. Verify services: `docker compose ps`
5. Check API health: `curl http://localhost:8080/health`

---

**Quick Checklist:**
- ✅ Conda environment activated
- ✅ Docker services running (postgres, redis)
- ✅ Database migrated
- ✅ API server started
- ✅ **Worker started (REQUIRED!)**
- ✅ Health check passes

**That's it! You're ready to send messages.** 🚀
