# Redis Caching Implementation

## Overview

This document describes the Redis caching implementation for the messaging service, specifically for the `get_message` and `get_conversation` endpoints.

## Implementation Details

### Cache Strategy

The implementation follows a **Cache-Aside** (Lazy Loading) pattern:

1. **Check Cache First**: When a GET request arrives, check Redis cache
2. **Cache Miss**: If not in cache, fetch from database and store in cache
3. **Cache Hit**: If in cache, return cached data (and still fetch full object from DB for relationships)
4. **Cache Invalidation**: When data is updated, invalidate the cache entry

### Cache Keys

- **Messages**: `message:{message_id}`
- **Conversations**: `conversation:{conversation_id}`

### Cache TTL

All cached entries have a **5-minute (300 seconds)** TTL to ensure data freshness.

## Modified Files

### 1. `app/services/message_service.py`

#### `get_message()` Method
- **Before**: Direct database query
- **After**: 
  - Check Redis cache first
  - On cache miss: fetch from DB, cache the result, track metrics
  - On cache hit: log hit, track metrics, still fetch full object from DB
  - Cache structure includes all message fields serialized as JSON

#### Cache Invalidation Points
- `send_message()`: Invalidates conversation cache when new message is sent
- `receive_message()`: Invalidates conversation cache when message is received
- `process_outbound_message()`: Invalidates message cache on status change (sent/failed/retry)
- `update_message_status()`: Invalidates message cache after status update

### 2. `app/services/conversation_service.py`

#### `get_conversation()` Method
- **Before**: Direct database query (with cache write only)
- **After**:
  - Check Redis cache first
  - On cache miss: fetch from DB, cache the result, track metrics
  - On cache hit: log hit, track metrics, still fetch full object from DB
  - Cache structure includes conversation metadata

#### Cache Invalidation Points
- `update_conversation()`: Invalidates cache (already existed)
- `mark_as_read()`: Invalidates conversation cache

## Cached Data Structure

### Message Cache Entry
```json
{
  "id": "uuid",
  "conversation_id": "uuid",
  "provider": "twilio|sendgrid",
  "provider_message_id": "string",
  "direction": "inbound|outbound",
  "status": "pending|sent|delivered|failed",
  "message_type": "sms|mms|email",
  "from_address": "string",
  "to_address": "string",
  "body": "string",
  "attachments": [],
  "sent_at": "ISO8601",
  "delivered_at": "ISO8601",
  "created_at": "ISO8601",
  "updated_at": "ISO8601",
  "meta_data": {}
}
```

### Conversation Cache Entry
```json
{
  "id": "uuid",
  "participant_from": "string",
  "participant_to": "string",
  "channel_type": "sms|mms|email",
  "status": "active|archived|closed",
  "message_count": 0,
  "unread_count": 0,
  "title": "string",
  "last_message_at": "ISO8601",
  "created_at": "ISO8601",
  "updated_at": "ISO8601",
  "meta_data": {}
}
```

## Metrics and Observability

### Cache Metrics
The implementation tracks cache operations using `MetricsCollector.track_cache_operation()`:
- **Cache hits**: `track_cache_operation("get", True)`
- **Cache misses**: `track_cache_operation("get", False)`
- **Cache writes**: `track_cache_operation("set", True)`

### Debug Logging
Cache operations are logged at DEBUG level:
- `Message cache hit: {message_id}`
- `Message cache miss: {message_id}`
- `Cached message: {message_id}`
- `Invalidated message cache: {message_id}`
- `Conversation cache hit: {conversation_id}`
- `Conversation cache miss: {conversation_id}`
- `Cached conversation: {conversation_id}`
- `Invalidated conversation cache: {conversation_id}`

## Performance Impact

### Expected Benefits
1. **Reduced Database Load**: Repeated reads hit cache instead of database
2. **Lower Latency**: Redis reads are typically 10-100x faster than database queries
3. **Better Scalability**: Can handle more read traffic without scaling database

### Trade-offs
1. **Additional Complexity**: Cache invalidation logic must be maintained
2. **Eventual Consistency**: Data may be slightly stale (max 5 minutes)
3. **Memory Usage**: Redis memory consumption increases with cached entries

## Testing

### Unit Tests
Created `tests/unit/test_redis_caching.py` with tests for:
- Message cache miss and hit scenarios
- Conversation cache miss and hit scenarios
- Cache invalidation on updates
- Metrics tracking

### Manual Testing
Use `test_cache_demo.py` to demonstrate caching behavior:
```bash
# Start the service
make run

# In another terminal, run the demo
python test_cache_demo.py
```

The demo script will:
1. Create test messages and conversations
2. Show cache miss on first GET
3. Show cache hit on second GET (with performance comparison)
4. Show cache invalidation after updates
5. Show cache miss again after invalidation

## Monitoring

### Checking Cache Performance

1. **View Logs**: Check application logs for cache hit/miss patterns
   ```bash
   docker compose logs -f api | grep "cache"
   ```

2. **Redis Monitoring**: Check cache size and hit rate
   ```bash
   docker compose exec redis redis-cli INFO stats
   ```

3. **Metrics Dashboard**: View cache metrics in Prometheus/Grafana
   - `cache_operations_total{operation="get", result="hit"}`
   - `cache_operations_total{operation="get", result="miss"}`
   - `cache_operations_total{operation="set"}`

## Configuration

### Cache TTL
Default: 300 seconds (5 minutes)

To modify, update the `ttl` parameter in:
- `message_service.py`: Line ~453
- `conversation_service.py`: Line ~80

### Redis Connection
Configure via environment variables:
- `REDIS_HOST`: Redis server hostname
- `REDIS_PORT`: Redis server port (default: 6379)
- `REDIS_DB`: Redis database number (default: 0)
- `REDIS_PASSWORD`: Redis password (if required)

## Best Practices

### When to Invalidate Cache
Always invalidate cache when:
- Message status changes
- Conversation metadata changes
- New messages are added to conversation
- Conversation is marked as read/unread
- Any field in cached data is modified

### Cache Key Naming
Follow the pattern: `{entity_type}:{entity_id}`
- Consistent and predictable
- Easy to invalidate specific entries
- Supports pattern matching for bulk operations

### Error Handling
- Cache failures should not break the application
- Always fall back to database on cache errors
- Log cache errors for monitoring

## Future Enhancements

### Potential Improvements
1. **Cache Warming**: Pre-populate cache for frequently accessed items
2. **Write-Through Caching**: Update cache immediately on writes
3. **Cache Statistics**: Add detailed cache hit rate tracking
4. **Selective Caching**: Cache only hot data based on access patterns
5. **Distributed Cache Invalidation**: Notify other instances on updates
6. **Smart TTL**: Adjust TTL based on data volatility
7. **Cache Compression**: Compress large entries to save memory

### Performance Tuning
1. **Monitor cache hit rate**: Target >80% hit rate
2. **Adjust TTL**: Balance freshness vs. cache efficiency
3. **Optimize cache size**: Use Redis maxmemory policies
4. **Consider cache partitioning**: Separate hot/cold data

## Troubleshooting

### Cache Not Working
1. Check Redis connection: `docker compose ps redis`
2. Verify Redis is accessible: `docker compose exec redis redis-cli PING`
3. Check logs for Redis errors: `docker compose logs redis`

### Stale Data Issues
1. Verify cache invalidation is triggered
2. Check cache TTL settings
3. Consider reducing TTL for critical data

### High Memory Usage
1. Monitor Redis memory: `docker compose exec redis redis-cli INFO memory`
2. Adjust TTL to reduce cache retention
3. Implement cache size limits
4. Use Redis maxmemory-policy settings

## Related Documentation
- [ARCHITECTURE.md](./ARCHITECTURE.md) - System architecture overview
- [ERROR_HANDLING.md](./ERROR_HANDLING.md) - Error handling patterns
- [PRD.md](./PRD.md) - Product requirements

## Summary

The Redis caching implementation provides:
✅ Cache-first read pattern for messages and conversations
✅ Automatic cache invalidation on updates
✅ 5-minute TTL for cache entries
✅ Comprehensive metrics and logging
✅ Minimal impact on existing code
✅ Improved performance and scalability

The implementation follows established patterns and best practices, ensuring maintainability and reliability while providing significant performance improvements for read-heavy workloads.

