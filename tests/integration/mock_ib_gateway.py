"""Mock IB Gateway for integration testing."""

import asyncio
import json
import time
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass
import random


@dataclass
class MockTick:
    """Mock tick data."""
    symbol: str
    bid: float
    ask: float
    last: float
    bid_size: int
    ask_size: int
    last_size: int
    timestamp: datetime


@dataclass
class MockBar:
    """Mock bar data."""
    symbol: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    timestamp: datetime


@dataclass
class MockOrder:
    """Mock order."""
    order_id: int
    symbol: str
    side: str
    quantity: int
    price: float
    order_type: str
    status: str
    timestamp: datetime


class MockIBGateway:
    """Mock IB Gateway for testing."""
    
    def __init__(self, host: str = "localhost", port: int = 7497):
        self.host = host
        self.port = port
        self.connected = False
        self.orders: Dict[int, MockOrder] = {}
        self.positions: Dict[str, float] = {}
        self.account_value = 100000.0
        self.next_order_id = 1
        
        # Market data
        self.symbols = ["SPY", "QQQ", "IWM", "GLD", "TLT"]
        self.base_prices = {
            "SPY": 450.0,
            "QQQ": 380.0,
            "IWM": 200.0,
            "GLD": 180.0,
            "TLT": 100.0
        }
        
        # Subscriptions
        self.tick_subscriptions: List[str] = []
        self.bar_subscriptions: List[str] = []
        
        # Callbacks
        self.tick_callbacks: List[callable] = []
        self.bar_callbacks: List[callable] = []
        self.order_callbacks: List[callable] = []
    
    async def start(self):
        """Start the mock gateway."""
        self.connected = True
        print(f"Mock IB Gateway started on {self.host}:{self.port}")
        
        # Start market data simulation
        asyncio.create_task(self._simulate_market_data())
        
        # Start order processing
        asyncio.create_task(self._process_orders())
    
    async def stop(self):
        """Stop the mock gateway."""
        self.connected = False
        print("Mock IB Gateway stopped")
    
    async def connect(self, host: str, port: int, client_id: int) -> bool:
        """Connect to the gateway."""
        if host == self.host and port == self.port:
            self.connected = True
            return True
        return False
    
    def disconnect(self):
        """Disconnect from the gateway."""
        self.connected = False
    
    def is_connected(self) -> bool:
        """Check if connected."""
        return self.connected
    
    async def subscribe_ticks(self, symbol: str, callback: callable):
        """Subscribe to tick data."""
        if symbol not in self.tick_subscriptions:
            self.tick_subscriptions.append(symbol)
        self.tick_callbacks.append(callback)
        print(f"Subscribed to ticks for {symbol}")
    
    async def subscribe_bars(self, symbol: str, callback: callable):
        """Subscribe to bar data."""
        if symbol not in self.bar_subscriptions:
            self.bar_subscriptions.append(symbol)
        self.bar_callbacks.append(callback)
        print(f"Subscribed to bars for {symbol}")
    
    async def place_order(self, symbol: str, side: str, quantity: int, 
                         price: Optional[float] = None, order_type: str = "MKT") -> int:
        """Place an order."""
        if not self.connected:
            raise Exception("Not connected to gateway")
        
        order_id = self.next_order_id
        self.next_order_id += 1
        
        order = MockOrder(
            order_id=order_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price or self.base_prices.get(symbol, 100.0),
            order_type=order_type,
            status="PENDING",
            timestamp=datetime.utcnow()
        )
        
        self.orders[order_id] = order
        
        # Notify callbacks
        for callback in self.order_callbacks:
            try:
                callback(order)
            except Exception as e:
                print(f"Error in order callback: {e}")
        
        print(f"Order placed: {order_id} - {side} {quantity} {symbol} @ {order.price}")
        return order_id
    
    async def cancel_order(self, order_id: int) -> bool:
        """Cancel an order."""
        if order_id in self.orders:
            self.orders[order_id].status = "CANCELLED"
            print(f"Order cancelled: {order_id}")
            return True
        return False
    
    def get_orders(self) -> List[MockOrder]:
        """Get all orders."""
        return list(self.orders.values())
    
    def get_order(self, order_id: int) -> Optional[MockOrder]:
        """Get specific order."""
        return self.orders.get(order_id)
    
    def get_positions(self) -> Dict[str, float]:
        """Get current positions."""
        return self.positions.copy()
    
    def get_account_summary(self) -> Dict[str, str]:
        """Get account summary."""
        return {
            "TotalCashValue": str(self.account_value),
            "NetLiquidation": str(self.account_value + sum(
                qty * self.base_prices.get(symbol, 0) 
                for symbol, qty in self.positions.items()
            )),
            "BuyingPower": str(self.account_value * 4),
            "EquityWithLoanValue": str(self.account_value)
        }
    
    async def _simulate_market_data(self):
        """Simulate market data updates."""
        while self.connected:
            try:
                # Generate ticks for subscribed symbols
                for symbol in self.tick_subscriptions:
                    await self._generate_tick(symbol)
                
                # Generate bars for subscribed symbols
                for symbol in self.bar_subscriptions:
                    await self._generate_bar(symbol)
                
                await asyncio.sleep(0.1)  # 100ms updates
                
            except Exception as e:
                print(f"Error in market data simulation: {e}")
                await asyncio.sleep(1)
    
    async def _generate_tick(self, symbol: str):
        """Generate tick data for symbol."""
        base_price = self.base_prices.get(symbol, 100.0)
        
        # Add some random movement
        price_change = random.uniform(-0.01, 0.01)
        current_price = base_price * (1 + price_change)
        
        # Generate bid/ask spread
        spread = current_price * 0.001  # 0.1% spread
        bid = current_price - spread / 2
        ask = current_price + spread / 2
        
        tick = MockTick(
            symbol=symbol,
            bid=round(bid, 2),
            ask=round(ask, 2),
            last=round(current_price, 2),
            bid_size=random.randint(100, 1000),
            ask_size=random.randint(100, 1000),
            last_size=random.randint(100, 500),
            timestamp=datetime.utcnow()
        )
        
        # Notify callbacks
        for callback in self.tick_callbacks:
            try:
                callback(tick)
            except Exception as e:
                print(f"Error in tick callback: {e}")
    
    async def _generate_bar(self, symbol: str):
        """Generate bar data for symbol."""
        base_price = self.base_prices.get(symbol, 100.0)
        
        # Generate OHLC data
        open_price = base_price * random.uniform(0.99, 1.01)
        close_price = open_price * random.uniform(0.995, 1.005)
        high_price = max(open_price, close_price) * random.uniform(1.0, 1.002)
        low_price = min(open_price, close_price) * random.uniform(0.998, 1.0)
        volume = random.randint(1000, 10000)
        
        bar = MockBar(
            symbol=symbol,
            open=round(open_price, 2),
            high=round(high_price, 2),
            low=round(low_price, 2),
            close=round(close_price, 2),
            volume=volume,
            timestamp=datetime.utcnow()
        )
        
        # Notify callbacks
        for callback in self.bar_callbacks:
            try:
                callback(bar)
            except Exception as e:
                print(f"Error in bar callback: {e}")
    
    async def _process_orders(self):
        """Process pending orders."""
        while self.connected:
            try:
                # Process pending orders
                for order_id, order in self.orders.items():
                    if order.status == "PENDING":
                        # Simulate order processing
                        if random.random() < 0.8:  # 80% fill rate
                            order.status = "FILLED"
                            
                            # Update position
                            if order.side.upper() == "BUY":
                                self.positions[order.symbol] = self.positions.get(order.symbol, 0) + order.quantity
                            else:
                                self.positions[order.symbol] = self.positions.get(order.symbol, 0) - order.quantity
                            
                            print(f"Order filled: {order_id}")
                        else:
                            order.status = "REJECTED"
                            print(f"Order rejected: {order_id}")
                
                await asyncio.sleep(1)  # Check every second
                
            except Exception as e:
                print(f"Error in order processing: {e}")
                await asyncio.sleep(1)


async def create_mock_gateway(host: str = "localhost", port: int = 7497) -> MockIBGateway:
    """Create and start a mock IB Gateway."""
    gateway = MockIBGateway(host, port)
    await gateway.start()
    return gateway


async def main():
    """Main function for testing."""
    gateway = await create_mock_gateway()
    
    try:
        # Keep running
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down...")
        await gateway.stop()


if __name__ == "__main__":
    asyncio.run(main())
