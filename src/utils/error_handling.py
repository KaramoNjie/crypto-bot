"""
Error Handling Utilities

This module provides comprehensive error handling utilities for the crypto trading bot,
including custom exceptions, standardized error responses, retry logic, and validation.
"""

import logging
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from functools import wraps
from typing import Any, Dict, Optional, Callable, TypeVar

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


class TradingBotException(Exception):
    """Base exception for trading bot errors"""

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code or "UNKNOWN_ERROR"
        self.details = details or {}
        self.timestamp = datetime.utcnow()


class BinanceAPIError(TradingBotException):
    """Exception for Binance API errors"""

    pass


class NewsAPIError(TradingBotException):
    """Exception for News API errors"""

    pass


class DatabaseError(TradingBotException):
    """Exception for database errors"""

    pass


class ValidationError(TradingBotException):
    """Exception for validation errors"""

    pass


class ConfigurationError(TradingBotException):
    """Exception for configuration errors"""

    pass


class NetworkError(TradingBotException):
    """Exception for network-related errors"""

    pass


class RateLimitError(TradingBotException):
    """Exception for rate limiting errors"""

    pass


class InsufficientFundsError(TradingBotException):
    """Exception for insufficient funds errors"""

    pass


class ErrorSeverity(Enum):
    """Error severity levels"""

    INFO = "info"
    WARNING = "warning"
    MEDIUM = "medium"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ErrorContext:
    """Error context information for better debugging"""

    component: str
    operation: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    additional_data: Optional[Dict[str, Any]] = None


class CircuitBreakerState(Enum):
    """Circuit breaker states"""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Circuit breaker pattern implementation"""

    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitBreakerState.CLOSED

    def call(self, func: Callable, *args, **kwargs) -> None:
        """Execute function with circuit breaker protection"""
        if self.state == CircuitBreakerState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitBreakerState.HALF_OPEN
            else:
                raise TradingBotException(
                    "Circuit breaker is OPEN", "CIRCUIT_BREAKER_OPEN"
                )

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise

    def _should_attempt_reset(self) -> bool:
        """Check if circuit breaker should attempt reset"""
        return (
            self.last_failure_time
            and time.time() - self.last_failure_time >= self.recovery_timeout
        )

    def _on_success(self):
        """Handle successful execution"""
        self.failure_count = 0
        self.state = CircuitBreakerState.CLOSED

    def _on_failure(self):
        """Handle failed execution"""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = CircuitBreakerState.OPEN


class ErrorTracker:
    """Track and aggregate errors for monitoring"""

    def __init__(self) -> None:
        self.error_counts = {}
        self.error_history = []
        self.max_history = 1000

    def track_error(
        self, error: TradingBotException, context: Optional[ErrorContext] = None
    ):
        """Track an error occurrence"""
        error_key = f"{error.__class__.__name__}:{error.error_code}"

        # Update error counts
        self.error_counts[error_key] = self.error_counts.get(error_key, 0) + 1

        # Add to history
        error_record = {
            "timestamp": error.timestamp,
            "error_type": error.__class__.__name__,
            "error_code": error.error_code,
            "message": error.message,
            "context": context.__dict__ if context else None,
        }

        self.error_history.append(error_record)

        # Trim history if too long
        if len(self.error_history) > self.max_history:
            self.error_history = self.error_history[-self.max_history :]

    def get_error_rate(self, error_type: str, time_window_minutes: int = 5) -> float:
        """Get error rate for specific error type"""
        cutoff_time = datetime.utcnow().timestamp() - (time_window_minutes * 60)

        recent_errors = [
            e
            for e in self.error_history
            if e["timestamp"].timestamp() > cutoff_time
            and e["error_type"] == error_type
        ]

        return len(recent_errors) / time_window_minutes

    def get_error_summary(self) -> Dict[str, Any]:
        """Get summary of error statistics"""
        total_errors = len(self.error_history)

        if total_errors == 0:
            return {"total_errors": 0, "error_types": {}, "recent_errors": []}

        error_types = {}
        for error_code, count in self.error_counts.items():
            error_types[error_code] = {
                "count": count,
                "percentage": (count / total_errors) * 100,
            }

        recent_errors = self.error_history[-10:] if self.error_history else []

        return {
            "total_errors": total_errors,
            "error_types": error_types,
            "recent_errors": recent_errors,
        }


class ErrorRecoveryStrategy:
    """Base class for error recovery strategies"""

    def can_recover(self, error: Exception) -> bool:
        """Check if error can be recovered from"""
        return False

    def recover(self, error: Exception, context: Optional[ErrorContext] = None) -> Any:
        """Attempt to recover from error"""
        raise NotImplementedError


class RetryStrategy(ErrorRecoveryStrategy):
    """Retry-based error recovery"""

    def __init__(
        self, max_attempts: int = 3, delay: float = 1.0, backoff_multiplier: float = 2.0
    ) -> None:
        self.max_attempts = max_attempts
        self.delay = delay
        self.backoff_multiplier = backoff_multiplier

    def can_recover(self, error: Exception) -> bool:
        """Check if error is retryable"""
        retryable_errors = (NetworkError, RateLimitError, BinanceAPIError)
        return isinstance(error, retryable_errors)

    def execute_with_retry(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with retry logic"""
        last_exception = None
        current_delay = self.delay

        for attempt in range(self.max_attempts):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e

                if not self.can_recover(e) or attempt == self.max_attempts - 1:
                    raise

                logger.warning(
                    f"Attempt {attempt + 1} failed: {e}. Retrying in {current_delay}s..."
                )
                time.sleep(current_delay)
                current_delay *= self.backoff_multiplier

        raise last_exception


class FallbackStrategy(ErrorRecoveryStrategy):
    """Fallback-based error recovery"""

    def __init__(self, fallback_func: Callable) -> None:
        self.fallback_func = fallback_func

    def can_recover(self, error: Exception) -> bool:
        """Fallback can handle any error"""
        return True

    def recover(self, error: Exception, context: Optional[ErrorContext] = None) -> Any:
        """Execute fallback function"""
        logger.warning(f"Using fallback for error: {error}")
        return self.fallback_func()


class ErrorMessageTranslator:
    """Translate technical errors to user-friendly messages"""

    ERROR_MESSAGES = {
        "BINANCE_API_ERROR": {
            "user_message": "Trading service temporarily unavailable. Please try again later.",
            "suggestions": [
                "Check your internet connection",
                "Verify API credentials",
                "Try again in a few minutes",
            ],
        },
        "DATABASE_ERROR": {
            "user_message": "Data service temporarily unavailable.",
            "suggestions": ["Please refresh the page", "Try again in a few moments"],
        },
        "NETWORK_ERROR": {
            "user_message": "Network connection issue detected.",
            "suggestions": [
                "Check your internet connection",
                "Try again when connection is stable",
            ],
        },
        "RATE_LIMIT_ERROR": {
            "user_message": "Too many requests. Please wait a moment before trying again.",
            "suggestions": [
                "Wait 30 seconds before retrying",
                "Reduce trading frequency",
            ],
        },
        "INSUFFICIENT_FUNDS_ERROR": {
            "user_message": "Insufficient balance to complete this operation.",
            "suggestions": [
                "Check your account balance",
                "Reduce order size",
                "Deposit additional funds",
            ],
        },
        "VALIDATION_ERROR": {
            "user_message": "Invalid input provided.",
            "suggestions": [
                "Check your input values",
                "Ensure all required fields are filled",
            ],
        },
    }

    @classmethod
    def get_user_message(cls, error_code: str, default: str = None) -> Dict[str, Any]:
        """Get user-friendly error message"""
        message_info = cls.ERROR_MESSAGES.get(
            error_code,
            {
                "user_message": default or "An unexpected error occurred.",
                "suggestions": [
                    "Please try again or contact support if the issue persists"
                ],
            },
        )
        return message_info


class ErrorHandler:
    """Comprehensive error handler with recovery strategies"""

    def __init__(self) -> None:
        self.error_tracker = ErrorTracker()
        self.circuit_breakers = {}
        self.recovery_strategies = {
            "retry": RetryStrategy(),
            "fallback": None,  # Set per use case
        }

    def handle_error(
        self,
        error: Exception,
        context: Optional[ErrorContext] = None,
        recovery_strategy: str = "retry",
        fallback_func: Optional[Callable] = None,
    ) -> Any:
        """Handle error with specified recovery strategy"""

        # Convert to TradingBotException if needed
        if not isinstance(error, TradingBotException):
            trading_error = TradingBotException(str(error), "UNKNOWN_ERROR")
        else:
            trading_error = error

        # Track the error
        self.error_tracker.track_error(trading_error, context)

        # Log error with context
        self._log_error(trading_error, context)

        # Apply recovery strategy
        if recovery_strategy == "retry":
            strategy = self.recovery_strategies["retry"]
        elif recovery_strategy == "fallback" and fallback_func:
            strategy = FallbackStrategy(fallback_func)
        else:
            # No recovery - re-raise
            raise trading_error

        if strategy.can_recover(trading_error):
            return strategy.recover(trading_error, context)
        else:
            raise trading_error

    def _log_error(self, error: TradingBotException, context: Optional[ErrorContext]):
        """Log error with appropriate level"""
        severity_map = {
            ErrorSeverity.INFO: logger.info,
            ErrorSeverity.WARNING: logger.warning,
            ErrorSeverity.ERROR: logger.error,
            ErrorSeverity.CRITICAL: logger.critical,
        }

        # Determine severity based on error type
        if isinstance(error, (ValidationError, ConfigurationError)):
            severity = ErrorSeverity.WARNING
        elif isinstance(error, (NetworkError, RateLimitError)):
            severity = ErrorSeverity.ERROR
        else:
            severity = ErrorSeverity.CRITICAL

        log_func = severity_map.get(severity, logger.error)

        log_message = f"[{error.error_code}] {error.message}"
        if context:
            log_message += (
                f" | Component: {context.component} | Operation: {context.operation}"
            )

        log_func(log_message)

    def get_circuit_breaker(self, service: str) -> CircuitBreaker:
        """Get or create circuit breaker for service"""
        if service not in self.circuit_breakers:
            self.circuit_breakers[service] = CircuitBreaker()
        return self.circuit_breakers[service]

    def with_circuit_breaker(self, service: str):
        """Decorator to apply circuit breaker to function"""

        def decorator(func: F) -> F:
            @wraps(func)
            def wrapper(*args, **kwargs) -> None:
                breaker = self.get_circuit_breaker(service)
                return breaker.call(func, *args, **kwargs)

            return wrapper

        return decorator

    def graceful_degradation(
        self, primary_func: Callable, fallback_func: Callable, **kwargs
    ):
        """Execute function with graceful degradation"""
        try:
            return primary_func(**kwargs)
        except Exception as e:
            logger.warning(f"Primary function failed: {e}. Using fallback.")
            return fallback_func(**kwargs)

    def get_health_status(self) -> Dict[str, Any]:
        """Get system health status based on error patterns"""
        error_summary = self.error_tracker.get_error_summary()

        # Determine health status
        if error_summary["total_errors"] == 0:
            health = "healthy"
        elif error_summary["total_errors"] < 10:
            health = "degraded"
        else:
            health = "unhealthy"

        # Check circuit breakers
        circuit_breaker_status = {}
        for service, breaker in self.circuit_breakers.items():
            circuit_breaker_status[service] = breaker.state.value

        return {
            "health": health,
            "error_summary": error_summary,
            "circuit_breakers": circuit_breaker_status,
            "timestamp": datetime.utcnow().isoformat(),
        }


# Global error handler instance
error_handler = ErrorHandler()


# Convenience decorators
def with_error_handling(
    recovery_strategy: str = "retry",
    fallback_func: Optional[Callable] = None,
    component: str = "unknown",
    operation: str = "unknown",
):
    """Decorator for automatic error handling"""

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args, **kwargs) -> None:
            context = ErrorContext(
                component=component,
                operation=operation,
                additional_data={"args": str(args)[:100], "kwargs": str(kwargs)[:100]},
            )

            try:
                return func(*args, **kwargs)
            except Exception as e:
                return error_handler.handle_error(
                    e, context, recovery_strategy, fallback_func
                )

        return wrapper

    return decorator


def circuit_breaker(service: str):
    """Decorator to apply circuit breaker pattern"""
    return error_handler.with_circuit_breaker(service)


class APIRateLimitError(TradingBotException):
    """Exception for API rate limit errors"""

    pass


class ConfigurationError(TradingBotException):
    """Exception for configuration errors"""

    pass


class ErrorSeverity(Enum):
    """Error severity levels"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ErrorResponse:
    """Standardized error response structure"""

    success: bool
    error_code: str
    message: str
    details: Dict[str, Any]
    timestamp: datetime
    severity: ErrorSeverity

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "success": self.success,
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
            "severity": self.severity.value,
        }


@dataclass
class RetryConfig:
    """Configuration for retry logic"""

    max_attempts: int = 3
    backoff_multiplier: float = 1.0
    max_backoff: float = 60.0
    jitter: bool = True


def retry_with_backoff(
    max_attempts: int = 3,
    backoff_multiplier: float = 1.0,
    max_backoff: float = 60.0,
    jitter: bool = True,
) -> Callable[[F], F]:
    """
    Decorator for retrying functions with exponential backoff

    Args:
        max_attempts: Maximum number of retry attempts
        backoff_multiplier: Multiplier for backoff calculation
        max_backoff: Maximum backoff time in seconds
        jitter: Whether to add random jitter to backoff
    """

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args, **kwargs) -> None:
            last_exception = None

            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    if attempt < max_attempts - 1:  # Not the last attempt
                        # Calculate backoff time
                        backoff_time = min(
                            backoff_multiplier * (2**attempt), max_backoff
                        )

                        if jitter:
                            import random

                            # Add up to 25% jitter
                            jitter_amount = backoff_time * 0.25 * random.random()
                            backoff_time += jitter_amount

                        logger.warning(
                            f"Attempt {attempt + 1}/{max_attempts} failed for {func.__name__}: {e}. "
                            f"Retrying in {backoff_time:.2f} seconds..."
                        )

                        time.sleep(backoff_time)
                    else:
                        logger.error(
                            f"All {max_attempts} attempts failed for {func.__name__}: {e}"
                        )

            # If we get here, all attempts failed
            raise last_exception

        return wrapper

    return decorator


def should_retry(error: Exception) -> bool:
    """
    Determine if an error should be retried

    Args:
        error: The exception that occurred

    Returns:
        True if the error should be retried, False otherwise
    """
    # Network-related errors that should be retried
    retryable_errors = (
        ConnectionError,
        TimeoutError,
        OSError,  # Includes network-related OS errors
    )

    # API-specific errors that should be retried
    if isinstance(error, (BinanceAPIError, NewsAPIError)):
        error_msg = str(error).lower()
        # Retry on rate limits, temporary server errors, network issues
        if any(
            keyword in error_msg
            for keyword in [
                "rate limit",
                "too many requests",
                "server error",
                "timeout",
                "connection",
                "network",
            ]
        ):
            return True

    # Don't retry validation errors, authentication errors, or configuration errors
    non_retryable_errors = (
        ValidationError,
        ValueError,  # Often validation-related
        ConfigurationError,
        KeyError,  # Missing configuration
        PermissionError,
    )

    if isinstance(error, non_retryable_errors):
        return False

    # Retry network and system errors
    return isinstance(error, retryable_errors)


def create_error_response(
    error: Exception,
    error_code: Optional[str] = None,
    severity: ErrorSeverity = ErrorSeverity.MEDIUM,
) -> ErrorResponse:
    """
    Create a standardized error response from an exception

    Args:
        error: The exception that occurred
        error_code: Optional custom error code
        severity: Error severity level

    Returns:
        Standardized ErrorResponse object
    """
    if isinstance(error, TradingBotException):
        code = error.error_code
        message = error.message
        details = error.details
    else:
        code = error_code or "UNKNOWN_ERROR"
        message = str(error)
        details = {}

    # Adjust severity based on error type
    if isinstance(error, (BinanceAPIError, NewsAPIError, DatabaseError)):
        severity = ErrorSeverity.HIGH
    elif isinstance(error, ValidationError):
        severity = ErrorSeverity.MEDIUM
    elif isinstance(error, ConfigurationError):
        severity = ErrorSeverity.CRITICAL

    return ErrorResponse(
        success=False,
        error_code=code,
        message=message,
        details=details,
        timestamp=datetime.utcnow(),
        severity=severity,
    )


def format_api_error(
    error: Exception, context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Format an API error into a standardized response

    Args:
        error: The exception that occurred
        context: Additional context information

    Returns:
        Dictionary with standardized error format
    """
    error_response = create_error_response(error)
    result = error_response.to_dict()

    if context:
        result["context"] = context

    return result


def create_user_friendly_message(error: Exception) -> str:
    """
    Create a user-friendly error message from a technical exception

    Args:
        error: The exception that occurred

    Returns:
        User-friendly error message
    """
    if isinstance(error, BinanceAPIError):
        if "rate limit" in str(error).lower():
            return (
                "Binance API rate limit exceeded. Please wait a moment and try again."
            )
        elif "authentication" in str(error).lower():
            return "Binance API authentication failed. Please check your API keys."
        elif "insufficient" in str(error).lower():
            return "Insufficient balance for this trade."
        else:
            return "Binance API error occurred. Please try again later."

    elif isinstance(error, NewsAPIError):
        if "rate limit" in str(error).lower():
            return "News API rate limit exceeded. News updates will resume shortly."
        elif "authentication" in str(error).lower():
            return "News API authentication failed. News features may be limited."
        else:
            return "Unable to fetch news updates. Please try again later."

    elif isinstance(error, DatabaseError):
        return "Database connection issue. Please contact support if this persists."

    elif isinstance(error, ValidationError):
        return "Invalid input data. Please check your entries and try again."

    elif isinstance(error, ConfigurationError):
        return "Configuration error. Please check your settings."

    elif isinstance(error, ConnectionError):
        return "Network connection error. Please check your internet connection."

    elif isinstance(error, TimeoutError):
        return "Request timed out. Please try again."

    else:
        return "An unexpected error occurred. Please try again or contact support."


def log_error(
    error: Exception,
    context: Optional[Dict[str, Any]] = None,
    level: int = logging.ERROR,
) -> None:
    """
    Log an error with context information

    Args:
        error: The exception that occurred
        context: Additional context information
        level: Logging level
    """
    error_info = {
        "error_type": type(error).__name__,
        "error_message": str(error),
        "timestamp": datetime.utcnow().isoformat(),
    }

    if hasattr(error, "error_code"):
        error_info["error_code"] = error.error_code

    if context:
        error_info["context"] = context

    logger.log(level, f"Error occurred: {error_info}")


def handle_api_failure(
    error: Exception,
    service_name: str,
    fallback_action: Optional[Callable] = None,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Handle API failures with logging, user messaging, and optional fallback

    Args:
        error: The exception that occurred
        service_name: Name of the service that failed
        fallback_action: Optional fallback function to call
        context: Additional context information

    Returns:
        Dictionary with error information and fallback result if applicable
    """
    # Log the error
    log_error(error, context)

    # Create user-friendly message
    user_message = create_user_friendly_message(error)

    # Attempt fallback if provided
    fallback_result = None
    if fallback_action and callable(fallback_action):
        try:
            logger.info(f"Attempting fallback action for {service_name}")
            fallback_result = fallback_action()
        except Exception as fallback_error:
            logger.error(f"Fallback action failed for {service_name}: {fallback_error}")

    return {
        "service": service_name,
        "error": str(error),
        "user_message": user_message,
        "fallback_attempted": fallback_action is not None,
        "fallback_success": fallback_result is not None,
        "fallback_result": fallback_result,
        "timestamp": datetime.utcnow().isoformat(),
    }


def graceful_degradation(
    primary_action: Callable,
    fallback_action: Callable,
    service_name: str,
    context: Optional[Dict[str, Any]] = None,
) -> Any:
    """
    Execute primary action with graceful fallback to secondary action

    Args:
        primary_action: Primary function to execute
        fallback_action: Fallback function to execute if primary fails
        service_name: Name of the service for logging
        context: Additional context information

    Returns:
        Result from primary action or fallback action
    """
    try:
        logger.debug(f"Attempting primary action for {service_name}")
        return primary_action()
    except Exception as e:
        logger.warning(
            f"Primary action failed for {service_name}, attempting fallback: {e}"
        )

        try:
            result = fallback_action()
            logger.info(f"Fallback action succeeded for {service_name}")
            return result
        except Exception as fallback_error:
            logger.error(
                f"Both primary and fallback actions failed for {service_name}: {fallback_error}"
            )
            raise fallback_error


def emergency_stop(error: Exception, context: Optional[Dict[str, Any]] = None) -> None:
    """
    Emergency stop procedure for critical errors

    Args:
        error: The critical exception that occurred
        context: Additional context information
    """
    logger.critical(f"EMERGENCY STOP triggered: {error}", extra=context)

    # Log critical error details
    error_response = create_error_response(error, severity=ErrorSeverity.CRITICAL)
    logger.critical(f"Critical error details: {error_response.to_dict()}")

    # In a real implementation, this might:
    # - Cancel all open orders
    # - Close all positions
    # - Send emergency notifications
    # - Shutdown trading activities
    # - Save emergency state

    logger.critical("Emergency stop procedure completed")


# Validation Utilities


def validate_api_response(response: Dict[str, Any], required_fields: list) -> bool:
    """
    Validate API response structure

    Args:
        response: API response dictionary
        required_fields: List of required field names

    Returns:
        True if response is valid, False otherwise

    Raises:
        ValidationError: If response is invalid
    """
    if not isinstance(response, dict):
        raise ValidationError(
            "API response must be a dictionary", "INVALID_RESPONSE_FORMAT"
        )

    missing_fields = []
    for field in required_fields:
        if field not in response:
            missing_fields.append(field)

    if missing_fields:
        raise ValidationError(
            f"Missing required fields: {missing_fields}",
            "MISSING_REQUIRED_FIELDS",
            {"missing_fields": missing_fields},
        )

    return True


def validate_trading_parameters(
    symbol: str, side: str, amount: float, price: Optional[float] = None
) -> Dict[str, Any]:
    """
    Validate trading parameters

    Args:
        symbol: Trading symbol
        side: Trade side (BUY/SELL)
        amount: Trade amount
        price: Optional trade price

    Returns:
        Validation result dictionary

    Raises:
        ValidationError: If parameters are invalid
    """
    errors = []

    # Validate symbol format
    if not symbol or not isinstance(symbol, str):
        errors.append("Symbol must be a non-empty string")
    elif "/" not in symbol:
        errors.append("Symbol must be in format 'BASE/QUOTE'")

    # Validate side
    if side not in ["BUY", "SELL"]:
        errors.append("Side must be 'BUY' or 'SELL'")

    # Validate amount
    if not isinstance(amount, (int, float)) or amount <= 0:
        errors.append("Amount must be a positive number")

    # Validate price if provided
    if price is not None and (not isinstance(price, (int, float)) or price <= 0):
        errors.append("Price must be a positive number")

    if errors:
        raise ValidationError(
            f"Invalid trading parameters: {errors}",
            "INVALID_TRADING_PARAMETERS",
            {"validation_errors": errors},
        )

    return {"valid": True, "message": "Parameters are valid"}


def validate_configuration(config: Dict[str, Any], required_keys: list) -> bool:
    """
    Validate configuration dictionary

    Args:
        config: Configuration dictionary
        required_keys: List of required configuration keys

    Returns:
        True if configuration is valid

    Raises:
        ConfigurationError: If configuration is invalid
    """
    if not isinstance(config, dict):
        raise ConfigurationError(
            "Configuration must be a dictionary", "INVALID_CONFIG_FORMAT"
        )

    missing_keys = []
    for key in required_keys:
        if key not in config or config[key] is None:
            missing_keys.append(key)

    if missing_keys:
        raise ConfigurationError(
            f"Missing required configuration keys: {missing_keys}",
            "MISSING_CONFIG_KEYS",
            {"missing_keys": missing_keys},
        )

    return True
