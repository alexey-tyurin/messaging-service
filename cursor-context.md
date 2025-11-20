# Cursor Context - Messaging Service Quick Reference

## 🎯 @mentions Guide
Use these references in Cursor for quick context:
- `@PRD.md` - Full product requirements and patterns
- `@cursor-context.md` - This quick reference
- `@ARCHITECTURE.md` - System design details
- `@.cursorrules` - Coding standards and rules

## 📁 Project Structure Quick Reference

```
@app/api/v1/         → API endpoints (messages, conversations, webhooks, health)
@app/services/       → Business logic (MessageService, ConversationService)
@app/providers/      → External integrations (Twilio, SendGrid)
@app/workers/        → Background processing (message_processor.py)
@app/models/         → Database models (SQLAlchemy)
@app/core/           → Config, logging, metrics
@app/db/             → Database and Redis connections
```

## 🔧 Common Operations

### Send a Message
```python
# API: POST /api/v1/messages/send
# Service: MessageService.send_message()
# Flow: API → Service → Queue → Worker → Provider
```

### Process Webhook
```python
# API: POST /api/v1/webhooks/{provider}
# Service: WebhookService.process_webhook()
# Flow: Webhook → Validate → Normalize → Process
```

### Background Processing
```python
# Worker: app/workers/message_processor.py
# Queues: message_queue:sms, message_queue:email
# Flow: Queue → Worker → Provider → Update Status
```

## 💾 Database Quick Reference

### Main Tables
```sql
conversations (id, participants, channel_type, status)
messages (id, conversation_id, provider, status, body)
message_events (id, message_id, event_type, event_data)
webhook_logs (id, provider, body, processed)
```

### Common Queries
```python
# Get message with conversation
message = await db.get(Message, message_id)

# List messages
query = select(Message).where(Message.status == status)
result = await db.execute(query)

# Update with transaction
async with db.begin():
    message.status = new_status
    await db.flush()
```

## 🔄 Message Flow States

```
PENDING → QUEUED → SENDING → SENT → DELIVERED
                      ↓
                   RETRY → FAILED
```

## 🔌 Provider Integration Points

### Adding Provider
1. Create class in `app/providers/`
2. Implement `MessageProvider` interface
3. Register in `ProviderFactory`
4. Add webhook endpoint

### Provider Methods
```python
send_message(data: Dict) → Dict
validate_webhook(headers: Dict, body: Any) → bool
process_webhook(data: Dict) → Dict
health_check() → bool
```

## ⚡ Redis Operations

### Cache
```python
await redis_manager.get(key)
await redis_manager.set(key, value, ttl=300)
await redis_manager.delete(key)
```

### Queue
```python
await redis_manager.enqueue_message(queue_name, data)
await redis_manager.dequeue_messages(queue_name, count=10)
```

### Pub/Sub
```python
await redis_manager.publish(channel, message)
await redis_manager.subscribe(channels)
```

## 📊 Metrics & Monitoring

### Key Metrics
```python
MetricsCollector.track_message(direction, type, status, provider)
MetricsCollector.track_duration(operation, provider)
MetricsCollector.update_queue_depth(queue_name, depth)
MetricsCollector.track_cache_operation(operation, hit)
```

### Health Endpoints
```
GET /health       → Basic health check
GET /ready        → Readiness with dependencies
GET /metrics      → Prometheus metrics
GET /dependencies → Detailed dependency status
```

## 🧪 Testing Patterns

### Unit Test
```python
@pytest.mark.asyncio
async def test_feature(async_db):
    service = MessageService(async_db)
    result = await service.method(data)
    assert result.status == expected
```

### Integration Test
```python
def test_endpoint(client):
    response = client.post("/api/v1/endpoint", json=data)
    assert response.status_code == 201
```

### Fixtures
```python
async_db         → Test database session
client           → FastAPI test client
redis_client     → Test Redis connection
sample_data      → Common test data
```

## 🐛 Common Issues

### Issue: Connection pool exhausted
```python
# Fix: Check for missing await
result = await db.execute(query)  # ✅
result = db.execute(query)        # ❌
```

### Issue: Message stuck in queue
```python
# Check: Worker running?
# Check: Redis connection?
# Check: Queue name matches?
```

### Issue: Webhook not processing
```python
# Check: Signature validation?
# Check: Duplicate detection?
# Check: Provider registered?
```

## 🚀 Quick Commands

### Development
```bash
make run              # Start API
make worker           # Start background worker
make test             # Run all tests
make migrate          # Apply database migrations
make lint             # Check code quality
```

### Docker
```bash
docker compose up -d  # Start all services
docker compose logs   # View logs
docker compose ps     # Check status
make docker-restart   # Restart services
```

### Database
```bash
make db-shell         # PostgreSQL shell
make redis-cli        # Redis CLI
alembic history       # Migration history
alembic upgrade head  # Apply migrations
```

## 📝 Code Templates

### New Endpoint
```python
@router.post("/endpoint", response_model=ResponseModel)
async def endpoint(
    request: RequestModel,
    db: AsyncSession = Depends(get_db)
):
    service = Service(db)
    result = await service.process(request.dict())
    return ResponseModel.from_orm(result)
```

### New Service Method
```python
@trace_operation("operation")
async def operation(self, data: Dict) -> Model:
    async with self.db.begin():
        # Business logic
        result = await self._helper(data)
        await self.db.flush()
    
    # Post-transaction operations
    await redis_manager.set(f"cache:{id}", result)
    return result
```

### New Background Task
```python
async def process_task(self):
    while self.running:
        try:
            items = await get_items()
            for item in items:
                await process_item(item)
            await asyncio.sleep(10)
        except Exception as e:
            logger.error(f"Task failed: {e}")
```

## 🎨 Pydantic Models

### Request Model
```python
class RequestModel(BaseModel):
    field: str = Field(..., description="Required field")
    optional: Optional[str] = Field(None, description="Optional")
    
    @validator("field")
    def validate_field(cls, v):
        if not v:
            raise ValueError("Field cannot be empty")
        return v
```

### Response Model
```python
class ResponseModel(BaseModel):
    id: str
    status: StatusEnum
    created_at: datetime
    
    class Config:
        orm_mode = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
```

## 🔐 Environment Variables

### Required
```
POSTGRES_HOST, POSTGRES_USER, POSTGRES_PASSWORD
REDIS_HOST, REDIS_PORT
SECRET_KEY
```

### Optional
```
RATE_LIMIT_ENABLED=true
METRICS_ENABLED=true
```

## 📚 Key Files Reference

| File | Purpose | When to Modify |
|------|---------|----------------|
| `app/main.py` | FastAPI app setup | Adding middleware |
| `app/core/config.py` | Settings management | New env variables |
| `app/models/database.py` | SQLAlchemy models | Schema changes |
| `app/workers/message_processor.py` | Background tasks | New queue processors |
| `alembic/env.py` | Migration config | Database setup |
| `docker-compose.yml` | Service orchestration | New services |

## 🎯 Performance Tips

1. **Use async everywhere** - Never block the event loop
2. **Batch operations** - Process multiple items together
3. **Cache aggressively** - But with appropriate TTLs
4. **Index properly** - All foreign keys and query fields
5. **Pool connections** - Database and Redis pools
6. **Monitor metrics** - Watch queue depths and latencies

## 🔍 Debugging Tips

```python
# Quick debug
logger.debug(f"State: {variable}")
import ipdb; ipdb.set_trace()  # Breakpoint

# Check health
curl http://localhost:8000/health
curl http://localhost:8000/ready

# View metrics
curl http://localhost:8000/metrics | grep message

# Check logs
docker compose logs -f app
docker compose logs -f worker
```

---
*Use `@cursor-context.md` in Cursor to quickly reference any section*
