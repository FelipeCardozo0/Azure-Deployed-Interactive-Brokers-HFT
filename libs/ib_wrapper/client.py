"""Robust IB client with auto-reconnection and error handling."""

import asyncio
import time
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
import ib_insync
from ib_insync import IB, Contract, Order, Trade, Ticker, BarData
from .errors import IBError, handle_ib_error, is_retryable_error
from .reconnect import ReconnectManager, CircuitBreaker
from ..common.log import get_logger, set_correlation_id, get_correlation_id
from ..common.config import settings


class IBClient:
    """Robust Interactive Brokers client with auto-reconnection."""
    
    def __init__(self):
        self.ib = IB()
        self.logger = get_logger(__name__)
        self.reconnect_manager = ReconnectManager()
        self.circuit_breaker = CircuitBreaker()
        self.connected = False
        self.last_heartbeat = 0.0
        self.heartbeat_interval = 30.0
        self._subscriptions: Dict[str, Contract] = {}
        self._order_callbacks: Dict[int, Callable] = {}
        self._data_callbacks: Dict[str, Callable] = {}
        
    async def connect(self) -> None:
        """Connect to IB Gateway with retry logic."""
        while not self.connected:
            try:
                if not self.circuit_breaker.allow_request():
                    self.logger.warning("Circuit breaker is open, waiting...")
                    await asyncio.sleep(5.0)
                    continue
                
                self.logger.info(f"Connecting to IB Gateway at {settings.ib_host}:{settings.ib_port}")
                await self.ib.connectAsync(
                    host=settings.ib_host,
                    port=settings.ib_port,
                    clientId=settings.ib_client_id,
                    timeout=settings.connect_timeout
                )
                
                self.connected = True
                self.circuit_breaker.record_success()
                self.reconnect_manager.reset()
                self.last_heartbeat = time.time()
                
                self.logger.info("Connected to IB Gateway successfully")
                
                # Set up event handlers
                self._setup_handlers()
                
                # Start heartbeat task
                asyncio.create_task(self._heartbeat_task())
                
            except Exception as e:
                error = handle_ib_error(0, str(e))
                self.logger.error(f"Connection failed: {error.message}")
                
                self.circuit_breaker.record_failure()
                
                if not await self.reconnect_manager.wait_and_retry(error):
                    self.logger.error("Max reconnection attempts reached")
                    raise error
    
    async def disconnect(self) -> None:
        """Disconnect from IB Gateway."""
        if self.connected:
            self.logger.info("Disconnecting from IB Gateway")
            self.ib.disconnect()
            self.connected = False
    
    def _setup_handlers(self) -> None:
        """Set up IB event handlers."""
        self.ib.errorEvent += self._on_error
        self.ib.orderEvent += self._on_order_event
        self.ib.tradeEvent += self._on_trade_event
        self.ib.tickEvent += self._on_tick_event
        self.ib.barEvent += self._on_bar_event
    
    def _on_error(self, reqId: int, errorCode: int, errorString: str, contract: Optional[Contract] = None) -> None:
        """Handle IB error events."""
        if errorCode in (2104, 2106, 2158):  # Market data farm connection messages
            return
        
        error = handle_ib_error(errorCode, errorString)
        self.logger.error(f"IB Error {errorCode}: {errorString}")
        
        if errorCode in (1100, 1101, 1102):  # Connection errors
            self.connected = False
            asyncio.create_task(self._handle_disconnection())
    
    def _on_order_event(self, order: Order) -> None:
        """Handle order events."""
        order_id = getattr(order, 'orderId', None)
        if order_id and order_id in self._order_callbacks:
            callback = self._order_callbacks[order_id]
            try:
                callback(order)
            except Exception as e:
                self.logger.error(f"Error in order callback: {e}")
    
    def _on_trade_event(self, trade: Trade) -> None:
        """Handle trade events."""
        self.logger.info(f"Trade event: {trade}")
    
    def _on_tick_event(self, ticker: Ticker) -> None:
        """Handle tick events."""
        symbol = getattr(ticker.contract, 'symbol', 'UNKNOWN')
        if symbol in self._data_callbacks:
            callback = self._data_callbacks[symbol]
            try:
                callback(ticker)
            except Exception as e:
                self.logger.error(f"Error in tick callback for {symbol}: {e}")
    
    def _on_bar_event(self, bars: List[BarData]) -> None:
        """Handle bar events."""
        for bar in bars:
            symbol = getattr(bar.contract, 'symbol', 'UNKNOWN')
            if symbol in self._data_callbacks:
                callback = self._data_callbacks[symbol]
                try:
                    callback(bar)
                except Exception as e:
                    self.logger.error(f"Error in bar callback for {symbol}: {e}")
    
    async def _handle_disconnection(self) -> None:
        """Handle disconnection and attempt reconnection."""
        self.logger.warning("Connection lost, attempting reconnection...")
        self.connected = False
        
        try:
            await self.connect()
        except Exception as e:
            self.logger.error(f"Reconnection failed: {e}")
    
    async def _heartbeat_task(self) -> None:
        """Heartbeat task to monitor connection."""
        while self.connected:
            try:
                await asyncio.sleep(self.heartbeat_interval)
                
                if not self.ib.isConnected():
                    self.logger.warning("Heartbeat failed, connection lost")
                    self.connected = False
                    await self._handle_disconnection()
                    break
                
                self.last_heartbeat = time.time()
                
            except Exception as e:
                self.logger.error(f"Heartbeat error: {e}")
                break
    
    async def qualify_contract(self, contract: Contract) -> Contract:
        """Qualify contract with IB."""
        try:
            qualified = await self.ib.qualifyContractsAsync(contract)
            if not qualified:
                raise IBError(f"Contract qualification failed: {contract}")
            return qualified[0]
        except Exception as e:
            raise IBError(f"Contract qualification error: {e}")
    
    async def subscribe_market_data(self, contract: Contract, callback: Callable) -> None:
        """Subscribe to market data for contract."""
        try:
            qualified = await self.qualify_contract(contract)
            symbol = qualified.symbol
            
            # Store callback
            self._data_callbacks[symbol] = callback
            self._subscriptions[symbol] = qualified
            
            # Request market data
            ticker = self.ib.reqMktData(qualified, '', False, False)
            self.logger.info(f"Subscribed to market data for {symbol}")
            
        except Exception as e:
            self.logger.error(f"Market data subscription failed: {e}")
            raise
    
    async def subscribe_bars(self, contract: Contract, duration: str, bar_size: str, callback: Callable) -> None:
        """Subscribe to real-time bars."""
        try:
            qualified = await self.qualify_contract(contract)
            symbol = qualified.symbol
            
            # Store callback
            self._data_callbacks[symbol] = callback
            self._subscriptions[symbol] = qualified
            
            # Request bars
            bars = self.ib.reqRealTimeBars(qualified, 5, duration, bar_size, False)
            self.logger.info(f"Subscribed to bars for {symbol}")
            
        except Exception as e:
            self.logger.error(f"Bar subscription failed: {e}")
            raise
    
    async def place_order(self, contract: Contract, order: Order, correlation_id: Optional[str] = None) -> str:
        """Place order with correlation ID."""
        try:
            if not self.connected:
                raise IBError("Not connected to IB Gateway")
            
            # Set correlation ID in order
            if correlation_id:
                order.orderId = int(correlation_id.split('-')[0], 16) % 1000000
                set_correlation_id(correlation_id)
            
            # Qualify contract
            qualified = await self.qualify_contract(contract)
            
            # Place order
            trade = self.ib.placeOrder(qualified, order)
            
            # Store order callback
            if hasattr(order, 'orderId'):
                self._order_callbacks[order.orderId] = self._default_order_callback
            
            self.logger.info(f"Order placed: {order.action} {order.totalQuantity} {qualified.symbol}")
            return str(trade.order.orderId)
            
        except Exception as e:
            error = handle_ib_error(0, str(e))
            self.logger.error(f"Order placement failed: {error.message}")
            raise error
    
    def _default_order_callback(self, order: Order) -> None:
        """Default order event callback."""
        self.logger.info(f"Order update: {order.orderId} - {order.status}")
    
    async def cancel_order(self, order_id: int) -> None:
        """Cancel order by ID."""
        try:
            self.ib.cancelOrder(order_id)
            self.logger.info(f"Order {order_id} cancelled")
        except Exception as e:
            self.logger.error(f"Order cancellation failed: {e}")
            raise
    
    async def get_positions(self) -> List[Dict[str, Any]]:
        """Get current positions."""
        try:
            positions = []
            for position in self.ib.positions():
                positions.append({
                    'symbol': position.contract.symbol,
                    'quantity': position.position,
                    'avg_cost': position.averageCost,
                    'market_value': position.marketValue,
                    'unrealized_pnl': position.unrealizedPNL,
                    'realized_pnl': position.realizedPNL
                })
            return positions
        except Exception as e:
            self.logger.error(f"Failed to get positions: {e}")
            raise
    
    async def get_account_summary(self) -> Dict[str, Any]:
        """Get account summary."""
        try:
            summary = self.ib.accountSummary()
            return {item.tag: item.value for item in summary}
        except Exception as e:
            self.logger.error(f"Failed to get account summary: {e}")
            raise
    
    def is_connected(self) -> bool:
        """Check if connected to IB Gateway."""
        return self.connected and self.ib.isConnected()
    
    def get_connection_info(self) -> Dict[str, Any]:
        """Get connection information."""
        return {
            'connected': self.connected,
            'ib_connected': self.ib.isConnected() if self.ib else False,
            'last_heartbeat': self.last_heartbeat,
            'subscriptions': list(self._subscriptions.keys()),
            'reconnect_info': self.reconnect_manager.get_attempt_info(),
            'circuit_breaker': self.circuit_breaker.get_state()
        }
