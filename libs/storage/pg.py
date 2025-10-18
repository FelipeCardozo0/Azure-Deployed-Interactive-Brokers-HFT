"""PostgreSQL and TimescaleDB client."""

import asyncio
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import asyncpg
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from .models import (
    Tick, Bar, Order, Fill, Position, PnL, Metric,
    TickModel, BarModel, OrderModel, FillModel, 
    PositionModel, PnLModel, MetricModel,
    create_tables, create_hypertables, create_compression_policies, create_retention_policies
)
from ..common.log import get_logger
from ..common.config import settings


class PostgreSQLClient:
    """PostgreSQL client with connection pooling."""
    
    def __init__(self, dsn: str):
        self.dsn = dsn
        self.logger = get_logger(__name__)
        self.pool: Optional[asyncpg.Pool] = None
        self.engine = None
        self.Session = None
    
    async def connect(self) -> None:
        """Connect to PostgreSQL."""
        try:
            # Create asyncpg pool
            self.pool = await asyncpg.create_pool(
                self.dsn,
                min_size=5,
                max_size=20,
                command_timeout=30
            )
            
            # Create SQLAlchemy engine
            self.engine = create_engine(self.dsn.replace("postgresql://", "postgresql+psycopg://"))
            self.Session = sessionmaker(bind=self.engine)
            
            self.logger.info("Connected to PostgreSQL")
            
        except Exception as e:
            self.logger.error(f"Failed to connect to PostgreSQL: {e}")
            raise
    
    async def disconnect(self) -> None:
        """Disconnect from PostgreSQL."""
        if self.pool:
            await self.pool.close()
        if self.engine:
            self.engine.dispose()
        self.logger.info("Disconnected from PostgreSQL")
    
    async def execute(self, query: str, *args) -> List[Dict[str, Any]]:
        """Execute query and return results."""
        if not self.pool:
            raise RuntimeError("Not connected to database")
        
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *args)
            return [dict(row) for row in rows]
    
    async def execute_one(self, query: str, *args) -> Optional[Dict[str, Any]]:
        """Execute query and return single result."""
        if not self.pool:
            raise RuntimeError("Not connected to database")
        
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, *args)
            return dict(row) if row else None
    
    async def execute_many(self, query: str, args_list: List[tuple]) -> None:
        """Execute query with multiple parameter sets."""
        if not self.pool:
            raise RuntimeError("Not connected to database")
        
        async with self.pool.acquire() as conn:
            await conn.executemany(query, args_list)


class TimescaleClient(PostgreSQLClient):
    """TimescaleDB client with time-series optimizations."""
    
    async def connect(self) -> None:
        """Connect to TimescaleDB and set up time-series features."""
        await super().connect()
        
        try:
            # Create tables
            create_tables(self.engine)
            
            # Create hypertables
            create_hypertables(self.engine)
            
            # Create compression policies
            create_compression_policies(self.engine)
            
            # Create retention policies
            create_retention_policies(self.engine)
            
            self.logger.info("TimescaleDB setup completed")
            
        except Exception as e:
            self.logger.error(f"TimescaleDB setup failed: {e}")
            raise
    
    async def insert_ticks(self, ticks: List[Tick]) -> None:
        """Insert tick data in batch."""
        if not ticks:
            return
        
        query = """
            INSERT INTO ticks (symbol, timestamp, bid, ask, last, size, volume)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
        """
        
        data = [
            (
                tick.symbol,
                tick.timestamp,
                tick.bid,
                tick.ask,
                tick.last,
                tick.size,
                tick.volume
            )
            for tick in ticks
        ]
        
        await self.execute_many(query, data)
    
    async def insert_bars(self, bars: List[Bar]) -> None:
        """Insert bar data in batch."""
        if not bars:
            return
        
        query = """
            INSERT INTO bars_1s (symbol, timestamp, open, high, low, close, volume, interval)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        """
        
        data = [
            (
                bar.symbol,
                bar.timestamp,
                bar.open,
                bar.high,
                bar.low,
                bar.close,
                bar.volume,
                bar.interval
            )
            for bar in bars
        ]
        
        await self.execute_many(query, data)
    
    async def insert_order(self, order: Order) -> None:
        """Insert order record."""
        query = """
            INSERT INTO orders (id, timestamp, symbol, side, quantity, price, order_type, 
                               time_in_force, status, reason, idempotency_key, correlation_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
        """
        
        await self.execute(
            query,
            order.id,
            order.timestamp,
            order.symbol,
            order.side,
            order.quantity,
            order.price,
            order.order_type,
            order.time_in_force,
            order.status,
            order.reason,
            order.idempotency_key,
            order.correlation_id
        )
    
    async def insert_fill(self, fill: Fill) -> None:
        """Insert fill record."""
        query = """
            INSERT INTO fills (order_id, timestamp, quantity, price, venue, fee, fill_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
        """
        
        await self.execute(
            query,
            fill.order_id,
            fill.timestamp,
            fill.quantity,
            fill.price,
            fill.venue,
            fill.fee,
            fill.fill_id
        )
    
    async def update_position(self, position: Position) -> None:
        """Update position record."""
        query = """
            INSERT INTO positions (symbol, timestamp, quantity, vwap, unrealized_pnl, realized_pnl)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (symbol, timestamp) DO UPDATE SET
                quantity = EXCLUDED.quantity,
                vwap = EXCLUDED.vwap,
                unrealized_pnl = EXCLUDED.unrealized_pnl,
                realized_pnl = EXCLUDED.realized_pnl
        """
        
        await self.execute(
            query,
            position.symbol,
            position.timestamp,
            position.quantity,
            position.vwap,
            position.unrealized_pnl,
            position.realized_pnl
        )
    
    async def insert_pnl(self, pnl: PnL) -> None:
        """Insert PnL record."""
        query = """
            INSERT INTO pnl (timestamp, realized, unrealized, fees, total)
            VALUES ($1, $2, $3, $4, $5)
        """
        
        await self.execute(
            query,
            pnl.timestamp,
            pnl.realized,
            pnl.unrealized,
            pnl.fees,
            pnl.total
        )
    
    async def insert_metric(self, metric: Metric) -> None:
        """Insert metric record."""
        query = """
            INSERT INTO metrics (timestamp, name, value, tags, symbol)
            VALUES ($1, $2, $3, $4, $5)
        """
        
        await self.execute(
            query,
            metric.timestamp,
            metric.name,
            metric.value,
            metric.tags,
            metric.symbol
        )
    
    async def get_latest_bars(self, symbol: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get latest bars for symbol."""
        query = """
            SELECT * FROM bars_1s 
            WHERE symbol = $1 
            ORDER BY timestamp DESC 
            LIMIT $2
        """
        
        return await self.execute(query, symbol, limit)
    
    async def get_latest_ticks(self, symbol: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get latest ticks for symbol."""
        query = """
            SELECT * FROM ticks 
            WHERE symbol = $1 
            ORDER BY timestamp DESC 
            LIMIT $2
        """
        
        return await self.execute(query, symbol, limit)
    
    async def get_positions(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get current positions."""
        if symbol:
            query = """
                SELECT * FROM positions 
                WHERE symbol = $1 
                ORDER BY timestamp DESC 
                LIMIT 1
            """
            return await self.execute(query, symbol)
        else:
            query = """
                SELECT DISTINCT ON (symbol) * FROM positions 
                ORDER BY symbol, timestamp DESC
            """
            return await self.execute(query)
    
    async def get_orders(self, symbol: Optional[str] = None, status: Optional[str] = None, 
                        start_time: Optional[datetime] = None, end_time: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Get orders with optional filters."""
        conditions = []
        params = []
        param_count = 0
        
        if symbol:
            param_count += 1
            conditions.append(f"symbol = ${param_count}")
            params.append(symbol)
        
        if status:
            param_count += 1
            conditions.append(f"status = ${param_count}")
            params.append(status)
        
        if start_time:
            param_count += 1
            conditions.append(f"timestamp >= ${param_count}")
            params.append(start_time)
        
        if end_time:
            param_count += 1
            conditions.append(f"timestamp <= ${param_count}")
            params.append(end_time)
        
        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
        
        query = f"""
            SELECT * FROM orders 
            {where_clause}
            ORDER BY timestamp DESC
        """
        
        return await self.execute(query, *params)
    
    async def get_fills(self, order_id: Optional[str] = None, 
                       start_time: Optional[datetime] = None, end_time: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Get fills with optional filters."""
        conditions = []
        params = []
        param_count = 0
        
        if order_id:
            param_count += 1
            conditions.append(f"order_id = ${param_count}")
            params.append(order_id)
        
        if start_time:
            param_count += 1
            conditions.append(f"timestamp >= ${param_count}")
            params.append(start_time)
        
        if end_time:
            param_count += 1
            conditions.append(f"timestamp <= ${param_count}")
            params.append(end_time)
        
        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
        
        query = f"""
            SELECT * FROM fills 
            {where_clause}
            ORDER BY timestamp DESC
        """
        
        return await self.execute(query, *params)
    
    async def get_pnl_summary(self, start_time: Optional[datetime] = None, end_time: Optional[datetime] = None) -> Dict[str, Any]:
        """Get PnL summary for time period."""
        conditions = []
        params = []
        param_count = 0
        
        if start_time:
            param_count += 1
            conditions.append(f"timestamp >= ${param_count}")
            params.append(start_time)
        
        if end_time:
            param_count += 1
            conditions.append(f"timestamp <= ${param_count}")
            params.append(end_time)
        
        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
        
        query = f"""
            SELECT 
                SUM(realized) as total_realized,
                AVG(unrealized) as avg_unrealized,
                SUM(fees) as total_fees,
                SUM(total) as total_pnl,
                COUNT(*) as record_count
            FROM pnl 
            {where_clause}
        """
        
        result = await self.execute_one(query, *params)
        return result or {}
    
    async def get_metrics(self, name: Optional[str] = None, symbol: Optional[str] = None,
                         start_time: Optional[datetime] = None, end_time: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Get metrics with optional filters."""
        conditions = []
        params = []
        param_count = 0
        
        if name:
            param_count += 1
            conditions.append(f"name = ${param_count}")
            params.append(name)
        
        if symbol:
            param_count += 1
            conditions.append(f"symbol = ${param_count}")
            params.append(symbol)
        
        if start_time:
            param_count += 1
            conditions.append(f"timestamp >= ${param_count}")
            params.append(start_time)
        
        if end_time:
            param_count += 1
            conditions.append(f"timestamp <= ${param_count}")
            params.append(end_time)
        
        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
        
        query = f"""
            SELECT * FROM metrics 
            {where_clause}
            ORDER BY timestamp DESC
        """
        
        return await self.execute(query, *params)
