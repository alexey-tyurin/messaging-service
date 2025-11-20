# Provider Error Handling (500, 429)

## Overview

The messaging service implements robust error handling for provider failures, specifically handling HTTP 500 (Server Error) and 429 (Rate Limit) errors with intelligent retry strategies.

## Error Types

### 1. HTTP 429 - Rate Limit Exceeded

**Cause**: Provider's API rate limits have been exceeded

**Handling Strategy**:
- **Immediate Response**: Message marked as `RETRY` status
- **Retry Delay**: Uses provider's `Retry-After` header (60-120 seconds) or exponential backoff (2x multiplier)
- **Backoff Logic**: Respects provider rate limits to avoid further penalties
- **Max Retries**: 3 attempts before marking as `FAILED`

**Example**:
```python
# Provider returns 429
ProviderRateLimitError(provider="twilio", retry_after=90)

# Service handles it:
- Retry delay: 90 seconds (or 2x previous delay)
- Status: RETRY
- Event logged: rate_limit_429
- Requeued for retry after delay
```

### 2. HTTP 500 - Server Error

**Cause**: Provider's internal server error or service unavailability

**Handling Strategy**:
- **Immediate Response**: Message marked as `RETRY` status
- **Retry Delay**: Exponential backoff (1.5x multiplier)
- **Backoff Logic**: Gradual increase to handle temporary outages
- **Max Retries**: 3 attempts before marking as `FAILED`

**Example**:
```python
# Provider returns 500
ProviderServerError(provider="sendgrid", details="Internal service unavailable")

# Service handles it:
- Retry delay: base_delay * 1.5^retry_count
- Status: RETRY
- Event logged: server_error_500
- Requeued for retry after delay
```

## Configuration

Control error simulation rates via environment variables:

```bash
# Enable error simulation (default: 0.1 = 10%)
export PROVIDER_ERROR_RATE=0.1

# Probability of 500 errors (default: 0.05 = 5%)
export PROVIDER_500_RATE=0.05

# Probability of 429 errors (default: 0.05 = 5%)
export PROVIDER_429_RATE=0.05

# Disable errors for normal operation
export PROVIDER_ERROR_RATE=0.0
export PROVIDER_500_RATE=0.0
export PROVIDER_429_RATE=0.0
```

### Configuration in `.env`:

```env
# Provider error simulation
PROVIDER_ERROR_RATE=0.0    # Disabled in production
PROVIDER_500_RATE=0.05     # 5% chance of 500 errors
PROVIDER_429_RATE=0.05     # 5% chance of 429 errors
```

## Retry Logic

### Retry Calculation

```python
# Base retry delay (from config)
base_delay = settings.queue_retry_delay  # Default: 60 seconds

# For 429 Rate Limit errors
retry_delay = max(provider_retry_after, base_delay * retry_count * 2)

# For 500 Server errors
retry_delay = base_delay * retry_count * 1.5

# For other errors
retry_delay = base_delay * retry_count
```

### Retry Flow

```
Message Send Attempt
        ↓
    [Success?]
        ↓
    Yes → Status: SENT
        ↓
        ✓ Complete
        
    No → [Check Error Type]
        ↓
    [429 Rate Limit]
        ↓
    • Log: rate_limit_429
    • Delay: 60-120s (or 2x)
    • Status: RETRY
    • Retry Count: +1
        ↓
    [Retry Count < 3?]
        ↓
    Yes → Requeue with delay
    No → Status: FAILED
    
    [500 Server Error]
        ↓
    • Log: server_error_500
    • Delay: base * 1.5^count
    • Status: RETRY
    • Retry Count: +1
        ↓
    [Retry Count < 3?]
        ↓
    Yes → Requeue with delay
    No → Status: FAILED
```

## Message Statuses

| Status | Description |
|--------|-------------|
| `PENDING` | Initial state, queued for sending |
| `SENDING` | Currently being sent to provider |
| `SENT` | Successfully sent to provider |
| `RETRY` | Failed, scheduled for retry |
| `FAILED` | Max retries exceeded |
| `DELIVERED` | Confirmed delivered (from webhook) |

## Processing Modes

### Synchronous Processing (sync_message_processing=true)

Messages are processed immediately when created:

```python
# Message created
message = await service.send_message(data)
# Immediately processed
await service.process_outbound_message(message.id)
# Returns with final status
```

**Error Handling**: Errors are handled inline with immediate retry attempts.

### Asynchronous Processing (sync_message_processing=false)

Messages are queued and processed by workers:

```python
# Message created and queued
message = await service.send_message(data)
# Returns immediately with PENDING status

# Worker picks up from queue
await worker.process_message(message.id)
# Retries handled by worker with delays
```

**Error Handling**: Failed messages are requeued with appropriate delays.

## Custom Exceptions

### ProviderError (Base)

```python
class ProviderError(Exception):
    """Base exception for provider errors."""
    def __init__(self, message: str, status_code: int, provider: str):
        self.message = message
        self.status_code = status_code
        self.provider = provider
```

### ProviderRateLimitError (429)

```python
class ProviderRateLimitError(ProviderError):
    """Exception for 429 rate limit errors."""
    def __init__(self, provider: str, retry_after: Optional[int] = None):
        self.retry_after = retry_after or 60
        super().__init__(
            f"Provider {provider} rate limit exceeded. Retry after {self.retry_after} seconds",
            429,
            provider
        )
```

### ProviderServerError (500)

```python
class ProviderServerError(ProviderError):
    """Exception for 500 server errors."""
    def __init__(self, provider: str, details: Optional[str] = None):
        message = f"Provider {provider} server error"
        if details:
            message += f": {details}"
        super().__init__(message, 500, provider)
```

## Testing

### Test Error Handling

Run the error handling test script:

```bash
# Start the service with error simulation enabled
export PROVIDER_ERROR_RATE=0.1
export PROVIDER_500_RATE=0.05
export PROVIDER_429_RATE=0.05
make restart-app

# Run the error handling test
./bin/test_error_handling.sh
```

### Expected Output

```
Provider Error Handling Test
=========================================
Sending 20 messages to demonstrate error handling...

Attempt 1: Sending sms message
✓ Message sent successfully (Status: sent, Provider: twilio)

Attempt 2: Sending email message
✗ Failed with HTTP 201 (will retry internally)

...

Message statuses:
  Sent: 16
  Retry: 3
  Failed: 1
```

### Monitor Logs

Watch error handling in real-time:

```bash
# Watch all error handling
tail -f logs/app.log | grep -E 'rate_limit|server_error|retry'

# Watch only 429 errors
tail -f logs/app.log | grep 'rate_limit_429'

# Watch only 500 errors
tail -f logs/app.log | grep 'server_error_500'
```

## Metrics

Error handling generates the following metrics:

```python
# Provider errors by type
provider_errors_total{provider="twilio", error_type="rate_limit_429"} 5
provider_errors_total{provider="twilio", error_type="server_error_500"} 3
provider_errors_total{provider="sendgrid", error_type="rate_limit_429"} 2

# Message retries
message_retry_total{provider="twilio"} 8
message_retry_total{provider="sendgrid"} 5

# Retry delays (histogram)
retry_delay_seconds{error_type="rate_limit_429"} 90
retry_delay_seconds{error_type="server_error_500"} 90
```

## Production Recommendations

### 1. Disable Error Simulation

```bash
export PROVIDER_ERROR_RATE=0.0
```

### 2. Monitor Retry Rates

- Alert if retry rate > 10%
- Alert if failed rate > 1%
- Track provider availability

### 3. Adjust Retry Configuration

```env
# Increase base delay for high-traffic
QUEUE_RETRY_DELAY=120

# Increase max retries for critical messages
QUEUE_MAX_RETRIES=5
```

### 4. Circuit Breaker

The providers already have circuit breaker configured:

```python
@circuit(failure_threshold=5, recovery_timeout=60)
```

- Opens after 5 consecutive failures
- Stays open for 60 seconds
- Prevents cascading failures

### 5. Dead Letter Queue

For messages that exceed max retries, implement a dead letter queue:

```python
if message.retry_count >= message.max_retries:
    await dead_letter_queue.add(message)
    # Manual investigation required
```

## Examples

### Example 1: Successful Send

```json
{
  "id": "abc123",
  "status": "sent",
  "provider": "twilio",
  "retry_count": 0,
  "sent_at": "2024-01-01T12:00:00Z"
}
```

### Example 2: Rate Limited (429)

```json
{
  "id": "def456",
  "status": "retry",
  "provider": "twilio",
  "retry_count": 1,
  "retry_after": "2024-01-01T12:02:00Z",
  "error_message": "Provider twilio rate limit exceeded. Retry after 90 seconds"
}
```

### Example 3: Server Error (500)

```json
{
  "id": "ghi789",
  "status": "retry",
  "provider": "sendgrid",
  "retry_count": 2,
  "retry_after": "2024-01-01T12:03:30Z",
  "error_message": "Provider sendgrid server error: Internal service unavailable"
}
```

### Example 4: Failed After Max Retries

```json
{
  "id": "jkl012",
  "status": "failed",
  "provider": "twilio",
  "retry_count": 3,
  "failed_at": "2024-01-01T12:05:00Z",
  "error_message": "Max retries exceeded"
}
```

## Architecture Benefits

1. **Resilient**: Handles provider failures gracefully
2. **Efficient**: Different strategies for different error types
3. **Observable**: Comprehensive logging and metrics
4. **Configurable**: Easy to adjust for different scenarios
5. **Testable**: Built-in error simulation for testing
6. **Production-Ready**: Circuit breakers and backoff strategies

