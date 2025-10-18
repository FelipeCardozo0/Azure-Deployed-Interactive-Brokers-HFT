"""Main market data collector application."""

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
from .cache import MarketDataCache
from .writer_timescale import TimescaleWriter
from .metrics import MDCollectorMetrics


class MDCollectorApp:
    """Main market data collector application."""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.running = False
        
        # Initialize components
        self.ib_client = IBClient()
        self.timescale = TimescaleClient(settings.postgres_dsn)
        self.redis = RedisClient(settings.redis_url)
        self.kafka = KafkaClient(settings.kafka_brokers)
        
        # Market data components
        self.cache = MarketDataCache(
            buffer_size=settings.md_buffer_size,
            flush_interval=settings.md_flush_interval
        )
        self.writer = TimescaleWriter(
            timescale=self.timescale,
            batch_size=settings.md_batch_size,
            flush_interval=settings.md_flush_interval
        )
        self.metrics = MDCollectorMetrics()
        
        # Market data subscriptions
        self.subscriptions: Dict[str, bool] = {}
        self.last_data_update: Dict[str, datetime] = {}
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum: int, frame: Any) -> None:
        """Handle shutdown signals."""
        self.logger.info(f"Received signal {signum}, shutting down...")
        self.running = False
    
    async def start(self) -> None:
        """Start the market data collector application."""
        try:
            self.logger.info("Starting market data collector...")
            
            # Connect to services
            await self._connect_services()
            
            # Subscribe to market data
            await self._subscribe_market_data()
            
            # Start main loop
            self.running = True
            await self._main_loop()
            
        except Exception as e:
            self.logger.error(f"Market data collector failed: {e}")
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
    
    async def _subscribe_market_data(self) -> None:
        """Subscribe to market data for all symbols."""
        self.logger.info("Subscribing to market data...")
        
        for symbol in settings.symbols:
            try:
                # Subscribe to real-time bars
                await self._subscribe_bars(symbol)
                
                # Subscribe to ticks
                await self._subscribe_ticks(symbol)
                
                self.subscriptions[symbol] = True
                self.logger.info(f"Subscribed to market data for {symbol}")
                
            except Exception as e:
                self.logger.error(f"Failed to subscribe to {symbol}: {e}")
                self.subscriptions[symbol] = False
    
    async def _subscribe_bars(self, symbol: str) -> None:
        """Subscribe to real-time bars for symbol."""
        try:
            # Create IB contract
            import ib_insync
            contract = ib_insync.Stock(symbol, 'SMART', 'USD')
            
            # Subscribe to 1-second bars
            def bar_callback(bars):
                for bar in bars:
                    self._process_bar(symbol, bar)
            
            # Request real-time bars
            self.ib_client.ib.reqRealTimeBars(
                contract, 5, '1 min', '1 sec', False
            )
            
        except Exception as e:
            self.logger.error(f"Error subscribing to bars for {symbol}: {e}")
    
    async def _subscribe_ticks(self, symbol: str) -> None:
        """Subscribe to ticks for symbol."""
        try:
            # Create IB contract
            import ib_insync
            contract = ib_insync.Stock(symbol, 'SMART', 'USD')
            
            # Subscribe to market data
            def tick_callback(ticker):
                self._process_tick(symbol, ticker)
            
            # Request market data
            ticker = self.ib_client.ib.reqMktData(contract, '', False, False)
            
        except Exception as e:
            self.logger.error(f"Error subscribing to ticks for {symbol}: {e}")
    
    def _process_bar(self, symbol: str, bar) -> None:
        """Process bar data from IB."""
        try:
            # Extract bar data
            bar_data = {
                'symbol': symbol,
                'timestamp': bar.time,
                'open': bar.open,
                'high': bar.high,
                'low': bar.low,
                'close': bar.close,
                'volume': bar.volume,
                'interval': '1s'
            }
            
            # Add to cache
            self.cache.add_bar(
                symbol=symbol,
                timestamp=bar_data['timestamp'],
                open_price=bar_data['open'],
                high=bar_data['high'],
                low=bar_data['low'],
                close=bar_data['close'],
                volume=bar_data['volume'],
                interval=bar_data['interval']
            )
            
            # Cache in Redis
            asyncio.create_task(self._cache_market_data(symbol, bar_data))
            
            # Send to Kafka
            asyncio.create_task(self._send_to_kafka('bar', symbol, bar_data))
            
            # Update last data time
            self.last_data_update[symbol] = datetime.utcnow()
            
            # Record metrics
            self.metrics.record_bar_received(symbol)
            
        except Exception as e:
            self.logger.error(f"Error processing bar for {symbol}: {e}")
    
    def _process_tick(self, symbol: str, ticker) -> None:
        """Process tick data from IB."""
        try:
            # Extract tick data
            tick_data = {
                'symbol': symbol,
                'timestamp': datetime.utcnow(),
                'bid': ticker.bid if hasattr(ticker, 'bid') else None,
                'ask': ticker.ask if hasattr(ticker, 'ask') else None,
                'last': ticker.last if hasattr(ticker, 'last') else None,
                'size': ticker.bidSize if hasattr(ticker, 'bidSize') else None,
                'volume': None  # Volume not available in ticks
            }
            
            # Add to cache
            self.cache.add_tick(
                symbol=symbol,
                timestamp=tick_data['timestamp'],
                bid=tick_data['bid'],
                ask=tick_data['ask'],
                last=tick_data['last'],
                size=tick_data['size'],
                volume=tick_data['volume']
            )
            
            # Cache in Redis
            asyncio.create_task(self._cache_market_data(symbol, tick_data))
            
            # Send to Kafka
            asyncio.create_task(self._send_to_kafka('tick', symbol, tick_data))
            
            # Update last data time
            self.last_data_update[symbol] = datetime.utcnow()
            
            # Record metrics
            self.metrics.record_tick_received(symbol)
            
        except Exception as e:
            self.logger.error(f"Error processing tick for {symbol}: {e}")
    
    async def _cache_market_data(self, symbol: str, data: Dict[str, Any]) -> None:
        """Cache market data in Redis."""
        try:
            await self.redis.cache_market_data(symbol, data, ttl=60)
        except Exception as e:
            self.logger.error(f"Error caching market data for {symbol}: {e}")
    
    async def _send_to_kafka(self, data_type: str, symbol: str, data: Dict[str, Any]) -> None:
        """Send market data to Kafka."""
        try:
            if data_type == 'tick':
                await self.kafka.send_tick(symbol, data)
            elif data_type == 'bar':
                await self.kafka.send_bar(symbol, data)
        except Exception as e:
            self.logger.error(f"Error sending {data_type} to Kafka for {symbol}: {e}")
    
    async def _main_loop(self) -> None:
        """Main application loop."""
        self.logger.info("Starting main application loop...")
        
        # Start background tasks
        tasks = [
            asyncio.create_task(self._data_processing_loop()),
            asyncio.create_task(self._writer_loop()),
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
    
    async def _data_processing_loop(self) -> None:
        """Data processing loop."""
        self.logger.info("Starting data processing loop...")
        
        while self.running:
            try:
                # Check if market is open
                if not is_market_open():
                    await asyncio.sleep(60)  # Check every minute when market is closed
                    continue
                
                # Process any pending data
                await self._process_pending_data()
                
                await asyncio.sleep(0.1)  # 100ms loop
                
            except Exception as e:
                self.logger.error(f"Error in data processing loop: {e}")
                await asyncio.sleep(1)
    
    async def _process_pending_data(self) -> None:
        """Process any pending market data."""
        try:
            # Get data from cache and write to database
            if self.cache.should_flush():
                bars_to_flush = self.cache.flush_bars()
                if bars_to_flush:
                    await self.writer.add_bars(bars_to_flush)
                    self.metrics.record_bars_written(len(bars_to_flush))
                
                self.cache.mark_flushed()
            
        except Exception as e:
            self.logger.error(f"Error processing pending data: {e}")
    
    async def _writer_loop(self) -> None:
        """Database writer loop."""
        self.logger.info("Starting writer loop...")
        
        while self.running:
            try:
                # Check if writer should flush
                if self.writer.should_flush():
                    await self.writer.flush()
                
                await asyncio.sleep(0.1)  # 100ms loop
                
            except Exception as e:
                self.logger.error(f"Error in writer loop: {e}")
                await asyncio.sleep(1)
    
    async def _metrics_loop(self) -> None:
        """Metrics collection loop."""
        self.logger.info("Starting metrics loop...")
        
        while self.running:
            try:
                # Update cache metrics
                cache_status = self.cache.get_cache_status()
                self.metrics.record_cache_status(cache_status)
                
                # Update writer metrics
                writer_stats = self.writer.get_stats()
                self.metrics.record_writer_stats(writer_stats)
                
                # Update subscription status
                active_subscriptions = sum(1 for active in self.subscriptions.values() if active)
                self.metrics.record_subscription_status(active_subscriptions, len(settings.symbols))
                
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
                stale_count = 0
                
                for symbol, last_update in self.last_data_update.items():
                    if last_update < stale_threshold:
                        stale_count += 1
                        self.logger.warning(f"Stale data for {symbol}, last update: {last_update}")
                
                self.metrics.record_stale_data_count(stale_count)
                
                # Check cache health
                cache_status = self.cache.get_cache_status()
                if cache_status['tick_buffers'] or cache_status['bar_buffers']:
                    self.logger.debug(f"Cache status: {cache_status}")
                
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                self.logger.error(f"Error in health check loop: {e}")
                await asyncio.sleep(30)
    
    async def get_status(self) -> Dict[str, Any]:
        """Get application status."""
        return {
            'running': self.running,
            'ib_connected': self.ib_client.is_connected(),
            'subscriptions': dict(self.subscriptions),
            'cache_status': self.cache.get_cache_status(),
            'writer_stats': self.writer.get_stats(),
            'stale_data_count': len([
                symbol for symbol, last_update in self.last_data_update.items()
                if last_update < datetime.utcnow() - timedelta(seconds=30)
            ])
        }
    
    async def get_data_summary(self, symbol: str) -> Dict[str, Any]:
        """Get data summary for symbol."""
        return self.cache.get_data_summary(symbol)
    
    async def _cleanup(self) -> None:
        """Cleanup resources."""
        self.logger.info("Cleaning up resources...")
        
        try:
            # Force flush any pending data
            await self.writer.force_flush()
            
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
    
    # Create and start market data collector
    app = MDCollectorApp()
    await app.start()


if __name__ == "__main__":
    asyncio.run(main())
