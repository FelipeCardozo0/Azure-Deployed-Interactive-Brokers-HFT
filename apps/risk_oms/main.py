"""Main Risk and OMS application."""

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
from .pretrade import PreTradeRisk, RiskConfig
from .oms import OrderManagementSystem
from .metrics import RiskMetrics


class RiskOMSApp:
    """Main Risk and OMS application."""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.running = False
        self.kill_switch = False
        
        # Initialize components
        self.ib_client = IBClient()
        self.timescale = TimescaleClient(settings.postgres_dsn)
        self.redis = RedisClient(settings.redis_url)
        self.kafka = KafkaClient(settings.kafka_brokers)
        
        # Risk and OMS components
        self.risk_config = RiskConfig(
            max_notional=settings.max_notional,
            max_qty=settings.max_qty,
            price_band_bps=settings.price_band_bps,
            orders_per_sec=settings.orders_per_sec,
            max_open_orders=settings.max_open_orders,
            stale_data_threshold=3,
            drawdown_limit=settings.drawdown_limit
        )
        
        self.pre_trade_risk = PreTradeRisk(self.risk_config)
        self.oms = OrderManagementSystem(self.timescale, self.redis, self.kafka, self.ib_client)
        self.metrics = RiskMetrics()
        
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
        """Start the Risk and OMS application."""
        try:
            self.logger.info("Starting Risk and OMS application...")
            
            # Connect to services
            await self._connect_services()
            
            # Start OMS
            await self.oms.start()
            
            # Start main loop
            self.running = True
            await self._main_loop()
            
        except Exception as e:
            self.logger.error(f"Risk and OMS application failed: {e}")
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
        """Main application loop."""
        self.logger.info("Starting main application loop...")
        
        # Start background tasks
        tasks = [
            asyncio.create_task(self._market_data_loop()),
            asyncio.create_task(self._order_processing_loop()),
            asyncio.create_task(self._risk_monitoring_loop()),
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
            
            # Update risk system with market data
            self.pre_trade_risk.update_market_data(symbol, market_data)
            
            # Update market data cache
            self.market_data[symbol] = market_data
            self.last_data_update[symbol] = datetime.utcnow()
            
        except Exception as e:
            self.logger.error(f"Error processing data for {symbol}: {e}")
    
    async def _order_processing_loop(self) -> None:
        """Order processing loop."""
        self.logger.info("Starting order processing loop...")
        
        while self.running:
            try:
                # Check if market is open and kill switch is off
                if not is_market_open() or self.kill_switch:
                    await asyncio.sleep(1)
                    continue
                
                # Process orders from Kafka
                await self._process_orders()
                
                await asyncio.sleep(0.1)  # 100ms loop
                
            except Exception as e:
                self.logger.error(f"Error in order processing loop: {e}")
                await asyncio.sleep(1)
    
    async def _process_orders(self) -> None:
        """Process orders from Kafka."""
        try:
            # Get orders from Kafka
            # This would be implemented with actual Kafka consumption
            # For now, we'll process orders from Redis
            pending_orders = await self.redis.lrange("pending_orders", 0, -1)
            
            for order_data in pending_orders:
                await self._process_single_order(order_data)
                
        except Exception as e:
            self.logger.error(f"Error processing orders: {e}")
    
    async def _process_single_order(self, order_data: Dict[str, Any]) -> None:
        """Process a single order."""
        try:
            symbol = order_data['symbol']
            side = order_data['side']
            quantity = order_data['quantity']
            price = order_data.get('price')
            order_type = order_data.get('order_type', 'MKT')
            idempotency_key = order_data.get('idempotency_key')
            correlation_id = order_data.get('correlation_id')
            
            # Perform pre-trade risk checks
            start_time = datetime.utcnow()
            risk_check = self.pre_trade_risk.check_order(
                symbol=symbol,
                side=side,
                quantity=quantity,
                price=price,
                order_id="",  # Will be generated by OMS
                correlation_id=correlation_id or ""
            )
            risk_duration = (datetime.utcnow() - start_time).total_seconds()
            
            # Record risk check metrics
            self.metrics.record_risk_check(
                symbol=symbol,
                decision=risk_check.decision.value,
                level=risk_check.level.value,
                duration=risk_duration
            )
            
            # Check risk decision
            if risk_check.decision.value == "REJECT":
                self.metrics.record_risk_rejection(symbol, risk_check.reason)
                self.logger.warning(f"Order rejected by risk: {risk_check.reason}")
                return
            
            # Submit order to OMS
            start_time = datetime.utcnow()
            order_id, success = await self.oms.submit_order(
                symbol=symbol,
                side=side,
                quantity=quantity,
                price=price,
                order_type=order_type,
                idempotency_key=idempotency_key,
                correlation_id=correlation_id
            )
            order_duration = (datetime.utcnow() - start_time).total_seconds()
            
            # Record order metrics
            if success:
                self.metrics.record_order_submitted(symbol, side, order_type, order_duration)
                self.logger.info(f"Order submitted: {order_id}")
            else:
                self.metrics.record_order_rejected(symbol, "OMS submission failed")
                self.logger.error(f"Order submission failed: {order_id}")
            
        except Exception as e:
            self.logger.error(f"Error processing order: {e}")
    
    async def _risk_monitoring_loop(self) -> None:
        """Risk monitoring loop."""
        self.logger.info("Starting risk monitoring loop...")
        
        while self.running:
            try:
                # Check for stale data
                stale_count = 0
                stale_threshold = datetime.utcnow() - timedelta(seconds=self.risk_config.stale_data_threshold)
                
                for symbol, last_update in self.last_data_update.items():
                    if last_update < stale_threshold:
                        stale_count += 1
                        self.logger.warning(f"Stale data for {symbol}: {last_update}")
                
                self.metrics.record_stale_data(stale_count)
                
                # Check for high rejection rates
                # This would implement more sophisticated risk monitoring
                
                # Update risk limits utilization
                # This would calculate actual utilization based on current positions
                
                await asyncio.sleep(5)  # Check every 5 seconds
                
            except Exception as e:
                self.logger.error(f"Error in risk monitoring loop: {e}")
                await asyncio.sleep(5)
    
    async def _metrics_loop(self) -> None:
        """Metrics collection loop."""
        self.logger.info("Starting metrics loop...")
        
        while self.running:
            try:
                # Update OMS metrics
                oms_status = self.oms.get_oms_status()
                self.metrics.record_active_orders(oms_status['total_orders'])
                
                # Update risk metrics
                risk_status = self.pre_trade_risk.get_risk_status()
                
                # Update position metrics
                # This would get actual position data from portfolio manager
                
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
                
                # Check for critical risk alerts
                alerts = self.metrics.get_risk_alerts()
                for alert in alerts:
                    if alert['severity'] == 'CRITICAL':
                        self.logger.error(f"Critical risk alert: {alert['message']}")
                        # Could trigger kill switch here
                
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                self.logger.error(f"Error in health check loop: {e}")
                await asyncio.sleep(30)
    
    async def set_kill_switch(self, active: bool) -> None:
        """Set kill switch state."""
        self.kill_switch = active
        self.pre_trade_risk.set_kill_switch(active)
        
        if active:
            self.metrics.record_kill_switch_activation()
            self.logger.warning("Kill switch activated")
        else:
            self.logger.info("Kill switch deactivated")
    
    async def get_status(self) -> Dict[str, Any]:
        """Get application status."""
        return {
            'running': self.running,
            'kill_switch': self.kill_switch,
            'ib_connected': self.ib_client.is_connected(),
            'oms_status': self.oms.get_oms_status(),
            'risk_status': self.pre_trade_risk.get_risk_status(),
            'market_data_symbols': list(self.market_data.keys()),
            'stale_data_count': len([
                symbol for symbol, last_update in self.last_data_update.items()
                if last_update < datetime.utcnow() - timedelta(seconds=self.risk_config.stale_data_threshold)
            ])
        }
    
    async def _cleanup(self) -> None:
        """Cleanup resources."""
        self.logger.info("Cleaning up resources...")
        
        try:
            # Stop OMS
            await self.oms.stop()
            
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
    
    # Create and start Risk and OMS app
    app = RiskOMSApp()
    await app.start()


if __name__ == "__main__":
    asyncio.run(main())
