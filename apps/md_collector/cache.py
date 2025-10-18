"""Market data caching and buffering."""

import asyncio
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import deque
import json
from ..common.log import get_logger


@dataclass
class Tick:
    """Market tick data."""
    symbol: str
    timestamp: datetime
    bid: Optional[float] = None
    ask: Optional[float] = None
    last: Optional[float] = None
    size: Optional[int] = None
    volume: Optional[int] = None


@dataclass
class Bar:
    """OHLCV bar data."""
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    interval: str = "1s"


class MarketDataCache:
    """Market data cache with buffering and aggregation."""
    
    def __init__(self, buffer_size: int = 10000, flush_interval: float = 1.0):
        self.buffer_size = buffer_size
        self.flush_interval = flush_interval
        self.logger = get_logger(__name__)
        
        # Tick buffers
        self.tick_buffers: Dict[str, deque] = {}
        self.bar_buffers: Dict[str, deque] = {}
        
        # Current bar data for aggregation
        self.current_bars: Dict[str, Dict[str, Any]] = {}
        
        # Last flush time
        self.last_flush = datetime.utcnow()
        
        # Statistics
        self.stats = {
            'ticks_received': 0,
            'bars_generated': 0,
            'cache_hits': 0,
            'cache_misses': 0
        }
    
    def add_tick(self, symbol: str, timestamp: datetime, bid: Optional[float] = None,
                 ask: Optional[float] = None, last: Optional[float] = None,
                 size: Optional[int] = None, volume: Optional[int] = None) -> None:
        """Add tick data to cache."""
        try:
            # Create tick
            tick = Tick(
                symbol=symbol,
                timestamp=timestamp,
                bid=bid,
                ask=ask,
                last=last,
                size=size,
                volume=volume
            )
            
            # Add to buffer
            if symbol not in self.tick_buffers:
                self.tick_buffers[symbol] = deque(maxlen=self.buffer_size)
            
            self.tick_buffers[symbol].append(tick)
            self.stats['ticks_received'] += 1
            
            # Update current bar
            self._update_current_bar(symbol, tick)
            
        except Exception as e:
            self.logger.error(f"Error adding tick for {symbol}: {e}")
    
    def add_bar(self, symbol: str, timestamp: datetime, open_price: float,
                high: float, low: float, close: float, volume: int,
                interval: str = "1s") -> None:
        """Add bar data to cache."""
        try:
            # Create bar
            bar = Bar(
                symbol=symbol,
                timestamp=timestamp,
                open=open_price,
                high=high,
                low=low,
                close=close,
                volume=volume,
                interval=interval
            )
            
            # Add to buffer
            if symbol not in self.bar_buffers:
                self.bar_buffers[symbol] = deque(maxlen=self.buffer_size)
            
            self.bar_buffers[symbol].append(bar)
            self.stats['bars_generated'] += 1
            
        except Exception as e:
            self.logger.error(f"Error adding bar for {symbol}: {e}")
    
    def _update_current_bar(self, symbol: str, tick: Tick) -> None:
        """Update current bar with tick data."""
        if symbol not in self.current_bars:
            self.current_bars[symbol] = {
                'open': None,
                'high': None,
                'low': None,
                'close': None,
                'volume': 0,
                'timestamp': tick.timestamp
            }
        
        bar = self.current_bars[symbol]
        
        # Use last price for OHLC
        price = tick.last
        if price is None:
            # Use mid price if last is not available
            if tick.bid is not None and tick.ask is not None:
                price = (tick.bid + tick.ask) / 2
            else:
                return  # No valid price
        
        # Update OHLC
        if bar['open'] is None:
            bar['open'] = price
        
        bar['high'] = max(bar['high'] or price, price)
        bar['low'] = min(bar['low'] or price, price)
        bar['close'] = price
        
        # Update volume
        if tick.volume is not None:
            bar['volume'] += tick.volume
        elif tick.size is not None:
            bar['volume'] += tick.size
    
    def get_ticks(self, symbol: str, limit: int = 100) -> List[Tick]:
        """Get recent ticks for symbol."""
        if symbol not in self.tick_buffers:
            return []
        
        ticks = list(self.tick_buffers[symbol])
        return ticks[-limit:] if limit else ticks
    
    def get_bars(self, symbol: str, limit: int = 100) -> List[Bar]:
        """Get recent bars for symbol."""
        if symbol not in self.bar_buffers:
            return []
        
        bars = list(self.bar_buffers[symbol])
        return bars[-limit:] if limit else bars
    
    def get_latest_tick(self, symbol: str) -> Optional[Tick]:
        """Get latest tick for symbol."""
        if symbol not in self.tick_buffers or not self.tick_buffers[symbol]:
            return None
        
        return self.tick_buffers[symbol][-1]
    
    def get_latest_bar(self, symbol: str) -> Optional[Bar]:
        """Get latest bar for symbol."""
        if symbol not in self.bar_buffers or not self.bar_buffers[symbol]:
            return None
        
        return self.bar_buffers[symbol][-1]
    
    def get_current_bar(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get current bar data for symbol."""
        return self.current_bars.get(symbol)
    
    def flush_bars(self) -> List[Bar]:
        """Flush current bars and return them."""
        bars_to_flush = []
        
        for symbol, bar_data in self.current_bars.items():
            if bar_data['open'] is not None:
                # Create bar from current data
                bar = Bar(
                    symbol=symbol,
                    timestamp=bar_data['timestamp'],
                    open=bar_data['open'],
                    high=bar_data['high'],
                    low=bar_data['low'],
                    close=bar_data['close'],
                    volume=bar_data['volume'],
                    interval="1s"
                )
                
                bars_to_flush.append(bar)
                
                # Add to bar buffer
                if symbol not in self.bar_buffers:
                    self.bar_buffers[symbol] = deque(maxlen=self.buffer_size)
                
                self.bar_buffers[symbol].append(bar)
                self.stats['bars_generated'] += 1
                
                # Reset current bar
                self.current_bars[symbol] = {
                    'open': None,
                    'high': None,
                    'low': None,
                    'close': None,
                    'volume': 0,
                    'timestamp': None
                }
        
        return bars_to_flush
    
    def should_flush(self) -> bool:
        """Check if buffers should be flushed."""
        now = datetime.utcnow()
        return (now - self.last_flush).total_seconds() >= self.flush_interval
    
    def mark_flushed(self) -> None:
        """Mark buffers as flushed."""
        self.last_flush = datetime.utcnow()
    
    def get_cache_status(self) -> Dict[str, Any]:
        """Get cache status and statistics."""
        return {
            'tick_buffers': {
                symbol: len(buffer) for symbol, buffer in self.tick_buffers.items()
            },
            'bar_buffers': {
                symbol: len(buffer) for symbol, buffer in self.bar_buffers.items()
            },
            'current_bars': {
                symbol: bar_data for symbol, bar_data in self.current_bars.items()
                if bar_data['open'] is not None
            },
            'stats': self.stats.copy(),
            'last_flush': self.last_flush.isoformat(),
            'flush_interval': self.flush_interval
        }
    
    def clear_old_data(self, cutoff_time: datetime) -> None:
        """Clear old data from buffers."""
        # Clear old ticks
        for symbol in list(self.tick_buffers.keys()):
            buffer = self.tick_buffers[symbol]
            while buffer and buffer[0].timestamp < cutoff_time:
                buffer.popleft()
            
            if not buffer:
                del self.tick_buffers[symbol]
        
        # Clear old bars
        for symbol in list(self.bar_buffers.keys()):
            buffer = self.bar_buffers[symbol]
            while buffer and buffer[0].timestamp < cutoff_time:
                buffer.popleft()
            
            if not buffer:
                del self.bar_buffers[symbol]
    
    def get_symbols(self) -> List[str]:
        """Get all symbols with data."""
        symbols = set()
        symbols.update(self.tick_buffers.keys())
        symbols.update(self.bar_buffers.keys())
        symbols.update(self.current_bars.keys())
        return list(symbols)
    
    def get_data_summary(self, symbol: str) -> Dict[str, Any]:
        """Get data summary for symbol."""
        tick_count = len(self.tick_buffers.get(symbol, []))
        bar_count = len(self.bar_buffers.get(symbol, []))
        current_bar = self.get_current_bar(symbol)
        
        latest_tick = self.get_latest_tick(symbol)
        latest_bar = self.get_latest_bar(symbol)
        
        return {
            'symbol': symbol,
            'tick_count': tick_count,
            'bar_count': bar_count,
            'has_current_bar': current_bar is not None,
            'latest_tick': {
                'timestamp': latest_tick.timestamp.isoformat() if latest_tick else None,
                'last': latest_tick.last if latest_tick else None,
                'bid': latest_tick.bid if latest_tick else None,
                'ask': latest_tick.ask if latest_tick else None
            } if latest_tick else None,
            'latest_bar': {
                'timestamp': latest_bar.timestamp.isoformat() if latest_bar else None,
                'open': latest_bar.open if latest_bar else None,
                'high': latest_bar.high if latest_bar else None,
                'low': latest_bar.low if latest_bar else None,
                'close': latest_bar.close if latest_bar else None,
                'volume': latest_bar.volume if latest_bar else None
            } if latest_bar else None
        }
