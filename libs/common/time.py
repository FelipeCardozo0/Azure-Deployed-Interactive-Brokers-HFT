"""Trading time utilities."""

import pytz
from datetime import datetime, time, timedelta
from typing import Optional
from dataclasses import dataclass


@dataclass
class TradingHours:
    """Trading hours configuration."""
    start: time
    end: time
    timezone: str
    
    def __post_init__(self) -> None:
        """Convert timezone string to pytz timezone."""
        self.tz = pytz.timezone(self.timezone)
    
    def is_trading_time(self, dt: Optional[datetime] = None) -> bool:
        """Check if given datetime is within trading hours."""
        if dt is None:
            dt = datetime.now(self.tz)
        elif dt.tzinfo is None:
            dt = self.tz.localize(dt)
        else:
            dt = dt.astimezone(self.tz)
        
        current_time = dt.time()
        return self.start <= current_time <= self.end
    
    def next_open(self, dt: Optional[datetime] = None) -> datetime:
        """Get next trading session open time."""
        if dt is None:
            dt = datetime.now(self.tz)
        elif dt.tzinfo is None:
            dt = self.tz.localize(dt)
        else:
            dt = dt.astimezone(self.tz)
        
        # If we're before today's open, return today's open
        today_open = self.tz.localize(datetime.combine(dt.date(), self.start))
        if dt < today_open:
            return today_open
        
        # Otherwise, return tomorrow's open
        tomorrow = dt.date() + timedelta(days=1)
        return self.tz.localize(datetime.combine(tomorrow, self.start))
    
    def next_close(self, dt: Optional[datetime] = None) -> datetime:
        """Get next trading session close time."""
        if dt is None:
            dt = datetime.now(self.tz)
        elif dt.tzinfo is None:
            dt = self.tz.localize(dt)
        else:
            dt = dt.astimezone(self.tz)
        
        # If we're before today's close, return today's close
        today_close = self.tz.localize(datetime.combine(dt.date(), self.end))
        if dt < today_close:
            return today_close
        
        # Otherwise, return tomorrow's close
        tomorrow = dt.date() + timedelta(days=1)
        return self.tz.localize(datetime.combine(tomorrow, self.end))


def get_trading_time() -> TradingHours:
    """Get trading hours from configuration."""
    from .config import settings
    
    start_time = time.fromisoformat(settings.trading_hours_start)
    end_time = time.fromisoformat(settings.trading_hours_end)
    
    return TradingHours(
        start=start_time,
        end=end_time,
        timezone=settings.timezone
    )


def is_market_open() -> bool:
    """Check if market is currently open."""
    trading_hours = get_trading_time()
    return trading_hours.is_trading_time()


def get_market_status() -> dict:
    """Get current market status."""
    trading_hours = get_trading_time()
    now = datetime.now(trading_hours.tz)
    
    is_open = trading_hours.is_trading_time(now)
    
    if is_open:
        next_close = trading_hours.next_close(now)
        time_to_close = next_close - now
        return {
            "is_open": True,
            "next_event": "close",
            "next_event_time": next_close.isoformat(),
            "time_to_event": time_to_close.total_seconds()
        }
    else:
        next_open = trading_hours.next_open(now)
        time_to_open = next_open - now
        return {
            "is_open": False,
            "next_event": "open",
            "next_event_time": next_open.isoformat(),
            "time_to_event": time_to_open.total_seconds()
        }


def get_trading_day() -> datetime:
    """Get current trading day (date when market opens)."""
    trading_hours = get_trading_time()
    now = datetime.now(trading_hours.tz)
    
    if trading_hours.is_trading_time(now):
        # Market is open, return today
        return now.date()
    else:
        # Market is closed, return next trading day
        next_open = trading_hours.next_open(now)
        return next_open.date()


def format_trading_time(dt: datetime) -> str:
    """Format datetime for trading logs."""
    return dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] + " " + dt.tzname()


def get_seconds_until_close() -> float:
    """Get seconds until market close."""
    trading_hours = get_trading_time()
    now = datetime.now(trading_hours.tz)
    
    if not trading_hours.is_trading_time(now):
        return 0.0
    
    next_close = trading_hours.next_close(now)
    return (next_close - now).total_seconds()


def get_seconds_until_open() -> float:
    """Get seconds until market open."""
    trading_hours = get_trading_time()
    now = datetime.now(trading_hours.tz)
    
    if trading_hours.is_trading_time(now):
        return 0.0
    
    next_open = trading_hours.next_open(now)
    return (next_open - now).total_seconds()
