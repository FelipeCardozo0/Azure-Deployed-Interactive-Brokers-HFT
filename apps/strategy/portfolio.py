"""Portfolio management and position tracking."""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from ..common.log import get_logger


class PositionSide(Enum):
    """Position sides."""
    LONG = "LONG"
    SHORT = "SHORT"
    FLAT = "FLAT"


@dataclass
class Position:
    """Position information."""
    symbol: str
    side: PositionSide
    quantity: float
    avg_price: float
    unrealized_pnl: float
    realized_pnl: float
    timestamp: datetime


@dataclass
class Portfolio:
    """Portfolio state."""
    total_value: float
    cash: float
    positions: Dict[str, Position]
    total_pnl: float
    daily_pnl: float
    timestamp: datetime


@dataclass
class PortfolioConfig:
    """Portfolio configuration."""
    max_position_size: float = 0.1  # 10% of portfolio
    max_total_exposure: float = 0.5  # 50% of portfolio
    stop_loss_pct: float = 0.02  # 2% stop loss
    take_profit_pct: float = 0.04  # 4% take profit
    max_positions: int = 10


class PortfolioManager:
    """Manage portfolio positions and risk."""
    
    def __init__(self, config: PortfolioConfig):
        self.config = config
        self.logger = get_logger(__name__)
        self.positions: Dict[str, Position] = {}
        self.cash: float = 100000.0  # Starting cash
        self.total_pnl: float = 0.0
        self.daily_pnl: float = 0.0
        self.last_reset_date = datetime.now().date()
    
    def update_position(self, symbol: str, side: PositionSide, quantity: float, 
                       price: float, timestamp: datetime) -> None:
        """Update position after trade."""
        if symbol not in self.positions:
            self.positions[symbol] = Position(
                symbol=symbol,
                side=PositionSide.FLAT,
                quantity=0.0,
                avg_price=0.0,
                unrealized_pnl=0.0,
                realized_pnl=0.0,
                timestamp=timestamp
            )
        
        position = self.positions[symbol]
        
        if side == PositionSide.LONG:
            if position.side == PositionSide.SHORT:
                # Closing short position
                if quantity >= position.quantity:
                    # Complete close
                    realized_pnl = position.quantity * (position.avg_price - price)
                    self.total_pnl += realized_pnl
                    self.daily_pnl += realized_pnl
                    
                    remaining_qty = quantity - position.quantity
                    if remaining_qty > 0:
                        # Open new long position
                        position.side = PositionSide.LONG
                        position.quantity = remaining_qty
                        position.avg_price = price
                    else:
                        # Position closed
                        position.side = PositionSide.FLAT
                        position.quantity = 0.0
                        position.avg_price = 0.0
                else:
                    # Partial close
                    realized_pnl = quantity * (position.avg_price - price)
                    self.total_pnl += realized_pnl
                    self.daily_pnl += realized_pnl
                    
                    position.quantity -= quantity
            else:
                # Adding to long position or opening new
                if position.side == PositionSide.LONG:
                    # Adding to existing long
                    total_value = position.quantity * position.avg_price + quantity * price
                    position.quantity += quantity
                    position.avg_price = total_value / position.quantity
                else:
                    # Opening new long
                    position.side = PositionSide.LONG
                    position.quantity = quantity
                    position.avg_price = price
        
        elif side == PositionSide.SHORT:
            if position.side == PositionSide.LONG:
                # Closing long position
                if quantity >= position.quantity:
                    # Complete close
                    realized_pnl = position.quantity * (price - position.avg_price)
                    self.total_pnl += realized_pnl
                    self.daily_pnl += realized_pnl
                    
                    remaining_qty = quantity - position.quantity
                    if remaining_qty > 0:
                        # Open new short position
                        position.side = PositionSide.SHORT
                        position.quantity = remaining_qty
                        position.avg_price = price
                    else:
                        # Position closed
                        position.side = PositionSide.FLAT
                        position.quantity = 0.0
                        position.avg_price = 0.0
                else:
                    # Partial close
                    realized_pnl = quantity * (price - position.avg_price)
                    self.total_pnl += realized_pnl
                    self.daily_pnl += realized_pnl
                    
                    position.quantity -= quantity
            else:
                # Adding to short position or opening new
                if position.side == PositionSide.SHORT:
                    # Adding to existing short
                    total_value = position.quantity * position.avg_price + quantity * price
                    position.quantity += quantity
                    position.avg_price = total_value / position.quantity
                else:
                    # Opening new short
                    position.side = PositionSide.SHORT
                    position.quantity = quantity
                    position.avg_price = price
        
        position.timestamp = timestamp
        self.logger.info(f"Updated position {symbol}: {position.side.value} {position.quantity} @ {position.avg_price}")
    
    def update_market_prices(self, prices: Dict[str, float]) -> None:
        """Update unrealized PnL based on current market prices."""
        for symbol, position in self.positions.items():
            if position.quantity > 0 and symbol in prices:
                current_price = prices[symbol]
                
                if position.side == PositionSide.LONG:
                    position.unrealized_pnl = position.quantity * (current_price - position.avg_price)
                elif position.side == PositionSide.SHORT:
                    position.unrealized_pnl = position.quantity * (position.avg_price - current_price)
                else:
                    position.unrealized_pnl = 0.0
    
    def get_portfolio(self) -> Portfolio:
        """Get current portfolio state."""
        # Calculate total value
        total_value = self.cash
        for position in self.positions.values():
            if position.quantity > 0:
                total_value += position.quantity * position.avg_price
        
        return Portfolio(
            total_value=total_value,
            cash=self.cash,
            positions=self.positions.copy(),
            total_pnl=self.total_pnl,
            daily_pnl=self.daily_pnl,
            timestamp=datetime.utcnow()
        )
    
    def can_open_position(self, symbol: str, side: PositionSide, quantity: float, 
                         price: float) -> Tuple[bool, str]:
        """Check if position can be opened."""
        # Check max positions
        active_positions = sum(1 for p in self.positions.values() if p.quantity > 0)
        if active_positions >= self.config.max_positions:
            return False, f"Maximum positions ({self.config.max_positions}) reached"
        
        # Check position size
        portfolio = self.get_portfolio()
        position_value = quantity * price
        position_pct = position_value / portfolio.total_value if portfolio.total_value > 0 else 0
        
        if position_pct > self.config.max_position_size:
            return False, f"Position size ({position_pct:.1%}) exceeds limit ({self.config.max_position_size:.1%})"
        
        # Check total exposure
        total_exposure = sum(
            p.quantity * p.avg_price for p in self.positions.values() if p.quantity > 0
        )
        new_exposure = total_exposure + position_value
        exposure_pct = new_exposure / portfolio.total_value if portfolio.total_value > 0 else 0
        
        if exposure_pct > self.config.max_total_exposure:
            return False, f"Total exposure ({exposure_pct:.1%}) exceeds limit ({self.config.max_total_exposure:.1%})"
        
        # Check cash availability for long positions
        if side == PositionSide.LONG and position_value > self.cash:
            return False, f"Insufficient cash: need {position_value:.2f}, have {self.cash:.2f}"
        
        return True, "OK"
    
    def should_close_position(self, symbol: str, current_price: float) -> Tuple[bool, str]:
        """Check if position should be closed due to stop loss or take profit."""
        if symbol not in self.positions:
            return False, "No position"
        
        position = self.positions[symbol]
        if position.quantity == 0:
            return False, "No position"
        
        # Calculate PnL percentage
        if position.side == PositionSide.LONG:
            pnl_pct = (current_price - position.avg_price) / position.avg_price
        elif position.side == PositionSide.SHORT:
            pnl_pct = (position.avg_price - current_price) / position.avg_price
        else:
            return False, "No position"
        
        # Check stop loss
        if pnl_pct <= -self.config.stop_loss_pct:
            return True, f"Stop loss triggered: {pnl_pct:.2%}"
        
        # Check take profit
        if pnl_pct >= self.config.take_profit_pct:
            return True, f"Take profit triggered: {pnl_pct:.2%}"
        
        return False, "Hold"
    
    def get_position_risk(self, symbol: str) -> Dict[str, float]:
        """Get risk metrics for position."""
        if symbol not in self.positions or self.positions[symbol].quantity == 0:
            return {}
        
        position = self.positions[symbol]
        portfolio = self.get_portfolio()
        
        position_value = position.quantity * position.avg_price
        position_pct = position_value / portfolio.total_value if portfolio.total_value > 0 else 0
        
        return {
            'quantity': position.quantity,
            'avg_price': position.avg_price,
            'side': position.side.value,
            'value': position_value,
            'percentage': position_pct,
            'unrealized_pnl': position.unrealized_pnl,
            'realized_pnl': position.realized_pnl,
            'total_pnl': position.unrealized_pnl + position.realized_pnl
        }
    
    def reset_daily_pnl(self) -> None:
        """Reset daily PnL (call at start of trading day)."""
        self.daily_pnl = 0.0
        self.last_reset_date = datetime.now().date()
        self.logger.info("Daily PnL reset")
    
    def get_portfolio_metrics(self) -> Dict[str, float]:
        """Get portfolio performance metrics."""
        portfolio = self.get_portfolio()
        
        # Calculate returns
        total_return = self.total_pnl / (portfolio.total_value - self.total_pnl) if portfolio.total_value > self.total_pnl else 0
        daily_return = self.daily_pnl / (portfolio.total_value - self.daily_pnl) if portfolio.total_value > self.daily_pnl else 0
        
        # Count active positions
        active_positions = sum(1 for p in self.positions.values() if p.quantity > 0)
        
        # Calculate exposure
        total_exposure = sum(p.quantity * p.avg_price for p in self.positions.values() if p.quantity > 0)
        exposure_pct = total_exposure / portfolio.total_value if portfolio.total_value > 0 else 0
        
        return {
            'total_value': portfolio.total_value,
            'cash': self.cash,
            'total_pnl': self.total_pnl,
            'daily_pnl': self.daily_pnl,
            'total_return': total_return,
            'daily_return': daily_return,
            'active_positions': active_positions,
            'exposure_pct': exposure_pct,
            'max_exposure': self.config.max_total_exposure,
            'max_position_size': self.config.max_position_size
        }
