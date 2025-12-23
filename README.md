# Messaging Service: Production-Grade Distributed System Built with AI-Augmented Development

[![Architecture](https://img.shields.io/badge/Architecture-Event--Driven-orange.svg)](./ARCHITECTURE.md)
[![AI Augmented](https://img.shields.io/badge/Built%20With-Cursor%20%7C%20Claude%20%7C%20Antigravity-purple)](https://cursor.sh)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?style=flat&logo=FastAPI&logoColor=white)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB.svg?style=flat&logo=python&logoColor=white)](https://www.python.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-316192.svg?style=flat&logo=postgresql&logoColor=white)](https://www.postgresql.org)
[![Redis](https://img.shields.io/badge/Redis-7.2+-DC382D.svg?style=flat&logo=redis&logoColor=white)](https://redis.io)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 🎯 **The "Vibe Engineering" Paradigm**

This project demonstrates what happens when **senior-level architectural thinking meets AI-powered code generation**. Using a combination of cutting-edge AI tools—[Cursor](https://cursor.sh/) with Claude Sonnet 4.5, Claude for architecture guidance, and Google Antigravity for refinements—I went from concept to a **production-ready distributed messaging platform** in a fraction of the time traditional development would require—**without compromising on architectural rigor**.

**The Result**: A system featuring Redis-based sliding window rate limiting, event-driven architecture with Redis Streams, circuit breakers, async message processing, webhook validation, and comprehensive observability—**all implemented with patterns you'd expect from a Staff+ engineer with 15+ years of experience**.

This isn't scaffolding. This is **production code**.

---

## 🏗️ **Architecture Highlights**

### **Distributed, Event-Driven Design**
- **Async-First**: Full async/await implementation with FastAPI and SQLAlchemy 2.0
- **Message Queue**: Redis Streams for reliable, ordered message delivery with consumer groups
- **Event Sourcing**: Complete audit trail with `message_events` table for delivery tracking
- **Horizontal Scalability**: Stateless API design ready for Kubernetes deployment

### **Enterprise-Grade Reliability**
- **Rate Limiting**: Sliding window algorithm using Redis sorted sets (O(log N) operations)
  - Per-client + per-endpoint granularity
  - Distributed across instances
  - Automatic cleanup with TTL
  - Fails open gracefully if Redis unavailable
- **Circuit Breakers**: Provider fault isolation with automatic recovery
- **Retry Logic**: Exponential backoff with dead letter queue
- **Health Checks**: `/health`, `/ready`, and `/metrics` endpoints

### **Provider Abstraction Layer**
- **Multi-Channel Support**: SMS, MMS, Email (extensible to voice/voicemail)
- **Strategy Pattern**: Clean provider selection and failover logic
- **Webhook Processing**: Signature validation, duplicate detection, async handling
- **Error Mapping**: Normalized error handling across providers (Twilio, SendGrid)

### **Data Architecture**
```
PostgreSQL (ACID transactions)
├── conversations: Thread messages by participants
├── messages: Full lifecycle tracking (pending → sending → sent → delivered)
└── message_events: Event sourcing for audit and debugging

Redis (Sub-millisecond operations)
├── Streams: Async message queue with at-least-once delivery
├── Sorted Sets: Sliding window rate limiting
├── Hash Maps: Conversation metadata cache
└── Distributed Locks: Cross-instance coordination
```

---

## 🚀 **Key Features That Prove Sophistication**

| Feature | Implementation | Why It Matters |
|---------|----------------|----------------|
| **Conversation Threading** | Automatic grouping by `(from, to)` tuple | Multi-channel message continuity |
| **Sliding Window Rate Limiting** | Redis sorted sets with atomic operations | Prevents API abuse, distributes load |
| **Async Message Processing** | Redis Streams + background workers | Sub-50ms API response times |
| **Provider Failover** | Circuit breaker pattern with health checks | 99.99% uptime target |
| **Webhook Signature Validation** | HMAC verification for Twilio/SendGrid | Security against replay attacks |
| **Idempotency** | Client-provided `idempotency_key` support | Prevents duplicate sends |
| **Structured Logging** | JSON logs with correlation IDs | Production debugging and tracing |
| **OpenTelemetry Ready** | Instrumentation for distributed tracing | Performance bottleneck identification |

**Performance Targets**:
- **API Latency**: p99 < 100ms
- **Throughput**: 10,000 messages/second per instance
- **Message Delivery**: < 5 seconds end-to-end

---

## 🤖 **The AI-Augmented Workflow**

### **Toolchain**
1. **[Cursor](https://cursor.sh/)** - AI-native code editor with Claude Sonnet 4.5 integration
  - Primary development environment for the majority of the codebase
  - Inline code generation with full project context
  - Refactoring and test generation
2. **Claude (Anthropic)** - Architecture design, code review, pattern validation
  - System design discussions and architectural decision-making
  - Documentation generation and refinement
  - Complex pattern implementation guidance
3. **Google Antigravity** - Final refinements and vibe engineering validation
  - Testing alternative AI approaches for specific features
  - Comparative analysis of AI-generated solutions
  - Validation of the "vibe engineering" methodology

### **Development Workflow**
```
Cursor + Claude Sonnet 4.5          →  Core implementation (80% of code)
          ↓
Claude (via chat)                   →  Architecture validation & docs
          ↓
Google Antigravity                  →  Refinements & methodology testing
          ↓
Production-Ready System
```

### **What AI Enabled**
- ✅ **Complex Patterns in Minutes**: Redis Streams implementation with consumer groups in one prompt
- ✅ **Architectural Consistency**: AI maintains patterns across the codebase (e.g., async everywhere)
- ✅ **Comprehensive Testing**: Generated unit/integration tests covering edge cases
- ✅ **Documentation**: Architecture diagrams, API specs, and this README
- ✅ **Rapid Iteration**: Testing multiple implementation approaches with different AI tools

### **What AI Didn't Replace**
- 🧠 **System Design Decisions**: Event-driven architecture, queue choice, database schema
- 🧠 **Trade-off Analysis**: When to use cache vs. database, async vs. sync endpoints
- 🧠 **Production Readiness**: Security considerations, observability strategy, failure modes
- 🧠 **Tool Selection**: Choosing when to use Cursor vs. Claude vs. Antigravity

**The "Vibe"**: AI handles the **mechanical complexity** (syntax, boilerplate, implementation details) while the engineer focuses on **strategic decisions** (architecture, trade-offs, business logic). This is 10x leverage for senior engineers who know *what* to build.

---

## 📋 **Quick Start**

### **Prerequisites**
- Python 3.11+
- Docker & Docker Compose
- Conda (or virtualenv)

### **Setup**
```bash
# Clone the repository
git clone git@github.com:alexey-tyurin/messaging-service.git
cd messaging-service

# Activate Python environment
conda activate py311

# Start infrastructure (PostgreSQL + Redis)
docker compose up -d postgres redis

# Run the application
make run

# Verify health
curl http://localhost:8080/health
```

### **Application URLs**
- 📚 **API Documentation**: http://localhost:8080/docs (Swagger UI)
- 💚 **Health Check**: http://localhost:8080/health
- ⚡ **Readiness Probe**: http://localhost:8080/ready
- 📊 **Prometheus Metrics**: http://localhost:8080/metrics

### **Send Your First Message**
```bash
curl -X POST "http://localhost:8080/api/v1/messages/send" \
  -H "Content-Type: application/json" \
  -d '{
    "from": "+15555551234",
    "to": "+15555555678",
    "type": "sms",
    "body": "Hello from the distributed messaging service!"
  }'
```

**See [QUICK_START.md](./QUICK_START.md) for detailed setup or [RUN_GUIDE.md](./RUN_GUIDE.md) for operations and troubleshooting.**

---

## 🏛️ **System Architecture**

```
┌─────────────────┐
│  Load Balancer  │  ← Geographic distribution, auto-scaling
└────────┬────────┘
         │
┌────────▼────────┐
│   API Gateway   │  ← Rate limiting (Redis), Auth, Circuit breakers
└────────┬────────┘
         │
    ┌────┴────┬────────────────┐
    ▼         ▼                ▼
┌─────────┐ ┌─────────┐ ┌─────────┐
│ Message │ │ Convo   │ │ Webhook │  ← Async services with FastAPI
│ Service │ │ Service │ │ Service │
└────┬────┘ └────┬────┘ └────┬────┘
     │           │           │
     └───────────┴───────────┘
                 ▼
    ┌────────────────────────┐
    │   Redis Streams        │  ← Message queue with consumer groups
    │   (at-least-once)      │
    └────────┬───────────────┘
             │
     ┌───────┴───────┐
     ▼               ▼
┌─────────┐     ┌─────────┐
│ Twilio  │     │SendGrid │  ← Provider adapters (Strategy pattern)
│ Adapter │     │ Adapter │
└─────────┘     └─────────┘
```

**Full architecture details**: See [ARCHITECTURE.md](./ARCHITECTURE.md)

---

## 📦 **Project Structure**

```
messaging-service/
├── app/
│   ├── main.py              # FastAPI app with rate limiting middleware
│   ├── core/
│   │   ├── config.py        # Environment configuration
│   │   └── observability.py # Metrics and debugging
│   ├── api/
│   │   └── v1/
│   │       ├── messages.py  # Message endpoints
│   │       └── webhooks.py  # Provider webhook handlers
│   ├── db/   
│   │   └── redis.py         # Redis connection management for caching, rate limiting, and message queuing
│   │   └── session.py       # Database session management 
│   ├── models/              # SQLAlchemy models
│   ├── services/            # Business logic layer
│   ├── providers/           # Provider adapters
│   └── workers/             # Processor for message queues
├── bin/                     # Scripts for service lifecycle and integration tests
├── tests/                   # Unit + integration tests
├── alembic/                 # Database migrations
├── docker-compose.yml       # Local development stack
└── Makefile                 # Development commands
```

---

## 🔧 **Development Commands**

```bash
make run           # Start the application
make stop          # Stop the application
make restart-app   # Restart app (keep DB/Redis running)
make logs          # View application logs
make test          # Run test suite
make lint          # Run code linters
make format        # Auto-format code
make migration MSG="description"  # Create new database migration
make migrate       # Apply pending migrations
```

---

## 📊 **Technical Specifications**

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Web Framework** | FastAPI 0.115+ | Async API with automatic OpenAPI docs |
| **Database** | PostgreSQL 16 | ACID transactions, JSONB support |
| **Cache/Queue** | Redis 7.2+ | Streams, sorted sets, distributed locks |
| **ORM** | SQLAlchemy 2.0 | Async queries, relationship management |
| **Migrations** | Alembic | Schema versioning |
| **Validation** | Pydantic v2 | Request/response schemas |
| **Testing** | pytest + pytest-asyncio | Async test support |
| **Observability** | Prometheus + structured logs | Metrics and debugging |

---

## 🎓 **Lessons for AI-Augmented Development**

### **What Works**
1. **Be Specific**: "Implement Redis sliding window rate limiting using sorted sets" > "Add rate limiting"
2. **Architectural Context**: Share design docs (like ARCHITECTURE.md) with AI to maintain consistency
3. **Iterative Refinement**: Use AI for multiple passes—generation, then optimization, then testing
4. **Leverage AI Strengths**: Boilerplate, error handling, test generation, documentation
5. **Multi-Tool Strategy**: Different AI tools excel at different tasks—use the right tool for the job

### **What to Own**
1. **System Design**: AI doesn't make architectural decisions (sync vs async, SQL vs NoSQL)
2. **Trade-offs**: Performance vs complexity, consistency vs availability
3. **Production Concerns**: Security boundaries, failure modes, monitoring strategy
4. **Code Review**: AI-generated code still needs senior review for edge cases
5. **Tool Orchestration**: Deciding when to use Cursor vs. Claude vs. Antigravity

### **AI Tool Comparison (From This Project)**

| Tool | Best For | Used In This Project For |
|------|----------|--------------------------|
| **Cursor + Claude** | Core development, refactoring, tests | 80% of implementation, main development flow |
| **Claude (Chat)** | Architecture discussions, documentation | System design validation, README/ARCHITECTURE.md |
| **Google Antigravity** | Alternative approaches, refinements | Testing vibe engineering methodology, specific feature improvements |

---

## 📄 **License**

MIT License - see [LICENSE](LICENSE) file for details.

---

## 🙏 **Acknowledgments**

- **Cursor IDE** for AI-native development experience
- **Claude (Anthropic)** for architectural guidance and code generation
- **Google Antigravity** for alternative AI perspectives and refinements
- **FastAPI** for async Python done right
- **Redis** for sub-millisecond operations at scale

---

**Built with AI. Architected by a human. Production-ready by design.**

