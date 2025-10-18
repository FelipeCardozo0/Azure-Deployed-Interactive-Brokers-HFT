"""TimescaleDB writer for market data."""

import asyncio
from typing import List, Dict, Optional, Any
from datetime import datetime
from dataclasses import dataclass
from ..common.log import get_logger
from ..storage import TimescaleClient
from .cache import Tick, Bar


@dataclass
class WriteBatch:
    """Batch of data to write."""
    ticks: List[Tick]
    bars: List[Bar]
    timestamp: datetime


class TimescaleWriter:
    """TimescaleDB writer for market data with batching."""
    
    def __init__(self, timescale: TimescaleClient, batch_size: int = 100, 
                 flush_interval: float = 1.0):
        self.timescale = timescale
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.logger = get_logger(__name__)
        
        # Batching
        self.pending_ticks: List[Tick] = []
        self.pending_bars: List[Bar] = []
        self.last_flush = datetime.utcnow()
        
        # Statistics
        self.stats = {
            'ticks_written': 0,
            'bars_written': 0,
            'write_errors': 0,
            'batch_count': 0
        }
    
    async def add_tick(self, tick: Tick) -> None:
        """Add tick to pending batch."""
        self.pending_ticks.append(tick)
        
        # Check if batch is full
        if len(self.pending_ticks) >= self.batch_size:
            await self.flush()
    
    async def add_bar(self, bar: Bar) -> None:
        """Add bar to pending batch."""
        self.pending_bars.append(bar)
        
        # Check if batch is full
        if len(self.pending_bars) >= self.batch_size:
            await self.flush()
    
    async def add_ticks(self, ticks: List[Tick]) -> None:
        """Add multiple ticks to pending batch."""
        self.pending_ticks.extend(ticks)
        
        # Check if batch is full
        if len(self.pending_ticks) >= self.batch_size:
            await self.flush()
    
    async def add_bars(self, bars: List[Bar]) -> None:
        """Add multiple bars to pending batch."""
        self.pending_bars.extend(bars)
        
        # Check if batch is full
        if len(self.pending_bars) >= self.batch_size:
            await self.flush()
    
    async def flush(self) -> None:
        """Flush pending data to TimescaleDB."""
        if not self.pending_ticks and not self.pending_bars:
            return
        
        try:
            # Write ticks
            if self.pending_ticks:
                await self._write_ticks(self.pending_ticks)
                self.stats['ticks_written'] += len(self.pending_ticks)
                self.pending_ticks.clear()
            
            # Write bars
            if self.pending_bars:
                await self._write_bars(self.pending_bars)
                self.stats['bars_written'] += len(self.pending_bars)
                self.pending_bars.clear()
            
            self.stats['batch_count'] += 1
            self.last_flush = datetime.utcnow()
            
            self.logger.debug(f"Flushed batch: {self.stats['ticks_written']} ticks, {self.stats['bars_written']} bars")
            
        except Exception as e:
            self.stats['write_errors'] += 1
            self.logger.error(f"Error flushing data: {e}")
            raise
    
    async def _write_ticks(self, ticks: List[Tick]) -> None:
        """Write ticks to TimescaleDB."""
        try:
            from ..storage.models import Tick as TickModel
            
            # Convert to database models
            tick_models = []
            for tick in ticks:
                tick_model = TickModel(
                    symbol=tick.symbol,
                    timestamp=tick.timestamp,
                    bid=tick.bid,
                    ask=tick.ask,
                    last=tick.last,
                    size=tick.size,
                    volume=tick.volume
                )
                tick_models.append(tick_model)
            
            # Write to database
            await self.timescale.insert_ticks(tick_models)
            
        except Exception as e:
            self.logger.error(f"Error writing ticks: {e}")
            raise
    
    async def _write_bars(self, bars: List[Bar]) -> None:
        """Write bars to TimescaleDB."""
        try:
            from ..storage.models import Bar as BarModel
            
            # Convert to database models
            bar_models = []
            for bar in bars:
                bar_model = BarModel(
                    symbol=bar.symbol,
                    timestamp=bar.timestamp,
                    open=bar.open,
                    high=bar.high,
                    low=bar.low,
                    close=bar.close,
                    volume=bar.volume,
                    interval=bar.interval
                )
                bar_models.append(bar_model)
            
            # Write to database
            await self.timescale.insert_bars(bar_models)
            
        except Exception as e:
            self.logger.error(f"Error writing bars: {e}")
            raise
    
    def should_flush(self) -> bool:
        """Check if data should be flushed."""
        now = datetime.utcnow()
        time_elapsed = (now - self.last_flush).total_seconds()
        
        return (time_elapsed >= self.flush_interval or 
                len(self.pending_ticks) >= self.batch_size or
                len(self.pending_bars) >= self.batch_size)
    
    async def force_flush(self) -> None:
        """Force flush all pending data."""
        await self.flush()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get writer statistics."""
        return {
            'pending_ticks': len(self.pending_ticks),
            'pending_bars': len(self.pending_bars),
            'stats': self.stats.copy(),
            'last_flush': self.last_flush.isoformat(),
            'batch_size': self.batch_size,
            'flush_interval': self.flush_interval
        }
    
    async def start_background_flush(self) -> None:
        """Start background flush task."""
        while True:
            try:
                if self.should_flush():
                    await self.flush()
                
                await asyncio.sleep(0.1)  # Check every 100ms
                
            except Exception as e:
                self.logger.error(f"Error in background flush: {e}")
                await asyncio.sleep(1)
    
    async def write_historical_data(self, symbol: str, start_time: datetime, 
                                   end_time: datetime) -> None:
        """Write historical data for symbol."""
        try:
            # Get historical data from TimescaleDB
            # This would implement actual historical data retrieval
            self.logger.info(f"Writing historical data for {symbol} from {start_time} to {end_time}")
            
        except Exception as e:
            self.logger.error(f"Error writing historical data: {e}")
            raise
    
    async def get_data_summary(self, symbol: str, start_time: Optional[datetime] = None,
                              end_time: Optional[datetime] = None) -> Dict[str, Any]:
        """Get data summary for symbol."""
        try:
            if start_time is None:
                start_time = datetime.utcnow() - timedelta(hours=1)
            if end_time is None:
                end_time = datetime.utcnow()
            
            # Get tick count
            tick_query = """
                SELECT COUNT(*) as tick_count 
                FROM ticks 
                WHERE symbol = $1 AND timestamp BETWEEN $2 AND $3
            """
            tick_result = await self.timescale.execute_one(tick_query, symbol, start_time, end_time)
            tick_count = tick_result['tick_count'] if tick_result else 0
            
            # Get bar count
            bar_query = """
                SELECT COUNT(*) as bar_count 
                FROM bars_1s 
                WHERE symbol = $1 AND timestamp BETWEEN $2 AND $3
            """
            bar_result = await self.timescale.execute_one(bar_query, symbol, start_time, end_time)
            bar_count = bar_result['bar_count'] if bar_result else 0
            
            return {
                'symbol': symbol,
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat(),
                'tick_count': tick_count,
                'bar_count': bar_count,
                'data_availability': tick_count > 0 or bar_count > 0
            }
            
        except Exception as e:
            self.logger.error(f"Error getting data summary: {e}")
            return {}
    
    async def cleanup_old_data(self, cutoff_time: datetime) -> None:
        """Clean up old data from database."""
        try:
            # Delete old ticks
            tick_query = "DELETE FROM ticks WHERE timestamp < $1"
            await self.timescale.execute(tick_query, cutoff_time)
            
            # Delete old bars
            bar_query = "DELETE FROM bars_1s WHERE timestamp < $1"
            await self.timescale.execute(bar_query, cutoff_time)
            
            self.logger.info(f"Cleaned up data older than {cutoff_time}")
            
        except Exception as e:
            self.logger.error(f"Error cleaning up old data: {e}")
            raise
