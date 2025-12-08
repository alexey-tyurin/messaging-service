
import pytest
from unittest.mock import Mock, patch
from app.core.observability import MetricsCollector, init_observability, HealthMonitor

# Mock structlog to avoid configuration errors during tests if multiple calls
@patch("app.core.observability.setup_logging")
@patch("app.core.observability.setup_tracing")
def test_init_observability(mock_tracing, mock_logging):
    """Test initialization."""
    init_observability()
    mock_logging.assert_called_once()
    mock_tracing.assert_called_once()

def test_metrics_collector():
    """Test metrics collector."""
    # Test tracking message - verify no error raised
    MetricsCollector.track_message("outbound", "sms", "sent", "twilio")
    
    # Test error tracking
    MetricsCollector.track_provider_error("twilio", "ValueError")
    
    # Test track duration context manager
    with MetricsCollector.track_duration("sms", "twilio"):
         pass
         
    # Test api request
    MetricsCollector.track_api_request("GET", "/test", 200, 0.1)
    
    # Test queues
    MetricsCollector.update_queue_depth("sms", 10)
    
    # Test cache
    MetricsCollector.track_cache_operation("get", True)

@pytest.mark.asyncio
async def test_health_monitor():
    """Test health monitor."""
    monitor = HealthMonitor()
    
    def sync_check():
        return True
        
    async def async_check():
        return True
        
    def fail_check():
        return False
        
    monitor.register_check("sync", sync_check)
    monitor.register_check("async", async_check)
    
    result = await monitor.check_health()
    assert result["status"] == "healthy"
    assert result["checks"]["sync"]["status"] == "healthy"
    assert result["checks"]["async"]["status"] == "healthy"
    
    monitor.register_check("fail", fail_check)
    result = await monitor.check_health()
    assert result["status"] == "unhealthy"
