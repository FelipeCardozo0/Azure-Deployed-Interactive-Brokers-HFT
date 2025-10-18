"""Structured logging with correlation IDs."""

import json
import logging
import sys
from typing import Any, Dict, Optional
from contextvars import ContextVar
from pythonjsonlogger import jsonlogger

# Context variable for correlation ID
correlation_id: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)


class CorrelationFilter(logging.Filter):
    """Filter to add correlation ID to log records."""
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Add correlation ID to log record."""
        record.correlation_id = correlation_id.get()
        return True


class TradingFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter for trading logs."""
    
    def add_fields(self, log_record: Dict[str, Any], record: logging.LogRecord, message_dict: Dict[str, Any]) -> None:
        """Add custom fields to log record."""
        super().add_fields(log_record, record, message_dict)
        
        # Add correlation ID if available
        if hasattr(record, "correlation_id") and record.correlation_id:
            log_record["correlation_id"] = record.correlation_id
        
        # Add order ID if available
        if hasattr(record, "order_id") and record.order_id:
            log_record["order_id"] = record.order_id
        
        # Add symbol if available
        if hasattr(record, "symbol") and record.symbol:
            log_record["symbol"] = record.symbol
        
        # Add timestamp in ISO format
        log_record["timestamp"] = record.created
        log_record["level"] = record.levelname
        log_record["logger"] = record.name


def get_logger(name: str, level: str = "INFO") -> logging.Logger:
    """Get a configured logger instance."""
    logger = logging.getLogger(name)
    
    # Avoid duplicate handlers
    if logger.handlers:
        return logger
    
    logger.setLevel(getattr(logging, level.upper()))
    
    # Create console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(getattr(logging, level.upper()))
    
    # Add correlation filter
    handler.addFilter(CorrelationFilter())
    
    # Set formatter based on format preference
    from .config import settings
    
    if settings.log_format == "json":
        formatter = TradingFormatter(
            fmt="%(timestamp)s %(level)s %(logger)s %(message)s %(correlation_id)s %(order_id)s %(symbol)s"
        )
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
    
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    return logger


def set_correlation_id(cid: str) -> None:
    """Set correlation ID for current context."""
    correlation_id.set(cid)


def get_correlation_id() -> Optional[str]:
    """Get current correlation ID."""
    return correlation_id.get()


def log_order(logger: logging.Logger, order_id: str, symbol: str, side: str, qty: float, price: float, **kwargs: Any) -> None:
    """Log order information with structured data."""
    logger.info(
        f"Order {side} {qty} {symbol} @ {price}",
        extra={
            "order_id": order_id,
            "symbol": symbol,
            "side": side,
            "qty": qty,
            "price": price,
            **kwargs
        }
    )


def log_fill(logger: logging.Logger, order_id: str, symbol: str, qty: float, price: float, venue: str = "IBKR", **kwargs: Any) -> None:
    """Log fill information with structured data."""
    logger.info(
        f"Fill {qty} {symbol} @ {price} on {venue}",
        extra={
            "order_id": order_id,
            "symbol": symbol,
            "qty": qty,
            "price": price,
            "venue": venue,
            **kwargs
        }
    )


def log_risk_event(logger: logging.Logger, event_type: str, symbol: str, reason: str, **kwargs: Any) -> None:
    """Log risk management events."""
    logger.warning(
        f"Risk event: {event_type} for {symbol} - {reason}",
        extra={
            "event_type": event_type,
            "symbol": symbol,
            "reason": reason,
            **kwargs
        }
    )


def log_system_event(logger: logging.Logger, event_type: str, message: str, **kwargs: Any) -> None:
    """Log system events."""
    logger.info(
        f"System event: {event_type} - {message}",
        extra={
            "event_type": event_type,
            "message": message,
            **kwargs
        }
    )
