"""Order management utilities."""

import asyncio
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
import ib_insync
from ib_insync import Contract, Order, MarketOrder, LimitOrder, StopOrder
from ..common.log import get_logger
from ..common.ids import generate_order_id, generate_correlation_id
from ..common.config import settings


class OrderSide(Enum):
    """Order sides."""
    BUY = "BUY"
    SELL = "SELL"


class OrderType(Enum):
    """Order types."""
    MARKET = "MKT"
    LIMIT = "LMT"
    STOP = "STP"
    STOP_LIMIT = "STP LMT"


class OrderStatus(Enum):
    """Order statuses."""
    PENDING = "Pending"
    SUBMITTED = "Submitted"
    FILLED = "Filled"
    CANCELLED = "Cancelled"
    REJECTED = "Rejected"


@dataclass
class OrderRequest:
    """Order request."""
    symbol: str
    side: OrderSide
    quantity: float
    order_type: OrderType
    price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: str = "DAY"
    correlation_id: Optional[str] = None


@dataclass
class OrderResponse:
    """Order response."""
    order_id: str
    status: OrderStatus
    message: str
    timestamp: datetime
    correlation_id: Optional[str] = None


class OrderManager:
    """Manages order placement and tracking."""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.pending_orders: Dict[str, OrderRequest] = {}
        self.order_status: Dict[str, OrderStatus] = {}
    
    async def place_order(self, ib_client, symbol: str, side: str, quantity: float, 
                         price: Optional[float] = None, order_type: str = "MKT") -> str:
        """Place order with IB."""
        try:
            # Generate order ID and correlation ID
            order_id = generate_order_id()
            correlation_id = generate_correlation_id()
            
            # Create contract
            contract = self._create_contract(symbol)
            if not contract:
                raise ValueError(f"Invalid symbol: {symbol}")
            
            # Create order
            order = self._create_order(side, quantity, price, order_type)
            if not order:
                raise ValueError(f"Invalid order parameters")
            
            # Set order ID
            order.orderId = int(order_id.split('-')[0], 16) % 1000000
            
            # Place order
            trade = ib_client.ib.placeOrder(contract, order)
            
            # Store order info
            order_request = OrderRequest(
                symbol=symbol,
                side=OrderSide.BUY if side.upper() == "BUY" else OrderSide.SELL,
                quantity=quantity,
                order_type=OrderType.MARKET if order_type == "MKT" else OrderType.LIMIT,
                price=price,
                correlation_id=correlation_id
            )
            
            self.pending_orders[order_id] = order_request
            self.order_status[order_id] = OrderStatus.SUBMITTED
            
            self.logger.info(f"Order placed: {order_id} - {side} {quantity} {symbol}")
            return order_id
            
        except Exception as e:
            self.logger.error(f"Failed to place order: {e}")
            raise
    
    def _create_contract(self, symbol: str) -> Optional[Contract]:
        """Create IB contract for symbol."""
        try:
            # For stocks, create Stock contract
            if symbol.isalpha() and len(symbol) <= 5:
                return ib_insync.Stock(symbol, 'SMART', 'USD')
            
            # For futures, create Future contract
            # TODO: Add futures support
            
            # For options, create Option contract
            # TODO: Add options support
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error creating contract for {symbol}: {e}")
            return None
    
    def _create_order(self, side: str, quantity: float, price: Optional[float], 
                     order_type: str) -> Optional[Order]:
        """Create IB order."""
        try:
            # Determine order side
            action = "BUY" if side.upper() == "BUY" else "SELL"
            total_quantity = int(quantity)
            
            if order_type.upper() == "MKT":
                # Market order
                return MarketOrder(action, total_quantity)
            
            elif order_type.upper() == "LMT":
                # Limit order
                if price is None:
                    raise ValueError("Price required for limit order")
                return LimitOrder(action, total_quantity, price)
            
            elif order_type.upper() == "STP":
                # Stop order
                if price is None:
                    raise ValueError("Stop price required for stop order")
                return StopOrder(action, total_quantity, price)
            
            else:
                raise ValueError(f"Unsupported order type: {order_type}")
                
        except Exception as e:
            self.logger.error(f"Error creating order: {e}")
            return None
    
    async def cancel_order(self, ib_client, order_id: str) -> bool:
        """Cancel order."""
        try:
            if order_id not in self.pending_orders:
                self.logger.warning(f"Order {order_id} not found")
                return False
            
            # Cancel with IB
            ib_client.ib.cancelOrder(int(order_id.split('-')[0], 16) % 1000000)
            
            # Update status
            self.order_status[order_id] = OrderStatus.CANCELLED
            
            self.logger.info(f"Order cancelled: {order_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to cancel order {order_id}: {e}")
            return False
    
    def update_order_status(self, order_id: str, status: OrderStatus, message: str = "") -> None:
        """Update order status."""
        if order_id in self.order_status:
            self.order_status[order_id] = status
            self.logger.info(f"Order {order_id} status: {status.value} - {message}")
    
    def get_order_status(self, order_id: str) -> Optional[OrderStatus]:
        """Get order status."""
        return self.order_status.get(order_id)
    
    def get_pending_orders(self) -> Dict[str, OrderRequest]:
        """Get all pending orders."""
        return {
            order_id: request 
            for order_id, request in self.pending_orders.items()
            if self.order_status.get(order_id) in [OrderStatus.PENDING, OrderStatus.SUBMITTED]
        }
    
    def get_order_info(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Get order information."""
        if order_id not in self.pending_orders:
            return None
        
        request = self.pending_orders[order_id]
        status = self.order_status.get(order_id, OrderStatus.PENDING)
        
        return {
            'order_id': order_id,
            'symbol': request.symbol,
            'side': request.side.value,
            'quantity': request.quantity,
            'order_type': request.order_type.value,
            'price': request.price,
            'status': status.value,
            'correlation_id': request.correlation_id,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def get_orders_by_symbol(self, symbol: str) -> List[Dict[str, Any]]:
        """Get orders for specific symbol."""
        orders = []
        for order_id, request in self.pending_orders.items():
            if request.symbol == symbol:
                order_info = self.get_order_info(order_id)
                if order_info:
                    orders.append(order_info)
        return orders
    
    def get_orders_by_status(self, status: OrderStatus) -> List[Dict[str, Any]]:
        """Get orders by status."""
        orders = []
        for order_id, order_status in self.order_status.items():
            if order_status == status:
                order_info = self.get_order_info(order_id)
                if order_info:
                    orders.append(order_info)
        return orders
    
    def clear_completed_orders(self) -> None:
        """Clear completed orders from tracking."""
        completed_statuses = {OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED}
        
        for order_id in list(self.pending_orders.keys()):
            if self.order_status.get(order_id) in completed_statuses:
                del self.pending_orders[order_id]
                del self.order_status[order_id]
    
    def get_order_statistics(self) -> Dict[str, Any]:
        """Get order statistics."""
        total_orders = len(self.pending_orders)
        status_counts = {}
        
        for status in self.order_status.values():
            status_counts[status.value] = status_counts.get(status.value, 0) + 1
        
        return {
            'total_orders': total_orders,
            'status_counts': status_counts,
            'pending_orders': len(self.get_pending_orders())
        }
