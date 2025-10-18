"""Pre-trade risk management."""

import time
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from ..common.log import get_logger
from ..common.config import settings


class RiskLevel(Enum):
    """Risk levels."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RiskDecision(Enum):
    """Risk decisions."""
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    REDUCE = "REDUCE"
    HOLD = "HOLD"


@dataclass
class RiskCheck:
    """Risk check result."""
    decision: RiskDecision
    level: RiskLevel
    reason: str
    suggested_quantity: Optional[float] = None
    suggested_price: Optional[float] = None


@dataclass
class RiskConfig:
    """Risk management configuration."""
    max_notional: float = 1000000.0
    max_qty: int = 1000
    price_band_bps: int = 50
    orders_per_sec: int = 10
    max_open_orders: int = 50
    stale_data_threshold: int = 3  # seconds
    drawdown_limit: float = 0.05
    position_limit_pct: float = 0.1
    exposure_limit_pct: float = 0.5


class PreTradeRisk:
    """Pre-trade risk management system."""
    
    def __init__(self, config: RiskConfig):
        self.config = config
        self.logger = get_logger(__name__)
        self.order_counts: Dict[str, List[datetime]] = {}
        self.open_orders: Dict[str, int] = {}
        self.positions: Dict[str, float] = {}
        self.last_prices: Dict[str, Dict[str, Any]] = {}
        self.kill_switch = False
        
    def check_order(self, symbol: str, side: str, quantity: float, price: Optional[float],
                   order_id: str, correlation_id: str) -> RiskCheck:
        """Perform comprehensive pre-trade risk checks."""
        try:
            # Check kill switch
            if self.kill_switch:
                return RiskCheck(
                    decision=RiskDecision.REJECT,
                    level=RiskLevel.CRITICAL,
                    reason="Kill switch is active"
                )
            
            # Check data freshness
            data_check = self._check_data_freshness(symbol)
            if data_check.decision == RiskDecision.REJECT:
                return data_check
            
            # Check position limits
            position_check = self._check_position_limits(symbol, side, quantity, price)
            if position_check.decision == RiskDecision.REJECT:
                return position_check
            
            # Check notional limits
            notional_check = self._check_notional_limits(symbol, quantity, price)
            if notional_check.decision == RiskDecision.REJECT:
                return notional_check
            
            # Check quantity limits
            quantity_check = self._check_quantity_limits(symbol, quantity)
            if quantity_check.decision == RiskDecision.REJECT:
                return quantity_check
            
            # Check price bands
            price_check = self._check_price_bands(symbol, price)
            if price_check.decision == RiskDecision.REJECT:
                return price_check
            
            # Check order rate limits
            rate_check = self._check_order_rate_limits(symbol)
            if rate_check.decision == RiskDecision.REJECT:
                return rate_check
            
            # Check open order limits
            order_check = self._check_open_order_limits(symbol)
            if order_check.decision == RiskDecision.REJECT:
                return order_check
            
            # Check drawdown limits
            drawdown_check = self._check_drawdown_limits()
            if drawdown_check.decision == RiskDecision.REJECT:
                return drawdown_check
            
            # All checks passed
            return RiskCheck(
                decision=RiskDecision.APPROVE,
                level=RiskLevel.LOW,
                reason="All risk checks passed"
            )
            
        except Exception as e:
            self.logger.error(f"Error in risk check: {e}")
            return RiskCheck(
                decision=RiskDecision.REJECT,
                level=RiskLevel.CRITICAL,
                reason=f"Risk check error: {e}"
            )
    
    def _check_data_freshness(self, symbol: str) -> RiskCheck:
        """Check if market data is fresh."""
        if symbol not in self.last_prices:
            return RiskCheck(
                decision=RiskDecision.REJECT,
                level=RiskLevel.HIGH,
                reason=f"No market data for {symbol}"
            )
        
        last_update = self.last_prices[symbol].get('timestamp')
        if not last_update:
            return RiskCheck(
                decision=RiskDecision.REJECT,
                level=RiskLevel.HIGH,
                reason=f"No timestamp for {symbol}"
            )
        
        age = (datetime.utcnow() - last_update).total_seconds()
        if age > self.config.stale_data_threshold:
            return RiskCheck(
                decision=RiskDecision.REJECT,
                level=RiskLevel.HIGH,
                reason=f"Stale data for {symbol}: {age:.1f}s old"
            )
        
        return RiskCheck(
            decision=RiskDecision.APPROVE,
            level=RiskLevel.LOW,
            reason="Data is fresh"
        )
    
    def _check_position_limits(self, symbol: str, side: str, quantity: float, 
                              price: Optional[float]) -> RiskCheck:
        """Check position size limits."""
        current_position = self.positions.get(symbol, 0.0)
        
        # Calculate new position after order
        if side.upper() == "BUY":
            new_position = current_position + quantity
        else:
            new_position = current_position - quantity
        
        # Check absolute position limit
        if abs(new_position) > self.config.max_qty:
            return RiskCheck(
                decision=RiskDecision.REJECT,
                level=RiskLevel.HIGH,
                reason=f"Position limit exceeded: {new_position} > {self.config.max_qty}"
            )
        
        # Check position percentage limit
        if price and abs(new_position * price) > self.config.max_notional * self.config.position_limit_pct:
            return RiskCheck(
                decision=RiskDecision.REJECT,
                level=RiskLevel.HIGH,
                reason=f"Position notional limit exceeded"
            )
        
        return RiskCheck(
            decision=RiskDecision.APPROVE,
            level=RiskLevel.LOW,
            reason="Position limits OK"
        )
    
    def _check_notional_limits(self, symbol: str, quantity: float, price: Optional[float]) -> RiskCheck:
        """Check notional limits."""
        if not price:
            return RiskCheck(
                decision=RiskDecision.APPROVE,
                level=RiskLevel.LOW,
                reason="No price limit for market order"
            )
        
        notional = quantity * price
        if notional > self.config.max_notional:
            return RiskCheck(
                decision=RiskDecision.REJECT,
                level=RiskLevel.HIGH,
                reason=f"Notional limit exceeded: {notional} > {self.config.max_notional}"
            )
        
        return RiskCheck(
            decision=RiskDecision.APPROVE,
            level=RiskLevel.LOW,
            reason="Notional limits OK"
        )
    
    def _check_quantity_limits(self, symbol: str, quantity: float) -> RiskCheck:
        """Check quantity limits."""
        if quantity <= 0:
            return RiskCheck(
                decision=RiskDecision.REJECT,
                level=RiskLevel.HIGH,
                reason="Invalid quantity: must be positive"
            )
        
        if quantity > self.config.max_qty:
            return RiskCheck(
                decision=RiskDecision.REJECT,
                level=RiskLevel.HIGH,
                reason=f"Quantity limit exceeded: {quantity} > {self.config.max_qty}"
            )
        
        return RiskCheck(
            decision=RiskDecision.APPROVE,
            level=RiskLevel.LOW,
            reason="Quantity limits OK"
        )
    
    def _check_price_bands(self, symbol: str, price: Optional[float]) -> RiskCheck:
        """Check price bands around mid price."""
        if not price or symbol not in self.last_prices:
            return RiskCheck(
                decision=RiskDecision.APPROVE,
                level=RiskLevel.LOW,
                reason="No price band check needed"
            )
        
        market_data = self.last_prices[symbol]
        mid_price = (market_data.get('bid', 0) + market_data.get('ask', 0)) / 2
        
        if mid_price <= 0:
            return RiskCheck(
                decision=RiskDecision.REJECT,
                level=RiskLevel.HIGH,
                reason="Invalid mid price"
            )
        
        # Calculate price band
        band_pct = self.config.price_band_bps / 10000.0
        upper_band = mid_price * (1 + band_pct)
        lower_band = mid_price * (1 - band_pct)
        
        if price > upper_band or price < lower_band:
            return RiskCheck(
                decision=RiskDecision.REJECT,
                level=RiskLevel.MEDIUM,
                reason=f"Price outside band: {price} not in [{lower_band:.2f}, {upper_band:.2f}]"
            )
        
        return RiskCheck(
            decision=RiskDecision.APPROVE,
            level=RiskLevel.LOW,
            reason="Price within bands"
        )
    
    def _check_order_rate_limits(self, symbol: str) -> RiskCheck:
        """Check order rate limits."""
        now = datetime.utcnow()
        cutoff_time = now - timedelta(seconds=1)
        
        # Get recent orders for symbol
        if symbol not in self.order_counts:
            self.order_counts[symbol] = []
        
        # Remove old orders
        self.order_counts[symbol] = [
            order_time for order_time in self.order_counts[symbol]
            if order_time > cutoff_time
        ]
        
        # Check rate limit
        if len(self.order_counts[symbol]) >= self.config.orders_per_sec:
            return RiskCheck(
                decision=RiskDecision.REJECT,
                level=RiskLevel.MEDIUM,
                reason=f"Rate limit exceeded: {len(self.order_counts[symbol])} orders/sec"
            )
        
        # Add current order
        self.order_counts[symbol].append(now)
        
        return RiskCheck(
            decision=RiskDecision.APPROVE,
            level=RiskLevel.LOW,
            reason="Rate limits OK"
        )
    
    def _check_open_order_limits(self, symbol: str) -> RiskCheck:
        """Check open order limits."""
        open_count = self.open_orders.get(symbol, 0)
        
        if open_count >= self.config.max_open_orders:
            return RiskCheck(
                decision=RiskDecision.REJECT,
                level=RiskLevel.MEDIUM,
                reason=f"Open order limit exceeded: {open_count} >= {self.config.max_open_orders}"
            )
        
        return RiskCheck(
            decision=RiskDecision.APPROVE,
            level=RiskLevel.LOW,
            reason="Open order limits OK"
        )
    
    def _check_drawdown_limits(self) -> RiskCheck:
        """Check drawdown limits."""
        # TODO: Implement drawdown calculation
        # This would require access to portfolio PnL data
        return RiskCheck(
            decision=RiskDecision.APPROVE,
            level=RiskLevel.LOW,
            reason="Drawdown limits OK"
        )
    
    def update_market_data(self, symbol: str, market_data: Dict[str, Any]) -> None:
        """Update market data for risk checks."""
        self.last_prices[symbol] = {
            'bid': market_data.get('bid'),
            'ask': market_data.get('ask'),
            'last': market_data.get('last'),
            'timestamp': datetime.utcnow()
        }
    
    def update_position(self, symbol: str, quantity: float) -> None:
        """Update position for risk checks."""
        self.positions[symbol] = quantity
    
    def add_open_order(self, symbol: str) -> None:
        """Add open order to tracking."""
        self.open_orders[symbol] = self.open_orders.get(symbol, 0) + 1
    
    def remove_open_order(self, symbol: str) -> None:
        """Remove open order from tracking."""
        if symbol in self.open_orders and self.open_orders[symbol] > 0:
            self.open_orders[symbol] -= 1
    
    def set_kill_switch(self, active: bool) -> None:
        """Set kill switch state."""
        self.kill_switch = active
        self.logger.info(f"Kill switch {'activated' if active else 'deactivated'}")
    
    def get_risk_status(self) -> Dict[str, Any]:
        """Get current risk status."""
        return {
            'kill_switch': self.kill_switch,
            'open_orders': dict(self.open_orders),
            'positions': dict(self.positions),
            'order_counts': {
                symbol: len(orders) 
                for symbol, orders in self.order_counts.items()
            },
            'last_prices': {
                symbol: {
                    'bid': data.get('bid'),
                    'ask': data.get('ask'),
                    'last': data.get('last'),
                    'age_seconds': (datetime.utcnow() - data.get('timestamp', datetime.utcnow())).total_seconds()
                }
                for symbol, data in self.last_prices.items()
            }
        }
