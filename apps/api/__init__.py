"""FastAPI application for trading system control."""

from .main import create_app
from .routers.control import router as control_router
from .routers.health import router as health_router

__all__ = [
    "create_app",
    "control_router",
    "health_router",
]
