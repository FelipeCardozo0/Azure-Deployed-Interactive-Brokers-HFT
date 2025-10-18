"""Interactive Brokers error handling."""

from typing import Optional


class IBError(Exception):
    """Base exception for IB-related errors."""
    
    def __init__(self, message: str, code: Optional[int] = None, order_id: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.order_id = order_id


class IBConnectionError(IBError):
    """Connection-related errors."""
    pass


class IBTimeoutError(IBError):
    """Timeout-related errors."""
    pass


class IBOrderError(IBError):
    """Order-related errors."""
    pass


class IBRejectError(IBOrderError):
    """Order rejection errors."""
    
    def __init__(self, message: str, code: int, order_id: str, reason: str):
        super().__init__(message, code, order_id)
        self.reason = reason


class IBPacingError(IBError):
    """Pacing violation errors."""
    
    def __init__(self, message: str, retry_after: float):
        super().__init__(message)
        self.retry_after = retry_after


class IBDataError(IBError):
    """Market data errors."""
    pass


class IBAccountError(IBError):
    """Account-related errors."""
    pass


def handle_ib_error(error_code: int, error_message: str, order_id: Optional[str] = None) -> IBError:
    """Convert IB error codes to appropriate exception types."""
    
    # Connection errors
    if error_code in (1100, 1101, 1102):
        return IBConnectionError(f"Connection error {error_code}: {error_message}", error_code, order_id)
    
    # Timeout errors
    if error_code in (110, 111, 112):
        return IBTimeoutError(f"Timeout error {error_code}: {error_message}", error_code, order_id)
    
    # Order errors
    if error_code in (10182, 10187, 10188, 10189):
        return IBOrderError(f"Order error {error_code}: {error_message}", error_code, order_id)
    
    # Reject errors
    if error_code in (201, 202, 203, 204, 205):
        return IBRejectError(f"Order rejected {error_code}: {error_message}", error_code, order_id, error_message)
    
    # Pacing errors
    if error_code == 162:
        return IBPacingError(f"Pacing violation {error_code}: {error_message}", 1.0)
    
    # Data errors
    if error_code in (162, 200, 300, 301, 302):
        return IBDataError(f"Data error {error_code}: {error_message}", error_code, order_id)
    
    # Account errors
    if error_code in (2103, 2104, 2105, 2106):
        return IBAccountError(f"Account error {error_code}: {error_message}", error_code, order_id)
    
    # Generic error
    return IBError(f"IB error {error_code}: {error_message}", error_code, order_id)


def is_retryable_error(error: IBError) -> bool:
    """Check if error is retryable."""
    if isinstance(error, (IBConnectionError, IBTimeoutError)):
        return True
    if isinstance(error, IBPacingError):
        return True
    if isinstance(error, IBOrderError) and error.code in (10182, 10187):
        return True
    return False


def get_retry_delay(error: IBError, attempt: int) -> float:
    """Get retry delay for error."""
    if isinstance(error, IBPacingError):
        return error.retry_after
    if isinstance(error, IBConnectionError):
        return min(2.0 ** attempt, 30.0)  # Exponential backoff, max 30s
    if isinstance(error, IBTimeoutError):
        return min(1.0 * attempt, 10.0)  # Linear backoff, max 10s
    return 1.0  # Default 1 second
