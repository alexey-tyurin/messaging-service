"""
Main FastAPI application with API endpoints for the messaging service.
"""

from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from contextlib import asynccontextmanager
from typing import List, Optional, Dict, Any
import time
import logging

from app.core.config import settings
from app.core.observability import (
    init_observability, CorrelationIdMiddleware, health_monitor,
    MetricsCollector, get_logger
)
from app.db.session import init_database, close_database, get_db
from app.db.redis import init_redis, close_redis, redis_manager
from app.providers.base import ProviderFactory
from app.api.v1 import messages, conversations, webhooks, health
from app.api.v1.models import ErrorResponse


logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Handles startup and shutdown events.
    """
    # Startup
    logger.info("Starting messaging service...")
    
    # Initialize observability
    init_observability()
    
    # Initialize database
    await init_database()
    
    # Initialize Redis
    await init_redis()
    
    # Initialize providers
    await ProviderFactory.init_providers()
    
    # Register health checks
    health_monitor.register_check("database", lambda: True)
    health_monitor.register_check("redis", redis_manager.health_check)
    
    logger.info("Messaging service started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down messaging service...")
    
    # Close providers
    await ProviderFactory.close_providers()
    
    # Close Redis
    await close_redis()
    
    # Close database
    await close_database()
    
    logger.info("Messaging service shut down successfully")


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Unified messaging API for SMS, MMS, Email, and Voice",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=settings.cors_allow_methods,
    allow_headers=settings.cors_allow_headers,
)

# Add correlation ID middleware
app.add_middleware(CorrelationIdMiddleware)


# Middleware for request logging and metrics
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log and track all HTTP requests."""
    start_time = time.time()
    
    # Log request
    logger.info(
        "Request received",
        method=request.method,
        path=request.url.path,
        client=request.client.host if request.client else None
    )
    
    try:
        response = await call_next(request)
        
        # Calculate duration
        duration = time.time() - start_time
        
        # Track metrics
        MetricsCollector.track_api_request(
            method=request.method,
            endpoint=request.url.path,
            status_code=response.status_code,
            duration=duration
        )
        
        # Log response
        logger.info(
            "Request completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration=duration
        )
        
        return response
        
    except Exception as e:
        duration = time.time() - start_time
        
        logger.error(
            "Request failed",
            method=request.method,
            path=request.url.path,
            error=str(e),
            duration=duration
        )
        
        # Track error metric
        MetricsCollector.track_api_request(
            method=request.method,
            endpoint=request.url.path,
            status_code=500,
            duration=duration
        )
        
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error="Internal server error",
                message="An unexpected error occurred"
            ).dict()
        )


# Rate limiting middleware
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Apply rate limiting to API requests."""
    if not settings.rate_limit_enabled:
        return await call_next(request)
    
    # Get client identifier (IP or API key)
    client_id = request.client.host if request.client else "unknown"
    endpoint = request.url.path
    
    # Check rate limit
    allowed, remaining = await redis_manager.check_rate_limit(
        key=f"rate_limit:{client_id}:{endpoint}",
        limit=settings.rate_limit_requests,
        window=settings.rate_limit_period
    )
    
    if not allowed:
        MetricsCollector.track_rate_limit(client_id, endpoint)
        
        return JSONResponse(
            status_code=429,
            content=ErrorResponse(
                error="Rate limit exceeded",
                message=f"Too many requests. Please try again later."
            ).dict(),
            headers={
                "X-RateLimit-Limit": str(settings.rate_limit_requests),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(settings.rate_limit_period)
            }
        )
    
    # Add rate limit headers
    response = await call_next(request)
    response.headers["X-RateLimit-Limit"] = str(settings.rate_limit_requests)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    response.headers["X-RateLimit-Reset"] = str(settings.rate_limit_period)
    
    return response


# Include API routers
app.include_router(
    messages.router,
    prefix=f"{settings.api_prefix}/messages",
    tags=["messages"]
)

app.include_router(
    conversations.router,
    prefix=f"{settings.api_prefix}/conversations",
    tags=["conversations"]
)

app.include_router(
    webhooks.router,
    prefix=f"{settings.api_prefix}/webhooks",
    tags=["webhooks"]
)

app.include_router(
    health.router,
    prefix="",
    tags=["health"]
)


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "operational",
        "documentation": "/docs" if settings.debug else None
    }


# Metrics endpoint
@app.get("/metrics", response_class=PlainTextResponse)
async def metrics():
    """Prometheus metrics endpoint."""
    if not settings.metrics_enabled:
        raise HTTPException(
            status_code=404,
            detail="Metrics not enabled"
        )
    
    return MetricsCollector.get_metrics()


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle uncaught exceptions."""
    logger.error(
        "Unhandled exception",
        path=request.url.path,
        method=request.method,
        error=str(exc),
        exc_info=True
    )
    
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="Internal server error",
            message="An unexpected error occurred"
        ).dict()
    )


# 404 handler
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Handle 404 errors."""
    return JSONResponse(
        status_code=404,
        content=ErrorResponse(
            error="Not found",
            message=f"The requested resource was not found"
        ).dict()
    )


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        workers=settings.workers if not settings.debug else 1,
        log_level=settings.log_level.lower()
    )
