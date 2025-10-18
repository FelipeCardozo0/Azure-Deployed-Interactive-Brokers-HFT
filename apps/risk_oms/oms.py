"""Order Management System."""

import asyncio
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import uuid
from ..common.log import get_logger
from ..common.ids import generate_order_id, generate_fill_id
from ..storage import TimescaleClient, RedisClient, KafkaClient
from ..ib_wrapper import IBClient


class OrderStatus(Enum):
    """Order statuses."""
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class FillStatus(Enum):
    """Fill statuses."""
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"


@dataclass
class Order:
    """Order record."""
    id: str
    symbol: str
    side: str
    quantity: float
    price: Optional[float]
    order_type: str
    time_in_force: str
    status: OrderStatus
    reason: Optional[str]
    idempotency_key: str
    correlation_id: str
    timestamp: datetime
    ib_order_id: Optional[int] = None


@dataclass
class Fill:
    """Fill record."""
    id: str
    order_id: str
    quantity: float
    price: float
    venue: str
    fee: float
    status: FillStatus
    timestamp: datetime
    ib_fill_id: Optional[str] = None


class OrderManagementSystem:
    """Order Management System with idempotency and reconciliation."""
    
    def __init__(self, timescale: TimescaleClient, redis: RedisClient, 
                 kafka: KafkaClient, ib_client: IBClient):
        self.timescale = timescale
        self.redis = redis
        self.kafka = kafka
        self.ib_client = ib_client
        self.logger = get_logger(__name__)
        
        # Order tracking
        self.orders: Dict[str, Order] = {}
        self.fills: Dict[str, Fill] = {}
        self.idempotency_keys: Dict[str, str] = {}  # key -> order_id
        self.running = False
    
    async def start(self) -> None:
        """Start the OMS."""
        self.running = True
        self.logger.info("Order Management System started")
        
        # Start background tasks
        asyncio.create_task(self._reconciliation_loop())
        asyncio.create_task(self._cleanup_loop())
    
    async def stop(self) -> None:
        """Stop the OMS."""
        self.running = False
        self.logger.info("Order Management System stopped")
    
    async def submit_order(self, symbol: str, side: str, quantity: float,
                          price: Optional[float] = None, order_type: str = "MKT",
                          time_in_force: str = "DAY", idempotency_key: Optional[str] = None,
                          correlation_id: Optional[str] = None) -> Tuple[str, bool]:
        """Submit order with idempotency check."""
        try:
            # Generate idempotency key if not provided
            if not idempotency_key:
                idempotency_key = str(uuid.uuid4())
            
            # Check for duplicate order
            if idempotency_key in self.idempotency_keys:
                existing_order_id = self.idempotency_keys[idempotency_key]
                self.logger.info(f"Duplicate order detected: {idempotency_key} -> {existing_order_id}")
                return existing_order_id, False
            
            # Generate order ID
            order_id = generate_order_id()
            
            # Create order record
            order = Order(
                id=order_id,
                symbol=symbol,
                side=side,
                quantity=quantity,
                price=price,
                order_type=order_type,
                time_in_force=time_in_force,
                status=OrderStatus.PENDING,
                reason=None,
                idempotency_key=idempotency_key,
                correlation_id=correlation_id or "",
                timestamp=datetime.utcnow()
            )
            
            # Store order
            self.orders[order_id] = order
            self.idempotency_keys[idempotency_key] = order_id
            
            # Persist to database
            await self._persist_order(order)
            
            # Submit to IB
            success = await self._submit_to_ib(order)
            if success:
                order.status = OrderStatus.SUBMITTED
                await self._persist_order(order)
                
                # Send to Kafka
                await self.kafka.send_order({
                    'order_id': order_id,
                    'symbol': symbol,
                    'side': side,
                    'quantity': quantity,
                    'price': price,
                    'order_type': order_type,
                    'status': order.status.value,
                    'timestamp': order.timestamp.isoformat()
                })
                
                self.logger.info(f"Order submitted: {order_id}")
                return order_id, True
            else:
                order.status = OrderStatus.REJECTED
                order.reason = "Failed to submit to IB"
                await self._persist_order(order)
                return order_id, False
                
        except Exception as e:
            self.logger.error(f"Error submitting order: {e}")
            return "", False
    
    async def _submit_to_ib(self, order: Order) -> bool:
        """Submit order to Interactive Brokers."""
        try:
            # Create IB contract
            contract = self._create_ib_contract(order.symbol)
            if not contract:
                return False
            
            # Create IB order
            ib_order = self._create_ib_order(order)
            if not ib_order:
                return False
            
            # Place order
            trade = self.ib_client.ib.placeOrder(contract, ib_order)
            order.ib_order_id = trade.order.orderId
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error submitting to IB: {e}")
            return False
    
    def _create_ib_contract(self, symbol: str):
        """Create IB contract."""
        try:
            import ib_insync
            return ib_insync.Stock(symbol, 'SMART', 'USD')
        except Exception as e:
            self.logger.error(f"Error creating IB contract: {e}")
            return None
    
    def _create_ib_order(self, order: Order):
        """Create IB order."""
        try:
            import ib_insync
            
            action = "BUY" if order.side.upper() == "BUY" else "SELL"
            total_quantity = int(order.quantity)
            
            if order.order_type.upper() == "MKT":
                return ib_insync.MarketOrder(action, total_quantity)
            elif order.order_type.upper() == "LMT" and order.price:
                return ib_insync.LimitOrder(action, total_quantity, order.price)
            else:
                return ib_insync.MarketOrder(action, total_quantity)
                
        except Exception as e:
            self.logger.error(f"Error creating IB order: {e}")
            return None
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel order."""
        try:
            if order_id not in self.orders:
                self.logger.warning(f"Order {order_id} not found")
                return False
            
            order = self.orders[order_id]
            
            # Cancel with IB if submitted
            if order.ib_order_id:
                self.ib_client.ib.cancelOrder(order.ib_order_id)
            
            # Update status
            order.status = OrderStatus.CANCELLED
            await self._persist_order(order)
            
            self.logger.info(f"Order cancelled: {order_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error cancelling order {order_id}: {e}")
            return False
    
    async def process_fill(self, order_id: str, quantity: float, price: float,
                          venue: str = "IBKR", fee: float = 0.0) -> str:
        """Process fill for order."""
        try:
            if order_id not in self.orders:
                self.logger.warning(f"Order {order_id} not found for fill")
                return ""
            
            order = self.orders[order_id]
            
            # Create fill record
            fill_id = generate_fill_id()
            fill = Fill(
                id=fill_id,
                order_id=order_id,
                quantity=quantity,
                price=price,
                venue=venue,
                fee=fee,
                status=FillStatus.CONFIRMED,
                timestamp=datetime.utcnow()
            )
            
            # Store fill
            self.fills[fill_id] = fill
            
            # Persist to database
            await self._persist_fill(fill)
            
            # Update order status
            if order.status == OrderStatus.SUBMITTED:
                order.status = OrderStatus.PARTIALLY_FILLED
            elif order.status == OrderStatus.PARTIALLY_FILLED:
                # Check if fully filled
                filled_qty = sum(f.quantity for f in self.fills.values() if f.order_id == order_id)
                if filled_qty >= order.quantity:
                    order.status = OrderStatus.FILLED
            
            await self._persist_order(order)
            
            # Send to Kafka
            await self.kafka.send_fill({
                'fill_id': fill_id,
                'order_id': order_id,
                'quantity': quantity,
                'price': price,
                'venue': venue,
                'fee': fee,
                'timestamp': fill.timestamp.isoformat()
            })
            
            self.logger.info(f"Fill processed: {fill_id} for order {order_id}")
            return fill_id
            
        except Exception as e:
            self.logger.error(f"Error processing fill: {e}")
            return ""
    
    async def _persist_order(self, order: Order) -> None:
        """Persist order to database."""
        try:
            from ..storage.models import Order as OrderModel
            
            order_model = OrderModel(
                id=order.id,
                timestamp=order.timestamp,
                symbol=order.symbol,
                side=order.side,
                quantity=order.quantity,
                price=order.price,
                order_type=order.order_type,
                time_in_force=order.time_in_force,
                status=order.status.value,
                reason=order.reason,
                idempotency_key=order.idempotency_key,
                correlation_id=order.correlation_id
            )
            
            await self.timescale.insert_order(order_model)
            
        except Exception as e:
            self.logger.error(f"Error persisting order: {e}")
    
    async def _persist_fill(self, fill: Fill) -> None:
        """Persist fill to database."""
        try:
            from ..storage.models import Fill as FillModel
            
            fill_model = FillModel(
                order_id=fill.order_id,
                timestamp=fill.timestamp,
                quantity=fill.quantity,
                price=fill.price,
                venue=fill.venue,
                fee=fill.fee,
                fill_id=fill.id
            )
            
            await self.timescale.insert_fill(fill_model)
            
        except Exception as e:
            self.logger.error(f"Error persisting fill: {e}")
    
    async def _reconciliation_loop(self) -> None:
        """Reconciliation loop to check order status with IB."""
        while self.running:
            try:
                # Get all submitted orders
                submitted_orders = [
                    order for order in self.orders.values()
                    if order.status in [OrderStatus.SUBMITTED, OrderStatus.PARTIALLY_FILLED]
                ]
                
                for order in submitted_orders:
                    await self._reconcile_order(order)
                
                await asyncio.sleep(5)  # Check every 5 seconds
                
            except Exception as e:
                self.logger.error(f"Error in reconciliation loop: {e}")
                await asyncio.sleep(5)
    
    async def _reconcile_order(self, order: Order) -> None:
        """Reconcile order with IB."""
        try:
            if not order.ib_order_id:
                return
            
            # Get order status from IB
            # This would require implementing IB order status checking
            # For now, we'll just log that reconciliation is needed
            self.logger.debug(f"Reconciling order {order.id} with IB order {order.ib_order_id}")
            
        except Exception as e:
            self.logger.error(f"Error reconciling order {order.id}: {e}")
    
    async def _cleanup_loop(self) -> None:
        """Cleanup old orders and fills."""
        while self.running:
            try:
                # Clean up old completed orders (older than 1 day)
                cutoff_time = datetime.utcnow() - timedelta(days=1)
                
                old_orders = [
                    order_id for order_id, order in self.orders.items()
                    if order.status in [OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED]
                    and order.timestamp < cutoff_time
                ]
                
                for order_id in old_orders:
                    del self.orders[order_id]
                
                # Clean up old fills
                old_fills = [
                    fill_id for fill_id, fill in self.fills.items()
                    if fill.timestamp < cutoff_time
                ]
                
                for fill_id in old_fills:
                    del self.fills[fill_id]
                
                await asyncio.sleep(3600)  # Cleanup every hour
                
            except Exception as e:
                self.logger.error(f"Error in cleanup loop: {e}")
                await asyncio.sleep(3600)
    
    def get_order(self, order_id: str) -> Optional[Order]:
        """Get order by ID."""
        return self.orders.get(order_id)
    
    def get_orders_by_symbol(self, symbol: str) -> List[Order]:
        """Get orders for symbol."""
        return [order for order in self.orders.values() if order.symbol == symbol]
    
    def get_orders_by_status(self, status: OrderStatus) -> List[Order]:
        """Get orders by status."""
        return [order for order in self.orders.values() if order.status == status]
    
    def get_fills_for_order(self, order_id: str) -> List[Fill]:
        """Get fills for order."""
        return [fill for fill in self.fills.values() if fill.order_id == order_id]
    
    def get_oms_status(self) -> Dict[str, Any]:
        """Get OMS status."""
        status_counts = {}
        for order in self.orders.values():
            status = order.status.value
            status_counts[status] = status_counts.get(status, 0) + 1
        
        return {
            'total_orders': len(self.orders),
            'total_fills': len(self.fills),
            'status_counts': status_counts,
            'idempotency_keys': len(self.idempotency_keys)
        }
