"""
Enhanced Error Handling and Logging System

This module provides comprehensive error handling with:
- Custom exception hierarchy
- Circuit breaker pattern
- Retry mechanisms with exponential backoff
- Structured logging
- Error recovery strategies
"""

import asyncio
import functools
import logging
import time
import traceback
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import structlog
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    wait_random_exponential,
    retry_if_exception_type,
    before_sleep_log,
    after_log,
)


# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)


class ErrorSeverity(Enum):
    """Error severity levels"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Error categories for classification"""

    API_ERROR = "api_error"
    DATABASE_ERROR = "database_error"
    TRADING_ERROR = "trading_error"
    NETWORK_ERROR = "network_error"
    VALIDATION_ERROR = "validation_error"
    AUTHENTICATION_ERROR = "authentication_error"
    CONFIGURATION_ERROR = "configuration_error"
    SYSTEM_ERROR = "system_error"


# Custom Exception Hierarchy
class TradingBotError(Exception):
    """Base exception for all trading bot errors"""

    def __init__(
        self,
        message: str,
        category: ErrorCategory = ErrorCategory.SYSTEM_ERROR,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        context: Optional[Dict] = None,
    ):
        super().__init__(message)
        self.message = message
        self.category = category
        self.severity = severity
        self.context = context or {}
        self.timestamp = datetime.utcnow()


class APIError(TradingBotError):
    """API-related errors"""

    def __init__(
        self,
        message: str,
        api_name: str,
        status_code: Optional[int] = None,
        response_body: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(message, ErrorCategory.API_ERROR, **kwargs)
        self.api_name = api_name
        self.status_code = status_code
        self.response_body = response_body


class DatabaseError(TradingBotError):
    """Database-related errors"""

    def __init__(
        self, message: str, operation: str, table: Optional[str] = None, **kwargs
    ):
        super().__init__(message, ErrorCategory.DATABASE_ERROR, **kwargs)
        self.operation = operation
        self.table = table


class TradingError(TradingBotError):
    """Trading operation errors"""

    def __init__(
        self,
        message: str,
        symbol: Optional[str] = None,
        order_id: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(message, ErrorCategory.TRADING_ERROR, **kwargs)
        self.symbol = symbol
        self.order_id = order_id


class ValidationError(TradingBotError):
    """Data validation errors"""

    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Optional[Any] = None,
        **kwargs,
    ):
        super().__init__(message, ErrorCategory.VALIDATION_ERROR, **kwargs)
        self.field = field
        self.value = value


class NetworkError(TradingBotError):
    """Network connectivity errors"""

    def __init__(self, message: str, endpoint: Optional[str] = None, **kwargs):
        super().__init__(message, ErrorCategory.NETWORK_ERROR, **kwargs)
        self.endpoint = endpoint


class InsufficientFundsError(TradingError):
    """Insufficient funds for trading operations"""

    def __init__(
        self, message: str, required_amount: float, available_amount: float, **kwargs
    ):
        super().__init__(message, severity=ErrorSeverity.HIGH, **kwargs)
        self.required_amount = required_amount
        self.available_amount = available_amount


class RiskManagementError(TradingError):
    """Risk management constraint violations"""

    def __init__(
        self,
        message: str,
        constraint_type: str,
        current_value: float,
        limit_value: float,
        **kwargs,
    ):
        super().__init__(message, severity=ErrorSeverity.HIGH, **kwargs)
        self.constraint_type = constraint_type
        self.current_value = current_value
        self.limit_value = limit_value


@dataclass
class CircuitBreakerState:
    """Circuit breaker state tracking"""

    failure_count: int = 0
    last_failure_time: Optional[datetime] = None
    state: str = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    total_requests: int = 0
    successful_requests: int = 0


class CircuitBreaker:
    """Circuit breaker pattern implementation"""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: Type[Exception] = Exception,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.state = CircuitBreakerState()
        self.logger = structlog.get_logger(__name__)

    def __call__(self, func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            return await self._execute_with_circuit_breaker(func, args, kwargs)

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            if asyncio.iscoroutinefunction(func):
                raise ValueError("Cannot use sync wrapper for async function")
            return self._execute_with_circuit_breaker_sync(func, args, kwargs)

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

    async def _execute_with_circuit_breaker(
        self, func: Callable, args: tuple, kwargs: dict
    ):
        """Execute function with circuit breaker protection (async)"""
        if self.state.state == "OPEN":
            if self._should_attempt_reset():
                self.state.state = "HALF_OPEN"
                self.logger.info("Circuit breaker transitioning to HALF_OPEN")
            else:
                raise TradingBotError(
                    f"Circuit breaker is OPEN for {func.__name__}",
                    category=ErrorCategory.SYSTEM_ERROR,
                    severity=ErrorSeverity.HIGH,
                    context={"function": func.__name__, "state": self.state.state},
                )

        try:
            self.state.total_requests += 1
            result = await func(*args, **kwargs)
            self._on_success()
            return result

        except self.expected_exception as e:
            self._on_failure(func.__name__, e)
            raise

    def _execute_with_circuit_breaker_sync(
        self, func: Callable, args: tuple, kwargs: dict
    ):
        """Execute function with circuit breaker protection (sync)"""
        if self.state.state == "OPEN":
            if self._should_attempt_reset():
                self.state.state = "HALF_OPEN"
                self.logger.info("Circuit breaker transitioning to HALF_OPEN")
            else:
                raise TradingBotError(
                    f"Circuit breaker is OPEN for {func.__name__}",
                    category=ErrorCategory.SYSTEM_ERROR,
                    severity=ErrorSeverity.HIGH,
                )

        try:
            self.state.total_requests += 1
            result = func(*args, **kwargs)
            self._on_success()
            return result

        except self.expected_exception as e:
            self._on_failure(func.__name__, e)
            raise

    def _should_attempt_reset(self) -> bool:
        """Check if circuit breaker should attempt to reset"""
        if not self.state.last_failure_time:
            return False

        time_since_failure = (
            datetime.utcnow() - self.state.last_failure_time
        ).total_seconds()
        return time_since_failure >= self.recovery_timeout

    def _on_success(self):
        """Handle successful execution"""
        self.state.successful_requests += 1
        self.state.failure_count = 0

        if self.state.state == "HALF_OPEN":
            self.state.state = "CLOSED"
            self.logger.info("Circuit breaker reset to CLOSED")

    def _on_failure(self, func_name: str, exception: Exception):
        """Handle failed execution"""
        self.state.failure_count += 1
        self.state.last_failure_time = datetime.utcnow()

        self.logger.error(
            "Circuit breaker failure recorded",
            function=func_name,
            failure_count=self.state.failure_count,
            exception=str(exception),
        )

        if self.state.failure_count >= self.failure_threshold:
            self.state.state = "OPEN"
            self.logger.error(
                "Circuit breaker opened due to failures",
                function=func_name,
                failure_count=self.state.failure_count,
            )


class ErrorHandler:
    """Centralized error handling and logging"""

    def __init__(self):
        self.logger = structlog.get_logger(__name__)
        self.error_counts: Dict[str, int] = {}
        self.last_error_times: Dict[str, datetime] = {}
        self.recovery_strategies: Dict[Type[Exception], Callable] = {}

    def register_recovery_strategy(
        self, exception_type: Type[Exception], strategy: Callable
    ):
        """Register a recovery strategy for specific exception types"""
        self.recovery_strategies[exception_type] = strategy

    async def handle_error(
        self, error: Exception, context: Optional[Dict] = None
    ) -> bool:
        """Handle error with logging and recovery attempts"""
        error_key = f"{type(error).__name__}:{str(error)}"
        self.error_counts[error_key] = self.error_counts.get(error_key, 0) + 1
        self.last_error_times[error_key] = datetime.utcnow()

        # Structured logging
        self.logger.error(
            "Error occurred",
            error_type=type(error).__name__,
            error_message=str(error),
            error_count=self.error_counts[error_key],
            context=context or {},
            stack_trace=traceback.format_exc(),
        )

        # Attempt recovery if strategy exists
        recovery_strategy = self.recovery_strategies.get(type(error))
        if recovery_strategy:
            try:
                self.logger.info(
                    "Attempting error recovery", error_type=type(error).__name__
                )
                await recovery_strategy(error, context)
                self.logger.info("Error recovery successful")
                return True
            except Exception as recovery_error:
                self.logger.error(
                    "Error recovery failed",
                    original_error=str(error),
                    recovery_error=str(recovery_error),
                )

        return False

    def get_error_statistics(self) -> Dict[str, Any]:
        """Get error statistics for monitoring"""
        return {
            "total_unique_errors": len(self.error_counts),
            "total_error_occurrences": sum(self.error_counts.values()),
            "most_common_errors": sorted(
                self.error_counts.items(), key=lambda x: x[1], reverse=True
            )[:10],
            "recent_errors": [
                {"error": error, "last_seen": time.isoformat()}
                for error, time in sorted(
                    self.last_error_times.items(), key=lambda x: x[1], reverse=True
                )[:5]
            ],
        }


# Global error handler instance
error_handler = ErrorHandler()


def enhanced_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retry_on: tuple = (APIError, NetworkError, DatabaseError),
):
    """Enhanced retry decorator with exponential backoff and jitter"""

    def decorator(func: Callable) -> Callable:
        if jitter:
            wait_strategy = wait_random_exponential(
                multiplier=base_delay,
                max=max_delay,
                exp_base=exponential_base,
            )
        else:
            wait_strategy = wait_exponential(
                multiplier=base_delay,
                max=max_delay,
                exp_base=exponential_base,
            )

        retry_decorator = retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_strategy,
            retry=retry_if_exception_type(retry_on),
            before_sleep=before_sleep_log(structlog.get_logger(), logging.WARNING),
            after=after_log(structlog.get_logger(), logging.INFO),
        )

        @retry_decorator
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                await error_handler.handle_error(
                    e,
                    {
                        "function": func.__name__,
                        "args": str(args)[:100],  # Truncate for logging
                        "attempt": "retry",
                    },
                )
                raise

        @retry_decorator
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                asyncio.create_task(
                    error_handler.handle_error(
                        e,
                        {
                            "function": func.__name__,
                            "args": str(args)[:100],
                            "attempt": "retry",
                        },
                    )
                )
                raise

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

    return decorator


def graceful_degradation(
    fallback_value: Any = None, fallback_func: Optional[Callable] = None
):
    """Graceful degradation decorator"""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                logger = structlog.get_logger()
                logger.warning(
                    "Function failed, applying graceful degradation",
                    function=func.__name__,
                    error=str(e),
                )

                if fallback_func:
                    try:
                        return (
                            await fallback_func(*args, **kwargs)
                            if asyncio.iscoroutinefunction(fallback_func)
                            else fallback_func(*args, **kwargs)
                        )
                    except Exception as fallback_error:
                        logger.error(
                            "Fallback function also failed",
                            function=func.__name__,
                            fallback_error=str(fallback_error),
                        )

                return fallback_value

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger = structlog.get_logger()
                logger.warning(
                    "Function failed, applying graceful degradation",
                    function=func.__name__,
                    error=str(e),
                )

                if fallback_func:
                    try:
                        return fallback_func(*args, **kwargs)
                    except Exception as fallback_error:
                        logger.error(
                            "Fallback function also failed",
                            function=func.__name__,
                            fallback_error=str(fallback_error),
                        )

                return fallback_value

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

    return decorator


def safe_execute(func: Callable, *args, default_return: Any = None, **kwargs) -> Any:
    """Safely execute a function with error handling"""
    try:
        return func(*args, **kwargs)
    except Exception as e:
        logger = structlog.get_logger()
        logger.error(
            "Safe execution failed",
            function=func.__name__,
            error=str(e),
            error_type=type(e).__name__,
        )
        return default_return


class HealthChecker:
    """System health monitoring"""

    def __init__(self):
        self.logger = structlog.get_logger(__name__)
        self.health_checks: Dict[str, Callable] = {}
        self.last_check_results: Dict[str, Dict] = {}

    def register_health_check(self, name: str, check_func: Callable):
        """Register a health check function"""
        self.health_checks[name] = check_func

    async def run_health_checks(self) -> Dict[str, Any]:
        """Run all registered health checks"""
        results = {}
        overall_status = "healthy"

        for name, check_func in self.health_checks.items():
            try:
                start_time = time.time()

                if asyncio.iscoroutinefunction(check_func):
                    result = await asyncio.wait_for(check_func(), timeout=5.0)
                else:
                    result = check_func()

                response_time = time.time() - start_time

                check_result = {
                    "status": "healthy" if result.get("healthy", True) else "unhealthy",
                    "response_time": response_time,
                    "details": result,
                    "timestamp": datetime.utcnow().isoformat(),
                }

                results[name] = check_result
                self.last_check_results[name] = check_result

                if check_result["status"] != "healthy":
                    overall_status = (
                        "degraded" if overall_status == "healthy" else "unhealthy"
                    )

            except asyncio.TimeoutError:
                check_result = {
                    "status": "timeout",
                    "error": "Health check timed out",
                    "timestamp": datetime.utcnow().isoformat(),
                }
                results[name] = check_result
                overall_status = "unhealthy"

            except Exception as e:
                check_result = {
                    "status": "error",
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat(),
                }
                results[name] = check_result
                overall_status = "unhealthy"

        return {
            "overall_status": overall_status,
            "checks": results,
            "timestamp": datetime.utcnow().isoformat(),
        }


# Global health checker instance
health_checker = HealthChecker()


# Recovery strategies
async def api_connection_recovery(error: Exception, context: Optional[Dict] = None):
    """Recovery strategy for API connection errors"""
    logger = structlog.get_logger()
    logger.info("Attempting API connection recovery")

    # Wait before retrying
    await asyncio.sleep(2)

    # Additional recovery logic can be added here
    # e.g., refresh tokens, switch endpoints, etc.


async def database_connection_recovery(
    error: Exception, context: Optional[Dict] = None
):
    """Recovery strategy for database connection errors"""
    logger = structlog.get_logger()
    logger.info("Attempting database connection recovery")

    # Wait before retrying
    await asyncio.sleep(1)

    # Additional recovery logic can be added here
    # e.g., reconnect to database, clear connection pool, etc.


# Register default recovery strategies
error_handler.register_recovery_strategy(APIError, api_connection_recovery)
error_handler.register_recovery_strategy(DatabaseError, database_connection_recovery)
error_handler.register_recovery_strategy(NetworkError, api_connection_recovery)


def setup_error_monitoring():
    """Setup error monitoring and alerting"""
    logger = structlog.get_logger()
    logger.info("Error monitoring system initialized")

    # Register basic health checks
    health_checker.register_health_check("error_handler", lambda: {"healthy": True})

    return {
        "error_handler": error_handler,
        "health_checker": health_checker,
        "circuit_breaker": CircuitBreaker,
    }
