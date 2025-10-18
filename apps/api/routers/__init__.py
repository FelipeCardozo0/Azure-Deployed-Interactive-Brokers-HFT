"""API routers."""

from .control import router as control_router
from .health import router as health_router

__all__ = [
    "control_router",
    "health_router",
]
