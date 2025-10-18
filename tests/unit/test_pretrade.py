"""Unit tests for pre-trade risk management."""

import pytest
from datetime import datetime, timedelta
from apps.risk_oms.pretrade import PreTradeRisk, RiskConfig, RiskDecision, RiskLevel


class TestPreTradeRisk:
    """Test pre-trade risk management."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.config = RiskConfig(
            max_notional=1000000.0,
            max_qty=1000,
            price_band_bps=50,
            orders_per_sec=10,
            max_open_orders=50,
            stale_data_threshold=3,
            drawdown_limit=0.05
        )
        self.risk = PreTradeRisk(self.config)
    
    def test_approve_order_normal_conditions(self):
        """Test order approval under normal conditions."""
        # Setup market data
        self.risk.update_market_data('SPY', {
            'bid': 450.0,
            'ask': 450.1,
            'last': 450.05,
            'timestamp': datetime.utcnow()
        })
        
        # Test order
        result = self.risk.check_order(
            symbol='SPY',
            side='BUY',
            quantity=100,
            price=450.0,
            order_id='test123',
            correlation_id='corr123'
        )
        
        assert result.decision == RiskDecision.APPROVE
        assert result.level == RiskLevel.LOW
        assert 'passed' in result.reason.lower()
    
    def test_reject_order_stale_data(self):
        """Test order rejection due to stale data."""
        # Setup stale market data
        stale_time = datetime.utcnow() - timedelta(seconds=10)
        self.risk.update_market_data('SPY', {
            'bid': 450.0,
            'ask': 450.1,
            'last': 450.05,
            'timestamp': stale_time
        })
        
        # Test order
        result = self.risk.check_order(
            symbol='SPY',
            side='BUY',
            quantity=100,
            price=450.0,
            order_id='test123',
            correlation_id='corr123'
        )
        
        assert result.decision == RiskDecision.REJECT
        assert result.level == RiskLevel.HIGH
        assert 'stale' in result.reason.lower()
    
    def test_reject_order_no_data(self):
        """Test order rejection due to no market data."""
        # Test order without market data
        result = self.risk.check_order(
            symbol='SPY',
            side='BUY',
            quantity=100,
            price=450.0,
            order_id='test123',
            correlation_id='corr123'
        )
        
        assert result.decision == RiskDecision.REJECT
        assert result.level == RiskLevel.HIGH
        assert 'no market data' in result.reason.lower()
    
    def test_reject_order_exceeds_quantity_limit(self):
        """Test order rejection due to quantity limit."""
        # Setup market data
        self.risk.update_market_data('SPY', {
            'bid': 450.0,
            'ask': 450.1,
            'last': 450.05,
            'timestamp': datetime.utcnow()
        })
        
        # Test order exceeding quantity limit
        result = self.risk.check_order(
            symbol='SPY',
            side='BUY',
            quantity=2000,  # Exceeds max_qty of 1000
            price=450.0,
            order_id='test123',
            correlation_id='corr123'
        )
        
        assert result.decision == RiskDecision.REJECT
        assert result.level == RiskLevel.HIGH
        assert 'quantity limit' in result.reason.lower()
    
    def test_reject_order_exceeds_notional_limit(self):
        """Test order rejection due to notional limit."""
        # Setup market data
        self.risk.update_market_data('SPY', {
            'bid': 450.0,
            'ask': 450.1,
            'last': 450.05,
            'timestamp': datetime.utcnow()
        })
        
        # Test order exceeding notional limit
        result = self.risk.check_order(
            symbol='SPY',
            side='BUY',
            quantity=1000,
            price=2000.0,  # High price to exceed notional limit
            order_id='test123',
            correlation_id='corr123'
        )
        
        assert result.decision == RiskDecision.REJECT
        assert result.level == RiskLevel.HIGH
        assert 'notional limit' in result.reason.lower()
    
    def test_reject_order_price_outside_band(self):
        """Test order rejection due to price outside band."""
        # Setup market data
        self.risk.update_market_data('SPY', {
            'bid': 450.0,
            'ask': 450.1,
            'last': 450.05,
            'timestamp': datetime.utcnow()
        })
        
        # Test order with price outside band
        result = self.risk.check_order(
            symbol='SPY',
            side='BUY',
            quantity=100,
            price=500.0,  # Way outside price band
            order_id='test123',
            correlation_id='corr123'
        )
        
        assert result.decision == RiskDecision.REJECT
        assert result.level == RiskLevel.MEDIUM
        assert 'outside band' in result.reason.lower()
    
    def test_reject_order_rate_limit_exceeded(self):
        """Test order rejection due to rate limit."""
        # Setup market data
        self.risk.update_market_data('SPY', {
            'bid': 450.0,
            'ask': 450.1,
            'last': 450.05,
            'timestamp': datetime.utcnow()
        })
        
        # Simulate rate limit by adding many orders quickly
        for i in range(15):  # Exceeds orders_per_sec of 10
            result = self.risk.check_order(
                symbol='SPY',
                side='BUY',
                quantity=100,
                price=450.0,
                order_id=f'test{i}',
                correlation_id=f'corr{i}'
            )
            
            if i < 10:
                assert result.decision == RiskDecision.APPROVE
            else:
                assert result.decision == RiskDecision.REJECT
                assert 'rate limit' in result.reason.lower()
    
    def test_reject_order_max_open_orders(self):
        """Test order rejection due to max open orders."""
        # Setup market data
        self.risk.update_market_data('SPY', {
            'bid': 450.0,
            'ask': 450.1,
            'last': 450.05,
            'timestamp': datetime.utcnow()
        })
        
        # Simulate max open orders
        for i in range(55):  # Exceeds max_open_orders of 50
            self.risk.add_open_order('SPY')
        
        result = self.risk.check_order(
            symbol='SPY',
            side='BUY',
            quantity=100,
            price=450.0,
            order_id='test123',
            correlation_id='corr123'
        )
        
        assert result.decision == RiskDecision.REJECT
        assert result.level == RiskLevel.MEDIUM
        assert 'open order limit' in result.reason.lower()
    
    def test_kill_switch_rejection(self):
        """Test order rejection when kill switch is active."""
        # Setup market data
        self.risk.update_market_data('SPY', {
            'bid': 450.0,
            'ask': 450.1,
            'last': 450.05,
            'timestamp': datetime.utcnow()
        })
        
        # Activate kill switch
        self.risk.set_kill_switch(True)
        
        result = self.risk.check_order(
            symbol='SPY',
            side='BUY',
            quantity=100,
            price=450.0,
            order_id='test123',
            correlation_id='corr123'
        )
        
        assert result.decision == RiskDecision.REJECT
        assert result.level == RiskLevel.CRITICAL
        assert 'kill switch' in result.reason.lower()
    
    def test_position_updates(self):
        """Test position updates."""
        # Update position
        self.risk.update_position('SPY', 100.0)
        
        # Check position
        risk_status = self.risk.get_risk_status()
        assert 'SPY' in risk_status['positions']
        assert risk_status['positions']['SPY'] == 100.0
    
    def test_open_order_tracking(self):
        """Test open order tracking."""
        # Add open order
        self.risk.add_open_order('SPY')
        
        # Check open orders
        risk_status = self.risk.get_risk_status()
        assert risk_status['open_orders']['SPY'] == 1
        
        # Remove open order
        self.risk.remove_open_order('SPY')
        
        # Check open orders
        risk_status = self.risk.get_risk_status()
        assert risk_status['open_orders']['SPY'] == 0
    
    def test_risk_status(self):
        """Test risk status reporting."""
        # Setup some data
        self.risk.update_market_data('SPY', {
            'bid': 450.0,
            'ask': 450.1,
            'last': 450.05,
            'timestamp': datetime.utcnow()
        })
        self.risk.update_position('SPY', 100.0)
        self.risk.add_open_order('SPY')
        
        # Get risk status
        status = self.risk.get_risk_status()
        
        assert 'kill_switch' in status
        assert 'open_orders' in status
        assert 'positions' in status
        assert 'order_counts' in status
        assert 'last_prices' in status
        
        assert status['positions']['SPY'] == 100.0
        assert status['open_orders']['SPY'] == 1
        assert 'SPY' in status['last_prices']
