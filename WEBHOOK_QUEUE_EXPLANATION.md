# How Messages Are Added to Webhook Queue

## Overview

This document explains how webhooks are handled in the messaging service and whether they use the Redis queue.

## Current Implementation: Synchronous Processing

### Webhook Flow

```
1. Provider (Twilio/SendGrid) sends webhook to our endpoint
2. Our API endpoint receives webhook
3. WebhookService processes it IMMEDIATELY
4. Response returned to provider
5. NO QUEUEING INVOLVED
```

### Code Implementation

In `app/api/v1/webhooks.py`:

```python
@router.post("/twilio")
async def twilio_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Handle Twilio webhooks for SMS/MMS messages."""
    # Get request data
    headers = dict(request.headers)
    body = await request.body()
    
    # Parse body
    data = parse_body(body, headers)
    
    # Process webhook SYNCHRONOUSLY
    service = WebhookService(db)
    result = await service.process_webhook(
        provider="twilio",
        headers=headers,
        body=data
    )
    
    # Return immediate response
    return Response(...)
```

In `app/services/webhook_service.py`:

```python
async def process_webhook(
    self,
    provider: str,
    headers: Dict[str, str],
    body: Dict[str, Any]
) -> Dict[str, Any]:
    """Process incoming webhook from provider."""
    # 1. Log webhook to database
    webhook_log = await self._log_webhook(provider, headers, body)
    
    # 2. Check for duplicates
    if await self._is_duplicate(provider, body):
        return {"status": "duplicate"}
    
    # 3. Validate signature
    provider_instance = ProviderFactory.get_provider(...)
    if not await provider_instance.validate_webhook(headers, body):
        return {"status": "error", "message": "Invalid signature"}
    
    # 4. Process webhook data
    webhook_data = await provider_instance.process_webhook(body)
    result = await self._handle_webhook_type(provider, webhook_data)
    
    # 5. Mark as processed
    webhook_log.processed = True
    await self.db.commit()
    
    return {"status": "success", "result": result}
```

### Types of Webhooks

#### 1. Inbound Messages

When someone sends us a message:

```python
async def _handle_inbound_message(
    self,
    provider: str,
    webhook_data: Dict[str, Any]
) -> Dict[str, Any]:
    """Handle inbound message webhook."""
    message_service = MessageService(self.db)
    
    # Create inbound message in database
    message = await message_service.receive_message(provider, webhook_data)
    
    return {
        "type": "inbound_message",
        "message_id": str(message.id),
        "conversation_id": str(message.conversation_id)
    }
```

#### 2. Status Updates

When provider updates us on message delivery:

```python
async def _handle_status_update(
    self,
    provider: str,
    webhook_data: Dict[str, Any]
) -> Dict[str, Any]:
    """Handle message status update webhook."""
    message_service = MessageService(self.db)
    
    # Find message by provider_message_id
    message = await self.db.execute(
        select(Message).where(
            Message.provider == Provider(provider),
            Message.provider_message_id == webhook_data.get("provider_message_id")
        )
    )
    
    # Update status
    if message:
        new_status = status_map.get(webhook_data.get("status"))
        await message_service.update_message_status(
            str(message.id),
            new_status,
            webhook_data
        )
    
    return {"type": "status_update", "message_id": str(message.id)}
```

## Why Webhooks Are NOT Queued

### Reason 1: Provider Expectations

Webhook providers expect **immediate responses**:
- Twilio: Expects response within 15 seconds
- SendGrid: Expects response within 10 seconds
- If no response, they will **retry** the webhook

If we queue and respond later, providers think delivery failed and retry → duplicates!

### Reason 2: Processing is Fast

Webhook processing is simple and fast:
1. Parse data (~1ms)
2. Validate signature (~5ms)
3. Insert to database (~20ms)
4. Return response

Total: **~26ms** - No need to queue!

### Reason 3: No External Calls

Unlike outbound messages (which call provider APIs), webhooks just:
- Parse
- Validate
- Store in database

No slow external API calls = synchronous processing is fine.

## Webhook Queue in Code

There IS a `webhook_queue` mentioned in the code, but it's **not currently used** for the main flow.

### In Worker (`app/workers/message_processor.py`):

```python
async def start(self):
    self.tasks = [
        asyncio.create_task(self.process_sms_queue()),
        asyncio.create_task(self.process_email_queue()),
        asyncio.create_task(self.process_retry_queue()),
        asyncio.create_task(self.process_webhook_queue()),  # ← Exists but unused
        asyncio.create_task(self.update_metrics()),
    ]

async def process_webhook_queue(self):
    """Process webhook queue."""
    while self.running:
        try:
            # Dequeue webhooks
            webhooks = await redis_manager.dequeue_messages(
                "webhook_queue",
                count=10,
                block=1000
            )
            
            for webhook_data in webhooks:
                await service.process_webhook(
                    webhook_data["provider"],
                    webhook_data["headers"],
                    webhook_data["body"]
                )
        except Exception as e:
            logger.error(f"Error in webhook processor: {e}")
            await asyncio.sleep(5)
```

**This worker task runs, but nothing adds to `webhook_queue`!**

## Could We Use Webhook Queue?

Yes, but there are tradeoffs:

### Approach: Acknowledge Then Queue

```python
@router.post("/twilio")
async def twilio_webhook(request: Request):
    # Parse webhook
    headers = dict(request.headers)
    body = await request.body()
    data = parse_body(body, headers)
    
    # IMMEDIATELY add to queue
    await redis_manager.enqueue_message("webhook_queue", {
        "provider": "twilio",
        "headers": headers,
        "body": data
    })
    
    # Return response immediately (before processing)
    return Response("<Response></Response>", media_type="application/xml")
    
    # Worker processes later
```

### Benefits:
- Faster webhook responses (~5ms instead of ~26ms)
- Better isolation (webhook endpoint doesn't touch database)
- Can scale webhook processing independently

### Drawbacks:
- More complex
- Webhooks processed eventually, not immediately
- Need to handle queue failures
- Duplicate detection harder (can't check DB immediately)

## Current Design Decision

**Decision: Process webhooks synchronously**

Reasoning:
1. Processing is already fast (<50ms)
2. Need database access for duplicate detection
3. Need to respond after validation
4. Simpler architecture
5. Industry standard (most services do this)

## When Would We Queue Webhooks?

Queue webhooks if:
1. Processing takes >1 second
2. Heavy computation required
3. Need to call external APIs
4. Very high webhook volume (>10k/sec)

Example: If we added "reply with AI" feature:
```python
@router.post("/twilio")
async def twilio_webhook(request: Request):
    # Quick validation and queue
    await redis_manager.enqueue_message("webhook_queue", data)
    return Response(...)
    
# Worker processes and sends AI reply
async def process_webhook_queue(self):
    for webhook in webhooks:
        # 1. Process inbound message
        # 2. Call AI API (slow!)
        # 3. Send reply message
```

## Comparison: Outbound Messages vs Webhooks

| Aspect | Outbound Messages | Webhooks |
|--------|------------------|----------|
| **Queue Used** | Yes (recommended) | No |
| **Processing** | Async | Sync |
| **Why?** | Slow (provider API) | Fast (just DB) |
| **Response Time** | Can be slow | Must be fast |
| **Volume** | Client controlled | Provider controlled |
| **Retry** | We control | Provider controls |

## Summary

**Webhooks are NOT added to webhook_queue in current implementation:**

1. **Webhook endpoints** (`app/api/v1/webhooks.py`):
   - Process synchronously
   - No queueing
   - Return immediate response

2. **WebhookService** (`app/services/webhook_service.py`):
   - Processes webhook data
   - Creates inbound messages
   - Updates message status
   - All done synchronously

3. **webhook_queue**:
   - Exists in Redis
   - Worker monitors it
   - **But nothing adds to it!**
   - Could be used in future for heavy processing

4. **Why this design?**:
   - Fast processing (<50ms)
   - Provider expectations
   - Simpler architecture
   - Industry standard

## Verification

Check webhook processing:

```bash
# Send test webhook
curl -X POST http://localhost:8080/api/v1/webhooks/twilio \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "From=%2B15559876543&To=%2B15551234567&Body=Test&MessageSid=TEST123"

# Check webhook queue (should be empty)
docker exec -it $(docker ps -q -f name=redis) redis-cli XLEN webhook_queue
# Output: 0 (nothing queued)

# Check database (webhook should be logged immediately)
docker exec -it $(docker ps -q -f name=postgres) psql -U messaging_user -d messaging_service \
  -c "SELECT id, provider, processed FROM webhook_logs ORDER BY created_at DESC LIMIT 1;"
# Should show the webhook already processed
```

## Related Documentation

- [MESSAGE_FLOW_TESTING.md](./MESSAGE_FLOW_TESTING.md) - Message flow testing
- [REDIS_QUEUE_VERIFICATION.md](./REDIS_QUEUE_VERIFICATION.md) - Queue verification
- [SYNC_VS_ASYNC_PROCESSING.md](./SYNC_VS_ASYNC_PROCESSING.md) - Sync vs async modes

