"""
Enhanced Binance API Client

Production-ready async Binance client with:
- Modern async/await patterns
- Connection pooling and optimization
- Comprehensive error handling
- Rate limiting and circuit breaker
- Structured logging
- WebSocket support with auto-reconnection
"""

import asyncio
import hashlib
import hmac
import json
import time
import urllib.parse
from contextlib import asynccontextmanager
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timezone

import aiohttp
import websockets
import structlog
from dataclasses import dataclass

from ..utils.error_handling_enhanced import (
    APIError,
    NetworkError,
    TradingError,
    enhanced_retry,
    CircuitBreaker,
    graceful_degradation,
)


logger = structlog.get_logger(__name__)


@dataclass
class TradeData:
    """Structured trade data"""

    symbol: str
    price: Decimal
    quantity: Decimal
    side: str
    timestamp: datetime
    trade_id: Optional[str] = None


@dataclass
class OrderBookData:
    """Order book data structure"""

    symbol: str
    bids: List[tuple]  # [(price, quantity), ...]
    asks: List[tuple]  # [(price, quantity), ...]
    timestamp: datetime


@dataclass
class MarketData:
    """Market data structure"""

    symbol: str
    open_price: Decimal
    high_price: Decimal
    low_price: Decimal
    close_price: Decimal
    volume: Decimal
    timestamp: datetime
    change_24h: Optional[Decimal] = None
    change_percent_24h: Optional[Decimal] = None


class RateLimiter:
    """Advanced rate limiter with multiple windows"""

    def __init__(self, limits: Dict[str, tuple]):  # {window: (requests, seconds)}
        self.limits = limits
        self.requests = {window: [] for window in limits}
        self.logger = structlog.get_logger(__name__)

    async def acquire(self, weight: int = 1):
        """Acquire rate limit permission"""
        now = time.time()

        # Check all windows
        for window, (limit, seconds) in self.limits.items():
            # Clean old requests
            self.requests[window] = [
                req_time
                for req_time in self.requests[window]
                if now - req_time < seconds
            ]

            # Check if we can make the request
            if len(self.requests[window]) + weight > limit:
                sleep_time = seconds - (now - self.requests[window][0])
                if sleep_time > 0:
                    self.logger.info(
                        "Rate limit reached, sleeping",
                        window=window,
                        sleep_time=sleep_time,
                        current_requests=len(self.requests[window]),
                    )
                    await asyncio.sleep(sleep_time)

            # Record the request
            for _ in range(weight):
                self.requests[window].append(now)


class EnhancedBinanceClient:
    """Enhanced async Binance API client"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        testnet: bool = True,
        session: Optional[aiohttp.ClientSession] = None,
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.base_url = (
            "https://testnet.binance.vision" if testnet else "https://api.binance.com"
        )
        self.ws_url = (
            "wss://testnet.binance.vision/ws"
            if testnet
            else "wss://stream.binance.com:9443/ws"
        )

        # Rate limiters for different endpoint categories
        self.rate_limiters = {
            "general": RateLimiter({"1min": (1200, 60), "1sec": (10, 1)}),
            "orders": RateLimiter({"10sec": (100, 10), "1day": (200000, 86400)}),
            "data": RateLimiter(
                {"1min": (6000, 60)}
            ),  # Weight-based for data endpoints
        }

        self.session = session
        self._owned_session = session is None
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=60.0,
            expected_exception=(APIError, NetworkError),
        )

        self.logger = structlog.get_logger(__name__)

        # WebSocket connections
        self.ws_connections: Dict[str, websockets.WebSocketServerProtocol] = {}
        self.ws_subscriptions: Dict[str, List[str]] = {}
        self._ws_reconnect_delay = 5

    async def __aenter__(self):
        """Async context manager entry"""
        if self._owned_session:
            connector = aiohttp.TCPConnector(
                limit=100,
                limit_per_host=30,
                ttl_dns_cache=300,
                use_dns_cache=True,
                keepalive_timeout=30,
                enable_cleanup_closed=True,
            )

            timeout = aiohttp.ClientTimeout(total=30, connect=10, sock_read=10)

            self.session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers={
                    "User-Agent": "Enhanced-Crypto-Trading-Bot/2.0",
                    "Accept": "application/json",
                },
            )

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()

    async def close(self):
        """Close all connections"""
        # Close WebSocket connections
        for stream_name, ws in self.ws_connections.items():
            try:
                await ws.close()
                self.logger.info("WebSocket connection closed", stream=stream_name)
            except Exception as e:
                self.logger.warning(
                    "Error closing WebSocket", stream=stream_name, error=str(e)
                )

        self.ws_connections.clear()

        # Close HTTP session
        if self._owned_session and self.session:
            await self.session.close()
            self.logger.info("HTTP session closed")

    def _generate_signature(self, params: str) -> str:
        """Generate HMAC SHA256 signature"""
        if not self.api_secret:
            raise APIError("API secret not configured", "binance")

        return hmac.new(
            self.api_secret.encode("utf-8"), params.encode("utf-8"), hashlib.sha256
        ).hexdigest()

    def _prepare_params(self, params: Dict[str, Any], signed: bool = False) -> str:
        """Prepare request parameters"""
        # Remove None values
        filtered_params = {k: v for k, v in params.items() if v is not None}

        # Add timestamp for signed requests
        if signed:
            filtered_params["timestamp"] = int(time.time() * 1000)

        # Convert to query string
        query_string = urllib.parse.urlencode(filtered_params)

        # Add signature for signed requests
        if signed:
            signature = self._generate_signature(query_string)
            query_string += f"&signature={signature}"

        return query_string

    @enhanced_retry(max_attempts=3, retry_on=(APIError, NetworkError))
    @CircuitBreaker(failure_threshold=5, recovery_timeout=60.0)
    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Dict[str, Any] = None,
        signed: bool = False,
        rate_limit_category: str = "general",
    ) -> Dict[str, Any]:
        """Make HTTP request with comprehensive error handling"""
        if not self.session:
            raise APIError("HTTP session not initialized", "binance")

        params = params or {}

        # Apply rate limiting
        await self.rate_limiters[rate_limit_category].acquire()

        # Prepare headers
        headers = {}
        if self.api_key:
            headers["X-MBX-APIKEY"] = self.api_key

        # Prepare URL and parameters
        url = f"{self.base_url}{endpoint}"
        query_string = self._prepare_params(params, signed)

        if method.upper() == "GET":
            url += f"?{query_string}" if query_string else ""
            data = None
        else:
            data = query_string.encode("utf-8") if query_string else None
            headers["Content-Type"] = "application/x-www-form-urlencoded"

        try:
            self.logger.debug(
                "Making API request", method=method, endpoint=endpoint, signed=signed
            )

            async with self.session.request(
                method, url, headers=headers, data=data
            ) as response:
                response_text = await response.text()

                # Log rate limit headers
                self._log_rate_limit_headers(response.headers)

                if response.status == 200:
                    try:
                        return json.loads(response_text)
                    except json.JSONDecodeError as e:
                        raise APIError(
                            f"Invalid JSON response: {e}",
                            "binance",
                            response.status,
                            response_text,
                        )
                else:
                    # Handle API errors
                    try:
                        error_data = json.loads(response_text)
                        error_msg = error_data.get("msg", response_text)
                        error_code = error_data.get("code", "unknown")
                    except json.JSONDecodeError:
                        error_msg = response_text
                        error_code = "unknown"

                    raise APIError(
                        f"Binance API error: {error_msg} (code: {error_code})",
                        "binance",
                        response.status,
                        response_text,
                    )

        except aiohttp.ClientError as e:
            raise NetworkError(f"Network error: {e}", f"{self.base_url}{endpoint}")
        except asyncio.TimeoutError:
            raise NetworkError("Request timeout", f"{self.base_url}{endpoint}")

    def _log_rate_limit_headers(self, headers):
        """Log rate limit information from response headers"""
        rate_limit_info = {}

        for header_name in [
            "x-mbx-used-weight-1m",
            "x-mbx-used-weight-1s",
            "x-mbx-order-count-10s",
            "x-mbx-order-count-1d",
        ]:
            if header_name in headers:
                rate_limit_info[header_name] = headers[header_name]

        if rate_limit_info:
            self.logger.info("Rate limit status", **rate_limit_info)

    # Market Data Methods

    async def get_server_time(self) -> Dict[str, Any]:
        """Get server time"""
        return await self._request("GET", "/api/v3/time")

    async def get_exchange_info(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """Get exchange information"""
        params = {"symbol": symbol} if symbol else {}
        return await self._request(
            "GET", "/api/v3/exchangeInfo", params, rate_limit_category="data"
        )

    async def get_symbol_price(self, symbol: str) -> MarketData:
        """Get current price for a symbol"""
        params = {"symbol": symbol}
        data = await self._request(
            "GET", "/api/v3/ticker/price", params, rate_limit_category="data"
        )

        return MarketData(
            symbol=data["symbol"],
            close_price=Decimal(data["price"]),
            timestamp=datetime.now(timezone.utc),
            open_price=Decimal(data["price"]),  # Price endpoint doesn't provide OHLC
            high_price=Decimal(data["price"]),
            low_price=Decimal(data["price"]),
            volume=Decimal("0"),
        )

    async def get_24hr_ticker(self, symbol: str) -> MarketData:
        """Get 24hr ticker statistics"""
        params = {"symbol": symbol}
        data = await self._request(
            "GET", "/api/v3/ticker/24hr", params, rate_limit_category="data"
        )

        return MarketData(
            symbol=data["symbol"],
            open_price=Decimal(data["openPrice"]),
            high_price=Decimal(data["highPrice"]),
            low_price=Decimal(data["lowPrice"]),
            close_price=Decimal(data["lastPrice"]),
            volume=Decimal(data["volume"]),
            change_24h=Decimal(data["priceChange"]),
            change_percent_24h=Decimal(data["priceChangePercent"]),
            timestamp=datetime.fromtimestamp(
                int(data["closeTime"]) / 1000, timezone.utc
            ),
        )

    async def get_klines(
        self,
        symbol: str,
        interval: str,
        limit: int = 500,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
    ) -> List[Dict]:
        """Get kline/candlestick data"""
        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": limit,
            "startTime": start_time,
            "endTime": end_time,
        }

        return await self._request(
            "GET", "/api/v3/klines", params, rate_limit_category="data"
        )

    async def get_order_book(self, symbol: str, limit: int = 100) -> OrderBookData:
        """Get order book data"""
        params = {"symbol": symbol, "limit": limit}
        data = await self._request(
            "GET", "/api/v3/depth", params, rate_limit_category="data"
        )

        return OrderBookData(
            symbol=symbol,
            bids=[(Decimal(price), Decimal(qty)) for price, qty in data["bids"]],
            asks=[(Decimal(price), Decimal(qty)) for price, qty in data["asks"]],
            timestamp=datetime.now(timezone.utc),
        )

    # Trading Methods (require signed requests)

    async def get_account_info(self) -> Dict[str, Any]:
        """Get account information"""
        return await self._request(
            "GET", "/api/v3/account", signed=True, rate_limit_category="general"
        )

    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        """Get open orders"""
        params = {"symbol": symbol} if symbol else {}
        return await self._request(
            "GET",
            "/api/v3/openOrders",
            params,
            signed=True,
            rate_limit_category="orders",
        )

    async def create_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: Union[str, Decimal],
        price: Optional[Union[str, Decimal]] = None,
        time_in_force: str = "GTC",
        **kwargs,
    ) -> Dict[str, Any]:
        """Create a new order"""
        params = {
            "symbol": symbol,
            "side": side.upper(),
            "type": order_type.upper(),
            "quantity": str(quantity),
            "timeInForce": time_in_force,
            **kwargs,
        }

        if price is not None:
            params["price"] = str(price)

        self.logger.info(
            "Creating order",
            symbol=symbol,
            side=side,
            type=order_type,
            quantity=str(quantity),
        )

        try:
            result = await self._request(
                "POST",
                "/api/v3/order",
                params,
                signed=True,
                rate_limit_category="orders",
            )
            self.logger.info(
                "Order created successfully",
                order_id=result.get("orderId"),
                client_order_id=result.get("clientOrderId"),
            )
            return result

        except APIError as e:
            self.logger.error(
                "Order creation failed", error=str(e), symbol=symbol, side=side
            )
            raise TradingError(f"Failed to create order: {e}", symbol=symbol)

    async def cancel_order(
        self,
        symbol: str,
        order_id: Optional[int] = None,
        orig_client_order_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Cancel an order"""
        params = {"symbol": symbol}

        if order_id:
            params["orderId"] = order_id
        elif orig_client_order_id:
            params["origClientOrderId"] = orig_client_order_id
        else:
            raise TradingError(
                "Either order_id or orig_client_order_id must be provided"
            )

        self.logger.info(
            "Cancelling order",
            symbol=symbol,
            order_id=order_id,
            client_order_id=orig_client_order_id,
        )

        try:
            result = await self._request(
                "DELETE",
                "/api/v3/order",
                params,
                signed=True,
                rate_limit_category="orders",
            )
            self.logger.info(
                "Order cancelled successfully", order_id=result.get("orderId")
            )
            return result

        except APIError as e:
            self.logger.error("Order cancellation failed", error=str(e), symbol=symbol)
            raise TradingError(
                f"Failed to cancel order: {e}", symbol=symbol, order_id=str(order_id)
            )

    async def get_order_status(
        self,
        symbol: str,
        order_id: Optional[int] = None,
        orig_client_order_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get order status"""
        params = {"symbol": symbol}

        if order_id:
            params["orderId"] = order_id
        elif orig_client_order_id:
            params["origClientOrderId"] = orig_client_order_id
        else:
            raise TradingError(
                "Either order_id or orig_client_order_id must be provided"
            )

        return await self._request(
            "GET", "/api/v3/order", params, signed=True, rate_limit_category="orders"
        )

    # WebSocket Methods

    async def subscribe_to_stream(
        self, stream: str
    ) -> websockets.WebSocketServerProtocol:
        """Subscribe to a WebSocket stream"""
        if stream in self.ws_connections:
            return self.ws_connections[stream]

        ws_url = f"{self.ws_url}/{stream}"

        try:
            websocket = await websockets.connect(
                ws_url, ping_interval=20, ping_timeout=10, close_timeout=10
            )

            self.ws_connections[stream] = websocket
            self.logger.info("WebSocket connected", stream=stream)

            return websocket

        except Exception as e:
            self.logger.error(
                "WebSocket connection failed", stream=stream, error=str(e)
            )
            raise NetworkError(f"WebSocket connection failed: {e}", ws_url)

    async def unsubscribe_from_stream(self, stream: str):
        """Unsubscribe from a WebSocket stream"""
        if stream in self.ws_connections:
            websocket = self.ws_connections[stream]
            await websocket.close()
            del self.ws_connections[stream]
            self.logger.info("WebSocket disconnected", stream=stream)

    @asynccontextmanager
    async def stream_trades(self, symbol: str):
        """Context manager for trade stream"""
        stream = f"{symbol.lower()}@trade"
        websocket = await self.subscribe_to_stream(stream)

        try:
            yield self._trade_stream_generator(websocket)
        finally:
            await self.unsubscribe_from_stream(stream)

    async def _trade_stream_generator(
        self, websocket: websockets.WebSocketServerProtocol
    ):
        """Generate trade data from WebSocket stream"""
        try:
            async for message in websocket:
                data = json.loads(message)

                yield TradeData(
                    symbol=data["s"],
                    price=Decimal(data["p"]),
                    quantity=Decimal(data["q"]),
                    side=(
                        "sell" if data["m"] else "buy"
                    ),  # m = true if buyer is market maker
                    trade_id=data["t"],
                    timestamp=datetime.fromtimestamp(data["T"] / 1000, timezone.utc),
                )

        except websockets.exceptions.ConnectionClosed:
            self.logger.warning("WebSocket connection closed")
        except Exception as e:
            self.logger.error("Error in trade stream", error=str(e))
            raise NetworkError(f"Trade stream error: {e}")

    # Utility Methods

    @graceful_degradation(fallback_value=False)
    async def test_connectivity(self) -> bool:
        """Test API connectivity"""
        try:
            await self.get_server_time()
            self.logger.info("Binance connectivity test passed")
            return True
        except Exception as e:
            self.logger.error("Binance connectivity test failed", error=str(e))
            return False

    async def get_trading_fees(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """Get trading fees"""
        params = {"symbol": symbol} if symbol else {}
        return await self._request(
            "GET",
            "/api/v3/tradeFee",
            params,
            signed=True,
            rate_limit_category="general",
        )

    def get_rate_limit_status(self) -> Dict[str, Dict]:
        """Get current rate limit status"""
        status = {}
        for category, limiter in self.rate_limiters.items():
            now = time.time()
            category_status = {}

            for window, (limit, seconds) in limiter.limits.items():
                # Clean old requests
                recent_requests = [
                    req_time
                    for req_time in limiter.requests[window]
                    if now - req_time < seconds
                ]

                category_status[window] = {
                    "limit": limit,
                    "used": len(recent_requests),
                    "remaining": max(0, limit - len(recent_requests)),
                    "window_seconds": seconds,
                }

            status[category] = category_status

        return status


# Example usage and testing functions
async def test_binance_client():
    """Test the enhanced Binance client"""
    async with EnhancedBinanceClient(testnet=True) as client:
        # Test connectivity
        connected = await client.test_connectivity()
        print(f"Connected: {connected}")

        # Get market data
        btc_ticker = await client.get_24hr_ticker("BTCUSDT")
        print(f"BTC Price: ${btc_ticker.close_price}")

        # Get rate limit status
        rate_limits = client.get_rate_limit_status()
        print(f"Rate limits: {rate_limits}")


if __name__ == "__main__":
    asyncio.run(test_binance_client())
