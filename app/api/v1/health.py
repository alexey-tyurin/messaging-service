"""
API endpoints for health checks and readiness probes.
"""

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.models import HealthResponse
from app.db.session import get_db, db_manager
from app.db.redis import redis_manager
from app.core.observability import health_monitor, get_logger
from datetime import datetime


logger = get_logger(__name__)
router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Basic health check endpoint.
    
    Returns the overall health status of the application.
    Used by load balancers and orchestrators for liveness probes.
    """
    try:
        # Run all registered health checks
        health_status = await health_monitor.check_health()
        
        return HealthResponse(**health_status)
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthResponse(
            status="unhealthy",
            timestamp=datetime.utcnow(),
            checks={
                "error": {
                    "status": "unhealthy",
                    "error": str(e)
                }
            }
        )


@router.get("/ready")
async def readiness_check(
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    """
    Readiness probe endpoint.
    
    Checks if the service is ready to accept traffic.
    Verifies database connectivity, Redis connection, and provider availability.
    """
    try:
        checks = {}
        is_ready = True
        
        # Check database
        try:
            db_healthy = await db_manager.health_check()
            checks["database"] = {
                "status": "healthy" if db_healthy else "unhealthy",
                "connected": db_healthy
            }
            if not db_healthy:
                is_ready = False
        except Exception as e:
            checks["database"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            is_ready = False
        
        # Check Redis
        try:
            redis_healthy = await redis_manager.health_check()
            checks["redis"] = {
                "status": "healthy" if redis_healthy else "unhealthy",
                "connected": redis_healthy
            }
            if not redis_healthy:
                is_ready = False
        except Exception as e:
            checks["redis"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            is_ready = False
        
        # Check providers
        try:
            from app.providers.base import ProviderFactory
            
            provider_checks = {}
            for provider_type, provider in ProviderFactory._providers.items():
                try:
                    provider_healthy = await provider.health_check()
                    provider_checks[provider_type] = {
                        "status": "healthy" if provider_healthy else "unhealthy",
                        "available": provider_healthy
                    }
                except Exception as e:
                    provider_checks[provider_type] = {
                        "status": "unhealthy",
                        "error": str(e)
                    }
            
            checks["providers"] = provider_checks
            
        except Exception as e:
            checks["providers"] = {
                "status": "unhealthy",
                "error": str(e)
            }
            is_ready = False
        
        # Set appropriate status code
        if not is_ready:
            response.status_code = 503  # Service Unavailable
        
        return {
            "ready": is_ready,
            "timestamp": datetime.utcnow().isoformat(),
            "checks": checks
        }
        
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        response.status_code = 503
        return {
            "ready": False,
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }


@router.get("/live")
async def liveness_check():
    """
    Simple liveness check endpoint.
    
    Returns 200 if the service is alive.
    Does not check external dependencies.
    """
    return {"status": "alive", "timestamp": datetime.utcnow().isoformat()}


@router.get("/startup")
async def startup_check():
    """
    Startup probe endpoint.
    
    Used during application startup to determine when the service
    is ready to accept traffic for the first time.
    """
    try:
        # Check if core services are initialized
        from app.providers.base import ProviderFactory
        
        checks = {
            "database_initialized": db_manager.engine is not None,
            "redis_initialized": redis_manager.redis_client is not None,
            "providers_initialized": len(ProviderFactory._providers) > 0
        }
        
        all_initialized = all(checks.values())
        
        return {
            "started": all_initialized,
            "timestamp": datetime.utcnow().isoformat(),
            "initialization": checks
        }
        
    except Exception as e:
        logger.error(f"Startup check failed: {e}")
        return {
            "started": False,
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }


@router.get("/dependencies")
async def dependency_check(db: AsyncSession = Depends(get_db)):
    """
    Check status of all external dependencies.
    
    Provides detailed information about each dependency's health.
    """
    try:
        dependencies = {}
        
        # Database version and connection info
        try:
            from sqlalchemy import text
            result = await db.execute(text("SELECT version()"))
            db_version = result.scalar()
            
            dependencies["postgresql"] = {
                "status": "healthy",
                "version": db_version,
                "connection_pool": {
                    "size": db_manager.engine.pool.size() if hasattr(db_manager.engine.pool, 'size') else "N/A",
                    "checked_out": db_manager.engine.pool.checkedout() if hasattr(db_manager.engine.pool, 'checkedout') else "N/A"
                }
            }
        except Exception as e:
            dependencies["postgresql"] = {
                "status": "unhealthy",
                "error": str(e)
            }
        
        # Redis info
        try:
            redis_info = await redis_manager.redis_client.info()
            dependencies["redis"] = {
                "status": "healthy",
                "version": redis_info.get("redis_version", "unknown"),
                "connected_clients": redis_info.get("connected_clients", 0),
                "used_memory": redis_info.get("used_memory_human", "unknown")
            }
        except Exception as e:
            dependencies["redis"] = {
                "status": "unhealthy",
                "error": str(e)
            }
        
        # Provider APIs
        from app.providers.base import ProviderFactory
        
        for provider_type, provider in ProviderFactory._providers.items():
            try:
                is_healthy = await provider.health_check()
                dependencies[f"provider_{provider_type}"] = {
                    "status": "healthy" if is_healthy else "unhealthy",
                    "type": provider_type
                }
            except Exception as e:
                dependencies[f"provider_{provider_type}"] = {
                    "status": "unhealthy",
                    "error": str(e)
                }
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "dependencies": dependencies
        }
        
    except Exception as e:
        logger.error(f"Dependency check failed: {e}")
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e),
            "dependencies": {}
        }
