"""Configuration management using pydantic-settings."""

from typing import List, Optional
from pydantic import Field, validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with validation."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Interactive Brokers Configuration
    ib_host: str = Field(default="localhost", description="IB Gateway host")
    ib_port: int = Field(default=7497, description="IB Gateway port")
    ib_client_id: int = Field(default=1, description="IB client ID")
    ib_account: str = Field(description="IB account number")
    ib_paper: bool = Field(default=True, description="Use paper trading")
    
    # Trading Configuration
    symbols: List[str] = Field(default_factory=lambda: ["SPY"], description="Trading symbols")
    environment: str = Field(default="paper", description="Environment: backtest|paper|shadow-live|live")
    trading_hours_start: str = Field(default="09:30", description="Trading hours start")
    trading_hours_end: str = Field(default="16:00", description="Trading hours end")
    timezone: str = Field(default="America/New_York", description="Trading timezone")
    
    # Risk Management
    max_notional: float = Field(default=1000000.0, description="Maximum notional per order")
    max_qty: int = Field(default=1000, description="Maximum quantity per order")
    price_band_bps: int = Field(default=50, description="Price band in basis points")
    orders_per_sec: int = Field(default=10, description="Maximum orders per second")
    drawdown_limit: float = Field(default=0.05, description="Maximum drawdown limit")
    max_open_orders: int = Field(default=50, description="Maximum open orders")
    
    # Database Configuration
    postgres_dsn: str = Field(description="PostgreSQL connection string")
    redis_url: str = Field(default="redis://localhost:6379/0", description="Redis connection URL")
    kafka_brokers: str = Field(default="localhost:9092", description="Kafka brokers")
    
    # Azure Configuration
    azure_tenant_id: Optional[str] = Field(default=None, description="Azure tenant ID")
    azure_client_id: Optional[str] = Field(default=None, description="Azure client ID")
    azure_client_secret: Optional[str] = Field(default=None, description="Azure client secret")
    key_vault_name: Optional[str] = Field(default=None, description="Azure Key Vault name")
    acr_name: Optional[str] = Field(default=None, description="Azure Container Registry name")
    
    # Monitoring
    app_insights_conn: Optional[str] = Field(default=None, description="Application Insights connection string")
    prometheus_port: int = Field(default=9090, description="Prometheus metrics port")
    grafana_url: Optional[str] = Field(default=None, description="Grafana URL")
    
    # Logging
    log_level: str = Field(default="INFO", description="Log level")
    log_format: str = Field(default="json", description="Log format")
    correlation_id_header: str = Field(default="X-Correlation-ID", description="Correlation ID header")
    
    # Feature Flags
    enable_kill_switch: bool = Field(default=True, description="Enable kill switch")
    enable_pre_trade_risk: bool = Field(default=True, description="Enable pre-trade risk checks")
    enable_throttling: bool = Field(default=True, description="Enable order throttling")
    enable_metrics: bool = Field(default=True, description="Enable metrics collection")
    enable_tracing: bool = Field(default=True, description="Enable distributed tracing")
    
    # Market Data
    md_buffer_size: int = Field(default=10000, description="Market data buffer size")
    md_batch_size: int = Field(default=100, description="Market data batch size")
    md_flush_interval: float = Field(default=1.0, description="Market data flush interval")
    
    # Order Management
    order_timeout: int = Field(default=30, description="Order timeout in seconds")
    order_retry_attempts: int = Field(default=3, description="Order retry attempts")
    order_retry_delay: float = Field(default=1.0, description="Order retry delay")
    
    # Strategy Configuration
    signal_threshold: float = Field(default=2.0, description="Signal threshold")
    lookback_period: int = Field(default=60, description="Lookback period in seconds")
    volatility_window: int = Field(default=20, description="Volatility window")
    momentum_window: int = Field(default=5, description="Momentum window")
    
    # Network Configuration
    connect_timeout: int = Field(default=10, description="Connection timeout")
    read_timeout: int = Field(default=30, description="Read timeout")
    max_reconnect_attempts: int = Field(default=5, description="Maximum reconnect attempts")
    reconnect_delay: float = Field(default=5.0, description="Reconnect delay")
    
    @validator("environment")
    def validate_environment(cls, v: str) -> str:
        """Validate environment setting."""
        allowed = {"backtest", "paper", "shadow-live", "live"}
        if v not in allowed:
            raise ValueError(f"Environment must be one of {allowed}")
        return v
    
    @validator("symbols")
    def validate_symbols(cls, v: List[str]) -> List[str]:
        """Validate trading symbols."""
        if not v:
            raise ValueError("At least one symbol must be specified")
        return [s.upper() for s in v]
    
    @validator("log_level")
    def validate_log_level(cls, v: str) -> str:
        """Validate log level."""
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in allowed:
            raise ValueError(f"Log level must be one of {allowed}")
        return v.upper()
    
    @validator("log_format")
    def validate_log_format(cls, v: str) -> str:
        """Validate log format."""
        allowed = {"json", "text"}
        if v not in allowed:
            raise ValueError(f"Log format must be one of {allowed}")
        return v


# Global settings instance
settings = Settings()
