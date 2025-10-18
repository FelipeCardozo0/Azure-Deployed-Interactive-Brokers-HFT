"""Control API endpoints."""

from typing import Dict, List, Optional, Any
from datetime import datetime
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from ...common.log import get_logger
from ...common.ids import generate_correlation_id

router = APIRouter(prefix="/api/v1", tags=["control"])
logger = get_logger(__name__)

# Global state (in production, this would be in a database or cache)
_kill_switch = False
_risk_limits = {
    "max_notional": 1000000.0,
    "max_qty": 1000,
    "price_band_bps": 50,
    "orders_per_sec": 10,
    "max_open_orders": 50
}
_positions = {}
_pnl = {
    "realized": 0.0,
    "unrealized": 0.0,
    "total": 0.0
}


class KillSwitchRequest(BaseModel):
    """Kill switch request."""
    active: bool
    reason: Optional[str] = None


class RiskLimitsRequest(BaseModel):
    """Risk limits request."""
    max_notional: Optional[float] = None
    max_qty: Optional[int] = None
    price_band_bps: Optional[int] = None
    orders_per_sec: Optional[int] = None
    max_open_orders: Optional[int] = None


class PositionResponse(BaseModel):
    """Position response."""
    symbol: str
    quantity: float
    avg_price: float
    market_value: float
    unrealized_pnl: float
    realized_pnl: float


class PnLResponse(BaseModel):
    """PnL response."""
    realized: float
    unrealized: float
    total: float
    timestamp: datetime


@router.get("/kill_switch")
async def get_kill_switch() -> Dict[str, Any]:
    """Get kill switch status."""
    return {
        "active": _kill_switch,
        "timestamp": datetime.utcnow().isoformat()
    }


@router.post("/kill_switch")
async def set_kill_switch(request: KillSwitchRequest) -> Dict[str, Any]:
    """Set kill switch status."""
    global _kill_switch
    
    _kill_switch = request.active
    
    logger.warning(f"Kill switch {'activated' if request.active else 'deactivated'}: {request.reason}")
    
    return {
        "active": _kill_switch,
        "reason": request.reason,
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/limits")
async def get_risk_limits() -> Dict[str, Any]:
    """Get current risk limits."""
    return {
        "limits": _risk_limits,
        "timestamp": datetime.utcnow().isoformat()
    }


@router.put("/limits")
async def update_risk_limits(request: RiskLimitsRequest) -> Dict[str, Any]:
    """Update risk limits."""
    global _risk_limits
    
    # Update only provided fields
    if request.max_notional is not None:
        _risk_limits["max_notional"] = request.max_notional
    if request.max_qty is not None:
        _risk_limits["max_qty"] = request.max_qty
    if request.price_band_bps is not None:
        _risk_limits["price_band_bps"] = request.price_band_bps
    if request.orders_per_sec is not None:
        _risk_limits["orders_per_sec"] = request.orders_per_sec
    if request.max_open_orders is not None:
        _risk_limits["max_open_orders"] = request.max_open_orders
    
    logger.info(f"Risk limits updated: {_risk_limits}")
    
    return {
        "limits": _risk_limits,
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/positions")
async def get_positions() -> List[PositionResponse]:
    """Get current positions."""
    positions = []
    
    for symbol, position in _positions.items():
        positions.append(PositionResponse(
            symbol=symbol,
            quantity=position.get("quantity", 0.0),
            avg_price=position.get("avg_price", 0.0),
            market_value=position.get("market_value", 0.0),
            unrealized_pnl=position.get("unrealized_pnl", 0.0),
            realized_pnl=position.get("realized_pnl", 0.0)
        ))
    
    return positions


@router.get("/positions/{symbol}")
async def get_position(symbol: str) -> PositionResponse:
    """Get position for specific symbol."""
    if symbol not in _positions:
        raise HTTPException(status_code=404, detail=f"Position not found for {symbol}")
    
    position = _positions[symbol]
    return PositionResponse(
        symbol=symbol,
        quantity=position.get("quantity", 0.0),
        avg_price=position.get("avg_price", 0.0),
        market_value=position.get("market_value", 0.0),
        unrealized_pnl=position.get("unrealized_pnl", 0.0),
        realized_pnl=position.get("realized_pnl", 0.0)
    )


@router.get("/pnl")
async def get_pnl() -> PnLResponse:
    """Get current PnL."""
    return PnLResponse(
        realized=_pnl["realized"],
        unrealized=_pnl["unrealized"],
        total=_pnl["total"],
        timestamp=datetime.utcnow()
    )


@router.get("/orders")
async def get_orders(symbol: Optional[str] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get orders with optional filters."""
    # This would query the actual order management system
    # For now, return mock data
    orders = [
        {
            "order_id": "12345",
            "symbol": "SPY",
            "side": "BUY",
            "quantity": 100,
            "price": 450.0,
            "status": "FILLED",
            "timestamp": datetime.utcnow().isoformat()
        }
    ]
    
    # Apply filters
    if symbol:
        orders = [o for o in orders if o["symbol"] == symbol]
    if status:
        orders = [o for o in orders if o["status"] == status]
    
    return orders


@router.get("/orders/{order_id}")
async def get_order(order_id: str) -> Dict[str, Any]:
    """Get specific order."""
    # This would query the actual order management system
    # For now, return mock data
    return {
        "order_id": order_id,
        "symbol": "SPY",
        "side": "BUY",
        "quantity": 100,
        "price": 450.0,
        "status": "FILLED",
        "timestamp": datetime.utcnow().isoformat(),
        "fills": [
            {
                "fill_id": "f12345",
                "quantity": 100,
                "price": 450.0,
                "timestamp": datetime.utcnow().isoformat()
            }
        ]
    }


@router.post("/orders/{order_id}/cancel")
async def cancel_order(order_id: str) -> Dict[str, Any]:
    """Cancel order."""
    # This would call the actual order management system
    logger.info(f"Cancelling order {order_id}")
    
    return {
        "order_id": order_id,
        "status": "CANCELLED",
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/fills")
async def get_fills(order_id: Optional[str] = None, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get fills with optional filters."""
    # This would query the actual order management system
    # For now, return mock data
    fills = [
        {
            "fill_id": "f12345",
            "order_id": "12345",
            "symbol": "SPY",
            "quantity": 100,
            "price": 450.0,
            "timestamp": datetime.utcnow().isoformat()
        }
    ]
    
    # Apply filters
    if order_id:
        fills = [f for f in fills if f["order_id"] == order_id]
    if symbol:
        fills = [f for f in fills if f["symbol"] == symbol]
    
    return fills


@router.get("/metrics")
async def get_metrics() -> Dict[str, Any]:
    """Get system metrics."""
    return {
        "system": {
            "uptime": "2h 30m",
            "memory_usage": "512MB",
            "cpu_usage": "15%"
        },
        "trading": {
            "orders_today": 150,
            "fills_today": 120,
            "rejections_today": 5,
            "avg_fill_latency": "45ms"
        },
        "risk": {
            "kill_switch": _kill_switch,
            "active_orders": 3,
            "exposure_pct": 25.5,
            "stale_data_count": 0
        },
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/alerts")
async def get_alerts() -> List[Dict[str, Any]]:
    """Get current alerts."""
    alerts = []
    
    if _kill_switch:
        alerts.append({
            "type": "KILL_SWITCH",
            "severity": "CRITICAL",
            "message": "Kill switch is active",
            "timestamp": datetime.utcnow().isoformat()
        })
    
    return alerts


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str) -> Dict[str, Any]:
    """Acknowledge alert."""
    logger.info(f"Alert {alert_id} acknowledged")
    
    return {
        "alert_id": alert_id,
        "acknowledged": True,
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/status")
async def get_system_status() -> Dict[str, Any]:
    """Get overall system status."""
    return {
        "status": "RUNNING" if not _kill_switch else "STOPPED",
        "kill_switch": _kill_switch,
        "risk_limits": _risk_limits,
        "positions_count": len(_positions),
        "active_orders": 3,
        "timestamp": datetime.utcnow().isoformat()
    }
