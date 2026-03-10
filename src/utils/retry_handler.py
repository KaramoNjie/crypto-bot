"""
Retry handler with tenacity for robust API calls
"""

import logging
import asyncio
from typing import Any, Callable, Optional, Union
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
    after_log,
)
import aiohttp
import websockets
from requests.exceptions import RequestException, ConnectionError, Timeout


class RetryHandler:
    """Enhanced retry handler for various API calls"""

    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(
            (RequestException, ConnectionError, Timeout, aiohttp.ClientError)
        ),
        before_sleep=before_sleep_log(logging.getLogger(__name__), logging.WARNING),
        after=after_log(logging.getLogger(__name__), logging.INFO),
    )
    async def retry_api_call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Retry API call with exponential backoff

        Args:
            func: Function to retry
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result
        """
        return await func(*args, **kwargs)

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        retry=retry_if_exception_type(
            (ConnectionError, TimeoutError, aiohttp.ClientError)
        ),
        before_sleep=before_sleep_log(logging.getLogger(__name__), logging.WARNING),
    )
    async def retry_exchange_call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Retry exchange API call with more aggressive retry policy

        Args:
            func: Function to retry
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result
        """
        try:
            result = await func(*args, **kwargs)

            # Check for exchange-specific error responses
            if isinstance(result, dict) and "code" in result and result["code"] != 200:
                error_msg = result.get("msg", "Unknown exchange error")
                self.logger.warning(f"Exchange error: {result['code']} - {error_msg}")

                # Retry on specific error codes
                retryable_codes = [
                    -1001,
                    -1021,
                    -2013,
                    -2014,
                    -2015,
                ]  # Connection, timestamp, order errors
                if result["code"] in retryable_codes:
                    raise ConnectionError(f"Retryable exchange error: {error_msg}")

            return result

        except Exception as e:
            self.logger.error(f"Exchange call failed: {e}")
            raise

    @retry(
        stop=stop_after_attempt(10),
        wait=wait_exponential(multiplier=1, min=1, max=60),
        retry=retry_if_exception_type(
            (websockets.ConnectionClosed, websockets.InvalidStatusCode, ConnectionError)
        ),
        before_sleep=before_sleep_log(logging.getLogger(__name__), logging.WARNING),
    )
    async def retry_websocket_connection(self, connect_func: Callable) -> Any:
        """
        Retry WebSocket connection with extended retry policy

        Args:
            connect_func: WebSocket connection function

        Returns:
            WebSocket connection
        """
        return await connect_func()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError)),
        before_sleep=before_sleep_log(logging.getLogger(__name__), logging.WARNING),
    )
    async def retry_news_api_call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Retry news API call with shorter retry policy

        Args:
            func: Function to retry
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result
        """
        return await func(*args, **kwargs)

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=4, max=30),
        retry=retry_if_exception_type((Exception,)),
        before_sleep=before_sleep_log(logging.getLogger(__name__), logging.ERROR),
    )
    async def retry_critical_operation(self, func: Callable, *args, **kwargs) -> Any:
        """
        Retry critical operations with conservative policy

        Args:
            func: Function to retry
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result
        """
        return await func(*args, **kwargs)


class AsyncRetrySession:
    """Enhanced async session with automatic retries"""

    def __init__(self, timeout: int = 30) -> None:
        self.retry_handler = RetryHandler()
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.session = None
        self.logger = logging.getLogger(__name__)

    async def __aenter__(self) -> None:
        self.session = aiohttp.ClientSession(timeout=self.timeout)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self.session:
            await self.session.close()

    async def get(self, url: str, **kwargs) -> aiohttp.ClientResponse:
        """GET request with retry logic"""

        async def _get() -> None:
            return await self.session.get(url, **kwargs)

        return await self.retry_handler.retry_api_call(_get)

    async def post(self, url: str, **kwargs) -> aiohttp.ClientResponse:
        """POST request with retry logic"""

        async def _post() -> None:
            return await self.session.post(url, **kwargs)

        return await self.retry_handler.retry_api_call(_post)

    async def put(self, url: str, **kwargs) -> aiohttp.ClientResponse:
        """PUT request with retry logic"""

        async def _put() -> None:
            return await self.session.put(url, **kwargs)

        return await self.retry_handler.retry_api_call(_put)

    async def delete(self, url: str, **kwargs) -> aiohttp.ClientResponse:
        """DELETE request with retry logic"""

        async def _delete() -> None:
            return await self.session.delete(url, **kwargs)

        return await self.retry_handler.retry_api_call(_delete)


class CircuitBreaker:
    """Circuit breaker pattern for API calls"""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception

        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

        self.logger = logging.getLogger(__name__)

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker pattern"""

        if self.state == "OPEN":
            if self._should_attempt_reset():
                self.state = "HALF_OPEN"
                self.logger.info("Circuit breaker moving to HALF_OPEN state")
            else:
                raise Exception("Circuit breaker is OPEN - calls are blocked")

        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result

        except self.expected_exception as e:
            self._on_failure()
            raise e

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset"""
        if not self.last_failure_time:
            return True

        import time

        return (time.time() - self.last_failure_time) >= self.recovery_timeout

    def _on_success(self) -> None:
        """Handle successful call"""
        if self.state == "HALF_OPEN":
            self.state = "CLOSED"
            self.logger.info("Circuit breaker reset to CLOSED state")

        self.failure_count = 0

    def _on_failure(self):
        """Handle failed call"""
        self.failure_count += 1

        import time

        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            self.logger.error(
                f"Circuit breaker tripped - moving to OPEN state after {self.failure_count} failures"
            )


# Global retry handler instance
retry_handler = RetryHandler()


# Decorators for easy use
def retry_on_exception(
    max_attempts: int = 3,
    wait_multiplier: int = 1,
    wait_min: int = 2,
    wait_max: int = 10,
    exceptions: tuple = (Exception,),
):
    """Decorator for retrying functions on exception"""
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=wait_multiplier, min=wait_min, max=wait_max),
        retry=retry_if_exception_type(exceptions),
        before_sleep=before_sleep_log(logging.getLogger(__name__), logging.WARNING),
        after=after_log(logging.getLogger(__name__), logging.INFO),
    )


def retry_exchange_operation(max_attempts: int = 5):
    """Decorator specifically for exchange operations"""
    return retry_on_exception(
        max_attempts=max_attempts,
        wait_multiplier=1,
        wait_min=1,
        wait_max=30,
        exceptions=(ConnectionError, TimeoutError, aiohttp.ClientError),
    )
