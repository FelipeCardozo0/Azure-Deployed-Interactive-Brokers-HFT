"""Database models and schema definitions."""

from datetime import datetime
from typing import Optional, Dict, Any
from dataclasses import dataclass
from sqlalchemy import (
    create_engine, Column, String, Integer, Float, DateTime, 
    Text, JSON, BigInteger, Boolean, Index
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import sessionmaker
import uuid

Base = declarative_base()


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


@dataclass
class Order:
    """Order record."""
    id: str
    timestamp: datetime
    symbol: str
    side: str
    quantity: float
    price: Optional[float]
    order_type: str
    time_in_force: str
    status: str
    reason: Optional[str] = None
    idempotency_key: Optional[str] = None
    correlation_id: Optional[str] = None


@dataclass
class Fill:
    """Fill record."""
    order_id: str
    timestamp: datetime
    quantity: float
    price: float
    venue: str = "IBKR"
    fee: float = 0.0
    fill_id: Optional[str] = None


@dataclass
class Position:
    """Position record."""
    symbol: str
    timestamp: datetime
    quantity: float
    vwap: float
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0


@dataclass
class PnL:
    """PnL record."""
    timestamp: datetime
    realized: float
    unrealized: float
    fees: float
    total: float


@dataclass
class Metric:
    """Metric record."""
    timestamp: datetime
    name: str
    value: float
    tags: Dict[str, Any]
    symbol: Optional[str] = None


# SQLAlchemy Models
class TickModel(Base):
    """Tick database model."""
    __tablename__ = "ticks"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    symbol = Column(String(20), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    bid = Column(Float)
    ask = Column(Float)
    last = Column(Float)
    size = Column(Integer)
    volume = Column(BigInteger)
    
    __table_args__ = (
        Index('idx_ticks_symbol_timestamp', 'symbol', 'timestamp'),
    )


class BarModel(Base):
    """Bar database model."""
    __tablename__ = "bars_1s"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    symbol = Column(String(20), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(BigInteger, nullable=False)
    interval = Column(String(10), default="1s")
    
    __table_args__ = (
        Index('idx_bars_symbol_timestamp', 'symbol', 'timestamp'),
    )


class OrderModel(Base):
    """Order database model."""
    __tablename__ = "orders"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    side = Column(String(10), nullable=False)
    quantity = Column(Float, nullable=False)
    price = Column(Float)
    order_type = Column(String(20), nullable=False)
    time_in_force = Column(String(10), nullable=False)
    status = Column(String(20), nullable=False, index=True)
    reason = Column(Text)
    idempotency_key = Column(String(100), unique=True, index=True)
    correlation_id = Column(String(100), index=True)
    
    __table_args__ = (
        Index('idx_orders_symbol_timestamp', 'symbol', 'timestamp'),
        Index('idx_orders_status', 'status'),
    )


class FillModel(Base):
    """Fill database model."""
    __tablename__ = "fills"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    quantity = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    venue = Column(String(20), default="IBKR")
    fee = Column(Float, default=0.0)
    fill_id = Column(String(100), unique=True, index=True)
    
    __table_args__ = (
        Index('idx_fills_order_id', 'order_id'),
        Index('idx_fills_timestamp', 'timestamp'),
    )


class PositionModel(Base):
    """Position database model."""
    __tablename__ = "positions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    symbol = Column(String(20), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    quantity = Column(Float, nullable=False)
    vwap = Column(Float, nullable=False)
    unrealized_pnl = Column(Float, default=0.0)
    realized_pnl = Column(Float, default=0.0)
    
    __table_args__ = (
        Index('idx_positions_symbol_timestamp', 'symbol', 'timestamp'),
    )


class PnLModel(Base):
    """PnL database model."""
    __tablename__ = "pnl"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    realized = Column(Float, nullable=False)
    unrealized = Column(Float, nullable=False)
    fees = Column(Float, nullable=False)
    total = Column(Float, nullable=False)
    
    __table_args__ = (
        Index('idx_pnl_timestamp', 'timestamp'),
    )


class MetricModel(Base):
    """Metric database model."""
    __tablename__ = "metrics"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    name = Column(String(100), nullable=False, index=True)
    value = Column(Float, nullable=False)
    tags = Column(JSONB)
    symbol = Column(String(20), index=True)
    
    __table_args__ = (
        Index('idx_metrics_name_timestamp', 'name', 'timestamp'),
        Index('idx_metrics_symbol_timestamp', 'symbol', 'timestamp'),
    )


def create_tables(engine):
    """Create all database tables."""
    Base.metadata.create_all(engine)


def drop_tables(engine):
    """Drop all database tables."""
    Base.metadata.drop_all(engine)


# TimescaleDB specific functions
def create_hypertables(engine):
    """Create TimescaleDB hypertables for time-series data."""
    with engine.connect() as conn:
        # Create hypertables for time-series tables
        conn.execute("""
            SELECT create_hypertable('ticks', 'timestamp', 
                chunk_time_interval => INTERVAL '1 day',
                if_not_exists => TRUE);
        """)
        
        conn.execute("""
            SELECT create_hypertable('bars_1s', 'timestamp',
                chunk_time_interval => INTERVAL '1 day', 
                if_not_exists => TRUE);
        """)
        
        conn.execute("""
            SELECT create_hypertable('orders', 'timestamp',
                chunk_time_interval => INTERVAL '1 day',
                if_not_exists => TRUE);
        """)
        
        conn.execute("""
            SELECT create_hypertable('fills', 'timestamp',
                chunk_time_interval => INTERVAL '1 day',
                if_not_exists => TRUE);
        """)
        
        conn.execute("""
            SELECT create_hypertable('positions', 'timestamp',
                chunk_time_interval => INTERVAL '1 day',
                if_not_exists => TRUE);
        """)
        
        conn.execute("""
            SELECT create_hypertable('pnl', 'timestamp',
                chunk_time_interval => INTERVAL '1 day',
                if_not_exists => TRUE);
        """)
        
        conn.execute("""
            SELECT create_hypertable('metrics', 'timestamp',
                chunk_time_interval => INTERVAL '1 day',
                if_not_exists => TRUE);
        """)
        
        conn.commit()


def create_compression_policies(engine):
    """Create compression policies for TimescaleDB."""
    with engine.connect() as conn:
        # Compress data older than 7 days
        conn.execute("""
            SELECT add_compression_policy('ticks', INTERVAL '7 days');
        """)
        
        conn.execute("""
            SELECT add_compression_policy('bars_1s', INTERVAL '7 days');
        """)
        
        conn.execute("""
            SELECT add_compression_policy('orders', INTERVAL '7 days');
        """)
        
        conn.execute("""
            SELECT add_compression_policy('fills', INTERVAL '7 days');
        """)
        
        conn.execute("""
            SELECT add_compression_policy('positions', INTERVAL '7 days');
        """)
        
        conn.execute("""
            SELECT add_compression_policy('pnl', INTERVAL '7 days');
        """)
        
        conn.execute("""
            SELECT add_compression_policy('metrics', INTERVAL '7 days');
        """)
        
        conn.commit()


def create_retention_policies(engine):
    """Create retention policies for TimescaleDB."""
    with engine.connect() as conn:
        # Keep data for 1 year
        conn.execute("""
            SELECT add_retention_policy('ticks', INTERVAL '1 year');
        """)
        
        conn.execute("""
            SELECT add_retention_policy('bars_1s', INTERVAL '1 year');
        """)
        
        conn.execute("""
            SELECT add_retention_policy('orders', INTERVAL '1 year');
        """)
        
        conn.execute("""
            SELECT add_retention_policy('fills', INTERVAL '1 year');
        """)
        
        conn.execute("""
            SELECT add_retention_policy('positions', INTERVAL '1 year');
        """)
        
        conn.execute("""
            SELECT add_retention_policy('pnl', INTERVAL '1 year');
        """)
        
        conn.execute("""
            SELECT add_retention_policy('metrics', INTERVAL '1 year');
        """)
        
        conn.commit()
