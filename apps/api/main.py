"""Main FastAPI application."""

import asyncio
import uvloop
from typing import Dict, Any
from datetime import datetime
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
import uvicorn

from ..common.log import get_logger, set_correlation_id, generate_correlation_id
from ..common.config import settings
from .routers.control import router as control_router
from .routers.health import router as health_router


def create_app() -> FastAPI:
    """Create FastAPI application."""
    app = FastAPI(
        title="Trading System API",
        description="High Frequency Trading System Control API",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc"
    )
    
    # Add middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*"]  # Configure appropriately for production
    )
    
    # Add request logging middleware
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        # Generate correlation ID
        correlation_id = generate_correlation_id()
        set_correlation_id(correlation_id)
        
        # Log request
        logger = get_logger(__name__)
        logger.info(f"Request: {request.method} {request.url}")
        
        # Process request
        start_time = datetime.utcnow()
        response = await call_next(request)
        process_time = (datetime.utcnow() - start_time).total_seconds()
        
        # Log response
        logger.info(f"Response: {response.status_code} in {process_time:.3f}s")
        
        # Add correlation ID to response headers
        response.headers["X-Correlation-ID"] = correlation_id
        
        return response
    
    # Add routers
    app.include_router(control_router)
    app.include_router(health_router)
    
    # Add Prometheus metrics endpoint
    @app.get("/metrics")
    async def metrics():
        """Prometheus metrics endpoint."""
        return Response(
            generate_latest(),
            media_type=CONTENT_TYPE_LATEST
        )
    
    # Add root endpoint
    @app.get("/")
    async def root():
        """Root endpoint."""
        return {
            "message": "Trading System API",
            "version": "1.0.0",
            "timestamp": datetime.utcnow().isoformat(),
            "docs": "/docs"
        }
    
    # Add global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """Global exception handler."""
        logger = get_logger(__name__)
        logger.error(f"Unhandled exception: {exc}")
        
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "message": str(exc),
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    return app


def main():
    """Main entry point for API server."""
    # Set up uvloop for better performance
    uvloop.install()
    
    # Create app
    app = create_app()
    
    # Run server
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
        access_log=True
    )


if __name__ == "__main__":
    main()
