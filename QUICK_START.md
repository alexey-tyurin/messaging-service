# Messaging Service

A production-ready, distributed messaging service supporting SMS, MMS, Email, and extensible for Voice/Voicemail. Built with FastAPI, PostgreSQL, Redis, and designed for horizontal scalability.

## 🏗️ Architecture Highlights

- **Event-driven architecture** with async message processing
- **Microservices-ready** design with clear service boundaries
- **Provider abstraction** using Strategy pattern
- **Comprehensive observability** with metrics, logging, and tracing
- **Rate limiting** and circuit breakers for resilience
- **Redis-based** queuing and caching
- **PostgreSQL** with proper indexing and migrations
- **Docker-ready** with multi-stage builds

## 📋 Features

### Core Functionality
- ✅ Unified API for SMS, MMS, and Email
- ✅ Automatic conversation threading
- ✅ Provider failover and retry logic
- ✅ Webhook processing for inbound messages
- ✅ Message status tracking and events
- ✅ Rate limiting per client
- ✅ Idempotency for message sending

### Production Features
- ✅ Health checks and readiness probes
- ✅ Prometheus metrics integration
- ✅ Structured JSON logging
- ✅ OpenTelemetry tracing support
- ✅ Database connection pooling
- ✅ Redis connection management
- ✅ Graceful shutdown handling

### Extensibility
- 🔄 Ready for Voice calls integration
- 🔄 Voicemail drop support structure
- 🔄 Attachment scanning capability
- 🔄 Multi-region deployment ready

## 🚀 Quick Start

### Prerequisites
- Python 3.11+ with conda environment
- Docker and Docker Compose
- PostgreSQL 15+ (via Docker)
- Redis 7+ (via Docker)

### Local Development Setup

1. **Activate your conda environment:**
```bash
conda activate py311
```

2. **Start Docker services (PostgreSQL & Redis):**
```bash
cd messaging-service
docker compose up -d postgres redis
```

3. **Verify Docker services are running:**
```bash
docker compose ps
# Should show postgres and redis as "Up (healthy)"
```

4. **Run database migrations:**
```bash
make migrate
```

5. **Start the application:**
```bash
# Using the conda Python directly
/Users/alexeytyurin/anaconda3/envs/py311/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Or create an alias for convenience:
```bash
# Add to ~/.zshrc or ~/.bashrc
alias messaging-run="cd /path/to/messaging-service && /Users/alexeytyurin/anaconda3/envs/py311/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
```

6. **Stop the application:**
```bash
make stop
```

7. **Restart the application:**
```bash
make restart
```

The service will be available at:
- API: http://localhost:8000
- Documentation: http://localhost:8000/api/v1/docs
- Metrics: http://localhost:8000/metrics
- Health: http://localhost:8000/health

### Docker Development (Full Stack)

```bash
# Start all services (including app and worker containers)
docker compose up -d

# View logs
docker compose logs -f

# Stop services
docker compose down
```

### Troubleshooting

**Error: "Address already in use"**
```bash
make stop  # Kill all processes on port 8000
```

**Error: "PostgreSQL is not available"**
```bash
docker compose up -d postgres
docker compose ps postgres  # Check status
```

**Error: "Redis connection failed"**
```bash
docker compose up -d redis
docker compose ps redis  # Check status
```

**Error: "FastAPI not found"**
```bash
# Make sure you're in the correct conda environment
conda activate py311
```

For more detailed troubleshooting, see [START_STOP.md](./START_STOP.md)

## 📡 API Endpoints

### Messages

#### Send Message
```bash
curl -X POST http://localhost:8000/api/v1/messages/send \
  -H "Content-Type: application/json" \
  -d '{
    "from": "+15551234567",
    "to": "+15559876543",
    "type": "sms",
    "body": "Hello from Hatch!"
  }'
```

#### List Messages
```bash
curl http://localhost:8000/api/v1/messages?limit=10
```

### Conversations

#### Get Conversation
```bash
curl http://localhost:8000/api/v1/conversations/{conversation_id}
```

#### List Conversations
```bash
curl http://localhost:8000/api/v1/conversations?participant=+15551234567
```

### Webhooks

#### Twilio Webhook
```
POST /api/v1/webhooks/twilio
```

#### SendGrid Webhook
```
POST /api/v1/webhooks/sendgrid
```

## 📊 Database Schema

### Core Tables
- **conversations** - Message threads between participants
- **messages** - Individual messages with status tracking
- **message_events** - Event sourcing for message lifecycle
- **webhook_logs** - Incoming webhook audit trail

### Indexes
- Composite indexes on frequently queried columns
- Partial indexes for status-based queries
- BRIN indexes for time-series data

## 🔧 Configuration

Environment variables (`.env` file):

```env
# Database
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=messaging_user
POSTGRES_PASSWORD=messaging_password
POSTGRES_DB=messaging_service

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# Application
ENVIRONMENT=development
DEBUG=true
SECRET_KEY=your-secret-key-here

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_PERIOD=60

```

## 🧪 Testing

### Unit Tests
```bash
pytest tests/unit -v --cov=app
```

### Integration Tests
```bash
pytest tests/integration -v
```

### Load Testing
```bash
locust -f tests/load/locustfile.py --host=http://localhost:8000
```

### API Testing
```bash
./bin/test.sh  # Runs curl-based API tests
```

## 📈 Monitoring

### Prometheus Metrics
- Request rate, latency, and error rate (RED metrics)
- Queue depth and processing times
- Provider success/failure rates
- Database connection pool metrics
- Cache hit/miss ratios

### Health Checks
- `/health` - Basic liveness check
- `/ready` - Readiness with dependency checks
- `/metrics` - Prometheus metrics endpoint

### Logging
- Structured JSON logging
- Correlation IDs for request tracing
- Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL

## 🏗️ System Design

### Message Flow
1. Client sends message via REST API
2. Message validated and stored in PostgreSQL
3. Queued in Redis for async processing
4. Worker picks up message from queue
5. Provider selected based on message type
6. Message sent through provider API
7. Status updated and events recorded
8. Webhooks processed for delivery confirmations

### Scaling Strategy
- **Horizontal scaling** of API servers behind load balancer
- **Worker scaling** based on queue depth
- **Database read replicas** for query distribution
- **Redis Cluster** for cache distribution
- **Message partitioning** by conversation ID

## 🔄 Extension Points

### Adding Voice Support
1. Implement `VoiceProvider` class
2. Add voice-specific message types
3. Handle SIP/WebRTC integration
4. Add call recording storage

### Adding New Providers
1. Extend `MessageProvider` base class
2. Implement required methods
3. Register in `ProviderFactory`
4. Add webhook endpoints

## 🚢 Deployment

### Production Build
```bash
docker build -t messaging-service:latest .
```

### Kubernetes
```bash
kubectl apply -f k8s/
```

### Environment-Specific Configs
- Development: Auto-reload, debug logging
- Staging: Production-like with verbose logging
- Production: Optimized, minimal logging

## 📝 Development Commands

```bash
make help          # Show all commands
make setup         # Initial setup
make run           # Run application
make worker        # Run background worker
make test          # Run tests
make lint          # Run linting
make format        # Format code
make migrate       # Run migrations
make docker-up     # Start Docker services
make docker-logs   # View logs
make db-shell      # PostgreSQL shell
make redis-cli     # Redis CLI
```

## 🎯 Performance Targets

- API Latency: p99 < 100ms
- Message Delivery: < 5 seconds end-to-end
- Throughput: 10,000 messages/second per instance
- Availability: 99.99% uptime
- Error Rate: < 0.1%

## 🔒 Security

- JWT-based authentication ready
- Rate limiting per client
- Webhook signature validation
- SQL injection prevention
- Input sanitization
- PII data masking in logs

## 📚 Documentation

- API Documentation: http://localhost:8000/docs
- Architecture: See `ARCHITECTURE.md`
- Database Schema: See migrations in `alembic/versions/`

## 🤝 Contributing

1. Create feature branch
2. Write tests
3. Ensure linting passes
4. Create pull request
