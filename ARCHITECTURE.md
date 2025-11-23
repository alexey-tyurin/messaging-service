# Messaging Service Architecture

## System Overview

The Messaging Service is designed as a distributed, event-driven system that provides a unified API for multi-channel messaging (SMS, MMS, Email) with extensibility for voice calls and voicemail drops.

## Architecture Principles

1. **Microservices-Ready**: Designed for horizontal scaling and service decomposition
2. **Event-Driven**: Asynchronous message processing with event sourcing
3. **Provider Agnostic**: Abstracted provider interface for easy integration
4. **Resilient**: Circuit breakers, retries, and graceful degradation
5. **Observable**: Comprehensive metrics, logging, and tracing

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                          Load Balancer                          │
└─────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────┐
│                         API Gateway Layer                       │
│                    (Rate Limiting, Auth, Routing)               │
└─────────────────────────────────────────────────────────────────┘
                                   │
        ┌──────────────────────────┼──────────────────────────┐
        ▼                          ▼                          ▼
┌──────────────┐          ┌──────────────┐          ┌──────────────┐
│   Message    │          │ Conversation │          │   Webhook    │
│   Service    │          │   Service    │          │   Service    │
└──────────────┘          └──────────────┘          └──────────────┘
        │                          │                          │
        └──────────────────────────┼──────────────────────────┘
                                   ▼
┌─────────────────────────────────────────────────────────────────┐
│                         Message Queue                           │
│                    (Redis Pub/Sub + Streams)                    │
└─────────────────────────────────────────────────────────────────┘
                                   │
        ┌──────────────────────────┼──────────────────────────┐
        ▼                          ▼                          ▼
┌──────────────┐          ┌──────────────┐          ┌──────────────┐
│   Provider   │          │   Provider   │          │   Provider   │
│   Adapter    │          │   Adapter    │          │   Adapter    │
│     (SMS)    │          │    (Email)   │          │   (Voice)*   │
└──────────────┘          └──────────────┘          └──────────────┘
        │                          │                          │
        ▼                          ▼                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                      External Providers                         │
│            (Twilio, SendGrid, Voice Services*)                  │
└─────────────────────────────────────────────────────────────────┘

Data Layer:
┌──────────────┐          ┌──────────────┐          ┌──────────────┐
│  PostgreSQL  │          │    Redis     │          │   S3/MinIO   │
│  (Primary)   │          │   (Cache)    │          │ (Attachments)│
└──────────────┘          └──────────────┘          └──────────────┘
```

## Core Components

### 1. API Gateway
- **Technology**: FastAPI with async support
- **Responsibilities**:
  - Request routing and validation
  - **Rate limiting** (using Redis sliding window)
  - Authentication/Authorization
  - Request/Response transformation
  - Circuit breaking for downstream services

**Rate Limiting Implementation**:
- **Algorithm**: Sliding window counter using Redis sorted sets
- **Granularity**: Per client IP + endpoint combination
- **Storage**: Redis sorted sets with automatic expiration
- **Configuration**: Configurable via environment variables
- **Headers**: Includes `X-RateLimit-*` headers in all responses
- **Fail-Safe**: Fails open if Redis is unavailable (allows requests)
- **Monitoring**: Tracks rate limit hits in Prometheus metrics

### 2. Message Service
- **Purpose**: Core messaging logic
- **Features**:
  - Message validation and enrichment
  - Provider selection logic
  - Retry mechanism with exponential backoff
  - Dead letter queue for failed messages
  - Idempotency handling

### 3. Conversation Service
- **Purpose**: Conversation management
- **Features**:
  - Automatic conversation threading
  - Participant management
  - Message aggregation
  - Conversation state management
  - Search and filtering capabilities

### 4. Webhook Service
- **Purpose**: Handle incoming provider webhooks
- **Features**:
  - Webhook validation (signatures)
  - Event normalization
  - Duplicate detection
  - Async processing via message queue

### 5. Provider Adapters
- **Purpose**: Abstract provider-specific logic
- **Pattern**: Strategy pattern for provider selection
- **Features**:
  - Provider-specific API integration
  - Response normalization
  - Error mapping
  - Health checking

### 6. Message Queue (Redis)
- **Purpose**: Asynchronous message processing
- **Implementation**:
  - Redis Streams for reliable message delivery
  - Pub/Sub for real-time notifications
  - Consumer groups for load distribution
  - Message persistence and replay capability

## Data Architecture

### PostgreSQL Schema
```sql
-- Core tables with proper indexing
conversations
├── id (UUID, PK)
├── participant_from
├── participant_to
├── channel_type
├── created_at
├── updated_at
└── metadata (JSONB)

messages
├── id (UUID, PK)
├── conversation_id (FK)
├── provider_message_id
├── direction (inbound/outbound)
├── status
├── provider
├── message_type
├── body
├── attachments (JSONB)
├── created_at
├── sent_at
├── delivered_at
└── metadata (JSONB)

message_events
├── id (UUID, PK)
├── message_id (FK)
├── event_type
├── event_data (JSONB)
├── created_at
└── provider_timestamp
```

### Redis Usage
1. **Cache Layer**: Conversation metadata, provider configurations
2. **Session Store**: Active conversation contexts
3. **Rate Limiting**: API rate limit counters (sliding window)
4. **Message Queue**: Redis Streams for async processing
5. **Distributed Locks**: For coordination across instances

### Rate Limiting Architecture

**Implementation Details**:

```
Client Request
     ↓
Rate Limit Middleware (app/main.py)
     ↓
Redis Sliding Window Check
     ↓
┌─────────────────────────────┐
│ Redis Sorted Set            │
│ Key: rate_limit:{client}:{endpoint}  │
│ Members: {timestamp: score} │
│ TTL: window + 1 second      │
└─────────────────────────────┘
     ↓
Decision: Allow or Reject
     ↓
Add X-RateLimit-* Headers
     ↓
Continue or Return 429
```

**Algorithm** (Sliding Window Counter):
1. Remove entries older than time window
2. Add current request timestamp
3. Count total requests in window
4. Compare against limit
5. Set TTL for automatic cleanup

**Key Features**:
- **Distributed**: Works across multiple API instances
- **Accurate**: Sliding window prevents burst at window boundaries
- **Efficient**: O(log N) time complexity for operations
- **Self-cleaning**: Automatic expiration prevents memory buildup
- **Resilient**: Fails open if Redis unavailable

**Default Configuration**:
- Limit: 100 requests
- Window: 60 seconds
- Granularity: Per client IP + endpoint
- Configurable via environment variables

## Message Flow (Async Mode - Default)

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

## Scalability Strategy

### Horizontal Scaling
- **API Servers**: Auto-scaling based on CPU/memory metrics
- **Workers**: Scale based on queue depth
- **Database**: Read replicas for query distribution
- **Cache**: Redis Cluster for high availability

### Performance Optimizations
1. **Connection Pooling**: Database and Redis connection pools
2. **Batch Processing**: Bulk message operations
3. **Async I/O**: Non-blocking operations throughout
4. **Caching Strategy**: 
   - L1: Application-level caching
   - L2: Redis distributed cache
   - Cache warming for frequently accessed data

### Load Distribution
- **Geographic Distribution**: Multi-region deployment capability
- **Queue Sharding**: Partition queues by message type/priority
- **Database Sharding**: Ready for sharding by conversation_id

## Observability

### Metrics (Prometheus)
- Request rate, latency, error rate (RED metrics)
- Queue depth and processing time
- Provider success/failure rates
- Database connection pool metrics
- Cache hit/miss ratios

### Logging (Structured JSON)
- Correlation IDs for request tracing
- Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
- Contextual logging with request metadata
- Centralized log aggregation ready

### Tracing (OpenTelemetry)
- Distributed tracing across services
- Span tracking for database queries
- Provider API call instrumentation
- Performance bottleneck identification

### Health Checks
- `/health`: Basic liveness check
- `/ready`: Readiness probe (DB, Redis, Provider connectivity)
- `/metrics`: Prometheus metrics endpoint

## Security Considerations

1. **API Security**:
   - JWT-based authentication
   - Rate limiting per client
   - Request signing for webhooks
   - Input validation and sanitization

2. **Data Security**:
   - Encryption at rest (database)
   - Encryption in transit (TLS)
   - PII data masking in logs
   - Attachment scanning capability

3. **Provider Security**:
   - Secure credential storage (environment variables/secrets manager)
   - Webhook signature validation
   - IP whitelisting for webhooks

## Extensibility for Voice Features

The architecture is designed to easily accommodate voice calls and voicemail drops:

1. **Voice Provider Adapter**: New adapter implementing the same interface
2. **Media Storage**: S3/MinIO integration for voicemail storage
3. **Transcription Service**: Integration point for speech-to-text
4. **WebSocket Support**: Real-time call status updates
5. **SIP Integration**: Ready for SIP trunk integration

## Deployment Considerations

### Container Strategy
- Docker containers for all services
- Multi-stage builds for optimization
- Health checks built into containers
- Resource limits defined

### Orchestration
- Kubernetes-ready with Helm charts structure
- Service mesh compatible (Istio/Linkerd)
- ConfigMaps for configuration
- Secrets management

### CI/CD Pipeline
- Automated testing (unit, integration, load)
- Container scanning for vulnerabilities
- Blue-green deployment capability
- Automated rollback on failure

## Failure Scenarios and Recovery

1. **Provider Outage**: 
   - Automatic failover to backup provider
   - Queue messages for retry
   - Circuit breaker activation

2. **Database Failure**:
   - Read from replicas
   - Cache fallback for critical data
   - Graceful degradation

3. **High Load**:
   - Auto-scaling triggers
   - Rate limiting activation
   - Priority queue processing

4. **Network Partition**:
   - Eventual consistency handling
   - Conflict resolution strategies
   - Partition tolerance

## Performance Targets

- **API Latency**: p99 < 100ms
- **Message Delivery**: < 5 seconds end-to-end
- **Throughput**: 10,000 messages/second per instance
- **Availability**: 99.99% uptime
- **Error Rate**: < 0.1%
