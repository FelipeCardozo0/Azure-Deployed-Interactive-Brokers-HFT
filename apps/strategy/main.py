"""Main strategy application."""

import asyncio
import uvloop
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import signal
import sys

from ..common.config import settings
from ..common.log import get_logger, set_correlation_id, generate_correlation_id
from ..common.time import is_market_open, get_trading_time
from ..ib_wrapper import IBClient
from ..storage import TimescaleClient, RedisClient, KafkaClient
from .signals import SignalGenerator, SignalConfig
from .features import FeatureCalculator, FeatureConfig
from .portfolio import PortfolioManager, PortfolioConfig
from .throttle import ThrottleManager, ThrottleConfig
from .metrics import StrategyMetrics
from .orders import OrderManager


class StrategyApp:
    """Main strategy application."""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.running = False
        self.kill_switch = False
        
        # Initialize components
        self.ib_client = IBClient()
        self.timescale = TimescaleClient(settings.postgres_dsn)
        self.redis = RedisClient(settings.redis_url)
        self.kafka = KafkaClient(settings.kafka_brokers)
        
        # Strategy components
        self.signal_generator = SignalGenerator(SignalConfig(
            zscore_threshold=settings.signal_threshold,
            momentum_threshold=0.001,
            volatility_threshold=0.01,
            volume_threshold=1.5,
            min_confidence=0.6
        ))
        
        self.feature_calculator = FeatureCalculator(FeatureConfig(
            lookback_period=settings.lookback_period,
            volatility_window=settings.volatility_window,
            momentum_window=settings.momentum_window,
            zscore_threshold=settings.signal_threshold
        ))
        
        self.portfolio_manager = PortfolioManager(PortfolioConfig(
            max_position_size=0.1,
            max_total_exposure=0.5,
            stop_loss_pct=0.02,
            take_profit_pct=0.04
        ))
        
        self.throttle_manager = ThrottleManager(ThrottleConfig(
            rate_per_sec=settings.orders_per_sec,
            burst_size=settings.orders_per_sec * 2,
            enabled=settings.enable_throttling
        ))
        
        self.metrics = StrategyMetrics()
        self.order_manager = OrderManager()
        
        # Market data cache
        self.market_data: Dict[str, Dict[str, Any]] = {}
        self.last_data_update: Dict[str, datetime] = {}
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum: int, frame: Any) -> None:
        """Handle shutdown signals."""
        self.logger.info(f"Received signal {signum}, shutting down...")
        self.running = False
    
    async def start(self) -> None:
        """Start the strategy application."""
        try:
            self.logger.info("Starting strategy application...")
            
            # Connect to services
            await self._connect_services()
            
            # Start main loop
            self.running = True
            await self._main_loop()
            
        except Exception as e:
            self.logger.error(f"Strategy application failed: {e}")
            raise
        finally:
            await self._cleanup()
    
    async def _connect_services(self) -> None:
        """Connect to all required services."""
        self.logger.info("Connecting to services...")
        
        # Connect to databases
        await self.timescale.connect()
        await self.redis.connect()
        await self.kafka.connect()
        
        # Connect to IB Gateway
        await self.ib_client.connect()
        
        self.logger.info("All services connected")
    
    async def _main_loop(self) -> None:
        """Main strategy loop."""
        self.logger.info("Starting main strategy loop...")
        
        # Start background tasks
        tasks = [
            asyncio.create_task(self._market_data_loop()),
            asyncio.create_task(self._signal_loop()),
            asyncio.create_task(self._order_loop()),
            asyncio.create_task(self._metrics_loop()),
            asyncio.create_task(self._health_check_loop())
        ]
        
        try:
            # Wait for all tasks
            await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            self.logger.error(f"Error in main loop: {e}")
        finally:
            # Cancel all tasks
            for task in tasks:
                task.cancel()
    
    async def _market_data_loop(self) -> None:
        """Market data processing loop."""
        self.logger.info("Starting market data loop...")
        
        while self.running:
            try:
                # Check if market is open
                if not is_market_open():
                    await asyncio.sleep(60)  # Check every minute when market is closed
                    continue
                
                # Process market data for each symbol
                for symbol in settings.symbols:
                    await self._process_symbol_data(symbol)
                
                await asyncio.sleep(0.1)  # 100ms loop
                
            except Exception as e:
                self.logger.error(f"Error in market data loop: {e}")
                await asyncio.sleep(1)
    
    async def _process_symbol_data(self, symbol: str) -> None:
        """Process market data for a symbol."""
        try:
            # Get latest market data from Redis
            market_data = await self.redis.get_market_data(symbol)
            if not market_data:
                return
            
            # Update feature calculator
            if 'price' in market_data and 'volume' in market_data:
                self.feature_calculator.add_tick(
                    symbol=symbol,
                    timestamp=datetime.utcnow(),
                    price=market_data['price'],
                    volume=market_data.get('volume', 0)
                )
            elif 'close' in market_data:
                self.feature_calculator.add_bar(
                    symbol=symbol,
                    timestamp=datetime.utcnow(),
                    open_price=market_data.get('open', market_data['close']),
                    high=market_data.get('high', market_data['close']),
                    low=market_data.get('low', market_data['close']),
                    close=market_data['close'],
                    volume=market_data.get('volume', 0)
                )
            
            # Update market data cache
            self.market_data[symbol] = market_data
            self.last_data_update[symbol] = datetime.utcnow()
            
        except Exception as e:
            self.logger.error(f"Error processing data for {symbol}: {e}")
    
    async def _signal_loop(self) -> None:
        """Signal generation loop."""
        self.logger.info("Starting signal loop...")
        
        while self.running:
            try:
                # Check if market is open and kill switch is off
                if not is_market_open() or self.kill_switch:
                    await asyncio.sleep(1)
                    continue
                
                # Generate signals for each symbol
                for symbol in settings.symbols:
                    await self._generate_signal(symbol)
                
                await asyncio.sleep(1)  # 1 second loop
                
            except Exception as e:
                self.logger.error(f"Error in signal loop: {e}")
                await asyncio.sleep(1)
    
    async def _generate_signal(self, symbol: str) -> None:
        """Generate trading signal for symbol."""
        try:
            # Get features
            features = self.feature_calculator.get_features(symbol)
            if not features:
                return
            
            # Generate signal
            signal = self.signal_generator.generate_signal(symbol, features)
            if not signal:
                return
            
            # Record metrics
            self.metrics.record_signal(
                symbol=symbol,
                signal_type=signal.signal_type.value,
                strength=signal.strength,
                confidence=signal.confidence
            )
            
            # Send signal to Kafka
            await self.kafka.send_signal({
                'symbol': symbol,
                'signal_type': signal.signal_type.value,
                'strength': signal.strength,
                'confidence': signal.confidence,
                'features': features,
                'reason': signal.reason,
                'timestamp': signal.timestamp.isoformat()
            })
            
            self.logger.info(f"Generated {signal.signal_type.value} signal for {symbol}: {signal.reason}")
            
        except Exception as e:
            self.logger.error(f"Error generating signal for {symbol}: {e}")
    
    async def _order_loop(self) -> None:
        """Order management loop."""
        self.logger.info("Starting order loop...")
        
        while self.running:
            try:
                # Check if market is open and kill switch is off
                if not is_market_open() or self.kill_switch:
                    await asyncio.sleep(1)
                    continue
                
                # Process pending orders
                await self._process_orders()
                
                await asyncio.sleep(0.1)  # 100ms loop
                
            except Exception as e:
                self.logger.error(f"Error in order loop: {e}")
                await asyncio.sleep(1)
    
    async def _process_orders(self) -> None:
        """Process pending orders."""
        try:
            # Get pending orders from Redis
            pending_orders = await self.redis.lrange("pending_orders", 0, -1)
            
            for order_data in pending_orders:
                await self._execute_order(order_data)
                
        except Exception as e:
            self.logger.error(f"Error processing orders: {e}")
    
    async def _execute_order(self, order_data: Dict[str, Any]) -> None:
        """Execute a single order."""
        try:
            symbol = order_data['symbol']
            side = order_data['side']
            quantity = order_data['quantity']
            price = order_data.get('price')
            
            # Check throttling
            if not self.throttle_manager.allow_symbol(symbol):
                self.metrics.record_throttle_violation(symbol)
                self.logger.warning(f"Throttle limit exceeded for {symbol}")
                return
            
            # Check portfolio limits
            can_trade, reason = self.portfolio_manager.can_open_position(
                symbol, side, quantity, price or 0
            )
            if not can_trade:
                self.logger.warning(f"Cannot open position for {symbol}: {reason}")
                return
            
            # Place order with IB
            start_time = datetime.utcnow()
            order_id = await self.order_manager.place_order(
                self.ib_client, symbol, side, quantity, price
            )
            latency = (datetime.utcnow() - start_time).total_seconds()
            
            # Record metrics
            self.metrics.record_order(
                symbol=symbol,
                side=side,
                quantity=quantity,
                status="placed",
                latency=latency
            )
            
            self.logger.info(f"Order placed: {side} {quantity} {symbol} @ {price}")
            
        except Exception as e:
            self.logger.error(f"Error executing order: {e}")
    
    async def _metrics_loop(self) -> None:
        """Metrics collection loop."""
        self.logger.info("Starting metrics loop...")
        
        while self.running:
            try:
                # Update portfolio metrics
                portfolio = self.portfolio_manager.get_portfolio()
                for symbol, position in portfolio.positions.items():
                    if position.quantity > 0:
                        self.metrics.record_pnl(
                            symbol=symbol,
                            total_pnl=position.realized_pnl + position.unrealized_pnl,
                            daily_pnl=position.realized_pnl,
                            unrealized_pnl=position.unrealized_pnl,
                            realized_pnl=position.realized_pnl
                        )
                
                # Update system metrics
                import psutil
                process = psutil.Process()
                self.metrics.record_system_metrics(
                    connections=1,  # TODO: Get actual connection count
                    memory_bytes=process.memory_info().rss,
                    cpu_percent=process.cpu_percent()
                )
                
                await asyncio.sleep(10)  # Update every 10 seconds
                
            except Exception as e:
                self.logger.error(f"Error in metrics loop: {e}")
                await asyncio.sleep(10)
    
    async def _health_check_loop(self) -> None:
        """Health check loop."""
        self.logger.info("Starting health check loop...")
        
        while self.running:
            try:
                # Check IB connection
                if not self.ib_client.is_connected():
                    self.logger.warning("IB connection lost, attempting reconnect...")
                    await self.ib_client.connect()
                
                # Check for stale data
                stale_threshold = datetime.utcnow() - timedelta(seconds=30)
                for symbol, last_update in self.last_data_update.items():
                    if last_update < stale_threshold:
                        self.logger.warning(f"Stale data for {symbol}, last update: {last_update}")
                        # Could trigger kill switch here
                
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                self.logger.error(f"Error in health check loop: {e}")
                await asyncio.sleep(30)
    
    async def _cleanup(self) -> None:
        """Cleanup resources."""
        self.logger.info("Cleaning up resources...")
        
        try:
            # Disconnect from services
            await self.ib_client.disconnect()
            await self.timescale.disconnect()
            await self.redis.disconnect()
            await self.kafka.disconnect()
            
            self.logger.info("Cleanup completed")
            
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")


async def main():
    """Main entry point."""
    # Set up uvloop for better performance
    uvloop.install()
    
    # Create and start strategy app
    app = StrategyApp()
    await app.start()


if __name__ == "__main__":
    asyncio.run(main())
