"""End-to-end paper trading integration test."""

import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from apps.strategy.main import StrategyApp
from apps.risk_oms.main import RiskOMSApp
from apps.md_collector.main import MDCollectorApp
from apps.api.main import create_app
from tests.integration.mock_ib_gateway import MockIBGateway


class TestPaperTradingEndToEnd:
    """End-to-end paper trading test."""
    
    @pytest.fixture
    async def mock_gateway(self):
        """Create mock IB Gateway."""
        gateway = MockIBGateway()
        await gateway.start()
        yield gateway
        await gateway.stop()
    
    @pytest.fixture
    async def mock_services(self):
        """Create mock services."""
        # Mock TimescaleDB
        mock_timescale = Mock()
        mock_timescale.connect = AsyncMock()
        mock_timescale.disconnect = AsyncMock()
        mock_timescale.insert_ticks = AsyncMock()
        mock_timescale.insert_bars = AsyncMock()
        mock_timescale.insert_order = AsyncMock()
        mock_timescale.insert_fill = AsyncMock()
        
        # Mock Redis
        mock_redis = Mock()
        mock_redis.connect = AsyncMock()
        mock_redis.disconnect = AsyncMock()
        mock_redis.cache_market_data = AsyncMock()
        mock_redis.get_market_data = AsyncMock(return_value=None)
        mock_redis.lrange = AsyncMock(return_value=[])
        
        # Mock Kafka
        mock_kafka = Mock()
        mock_kafka.connect = AsyncMock()
        mock_kafka.disconnect = AsyncMock()
        mock_kafka.send_tick = AsyncMock()
        mock_kafka.send_bar = AsyncMock()
        mock_kafka.send_signal = AsyncMock()
        mock_kafka.send_order = AsyncMock()
        mock_kafka.send_fill = AsyncMock()
        
        return mock_timescale, mock_redis, mock_kafka
    
    @pytest.mark.asyncio
    async def test_market_data_collection(self, mock_gateway, mock_services):
        """Test market data collection end-to-end."""
        mock_timescale, mock_redis, mock_kafka = mock_services
        
        # Create MD collector app
        with patch('apps.md_collector.main.TimescaleClient', return_value=mock_timescale), \
             patch('apps.md_collector.main.RedisClient', return_value=mock_redis), \
             patch('apps.md_collector.main.KafkaClient', return_value=mock_kafka), \
             patch('apps.md_collector.main.IBClient') as mock_ib_client:
            
            # Setup mock IB client
            mock_ib_client.return_value.connect = AsyncMock()
            mock_ib_client.return_value.disconnect = AsyncMock()
            mock_ib_client.return_value.is_connected = Mock(return_value=True)
            
            app = MDCollectorApp()
            
            # Start app
            await app.start()
            
            # Wait for some data collection
            await asyncio.sleep(2)
            
            # Verify market data was collected
            assert mock_timescale.insert_ticks.called or mock_timescale.insert_bars.called
            assert mock_redis.cache_market_data.called
            assert mock_kafka.send_tick.called or mock_kafka.send_bar.called
            
            await app._cleanup()
    
    @pytest.mark.asyncio
    async def test_signal_generation(self, mock_gateway, mock_services):
        """Test signal generation end-to-end."""
        mock_timescale, mock_redis, mock_kafka = mock_services
        
        # Mock market data
        mock_redis.get_market_data.return_value = {
            'bid': 450.0,
            'ask': 450.1,
            'last': 450.05,
            'timestamp': datetime.utcnow()
        }
        
        # Create strategy app
        with patch('apps.strategy.main.TimescaleClient', return_value=mock_timescale), \
             patch('apps.strategy.main.RedisClient', return_value=mock_redis), \
             patch('apps.strategy.main.KafkaClient', return_value=mock_kafka), \
             patch('apps.strategy.main.IBClient') as mock_ib_client:
            
            # Setup mock IB client
            mock_ib_client.return_value.connect = AsyncMock()
            mock_ib_client.return_value.disconnect = AsyncMock()
            mock_ib_client.return_value.is_connected = Mock(return_value=True)
            
            app = StrategyApp()
            
            # Start app
            await app.start()
            
            # Wait for signal generation
            await asyncio.sleep(2)
            
            # Verify signals were generated
            assert mock_kafka.send_signal.called
            
            await app._cleanup()
    
    @pytest.mark.asyncio
    async def test_order_processing(self, mock_gateway, mock_services):
        """Test order processing end-to-end."""
        mock_timescale, mock_redis, mock_kafka = mock_services
        
        # Mock order data
        mock_redis.lrange.return_value = [{
            'symbol': 'SPY',
            'side': 'BUY',
            'quantity': 100,
            'price': 450.0,
            'order_type': 'MKT',
            'idempotency_key': 'test123',
            'correlation_id': 'corr123'
        }]
        
        # Create risk/OMS app
        with patch('apps.risk_oms.main.TimescaleClient', return_value=mock_timescale), \
             patch('apps.risk_oms.main.RedisClient', return_value=mock_redis), \
             patch('apps.risk_oms.main.KafkaClient', return_value=mock_kafka), \
             patch('apps.risk_oms.main.IBClient') as mock_ib_client:
            
            # Setup mock IB client
            mock_ib_client.return_value.connect = AsyncMock()
            mock_ib_client.return_value.disconnect = AsyncMock()
            mock_ib_client.return_value.is_connected = Mock(return_value=True)
            mock_ib_client.return_value.place_order = AsyncMock(return_value="order123")
            
            app = RiskOMSApp()
            
            # Start app
            await app.start()
            
            # Wait for order processing
            await asyncio.sleep(2)
            
            # Verify order was processed
            assert mock_ib_client.return_value.place_order.called
            assert mock_kafka.send_order.called
            
            await app._cleanup()
    
    @pytest.mark.asyncio
    async def test_idempotency(self, mock_gateway, mock_services):
        """Test order idempotency."""
        mock_timescale, mock_redis, mock_kafka = mock_services
        
        # Mock duplicate order data
        duplicate_order = {
            'symbol': 'SPY',
            'side': 'BUY',
            'quantity': 100,
            'price': 450.0,
            'order_type': 'MKT',
            'idempotency_key': 'duplicate123',
            'correlation_id': 'corr123'
        }
        
        mock_redis.lrange.return_value = [duplicate_order, duplicate_order]
        
        # Create risk/OMS app
        with patch('apps.risk_oms.main.TimescaleClient', return_value=mock_timescale), \
             patch('apps.risk_oms.main.RedisClient', return_value=mock_redis), \
             patch('apps.risk_oms.main.KafkaClient', return_value=mock_kafka), \
             patch('apps.risk_oms.main.IBClient') as mock_ib_client:
            
            # Setup mock IB client
            mock_ib_client.return_value.connect = AsyncMock()
            mock_ib_client.return_value.disconnect = AsyncMock()
            mock_ib_client.return_value.is_connected = Mock(return_value=True)
            mock_ib_client.return_value.place_order = AsyncMock(return_value="order123")
            
            app = RiskOMSApp()
            
            # Start app
            await app.start()
            
            # Wait for order processing
            await asyncio.sleep(2)
            
            # Verify only one order was placed (idempotency)
            assert mock_ib_client.return_value.place_order.call_count == 1
            
            await app._cleanup()
    
    @pytest.mark.asyncio
    async def test_risk_rejection(self, mock_gateway, mock_services):
        """Test risk rejection."""
        mock_timescale, mock_redis, mock_kafka = mock_services
        
        # Mock order that should be rejected
        mock_redis.lrange.return_value = [{
            'symbol': 'SPY',
            'side': 'BUY',
            'quantity': 2000,  # Exceeds quantity limit
            'price': 450.0,
            'order_type': 'MKT',
            'idempotency_key': 'test123',
            'correlation_id': 'corr123'
        }]
        
        # Create risk/OMS app
        with patch('apps.risk_oms.main.TimescaleClient', return_value=mock_timescale), \
             patch('apps.risk_oms.main.RedisClient', return_value=mock_redis), \
             patch('apps.risk_oms.main.KafkaClient', return_value=mock_kafka), \
             patch('apps.risk_oms.main.IBClient') as mock_ib_client:
            
            # Setup mock IB client
            mock_ib_client.return_value.connect = AsyncMock()
            mock_ib_client.return_value.disconnect = AsyncMock()
            mock_ib_client.return_value.is_connected = Mock(return_value=True)
            
            app = RiskOMSApp()
            
            # Start app
            await app.start()
            
            # Wait for order processing
            await asyncio.sleep(2)
            
            # Verify order was rejected (not placed)
            assert not mock_ib_client.return_value.place_order.called
            
            await app._cleanup()
    
    @pytest.mark.asyncio
    async def test_api_endpoints(self):
        """Test API endpoints."""
        app = create_app()
        
        # Test health endpoint
        from fastapi.testclient import TestClient
        client = TestClient(app)
        
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        
        # Test kill switch endpoint
        response = client.get("/api/v1/kill_switch")
        assert response.status_code == 200
        
        # Test positions endpoint
        response = client.get("/api/v1/positions")
        assert response.status_code == 200
        
        # Test PnL endpoint
        response = client.get("/api/v1/pnl")
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_full_trading_cycle(self, mock_gateway, mock_services):
        """Test full trading cycle from data to order."""
        mock_timescale, mock_redis, mock_kafka = mock_services
        
        # Mock market data
        mock_redis.get_market_data.return_value = {
            'bid': 450.0,
            'ask': 450.1,
            'last': 450.05,
            'timestamp': datetime.utcnow()
        }
        
        # Mock order data
        mock_redis.lrange.return_value = [{
            'symbol': 'SPY',
            'side': 'BUY',
            'quantity': 100,
            'price': 450.0,
            'order_type': 'MKT',
            'idempotency_key': 'test123',
            'correlation_id': 'corr123'
        }]
        
        # Create all apps
        with patch('apps.md_collector.main.TimescaleClient', return_value=mock_timescale), \
             patch('apps.md_collector.main.RedisClient', return_value=mock_redis), \
             patch('apps.md_collector.main.KafkaClient', return_value=mock_kafka), \
             patch('apps.strategy.main.TimescaleClient', return_value=mock_timescale), \
             patch('apps.strategy.main.RedisClient', return_value=mock_redis), \
             patch('apps.strategy.main.KafkaClient', return_value=mock_kafka), \
             patch('apps.risk_oms.main.TimescaleClient', return_value=mock_timescale), \
             patch('apps.risk_oms.main.RedisClient', return_value=mock_redis), \
             patch('apps.risk_oms.main.KafkaClient', return_value=mock_kafka), \
             patch('apps.md_collector.main.IBClient') as mock_ib_client_md, \
             patch('apps.strategy.main.IBClient') as mock_ib_client_strategy, \
             patch('apps.risk_oms.main.IBClient') as mock_ib_client_risk:
            
            # Setup mock IB clients
            for mock_ib_client in [mock_ib_client_md, mock_ib_client_strategy, mock_ib_client_risk]:
                mock_ib_client.return_value.connect = AsyncMock()
                mock_ib_client.return_value.disconnect = AsyncMock()
                mock_ib_client.return_value.is_connected = Mock(return_value=True)
                mock_ib_client.return_value.place_order = AsyncMock(return_value="order123")
            
            # Start all apps
            md_app = MDCollectorApp()
            strategy_app = StrategyApp()
            risk_app = RiskOMSApp()
            
            await md_app.start()
            await strategy_app.start()
            await risk_app.start()
            
            # Wait for full cycle
            await asyncio.sleep(5)
            
            # Verify full cycle
            assert mock_timescale.insert_ticks.called or mock_timescale.insert_bars.called
            assert mock_kafka.send_signal.called
            assert mock_ib_client_risk.return_value.place_order.called
            assert mock_kafka.send_order.called
            
            # Cleanup
            await md_app._cleanup()
            await strategy_app._cleanup()
            await risk_app._cleanup()


if __name__ == "__main__":
    # Run the test
    asyncio.run(TestPaperTradingEndToEnd().test_full_trading_cycle(None, None))
