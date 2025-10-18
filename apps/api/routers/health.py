"""Health check API endpoints."""

from typing import Dict, Any
from datetime import datetime
from fastapi import APIRouter, HTTPException
from ...common.log import get_logger

router = APIRouter(prefix="/api/v1", tags=["health"])
logger = get_logger(__name__)


@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """Basic health check."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0"
    }


@router.get("/health/detailed")
async def detailed_health_check() -> Dict[str, Any]:
    """Detailed health check with component status."""
    try:
        # Check database connections
        db_status = await _check_database_health()
        
        # Check Redis connection
        redis_status = await _check_redis_health()
        
        # Check Kafka connection
        kafka_status = await _check_kafka_health()
        
        # Check IB Gateway connection
        ib_status = await _check_ib_health()
        
        # Overall health
        all_healthy = all([
            db_status["healthy"],
            redis_status["healthy"],
            kafka_status["healthy"],
            ib_status["healthy"]
        ])
        
        return {
            "status": "healthy" if all_healthy else "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "components": {
                "database": db_status,
                "redis": redis_status,
                "kafka": kafka_status,
                "ib_gateway": ib_status
            },
            "overall": "healthy" if all_healthy else "unhealthy"
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Health check failed")


@router.get("/health/readiness")
async def readiness_check() -> Dict[str, Any]:
    """Readiness check for Kubernetes."""
    try:
        # Check if all critical components are ready
        db_ready = await _check_database_health()
        redis_ready = await _check_redis_health()
        
        ready = db_ready["healthy"] and redis_ready["healthy"]
        
        return {
            "status": "ready" if ready else "not_ready",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return {
            "status": "not_ready",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


@router.get("/health/liveness")
async def liveness_check() -> Dict[str, Any]:
    """Liveness check for Kubernetes."""
    return {
        "status": "alive",
        "timestamp": datetime.utcnow().isoformat()
    }


async def _check_database_health() -> Dict[str, Any]:
    """Check database health."""
    try:
        # This would check actual database connection
        # For now, return mock status
        return {
            "healthy": True,
            "type": "postgresql",
            "response_time_ms": 5,
            "last_check": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {
            "healthy": False,
            "error": str(e),
            "last_check": datetime.utcnow().isoformat()
        }


async def _check_redis_health() -> Dict[str, Any]:
    """Check Redis health."""
    try:
        # This would check actual Redis connection
        # For now, return mock status
        return {
            "healthy": True,
            "type": "redis",
            "response_time_ms": 2,
            "last_check": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {
            "healthy": False,
            "error": str(e),
            "last_check": datetime.utcnow().isoformat()
        }


async def _check_kafka_health() -> Dict[str, Any]:
    """Check Kafka health."""
    try:
        # This would check actual Kafka connection
        # For now, return mock status
        return {
            "healthy": True,
            "type": "kafka",
            "response_time_ms": 10,
            "last_check": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {
            "healthy": False,
            "error": str(e),
            "last_check": datetime.utcnow().isoformat()
        }


async def _check_ib_health() -> Dict[str, Any]:
    """Check IB Gateway health."""
    try:
        # This would check actual IB Gateway connection
        # For now, return mock status
        return {
            "healthy": True,
            "type": "ib_gateway",
            "response_time_ms": 15,
            "last_check": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {
            "healthy": False,
            "error": str(e),
            "last_check": datetime.utcnow().isoformat()
        }
