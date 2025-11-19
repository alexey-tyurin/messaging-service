"""
Observability module providing structured logging, metrics collection, and distributed tracing.
"""

import logging
import time
import json
from typing import Dict, Any, Optional, Callable
from functools import wraps
from contextlib import contextmanager
from datetime import datetime
import structlog
from prometheus_client import (
    Counter, Histogram, Gauge, Summary,
    generate_latest, CollectorRegistry, CONTENT_TYPE_LATEST
)
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

from app.core.config import settings


# Initialize structured logging
def setup_logging():
    """Configure structured logging with correlation IDs."""
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.CallsiteParameterAdder(
                parameters=[
                    structlog.processors.CallsiteParameter.FILENAME,
                    structlog.processors.CallsiteParameter.FUNC_NAME,
                    structlog.processors.CallsiteParameter.LINENO,
                ]
            ),
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer() if settings.log_format == "json" else structlog.dev.ConsoleRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Set log level
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, settings.log_level.upper())
    )


# Get logger instance
def get_logger(name: str) -> structlog.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)


# Metrics Registry
registry = CollectorRegistry()

# Define metrics
message_counter = Counter(
    'messages_total',
    'Total number of messages processed',
    ['direction', 'type', 'status', 'provider'],
    registry=registry
)

message_duration = Histogram(
    'message_processing_duration_seconds',
    'Message processing duration',
    ['message_type', 'provider'],
    registry=registry
)

conversation_gauge = Gauge(
    'active_conversations',
    'Number of active conversations',
    ['channel_type'],
    registry=registry
)

api_request_counter = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status_code'],
    registry=registry
)

api_request_duration = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration',
    ['method', 'endpoint'],
    registry=registry
)

queue_depth_gauge = Gauge(
    'queue_depth',
    'Current queue depth',
    ['queue_name'],
    registry=registry
)

db_connection_pool = Gauge(
    'database_connection_pool_size',
    'Database connection pool metrics',
    ['metric_type'],  # active, idle, overflow
    registry=registry
)

cache_operations = Counter(
    'cache_operations_total',
    'Cache operations',
    ['operation', 'result'],  # hit/miss
    registry=registry
)

provider_errors = Counter(
    'provider_errors_total',
    'Provider API errors',
    ['provider', 'error_type'],
    registry=registry
)

rate_limit_hits = Counter(
    'rate_limit_hits_total',
    'Rate limit hits',
    ['client', 'endpoint'],
    registry=registry
)


class MetricsCollector:
    """Collects and exposes application metrics."""
    
    @staticmethod
    def track_message(direction: str, msg_type: str, status: str, provider: str):
        """Track message metrics."""
        message_counter.labels(
            direction=direction,
            type=msg_type,
            status=status,
            provider=provider
        ).inc()
    
    @staticmethod
    @contextmanager
    def track_duration(msg_type: str, provider: str):
        """Track operation duration."""
        start = time.time()
        yield
        duration = time.time() - start
        message_duration.labels(
            message_type=msg_type,
            provider=provider
        ).observe(duration)
    
    @staticmethod
    def track_api_request(method: str, endpoint: str, status_code: int, duration: float):
        """Track API request metrics."""
        api_request_counter.labels(
            method=method,
            endpoint=endpoint,
            status_code=status_code
        ).inc()
        api_request_duration.labels(
            method=method,
            endpoint=endpoint
        ).observe(duration)
    
    @staticmethod
    def update_conversation_count(channel_type: str, count: int):
        """Update active conversation count."""
        conversation_gauge.labels(channel_type=channel_type).set(count)
    
    @staticmethod
    def update_queue_depth(queue_name: str, depth: int):
        """Update queue depth metric."""
        queue_depth_gauge.labels(queue_name=queue_name).set(depth)
    
    @staticmethod
    def track_cache_operation(operation: str, hit: bool):
        """Track cache operations."""
        result = "hit" if hit else "miss"
        cache_operations.labels(operation=operation, result=result).inc()
    
    @staticmethod
    def track_provider_error(provider: str, error_type: str):
        """Track provider errors."""
        provider_errors.labels(provider=provider, error_type=error_type).inc()
    
    @staticmethod
    def track_rate_limit(client: str, endpoint: str):
        """Track rate limit hits."""
        rate_limit_hits.labels(client=client, endpoint=endpoint).inc()
    
    @staticmethod
    def get_metrics() -> bytes:
        """Get metrics in Prometheus format."""
        return generate_latest(registry)


# Tracing Setup
tracer = None

def setup_tracing():
    """Configure OpenTelemetry tracing."""
    global tracer
    
    if not settings.tracing_enabled:
        return
    
    # Create resource
    resource = Resource.create({
        "service.name": "messaging-service",
        "service.version": settings.app_version,
        "deployment.environment": settings.environment,
    })
    
    # Create tracer provider
    provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(provider)
    
    # Add OTLP exporter if configured
    if settings.environment != "development":
        otlp_exporter = OTLPSpanExporter(
            endpoint="otel-collector:4317",
            insecure=True
        )
        provider.add_span_processor(
            BatchSpanProcessor(otlp_exporter)
        )
    
    # Get tracer
    tracer = trace.get_tracer(__name__)


def trace_operation(name: str):
    """Decorator to trace function execution."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            if not tracer:
                return await func(*args, **kwargs)
            
            with tracer.start_as_current_span(name) as span:
                try:
                    span.set_attribute("function.name", func.__name__)
                    result = await func(*args, **kwargs)
                    span.set_status(trace.Status(trace.StatusCode.OK))
                    return result
                except Exception as e:
                    span.set_status(
                        trace.Status(trace.StatusCode.ERROR, str(e))
                    )
                    span.record_exception(e)
                    raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            if not tracer:
                return func(*args, **kwargs)
            
            with tracer.start_as_current_span(name) as span:
                try:
                    span.set_attribute("function.name", func.__name__)
                    result = func(*args, **kwargs)
                    span.set_status(trace.Status(trace.StatusCode.OK))
                    return result
                except Exception as e:
                    span.set_status(
                        trace.Status(trace.StatusCode.ERROR, str(e))
                    )
                    span.record_exception(e)
                    raise
        
        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


class CorrelationIdMiddleware:
    """Middleware to add correlation IDs to requests."""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            import uuid
            correlation_id = str(uuid.uuid4())
            
            # Add to context
            structlog.contextvars.bind_contextvars(
                correlation_id=correlation_id
            )
            
            # Add to response headers
            async def send_wrapper(message):
                if message["type"] == "http.response.start":
                    headers = dict(message.get("headers", []))
                    headers[b"x-correlation-id"] = correlation_id.encode()
                    message["headers"] = list(headers.items())
                await send(message)
            
            await self.app(scope, receive, send_wrapper)
        else:
            await self.app(scope, receive, send)


# Health monitoring
class HealthMonitor:
    """Monitor application health."""
    
    def __init__(self):
        self.checks = {}
    
    def register_check(self, name: str, check_func: Callable):
        """Register a health check."""
        self.checks[name] = check_func
    
    async def check_health(self) -> Dict[str, Any]:
        """Run all health checks."""
        results = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "checks": {}
        }
        
        for name, check_func in self.checks.items():
            try:
                # Handle both sync and async functions
                import asyncio
                if asyncio.iscoroutinefunction(check_func):
                    result = await check_func()
                else:
                    result = check_func()
                
                results["checks"][name] = {
                    "status": "healthy" if result else "unhealthy",
                    "result": result
                }
                
                if not result:
                    results["status"] = "unhealthy"
                    
            except Exception as e:
                results["checks"][name] = {
                    "status": "unhealthy",
                    "error": str(e)
                }
                results["status"] = "unhealthy"
        
        return results


# Initialize health monitor
health_monitor = HealthMonitor()


# Performance monitoring decorator
def monitor_performance(operation_name: str):
    """Decorator to monitor function performance."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            logger = get_logger(__name__)
            start_time = time.time()
            
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time
                
                logger.info(
                    f"{operation_name} completed",
                    operation=operation_name,
                    duration=duration,
                    status="success"
                )
                
                return result
                
            except Exception as e:
                duration = time.time() - start_time
                
                logger.error(
                    f"{operation_name} failed",
                    operation=operation_name,
                    duration=duration,
                    status="error",
                    error=str(e)
                )
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            logger = get_logger(__name__)
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                
                logger.info(
                    f"{operation_name} completed",
                    operation=operation_name,
                    duration=duration,
                    status="success"
                )
                
                return result
                
            except Exception as e:
                duration = time.time() - start_time
                
                logger.error(
                    f"{operation_name} failed",
                    operation=operation_name,
                    duration=duration,
                    status="error",
                    error=str(e)
                )
                raise
        
        # Return appropriate wrapper
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


# Initialize observability on startup
def init_observability():
    """Initialize all observability components."""
    setup_logging()
    setup_tracing()
    
    logger = get_logger(__name__)
    logger.info(
        "Observability initialized",
        metrics_enabled=settings.metrics_enabled,
        tracing_enabled=settings.tracing_enabled,
        log_level=settings.log_level
    )
