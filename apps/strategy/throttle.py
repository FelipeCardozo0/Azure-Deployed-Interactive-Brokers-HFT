"""Order throttling with token bucket algorithm."""

import time
from typing import Optional
from dataclasses import dataclass


@dataclass
class ThrottleConfig:
    """Throttling configuration."""
    rate_per_sec: int = 10
    burst_size: int = 20
    enabled: bool = True


class TokenBucket:
    """Token bucket for rate limiting orders."""
    
    def __init__(self, rate_per_sec: int, burst_size: int):
        self.rate = rate_per_sec
        self.burst = burst_size
        self.tokens = burst_size
        self.last_update = time.monotonic()
        self.lock = False
    
    def allow(self) -> bool:
        """Check if request is allowed and consume token if so."""
        if self.lock:
            return False
        
        now = time.monotonic()
        elapsed = now - self.last_update
        
        # Add tokens based on elapsed time
        self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
        self.last_update = now
        
        # Check if we have tokens
        if self.tokens >= 1:
            self.tokens -= 1
            return True
        
        return False
    
    def get_tokens_available(self) -> float:
        """Get number of tokens currently available."""
        now = time.monotonic()
        elapsed = now - self.last_update
        return min(self.burst, self.tokens + elapsed * self.rate)
    
    def reset(self) -> None:
        """Reset token bucket to full capacity."""
        self.tokens = self.burst
        self.last_update = time.monotonic()
    
    def set_rate(self, rate_per_sec: int) -> None:
        """Update rate limit."""
        self.rate = rate_per_sec
    
    def set_burst(self, burst_size: int) -> None:
        """Update burst size."""
        self.burst = burst_size
        self.tokens = min(self.tokens, burst_size)


class ThrottleManager:
    """Manages throttling for multiple symbols."""
    
    def __init__(self, config: ThrottleConfig):
        self.config = config
        self.buckets: dict[str, TokenBucket] = {}
        self.global_bucket = TokenBucket(config.rate_per_sec, config.burst_size)
    
    def get_bucket(self, symbol: str) -> TokenBucket:
        """Get or create token bucket for symbol."""
        if symbol not in self.buckets:
            self.buckets[symbol] = TokenBucket(
                self.config.rate_per_sec,
                self.config.burst_size
            )
        return self.buckets[symbol]
    
    def allow_global(self) -> bool:
        """Check global rate limit."""
        if not self.config.enabled:
            return True
        return self.global_bucket.allow()
    
    def allow_symbol(self, symbol: str) -> bool:
        """Check symbol-specific rate limit."""
        if not self.config.enabled:
            return True
        
        # Check both global and symbol limits
        global_allowed = self.allow_global()
        symbol_allowed = self.get_bucket(symbol).allow()
        
        return global_allowed and symbol_allowed
    
    def get_status(self) -> dict:
        """Get throttling status."""
        return {
            "enabled": self.config.enabled,
            "global_tokens": self.global_bucket.get_tokens_available(),
            "symbol_buckets": {
                symbol: bucket.get_tokens_available()
                for symbol, bucket in self.buckets.items()
            }
        }
    
    def reset_all(self) -> None:
        """Reset all token buckets."""
        self.global_bucket.reset()
        for bucket in self.buckets.values():
            bucket.reset()
    
    def update_config(self, config: ThrottleConfig) -> None:
        """Update throttling configuration."""
        self.config = config
        self.global_bucket.set_rate(config.rate_per_sec)
        self.global_bucket.set_burst(config.burst_size)
        
        for bucket in self.buckets.values():
            bucket.set_rate(config.rate_per_sec)
            bucket.set_burst(config.burst_size)
