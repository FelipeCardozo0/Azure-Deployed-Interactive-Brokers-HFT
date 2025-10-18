"""Reconnection and backoff utilities."""

import asyncio
import random
import time
from typing import AsyncGenerator, Optional
from dataclasses import dataclass
from .errors import IBError, is_retryable_error, get_retry_delay


@dataclass
class ReconnectConfig:
    """Reconnection configuration."""
    max_attempts: int = 5
    base_delay: float = 0.5
    max_delay: float = 30.0
    jitter: bool = True
    exponential: bool = True


async def backoff(
    base: float = 0.5,
    cap: float = 8.0,
    jitter: bool = True
) -> AsyncGenerator[float, None]:
    """Exponential backoff with jitter."""
    delay = base
    while True:
        if jitter:
            actual_delay = delay + random.random() * 0.2 * delay
        else:
            actual_delay = delay
        
        yield actual_delay
        delay = min(cap, delay * 2)


class ReconnectManager:
    """Manages reconnection logic for IB client."""
    
    def __init__(self, config: Optional[ReconnectConfig] = None):
        self.config = config or ReconnectConfig()
        self.attempts = 0
        self.last_attempt = 0.0
        self.backoff_gen = backoff(
            base=self.config.base_delay,
            cap=self.config.max_delay,
            jitter=self.config.jitter
        )
    
    def reset(self) -> None:
        """Reset reconnection state."""
        self.attempts = 0
        self.last_attempt = 0.0
        self.backoff_gen = backoff(
            base=self.config.base_delay,
            cap=self.config.max_delay,
            jitter=self.config.jitter
        )
    
    def should_retry(self, error: IBError) -> bool:
        """Check if we should retry after error."""
        if self.attempts >= self.config.max_attempts:
            return False
        
        if not is_retryable_error(error):
            return False
        
        # Rate limiting: don't retry too frequently
        now = time.time()
        if now - self.last_attempt < 1.0:  # Minimum 1 second between attempts
            return False
        
        return True
    
    async def get_delay(self, error: Optional[IBError] = None) -> float:
        """Get delay for next reconnection attempt."""
        if error:
            delay = get_retry_delay(error, self.attempts)
        else:
            delay = next(self.backoff_gen)
        
        self.attempts += 1
        self.last_attempt = time.time()
        
        return delay
    
    async def wait_and_retry(self, error: Optional[IBError] = None) -> bool:
        """Wait for delay and check if we should retry."""
        if not self.should_retry(error):
            return False
        
        delay = await self.get_delay(error)
        await asyncio.sleep(delay)
        return True
    
    def can_retry(self) -> bool:
        """Check if we can still retry."""
        return self.attempts < self.config.max_attempts
    
    def get_attempt_info(self) -> dict:
        """Get current attempt information."""
        return {
            "attempts": self.attempts,
            "max_attempts": self.config.max_attempts,
            "can_retry": self.can_retry(),
            "last_attempt": self.last_attempt
        }


class CircuitBreaker:
    """Circuit breaker for IB operations."""
    
    def __init__(self, failure_threshold: int = 5, timeout: float = 60.0):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = 0.0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    def record_success(self) -> None:
        """Record successful operation."""
        self.failure_count = 0
        self.state = "CLOSED"
    
    def record_failure(self) -> None:
        """Record failed operation."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
    
    def is_open(self) -> bool:
        """Check if circuit breaker is open."""
        if self.state == "OPEN":
            # Check if timeout has passed
            if time.time() - self.last_failure_time > self.timeout:
                self.state = "HALF_OPEN"
                return False
            return True
        return False
    
    def is_half_open(self) -> bool:
        """Check if circuit breaker is half-open."""
        return self.state == "HALF_OPEN"
    
    def allow_request(self) -> bool:
        """Check if request is allowed."""
        if self.is_open():
            return False
        return True
    
    def get_state(self) -> dict:
        """Get circuit breaker state."""
        return {
            "state": self.state,
            "failure_count": self.failure_count,
            "failure_threshold": self.failure_threshold,
            "last_failure_time": self.last_failure_time,
            "timeout": self.timeout
        }
