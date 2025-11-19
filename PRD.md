# Product Requirements Document (PRD) - Messaging Service

## 🎯 Purpose
This document serves as a comprehensive guide for AI-assisted development using Cursor IDE. It provides context, patterns, and requirements for maintaining and extending the Messaging Service.

## 📋 Table of Contents
- [Project Overview](#project-overview)
- [Technical Architecture](#technical-architecture)
- [Code Organization](#code-organization)
- [Development Patterns](#development-patterns)
- [Feature Specifications](#feature-specifications)
- [Implementation Guidelines](#implementation-guidelines)
- [Testing Requirements](#testing-requirements)
- [Common Development Tasks](#common-development-tasks)

---

## Project Overview

### Product Vision
A production-ready, distributed messaging service that provides a unified API for multi-channel communication (SMS, MMS, Email) with extensibility for Voice and Voicemail features.

### Core Principles
1. **Scalability First**: Every component must support horizontal scaling
2. **Provider Agnostic**: Abstract provider details behind interfaces
3. **Async by Default**: Use async/await for all I/O operations
4. **Observable**: Comprehensive metrics, logging, and tracing
5. **Resilient**: Handle failures gracefully with retries and circuit breakers

### Technology Stack
- **Language**: Python 3.11+
- **Framework**: FastAPI with async support
- **Database**: PostgreSQL 15 with asyncpg
- **Cache/Queue**: Redis 7 with Redis Streams
- **ORM**: SQLAlchemy 2.0 with async support
- **Monitoring**: Prometheus + OpenTelemetry
- **Container**: Docker with multi-stage builds

---

## Technical Architecture

### System Components

```
┌─────────────────────────────────────────────────────────┐
│                   Load Balancer                         │
└─────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────┐
│                    API Gateway                          │
│              (FastAPI - app/main.py)                    │
└─────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│   Message    │   │ Conversation │   │   Webhook    │
│   Service    │   │   Service    │   │   Service    │
└──────────────┘   └──────────────┘   └──────────────┘
        │                   │                   │
        └───────────────────┼───────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────┐
│                   Redis Queue/Cache                     │
│                 (Streams + Pub/Sub)                     │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│               Message Processor Worker                  │
│         (app/workers/message_processor.py)              │
└─────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│   Twilio     │   │   SendGrid   │   │    Voice     │
│   Provider   │   │   Provider   │   │   Provider   │
└──────────────┘   └──────────────┘   └──────────────┘
```

### Database Schema

#### Core Tables
```sql
conversations
├── id (UUID, PK)
├── participant_from (VARCHAR)
├── participant_to (VARCHAR)
├── channel_type (ENUM)
├── status (ENUM)
├── metadata (JSONB)
└── timestamps

messages
├── id (UUID, PK)
├── conversation_id (FK)
├── provider (ENUM)
├── provider_message_id (VARCHAR)
├── direction (ENUM)
├── status (ENUM)
├── message_type (ENUM)
├── body (TEXT)
├── attachments (JSONB)
└── timestamps

message_events (Event Sourcing)
├── id (UUID, PK)
├── message_id (FK)
├── event_type (ENUM)
├── event_data (JSONB)
└── timestamps
```

### Queue Architecture
- **Queue Names**: `message_queue:{type}` (sms, mms, email, voice)
- **Redis Streams** for reliable delivery
- **Consumer Groups** for load distribution
- **Dead Letter Queue** for failed messages

---

## Code Organization

### Directory Structure
```
app/
├── api/v1/          # REST API endpoints
├── core/            # Core utilities (config, logging, metrics)
├── db/              # Database and Redis connections
├── models/          # SQLAlchemy models
├── providers/       # Provider implementations
├── services/        # Business logic
└── workers/         # Background processors
```

### Module Responsibilities

#### API Layer (`app/api/v1/`)
- Request validation using Pydantic
- Response serialization
- Error handling with proper HTTP status codes
- Rate limiting enforcement

#### Service Layer (`app/services/`)
- Business logic implementation
- Transaction management
- Cross-cutting concerns (caching, metrics)
- No direct HTTP handling

#### Provider Layer (`app/providers/`)
- Provider-specific implementations
- Strategy pattern for provider selection
- Circuit breaker implementation
- Retry logic with exponential backoff

---

## Development Patterns

### Async/Await Pattern
```python
# ALWAYS use async for I/O operations
async def send_message(self, message_data: Dict[str, Any]) -> Message:
    async with self.db.begin():  # Transaction
        message = await self._create_message(message_data)
        await self._queue_for_sending(message)
    return message
```

### Dependency Injection
```python
# Use FastAPI's Depends for injection
@router.post("/send")
async def send_message(
    request: SendMessageRequest,
    db: AsyncSession = Depends(get_db),  # Injected
    service: MessageService = Depends(get_message_service)  # Injected
):
    return await service.send_message(request.dict())
```

### Error Handling
```python
# Use structured error responses
try:
    result = await operation()
except ValueError as e:
    raise HTTPException(status_code=400, detail=str(e))
except Exception as e:
    logger.error(f"Operation failed: {e}", exc_info=True)
    raise HTTPException(status_code=500, detail="Internal error")
```

### Observability Pattern
```python
@trace_operation("operation_name")
@monitor_performance("operation_name")
async def important_operation():
    logger.info("Starting operation", extra={"context": "value"})
    
    with MetricsCollector.track_duration("operation", "provider"):
        result = await perform_work()
    
    MetricsCollector.track_message("outbound", "sms", "sent", "twilio")
    return result
```

### Provider Strategy Pattern
```python
# Provider selection based on message type
provider = ProviderFactory.get_provider(message.message_type)
response = await provider.send_message(message_data)
```

---

## Feature Specifications

### 1. Message Sending
**Endpoint**: `POST /api/v1/messages/send`

**Requirements**:
- Auto-detect message type from recipient format
- Queue for async processing
- Return immediately with pending status
- Support attachments for MMS/Email
- Validate phone numbers and email addresses
- Create or reuse conversations

**Implementation**:
```python
# Service method signature
async def send_message(self, message_data: Dict[str, Any]) -> Message:
    # 1. Validate input
    # 2. Determine message type
    # 3. Get/create conversation
    # 4. Create message record
    # 5. Queue for processing
    # 6. Return message
```

### 2. Webhook Processing
**Endpoints**: 
- `POST /api/v1/webhooks/twilio`
- `POST /api/v1/webhooks/sendgrid`

**Requirements**:
- Validate webhook signatures
- Handle duplicates idempotently
- Process inbound messages
- Update delivery status
- Log all webhooks

**Implementation**:
```python
async def process_webhook(self, provider: str, data: Dict) -> Dict:
    # 1. Validate signature
    # 2. Check for duplicates
    # 3. Normalize data
    # 4. Process based on type
    # 5. Return success
```

### 3. Conversation Management
**Endpoints**:
- `GET /api/v1/conversations`
- `GET /api/v1/conversations/{id}`
- `POST /api/v1/conversations/search`

**Requirements**:
- Auto-thread messages by participants
- Track read/unread status
- Support archiving
- Enable search by content
- Provide statistics

### 4. Background Processing
**Worker**: `app/workers/message_processor.py`

**Requirements**:
- Process queued messages
- Handle retries with backoff
- Update metrics
- Process webhooks
- Graceful shutdown

**Queue Processing Flow**:
```python
while running:
    messages = await redis.dequeue_messages(queue_name)
    for message in messages:
        await process_message(message)
        await update_metrics()
```

---

## Implementation Guidelines

### Adding a New Provider

1. **Create Provider Class**:
```python
# app/providers/new_provider.py
class NewProvider(MessageProvider):
    async def send_message(self, data: Dict) -> Dict:
        # Implementation
    
    async def validate_webhook(self, headers: Dict, body: Any) -> bool:
        # Signature validation
    
    async def process_webhook(self, data: Dict) -> Dict:
        # Normalize to internal format
```

2. **Register Provider**:
```python
# app/providers/base.py
ProviderFactory.register_provider("new_provider", NewProvider())
```

3. **Add Webhook Endpoint**:
```python
# app/api/v1/webhooks.py
@router.post("/new_provider")
async def new_provider_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    # Process webhook
```

### Adding a New Message Type

1. **Update Enum**:
```python
# app/models/database.py
class MessageType(str, enum.Enum):
    VOICE_CALL = "voice_call"  # New type
```

2. **Update Provider Mapping**:
```python
# app/providers/base.py
provider_map = {
    MessageType.VOICE_CALL: "voice_provider"
}
```

3. **Add Queue Processing**:
```python
# app/workers/message_processor.py
async def process_voice_queue(self):
    # Voice-specific processing
```

### Database Migrations

```bash
# Create new migration
alembic revision --autogenerate -m "Add new feature"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

### Adding Metrics

```python
# Define metric in app/core/observability.py
new_metric = Counter(
    'metric_name',
    'Description',
    ['label1', 'label2'],
    registry=registry
)

# Track metric
new_metric.labels(label1="value1", label2="value2").inc()
```

---

## Testing Requirements

### Unit Tests
- Test all service methods in isolation
- Mock external dependencies (DB, Redis, Providers)
- Achieve 80%+ code coverage
- Use pytest fixtures for common data

### Integration Tests
- Test API endpoints end-to-end
- Use test database (SQLite in-memory)
- Test webhook processing
- Verify rate limiting

### Test Structure
```python
@pytest.mark.asyncio
async def test_feature(async_db, sample_data):
    # Arrange
    service = MessageService(async_db)
    
    # Act
    result = await service.operation(sample_data)
    
    # Assert
    assert result.status == expected_status
```

---

## Common Development Tasks

### 1. Add New API Endpoint
```python
# 1. Add route in app/api/v1/{resource}.py
@router.post("/new-endpoint")
async def new_endpoint(
    request: NewRequest,
    db: AsyncSession = Depends(get_db)
):
    service = ResourceService(db)
    result = await service.process(request)
    return NewResponse.from_orm(result)

# 2. Add Pydantic models in app/api/v1/models.py
class NewRequest(BaseModel):
    field: str = Field(..., description="Description")

# 3. Add service method in app/services/{resource}_service.py
async def process(self, data: Dict) -> Model:
    # Implementation
```

### 2. Add Background Task
```python
# Add to app/workers/message_processor.py
async def new_task(self):
    while self.running:
        try:
            # Task logic
            await asyncio.sleep(interval)
        except Exception as e:
            logger.error(f"Task failed: {e}")

# Register in start() method
self.tasks.append(asyncio.create_task(self.new_task()))
```

### 3. Add Caching
```python
# Check cache first
cached = await redis_manager.get(f"cache:{key}")
if cached:
    return cached

# Compute and cache
result = await expensive_operation()
await redis_manager.set(f"cache:{key}", result, ttl=300)
return result
```

### 4. Add Health Check
```python
# Register in app/main.py lifespan
health_monitor.register_check("new_service", check_function)

# Implement check function
async def check_new_service() -> bool:
    try:
        # Check service health
        return await service.ping()
    except Exception:
        return False
```

---

## Performance Requirements

### API Latency
- p50: < 50ms
- p95: < 100ms
- p99: < 200ms

### Throughput
- 10,000 messages/second per instance
- 100,000 concurrent connections
- 1M messages/day capacity

### Database
- Connection pool: 20-40 connections
- Query timeout: 30 seconds
- Index all foreign keys and frequently queried columns

### Caching
- Redis pool: 10 connections
- Cache TTL: 5 minutes for metadata
- Use Redis Streams for queuing

---

## Security Requirements

### Authentication & Authorization
- JWT tokens for API authentication (ready to implement)
- Rate limiting per client
- API key management

### Data Protection
- Encrypt sensitive data at rest
- Use TLS for all external communication
- Mask PII in logs
- Validate all inputs

### Provider Security
- Store credentials in environment variables
- Validate webhook signatures
- Implement request signing

---

## Monitoring & Alerts

### Key Metrics to Track
```python
# Business Metrics
- messages_sent_total
- messages_failed_total
- conversation_active_count
- provider_error_rate

# System Metrics
- api_request_duration_seconds
- queue_depth
- db_connection_pool_usage
- redis_memory_usage
```

### Alert Thresholds
- Error rate > 1%
- Queue depth > 10,000
- API latency p99 > 500ms
- Provider failures > 5 consecutive

---

## Extension Points

### Voice Integration (Future)
```python
# 1. Add VoiceProvider class
# 2. Handle SIP/WebRTC connections
# 3. Add call recording storage
# 4. Implement real-time events via WebSocket
```

### Attachment Storage (Future)
```python
# 1. Integrate S3/MinIO
# 2. Add virus scanning
# 3. Implement CDN distribution
# 4. Add attachment metadata table
```

### Analytics Pipeline (Future)
```python
# 1. Stream events to Kafka
# 2. Process with Apache Spark
# 3. Store in ClickHouse
# 4. Build dashboard APIs
```

---

## Cursor IDE Usage Tips

### Context Commands
When using Cursor, reference this PRD with:
```
@PRD.md explain the message flow
@PRD.md how to add a new provider
@PRD.md show the database schema
```

### Code Generation Prompts
```
Based on @PRD.md, create a new endpoint for bulk message sending
Following the patterns in @PRD.md, add voice call support
Using the testing requirements from @PRD.md, write tests for the new feature
```

### Refactoring Guidance
```
According to @PRD.md architecture, refactor this code to use async/await
Based on @PRD.md patterns, add proper error handling and logging
Following @PRD.md observability guidelines, add metrics to this operation
```

### Bug Fixing
```
Check @PRD.md for the correct error handling pattern
Verify against @PRD.md if this follows the service layer pattern
According to @PRD.md, what's the proper way to handle retries?
```

---

## Maintenance Notes

### Regular Tasks
1. Update dependencies monthly
2. Review and optimize slow queries
3. Clean up old webhook logs
4. Monitor queue depths
5. Update provider SDKs

### Performance Optimization
1. Add database indexes based on query patterns
2. Implement query result caching
3. Use batch operations where possible
4. Consider read replicas for scaling

### Code Quality
1. Maintain 80%+ test coverage
2. Run linting before commits
3. Update documentation with changes
4. Follow type hints consistently
5. Use meaningful variable names

---

## Contact & Support

**Project**: Messaging Service  
**Repository**: Internal GitHub  
**Documentation**: This PRD + README.md + ARCHITECTURE.md  
**Tech Stack Questions**: Reference this PRD section by section  

---

*This PRD is designed for AI-assisted development. Keep it updated as the system evolves.*
