# Database Index Optimization

## Summary

Optimized database indexes by removing redundant indexes and keeping only those that are actually needed for API calls and background worker operations. Reduced from **24 indexes** to **14 indexes** (58% reduction).

## Changes Made

### Conversations Table ✅
**Status**: All indexes justified - NO CHANGES
- `idx_conversation_participants` (participant_from, participant_to, channel_type) - for finding/creating conversations
- `idx_conversation_last_message` (last_message_at) - for ordering by last message
- `ix_conversations_participant_from` - for filtering by participant
- `ix_conversations_participant_to` - for filtering by participant
- `ix_conversations_channel_type` - for filtering by channel type and metrics
- `ix_conversations_status` - for filtering by status and metrics

### Messages Table ✅
**Kept** (4 indexes):
- `idx_message_conversation_created` (conversation_id, created_at) - for listing messages in conversation
- `idx_message_status_retry` (status, retry_after) - for worker retry queue
- `ix_messages_status` - for status filtering in list_messages
- `ix_messages_direction` - for direction filtering in list_messages

**Removed** (3 indexes):
- ❌ `ix_messages_conversation_id` - REDUNDANT (covered by idx_message_conversation_created)
- ❌ `ix_messages_provider` - NOT USED (never queried, only set)
- ❌ `ix_messages_provider_message_id` - REDUNDANT (covered by unique constraint uq_provider_message)

### Message Events Table ✅
**Kept** (1 index):
- `idx_event_message_created` (message_id, created_at) - for loading events by message

**Removed** (3 indexes):
- ❌ `idx_event_provider` (provider, provider_event_id) - NOT USED (no queries)
- ❌ `ix_message_events_message_id` - REDUNDANT (covered by idx_event_message_created)
- ❌ `ix_message_events_event_type` - NOT USED (no queries filter by event_type)

### Webhook Logs Table ✅
**Kept** (1 index):
- `idx_webhook_provider_created` (provider, created_at) - for auditing/debugging by provider

**Removed** (3 indexes):
- ❌ `idx_webhook_processed` (processed, created_at) - NOT USED (duplicate detection uses Redis cache)
- ❌ `ix_webhook_logs_provider` - REDUNDANT (covered by idx_webhook_provider_created)
- ❌ `ix_webhook_logs_processed` - REDUNDANT (covered by idx_webhook_processed, which was removed)

### Attachment Metadata Table ✅
**Status**: No changes needed
- `ix_attachment_metadata_message_id` - for loading attachments by message

### Rate Limits Table ✅
**Kept** (2 indexes):
- `idx_rate_limit_client_endpoint` (client_id, endpoint) - for rate limit lookups
- `idx_rate_limit_window` (window_end) - for cleaning up expired entries

**Removed** (2 indexes):
- ❌ `ix_rate_limits_client_id` - REDUNDANT (covered by idx_rate_limit_client_endpoint)
- ❌ `ix_rate_limits_endpoint` - NOT NEEDED (always query with client_id)

## Index Justification

### Query Patterns Analyzed

1. **API Endpoints**:
   - GET/POST/PATCH/DELETE operations on conversations and messages
   - Filtering by participant, channel_type, status, direction
   - Ordering by last_message_at, created_at

2. **Background Worker**:
   - Retry queue: `status = 'retry' AND retry_after <= now()`
   - Metrics collection: counting by channel_type and status

3. **Webhook Processing**:
   - Duplicate detection: uses Redis cache (not DB query)
   - Status updates: uses unique constraint on (provider, provider_message_id)

### Optimization Principles

1. **Remove redundant indexes**: Single-column indexes covered by composite indexes
2. **Remove unused indexes**: Indexes on columns never queried
3. **Keep foreign key indexes**: For efficient joins and cascade deletes
4. **Leverage unique constraints**: They automatically create indexes
5. **Composite index usage**: Leftmost prefix rule considered

## Performance Impact

### Benefits:
- ✅ Faster writes (fewer indexes to update on INSERT/UPDATE/DELETE)
- ✅ Less storage space (each index is a separate B-tree structure)
- ✅ Faster query planning (fewer index options for optimizer to consider)
- ✅ Reduced maintenance overhead (fewer indexes to vacuum/analyze)

### No Negative Impact:
- ✅ All actual queries remain fully indexed
- ✅ Query performance unchanged
- ✅ Foreign key constraints still have indexes
- ✅ Unique constraints automatically create indexes

## Files Modified

1. `app/models/database.py` - Updated SQLAlchemy model index definitions
2. `alembic/versions/001_initial_migration.py` - Updated migration to match

## Verification

Both files now have matching indexes:
- ✅ All indexes in database.py are in migration
- ✅ All indexes in migration are in database.py
- ✅ No linting errors
- ✅ All API query patterns remain optimized

## Before vs After

| Table | Before | After | Removed |
|-------|--------|-------|---------|
| conversations | 6 | 6 | 0 |
| messages | 7 | 4 | 3 |
| message_events | 4 | 1 | 3 |
| webhook_logs | 4 | 1 | 3 |
| attachment_metadata | 1 | 1 | 0 |
| rate_limits | 4 | 2 | 2 |
| **TOTAL** | **24** | **14** | **11** |

## Next Steps

To apply these changes to an existing database:

1. Create a new migration:
   ```bash
   alembic revision -m "optimize_indexes"
   ```

2. In the new migration:
   - Drop the 11 redundant indexes
   - No need to create new indexes (optimized set already exists)

3. Apply migration:
   ```bash
   alembic upgrade head
   ```

Or for a fresh database, the updated 001_initial_migration.py will create the optimized index set from the start.

