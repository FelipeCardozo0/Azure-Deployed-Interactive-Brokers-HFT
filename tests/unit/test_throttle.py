"""Unit tests for throttling."""

import pytest
import time
from apps.strategy.throttle import TokenBucket, ThrottleManager, ThrottleConfig


class TestTokenBucket:
    """Test token bucket implementation."""
    
    def test_token_bucket_initial_state(self):
        """Test token bucket initial state."""
        bucket = TokenBucket(rate_per_sec=10, burst_size=20)
        
        assert bucket.rate == 10
        assert bucket.burst == 20
        assert bucket.tokens == 20  # Initially full
    
    def test_token_bucket_allow_success(self):
        """Test token bucket allows request when tokens available."""
        bucket = TokenBucket(rate_per_sec=10, burst_size=20)
        
        # Should allow first request
        assert bucket.allow() == True
        assert bucket.tokens == 19
    
    def test_token_bucket_allow_failure(self):
        """Test token bucket rejects request when no tokens available."""
        bucket = TokenBucket(rate_per_sec=10, burst_size=1)
        
        # First request should succeed
        assert bucket.allow() == True
        assert bucket.tokens == 0
        
        # Second request should fail
        assert bucket.allow() == False
        assert bucket.tokens == 0
    
    def test_token_bucket_refill(self):
        """Test token bucket refills over time."""
        bucket = TokenBucket(rate_per_sec=10, burst_size=20)
        
        # Use all tokens
        for _ in range(20):
            assert bucket.allow() == True
        
        # No tokens left
        assert bucket.allow() == False
        
        # Wait for refill
        time.sleep(0.2)  # Should refill 2 tokens
        
        # Should allow requests again
        assert bucket.allow() == True
        assert bucket.allow() == True
        assert bucket.allow() == False  # Only 2 tokens refilled
    
    def test_token_bucket_reset(self):
        """Test token bucket reset."""
        bucket = TokenBucket(rate_per_sec=10, burst_size=20)
        
        # Use some tokens
        bucket.allow()
        bucket.allow()
        assert bucket.tokens == 18
        
        # Reset
        bucket.reset()
        assert bucket.tokens == 20
    
    def test_token_bucket_rate_update(self):
        """Test token bucket rate update."""
        bucket = TokenBucket(rate_per_sec=10, burst_size=20)
        
        # Update rate
        bucket.set_rate(20)
        assert bucket.rate == 20
    
    def test_token_bucket_burst_update(self):
        """Test token bucket burst update."""
        bucket = TokenBucket(rate_per_sec=10, burst_size=20)
        
        # Update burst size
        bucket.set_burst(30)
        assert bucket.burst == 30
        assert bucket.tokens == 30  # Should be updated to new burst size
    
    def test_token_bucket_burst_reduction(self):
        """Test token bucket burst reduction."""
        bucket = TokenBucket(rate_per_sec=10, burst_size=20)
        
        # Use some tokens
        bucket.allow()
        bucket.allow()
        assert bucket.tokens == 18
        
        # Reduce burst size
        bucket.set_burst(10)
        assert bucket.burst == 10
        assert bucket.tokens == 10  # Should be capped at new burst size


class TestThrottleManager:
    """Test throttle manager."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.config = ThrottleConfig(
            rate_per_sec=10,
            burst_size=20,
            enabled=True
        )
        self.manager = ThrottleManager(self.config)
    
    def test_throttle_manager_initial_state(self):
        """Test throttle manager initial state."""
        assert self.manager.config.enabled == True
        assert len(self.manager.buckets) == 0
        assert self.manager.global_bucket.rate == 10
        assert self.manager.global_bucket.burst == 20
    
    def test_allow_global_success(self):
        """Test global rate limit allows request."""
        assert self.manager.allow_global() == True
        assert self.manager.global_bucket.tokens == 19
    
    def test_allow_global_failure(self):
        """Test global rate limit rejects request when exceeded."""
        # Use all global tokens
        for _ in range(20):
            assert self.manager.allow_global() == True
        
        # Should reject
        assert self.manager.allow_global() == False
    
    def test_allow_symbol_success(self):
        """Test symbol rate limit allows request."""
        symbol = 'SPY'
        assert self.manager.allow_symbol(symbol) == True
        
        # Check that bucket was created
        assert symbol in self.manager.buckets
        assert self.manager.buckets[symbol].tokens == 19
    
    def test_allow_symbol_failure(self):
        """Test symbol rate limit rejects request when exceeded."""
        symbol = 'SPY'
        
        # Use all tokens for symbol
        for _ in range(20):
            assert self.manager.allow_symbol(symbol) == True
        
        # Should reject
        assert self.manager.allow_symbol(symbol) == False
    
    def test_allow_symbol_global_limit(self):
        """Test symbol request rejected due to global limit."""
        symbol = 'SPY'
        
        # Use all global tokens
        for _ in range(20):
            assert self.manager.allow_global() == True
        
        # Symbol request should fail due to global limit
        assert self.manager.allow_symbol(symbol) == False
    
    def test_throttle_disabled(self):
        """Test throttling when disabled."""
        self.manager.config.enabled = False
        
        # Should always allow when disabled
        assert self.manager.allow_global() == True
        assert self.manager.allow_symbol('SPY') == True
    
    def test_get_status(self):
        """Test throttle status reporting."""
        symbol = 'SPY'
        
        # Use some tokens
        self.manager.allow_symbol(symbol)
        self.manager.allow_symbol(symbol)
        
        status = self.manager.get_status()
        
        assert status['enabled'] == True
        assert status['global_tokens'] == 20  # Global bucket full
        assert symbol in status['symbol_buckets']
        assert status['symbol_buckets'][symbol] == 18  # 2 tokens used
    
    def test_reset_all(self):
        """Test reset all buckets."""
        symbol = 'SPY'
        
        # Use some tokens
        self.manager.allow_symbol(symbol)
        self.manager.allow_symbol(symbol)
        
        # Reset all
        self.manager.reset_all()
        
        # Check that all buckets are reset
        assert self.manager.global_bucket.tokens == 20
        assert self.manager.buckets[symbol].tokens == 20
    
    def test_update_config(self):
        """Test configuration update."""
        new_config = ThrottleConfig(
            rate_per_sec=20,
            burst_size=30,
            enabled=True
        )
        
        self.manager.update_config(new_config)
        
        assert self.manager.config.rate_per_sec == 20
        assert self.manager.config.burst_size == 30
        assert self.manager.global_bucket.rate == 20
        assert self.manager.global_bucket.burst == 30
    
    def test_multiple_symbols(self):
        """Test throttling with multiple symbols."""
        symbols = ['SPY', 'QQQ', 'IWM']
        
        # Each symbol should have its own bucket
        for symbol in symbols:
            assert self.manager.allow_symbol(symbol) == True
            assert symbol in self.manager.buckets
        
        # Check status
        status = self.manager.get_status()
        assert len(status['symbol_buckets']) == 3
        for symbol in symbols:
            assert symbol in status['symbol_buckets']
    
    def test_rate_limit_per_second(self):
        """Test rate limiting per second."""
        symbol = 'SPY'
        
        # Should allow 10 requests per second
        for i in range(10):
            assert self.manager.allow_symbol(symbol) == True
        
        # 11th request should fail
        assert self.manager.allow_symbol(symbol) == False
        
        # Wait for refill
        time.sleep(0.2)
        
        # Should allow more requests
        assert self.manager.allow_symbol(symbol) == True
