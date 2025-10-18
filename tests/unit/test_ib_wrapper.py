"""Unit tests for IB wrapper."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from apps.ib_wrapper.client import IBClient
from apps.ib_wrapper.errors import IBError, IBConnectionError, IBTimeoutError
from apps.ib_wrapper.reconnect import ReconnectManager, CircuitBreaker


class TestIBClient:
    """Test IB client."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.client = IBClient()
    
    @pytest.mark.asyncio
    async def test_connect_success(self):
        """Test successful connection."""
        with patch.object(self.client.ib, 'connectAsync', new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = None
            
            await self.client.connect()
            
            assert self.client.connected == True
            mock_connect.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_connect_failure(self):
        """Test connection failure."""
        with patch.object(self.client.ib, 'connectAsync', new_callable=AsyncMock) as mock_connect:
            mock_connect.side_effect = Exception("Connection failed")
            
            with pytest.raises(IBError):
                await self.client.connect()
            
            assert self.client.connected == False
    
    @pytest.mark.asyncio
    async def test_disconnect(self):
        """Test disconnection."""
        self.client.connected = True
        
        with patch.object(self.client.ib, 'disconnect') as mock_disconnect:
            await self.client.disconnect()
            
            assert self.client.connected == False
            mock_disconnect.assert_called_once()
    
    def test_is_connected(self):
        """Test connection status check."""
        self.client.connected = True
        
        with patch.object(self.client.ib, 'isConnected', return_value=True):
            assert self.client.is_connected() == True
        
        with patch.object(self.client.ib, 'isConnected', return_value=False):
            assert self.client.is_connected() == False
    
    @pytest.mark.asyncio
    async def test_qualify_contract_success(self):
        """Test successful contract qualification."""
        mock_contract = Mock()
        mock_qualified = [Mock()]
        
        with patch.object(self.client.ib, 'qualifyContractsAsync', new_callable=AsyncMock) as mock_qualify:
            mock_qualify.return_value = mock_qualified
            
            result = await self.client.qualify_contract(mock_contract)
            
            assert result == mock_qualified[0]
            mock_qualify.assert_called_once_with(mock_contract)
    
    @pytest.mark.asyncio
    async def test_qualify_contract_failure(self):
        """Test contract qualification failure."""
        mock_contract = Mock()
        
        with patch.object(self.client.ib, 'qualifyContractsAsync', new_callable=AsyncMock) as mock_qualify:
            mock_qualify.return_value = []
            
            with pytest.raises(IBError):
                await self.client.qualify_contract(mock_contract)
    
    @pytest.mark.asyncio
    async def test_place_order_success(self):
        """Test successful order placement."""
        mock_contract = Mock()
        mock_order = Mock()
        mock_order.orderId = 12345
        
        with patch.object(self.client, 'qualify_contract', new_callable=AsyncMock) as mock_qualify:
            mock_qualify.return_value = mock_contract
            
            with patch.object(self.client.ib, 'placeOrder') as mock_place:
                mock_place.return_value = Mock()
                
                result = await self.client.place_order(mock_contract, mock_order, "corr123")
                
                assert result == "12345"
                mock_qualify.assert_called_once_with(mock_contract)
                mock_place.assert_called_once_with(mock_contract, mock_order)
    
    @pytest.mark.asyncio
    async def test_place_order_not_connected(self):
        """Test order placement when not connected."""
        mock_contract = Mock()
        mock_order = Mock()
        
        self.client.connected = False
        
        with pytest.raises(IBError):
            await self.client.place_order(mock_contract, mock_order)
    
    @pytest.mark.asyncio
    async def test_cancel_order_success(self):
        """Test successful order cancellation."""
        order_id = 12345
        
        with patch.object(self.client.ib, 'cancelOrder') as mock_cancel:
            await self.client.cancel_order(order_id)
            
            mock_cancel.assert_called_once_with(order_id)
    
    @pytest.mark.asyncio
    async def test_get_positions_success(self):
        """Test successful position retrieval."""
        mock_positions = [
            Mock(contract=Mock(symbol='SPY'), position=100, averageCost=450.0, 
                 marketValue=45000.0, unrealizedPNL=1000.0, realizedPNL=500.0)
        ]
        
        with patch.object(self.client.ib, 'positions', return_value=mock_positions):
            result = await self.client.get_positions()
            
            assert len(result) == 1
            assert result[0]['symbol'] == 'SPY'
            assert result[0]['quantity'] == 100
            assert result[0]['avg_cost'] == 450.0
    
    @pytest.mark.asyncio
    async def test_get_account_summary_success(self):
        """Test successful account summary retrieval."""
        mock_summary = [
            Mock(tag='TotalCashValue', value='100000.0'),
            Mock(tag='NetLiquidation', value='150000.0')
        ]
        
        with patch.object(self.client.ib, 'accountSummary', return_value=mock_summary):
            result = await self.client.get_account_summary()
            
            assert result['TotalCashValue'] == '100000.0'
            assert result['NetLiquidation'] == '150000.0'
    
    def test_get_connection_info(self):
        """Test connection info retrieval."""
        self.client.connected = True
        self.client.last_heartbeat = 1234567890.0
        
        with patch.object(self.client.ib, 'isConnected', return_value=True):
            info = self.client.get_connection_info()
            
            assert info['connected'] == True
            assert info['ib_connected'] == True
            assert info['last_heartbeat'] == 1234567890.0


class TestReconnectManager:
    """Test reconnect manager."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.manager = ReconnectManager()
    
    def test_initial_state(self):
        """Test initial state."""
        assert self.manager.attempts == 0
        assert self.manager.last_attempt == 0.0
        assert self.manager.can_retry() == True
    
    def test_reset(self):
        """Test reset."""
        self.manager.attempts = 5
        self.manager.last_attempt = 1234567890.0
        
        self.manager.reset()
        
        assert self.manager.attempts == 0
        assert self.manager.last_attempt == 0.0
    
    def test_should_retry_success(self):
        """Test should retry when conditions are met."""
        from apps.ib_wrapper.errors import IBConnectionError
        
        error = IBConnectionError("Connection lost")
        
        assert self.manager.should_retry(error) == True
    
    def test_should_retry_max_attempts(self):
        """Test should retry when max attempts reached."""
        from apps.ib_wrapper.errors import IBConnectionError
        
        self.manager.attempts = 5  # Max attempts
        
        error = IBConnectionError("Connection lost")
        
        assert self.manager.should_retry(error) == False
    
    def test_should_retry_non_retryable_error(self):
        """Test should retry with non-retryable error."""
        from apps.ib_wrapper.errors import IBError
        
        error = IBError("Non-retryable error")
        
        assert self.manager.should_retry(error) == False
    
    @pytest.mark.asyncio
    async def test_get_delay(self):
        """Test delay calculation."""
        from apps.ib_wrapper.errors import IBConnectionError
        
        error = IBConnectionError("Connection lost")
        
        delay = await self.manager.get_delay(error)
        
        assert delay > 0
        assert self.manager.attempts == 1
        assert self.manager.last_attempt > 0
    
    @pytest.mark.asyncio
    async def test_wait_and_retry_success(self):
        """Test wait and retry when should retry."""
        from apps.ib_wrapper.errors import IBConnectionError
        
        error = IBConnectionError("Connection lost")
        
        result = await self.manager.wait_and_retry(error)
        
        assert result == True
        assert self.manager.attempts == 1
    
    @pytest.mark.asyncio
    async def test_wait_and_retry_failure(self):
        """Test wait and retry when should not retry."""
        from apps.ib_wrapper.errors import IBError
        
        error = IBError("Non-retryable error")
        
        result = await self.manager.wait_and_retry(error)
        
        assert result == False
        assert self.manager.attempts == 0
    
    def test_get_attempt_info(self):
        """Test attempt info retrieval."""
        self.manager.attempts = 3
        self.manager.last_attempt = 1234567890.0
        
        info = self.manager.get_attempt_info()
        
        assert info['attempts'] == 3
        assert info['max_attempts'] == 5
        assert info['can_retry'] == True
        assert info['last_attempt'] == 1234567890.0


class TestCircuitBreaker:
    """Test circuit breaker."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.breaker = CircuitBreaker()
    
    def test_initial_state(self):
        """Test initial state."""
        assert self.breaker.state == "CLOSED"
        assert self.breaker.failure_count == 0
        assert self.breaker.allow_request() == True
    
    def test_record_success(self):
        """Test success recording."""
        self.breaker.failure_count = 3
        self.breaker.state = "OPEN"
        
        self.breaker.record_success()
        
        assert self.breaker.failure_count == 0
        assert self.breaker.state == "CLOSED"
    
    def test_record_failure(self):
        """Test failure recording."""
        self.breaker.record_failure()
        
        assert self.breaker.failure_count == 1
        assert self.breaker.state == "CLOSED"
    
    def test_record_failure_threshold(self):
        """Test failure recording at threshold."""
        self.breaker.failure_count = 4  # One below threshold
        
        self.breaker.record_failure()
        
        assert self.breaker.failure_count == 5
        assert self.breaker.state == "OPEN"
    
    def test_is_open_closed(self):
        """Test is_open when closed."""
        assert self.breaker.is_open() == False
    
    def test_is_open_open(self):
        """Test is_open when open."""
        self.breaker.failure_count = 5
        self.breaker.state = "OPEN"
        
        assert self.breaker.is_open() == True
    
    def test_is_half_open(self):
        """Test is_half_open."""
        self.breaker.state = "HALF_OPEN"
        
        assert self.breaker.is_half_open() == True
    
    def test_allow_request_closed(self):
        """Test allow_request when closed."""
        assert self.breaker.allow_request() == True
    
    def test_allow_request_open(self):
        """Test allow_request when open."""
        self.breaker.failure_count = 5
        self.breaker.state = "OPEN"
        
        assert self.breaker.allow_request() == False
    
    def test_get_state(self):
        """Test state retrieval."""
        self.breaker.failure_count = 3
        self.breaker.last_failure_time = 1234567890.0
        
        state = self.breaker.get_state()
        
        assert state['state'] == "CLOSED"
        assert state['failure_count'] == 3
        assert state['failure_threshold'] == 5
        assert state['last_failure_time'] == 1234567890.0
        assert state['timeout'] == 60.0
