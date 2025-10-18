"""ID generation utilities."""

import uuid
import time
from typing import Optional


def generate_correlation_id() -> str:
    """Generate a unique correlation ID for request tracing."""
    return str(uuid.uuid4())


def generate_order_id() -> str:
    """Generate a unique order ID."""
    return str(uuid.uuid4())


def generate_fill_id() -> str:
    """Generate a unique fill ID."""
    return str(uuid.uuid4())


def generate_position_id() -> str:
    """Generate a unique position ID."""
    return str(uuid.uuid4())


def generate_risk_event_id() -> str:
    """Generate a unique risk event ID."""
    return str(uuid.uuid4())


def generate_timestamp_id() -> str:
    """Generate a timestamp-based ID for ordering."""
    return str(int(time.time() * 1000000))  # Microsecond precision


def parse_correlation_id(correlation_id: str) -> Optional[str]:
    """Parse and validate correlation ID."""
    try:
        uuid.UUID(correlation_id)
        return correlation_id
    except (ValueError, TypeError):
        return None


def is_valid_uuid(uuid_string: str) -> bool:
    """Check if string is a valid UUID."""
    try:
        uuid.UUID(uuid_string)
        return True
    except (ValueError, TypeError):
        return False


def create_order_reference(symbol: str, side: str, timestamp: Optional[float] = None) -> str:
    """Create a human-readable order reference."""
    if timestamp is None:
        timestamp = time.time()
    
    ts_str = str(int(timestamp * 1000))[-8:]  # Last 8 digits of millisecond timestamp
    return f"{symbol}_{side}_{ts_str}"


def create_fill_reference(order_id: str, fill_number: int) -> str:
    """Create a fill reference from order ID and fill number."""
    return f"{order_id}_F{fill_number:03d}"


def create_position_reference(symbol: str, account: str) -> str:
    """Create a position reference."""
    return f"{symbol}_{account}"


def extract_symbol_from_reference(ref: str) -> Optional[str]:
    """Extract symbol from order reference."""
    try:
        return ref.split("_")[0]
    except (IndexError, AttributeError):
        return None


def extract_side_from_reference(ref: str) -> Optional[str]:
    """Extract side from order reference."""
    try:
        parts = ref.split("_")
        if len(parts) >= 2:
            return parts[1]
    except (IndexError, AttributeError):
        pass
    return None
