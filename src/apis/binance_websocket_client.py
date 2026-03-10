import asyncio
import json
import logging
import time
from typing import Dict, List, Optional, Callable, Any
import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException
import threading
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)


class BinanceWebSocketClient:
    """
    Binance WebSocket client for real-time market data streaming
    Supports ticker updates, kline data, order book updates, and trade streams
    """

    def __init__(self, config) -> None:
        self.config = config
        self.base_url = "wss://stream.binance.com:9443/ws"
        self.testnet_url = "wss://testnet.binance.vision/ws"

        # Connection management
        self.websocket = None
        self.is_connected = False
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 10
        self.reconnect_delay = 5

        # Subscription management
        self.subscriptions = {}
        self.subscription_id = 1
        self.callbacks = {}

        # Message handling
        self.message_queue = asyncio.Queue()
        self.last_ping_time = time.time()
        self.ping_interval = 180  # 3 minutes (Binance requires ping every 24 hours)

        # Threading
        self.event_loop = None
        self.websocket_thread = None
        self.is_running = False

        # Statistics
        self.stats = {
            "messages_received": 0,
            "connection_time": None,
            "last_message_time": None,
            "errors": 0,
            "reconnections": 0,
        }

    def start(self) -> None:
        """Start the WebSocket client in a separate thread"""
        if self.is_running:
            logger.warning("WebSocket client is already running")
            return

        self.is_running = True
        self.websocket_thread = threading.Thread(
            target=self._run_async_loop, daemon=True
        )
        self.websocket_thread.start()

        # Wait for connection to establish
        timeout = 10
        start_time = time.time()
        while not self.is_connected and (time.time() - start_time) < timeout:
            time.sleep(0.1)

        if not self.is_connected:
            logger.error("Failed to establish WebSocket connection within timeout")
        else:
            logger.info("Binance WebSocket client started successfully")

    def stop(self):
        """Stop the WebSocket client"""
        self.is_running = False

        if self.event_loop and not self.event_loop.is_closed():
            asyncio.run_coroutine_threadsafe(self._disconnect(), self.event_loop)

        if self.websocket_thread and self.websocket_thread.is_alive():
            self.websocket_thread.join(timeout=5)

        logger.info("Binance WebSocket client stopped")

    def _run_async_loop(self):
        """Run the async event loop in a separate thread"""
        try:
            self.event_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.event_loop)
            self.event_loop.run_until_complete(self._connect_and_listen())
        except Exception as e:
            logger.error(f"Error in WebSocket event loop: {e}")
        finally:
            if self.event_loop and not self.event_loop.is_closed():
                self.event_loop.close()

    async def _connect_and_listen(self):
        """Main connection and listening loop"""
        while self.is_running:
            try:
                await self._connect()
                if self.is_connected:
                    await self._listen()
            except Exception as e:
                logger.error(f"Error in connect and listen loop: {e}")
                self.stats["errors"] += 1

            if self.is_running:
                await self._handle_reconnection()

    async def _connect(self):
        """Establish WebSocket connection"""
        try:
            url = self.testnet_url if self.config.BINANCE_TESTNET else self.base_url

            logger.info(f"Connecting to Binance WebSocket: {url}")

            self.websocket = await websockets.connect(
                url,
                ping_interval=None,  # We'll handle pings manually
                ping_timeout=10,
                close_timeout=10,
                max_size=1024 * 1024,  # 1MB max message size
                compression=None,
            )

            self.is_connected = True
            self.reconnect_attempts = 0
            self.stats["connection_time"] = datetime.utcnow().isoformat()

            logger.info("WebSocket connection established")

            # Start background tasks
            asyncio.create_task(self._ping_loop())
            asyncio.create_task(self._message_processor())

        except Exception as e:
            logger.error(f"Failed to connect to WebSocket: {e}")
            self.is_connected = False
            raise

    async def _listen(self):
        """Listen for incoming messages"""
        try:
            async for message in self.websocket:
                if not self.is_running:
                    break

                await self.message_queue.put(message)
                self.stats["messages_received"] += 1
                self.stats["last_message_time"] = datetime.utcnow().isoformat()

        except ConnectionClosed as e:
            logger.warning(f"WebSocket connection closed: {e}")
            self.is_connected = False
        except WebSocketException as e:
            logger.error(f"WebSocket error: {e}")
            self.is_connected = False
        except Exception as e:
            logger.error(f"Unexpected error in listen loop: {e}")
            self.is_connected = False

    async def _message_processor(self):
        """Process incoming messages"""
        while self.is_running and self.is_connected:
            try:
                # Wait for message with timeout
                message = await asyncio.wait_for(self.message_queue.get(), timeout=1.0)

                await self._handle_message(message)

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error processing message: {e}")

    async def _handle_message(self, message: str):
        """Handle incoming WebSocket message (Fix: Bug #3 - Complete implementation)"""
        try:
            data = json.loads(message)

            # Handle different message types
            if "stream" in data:
                # Stream data format
                stream_name = data["stream"]
                stream_data = data["data"]
                await self._process_stream_data(stream_name, stream_data)

            elif "e" in data:
                # Event format
                event_type = data["e"]
                await self._process_event(event_type, data)

            elif "id" in data:
                # Response to subscription request
                await self._process_subscription_response(data)

            else:
                # Unknown message format
                logger.warning(f"Unknown message format: {data}")

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse WebSocket message: {e}")
        except Exception as e:
            logger.error(f"Error handling WebSocket message: {e}")

    async def _process_stream_data(self, stream_name: str, data: dict):
        """Process stream data based on stream type"""
        try:
            # Extract symbol and stream type from stream name
            parts = stream_name.split("@")
            if len(parts) >= 2:
                symbol = parts[0].upper()
                stream_type = parts[1]

                # Call appropriate callback based on stream type
                if stream_type.startswith("ticker"):
                    await self._handle_ticker_update(symbol, data)
                elif stream_type.startswith("kline"):
                    await self._handle_kline_update(symbol, data)
                elif stream_type.startswith("depth"):
                    await self._handle_depth_update(symbol, data)
                elif stream_type.startswith("trade"):
                    await self._handle_trade_update(symbol, data)
                else:
                    logger.debug(f"Unhandled stream type: {stream_type}")

        except Exception as e:
            logger.error(f"Error processing stream data: {e}")

    async def _process_event(self, event_type: str, data: dict):
        """Process event-based messages"""
        try:
            if event_type == "24hrTicker":
                symbol = data.get("s", "")
                await self._handle_ticker_update(symbol, data)
            elif event_type == "kline":
                symbol = data.get("s", "")
                await self._handle_kline_update(symbol, data["k"])
            elif event_type == "depthUpdate":
                symbol = data.get("s", "")
                await self._handle_depth_update(symbol, data)
            elif event_type == "trade":
                symbol = data.get("s", "")
                await self._handle_trade_update(symbol, data)
            else:
                logger.debug(f"Unhandled event type: {event_type}")

        except Exception as e:
            logger.error(f"Error processing event: {e}")

    async def _process_subscription_response(self, data: dict):
        """Process subscription response"""
        try:
            result = data.get("result")
            req_id = data.get("id")

            if result is None:
                logger.info(f"Subscription successful for request {req_id}")
            else:
                logger.warning(f"Subscription response for request {req_id}: {result}")

        except Exception as e:
            logger.error(f"Error processing subscription response: {e}")

    async def _handle_ticker_update(self, symbol: str, data: dict):
        """Handle ticker price updates"""
        try:
            callback = self.callbacks.get("ticker")
            if callback:
                await callback(symbol, data)
            else:
                # Default handling - just log
                price = data.get("c", data.get("lastPrice", "N/A"))
                logger.debug(f"Ticker update for {symbol}: {price}")

        except Exception as e:
            logger.error(f"Error handling ticker update: {e}")

    async def _handle_kline_update(self, symbol: str, data: dict):
        """Handle kline/candlestick updates"""
        try:
            callback = self.callbacks.get("kline")
            if callback:
                await callback(symbol, data)
            else:
                # Default handling - just log
                close_price = data.get("c", "N/A")
                logger.debug(f"Kline update for {symbol}: close={close_price}")

        except Exception as e:
            logger.error(f"Error handling kline update: {e}")

    async def _handle_depth_update(self, symbol: str, data: dict):
        """Handle order book depth updates"""
        try:
            callback = self.callbacks.get("depth")
            if callback:
                await callback(symbol, data)
            else:
                # Default handling - just log
                logger.debug(f"Depth update for {symbol}")

        except Exception as e:
            logger.error(f"Error handling depth update: {e}")

    async def _handle_trade_update(self, symbol: str, data: dict):
        """Handle trade execution updates"""
        try:
            callback = self.callbacks.get("trade")
            if callback:
                await callback(symbol, data)
            else:
                # Default handling - just log
                price = data.get("p", "N/A")
                quantity = data.get("q", "N/A")
                logger.debug(
                    f"Trade update for {symbol}: price={price}, qty={quantity}"
                )

        except Exception as e:
            logger.error(f"Error handling trade update: {e}")

    async def _handle_subscription_response(self, data: Dict):
        """Handle subscription response"""
        sub_id = data.get("id")
        if sub_id in self.subscriptions:
            if "result" in data and data["result"] is None:
                logger.info(f"Subscription {sub_id} confirmed")
            elif "error" in data:
                logger.error(f"Subscription {sub_id} failed: {data['error']}")
        else:
            logger.warning(f"Received response for unknown subscription {sub_id}")

    async def _handle_stream_data(self, data: Dict):
        """Handle stream data message"""
        stream_name = data.get("stream")
        stream_data = data.get("data")

        if stream_name in self.callbacks:
            try:
                callback = self.callbacks[stream_name]
                if asyncio.iscoroutinefunction(callback):
                    await callback(stream_data)
                else:
                    callback(stream_data)
            except Exception as e:
                logger.error(f"Error in callback for stream {stream_name}: {e}")

    async def _handle_event_data(self, data: Dict):
        """Handle event data message (single stream)"""
        event_type = data.get("e")

        # Create stream name based on event type and symbol
        symbol = data.get("s", "").lower()
        stream_name = f"{symbol}@{event_type}"

        if stream_name in self.callbacks:
            try:
                callback = self.callbacks[stream_name]
                if asyncio.iscoroutinefunction(callback):
                    await callback(data)
                else:
                    callback(data)
            except Exception as e:
                logger.error(f"Error in callback for event {stream_name}: {e}")

    async def _ping_loop(self):
        """Send periodic pings to keep connection alive"""
        while self.is_running and self.is_connected:
            try:
                await asyncio.sleep(self.ping_interval)

                if self.websocket and not self.websocket.closed:
                    await self.websocket.ping()
                    self.last_ping_time = time.time()
                    logger.debug("Sent WebSocket ping")

            except Exception as e:
                logger.error(f"Error sending ping: {e}")
                break

    async def _handle_reconnection(self) -> None:
        """Handle reconnection logic"""
        if not self.is_running:
            return

        self.reconnect_attempts += 1
        self.stats["reconnections"] += 1

        if self.reconnect_attempts > self.max_reconnect_attempts:
            logger.error("Max reconnection attempts reached, stopping client")
            self.is_running = False
            return

        delay = min(self.reconnect_delay * (2 ** (self.reconnect_attempts - 1)), 300)
        logger.info(
            f"Reconnecting in {delay} seconds (attempt {self.reconnect_attempts})"
        )

        await asyncio.sleep(delay)

    async def _disconnect(self):
        """Disconnect from WebSocket"""
        self.is_connected = False

        if self.websocket and not self.websocket.closed:
            await self.websocket.close()

    def subscribe_ticker(self, symbol: str, callback: Callable[[Dict], None]) -> str:
        """
        Subscribe to 24hr ticker statistics

        Args:
            symbol: Trading pair symbol (e.g., 'btcusdt')
            callback: Function to call when ticker data is received

        Returns:
            Subscription ID
        """
        stream_name = f"{symbol.lower()}@ticker"
        return self._subscribe_stream(stream_name, callback)

    def subscribe_klines(
        self, symbol: str, interval: str, callback: Callable[[Dict], None]
    ) -> str:
        """
        Subscribe to kline/candlestick streams

        Args:
            symbol: Trading pair symbol (e.g., 'btcusdt')
            interval: Kline interval (1s, 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d, 3d, 1w, 1M)
            callback: Function to call when kline data is received

        Returns:
            Subscription ID
        """
        stream_name = f"{symbol.lower()}@kline_{interval}"
        return self._subscribe_stream(stream_name, callback)

    def subscribe_depth(
        self,
        symbol: str,
        levels: int = 20,
        update_speed: str = "100ms",
        callback: Callable[[Dict], None] = None,
    ) -> str:
        """
        Subscribe to partial book depth streams

        Args:
            symbol: Trading pair symbol (e.g., 'btcusdt')
            levels: Number of levels (5, 10, 20)
            update_speed: Update speed (1000ms or 100ms)
            callback: Function to call when depth data is received

        Returns:
            Subscription ID
        """
        stream_name = f"{symbol.lower()}@depth{levels}@{update_speed}"
        return self._subscribe_stream(stream_name, callback)

    def subscribe_trades(self, symbol: str, callback: Callable[[Dict], None]) -> str:
        """
        Subscribe to trade streams

        Args:
            symbol: Trading pair symbol (e.g., 'btcusdt')
            callback: Function to call when trade data is received

        Returns:
            Subscription ID
        """
        stream_name = f"{symbol.lower()}@trade"
        return self._subscribe_stream(stream_name, callback)

    def subscribe_mini_ticker(
        self, symbol: str, callback: Callable[[Dict], None]
    ) -> str:
        """
        Subscribe to individual symbol mini ticker

        Args:
            symbol: Trading pair symbol (e.g., 'btcusdt')
            callback: Function to call when mini ticker data is received

        Returns:
            Subscription ID
        """
        stream_name = f"{symbol.lower()}@miniTicker"
        return self._subscribe_stream(stream_name, callback)

    def subscribe_all_tickers(self, callback: Callable[[List[Dict]], None]) -> str:
        """
        Subscribe to all market tickers

        Args:
            callback: Function to call when ticker array is received

        Returns:
            Subscription ID
        """
        stream_name = "!ticker@arr"
        return self._subscribe_stream(stream_name, callback)

    def _subscribe_stream(self, stream_name: str, callback: Callable) -> str:
        """
        Internal method to subscribe to a stream

        Args:
            stream_name: Name of the stream to subscribe to
            callback: Callback function for the stream

        Returns:
            Subscription ID
        """
        if not self.is_connected:
            logger.error("Cannot subscribe: WebSocket not connected")
            return None

        sub_id = str(self.subscription_id)
        self.subscription_id += 1

        # Store subscription and callback
        self.subscriptions[sub_id] = stream_name
        self.callbacks[stream_name] = callback

        # Send subscription message
        subscription_message = {
            "method": "SUBSCRIBE",
            "params": [stream_name],
            "id": int(sub_id),
        }

        if self.event_loop and not self.event_loop.is_closed():
            asyncio.run_coroutine_threadsafe(
                self._send_message(json.dumps(subscription_message)), self.event_loop
            )

        logger.info(f"Subscribed to stream: {stream_name} (ID: {sub_id})")
        return sub_id

    def unsubscribe(self, subscription_id: str) -> bool:
        """
        Unsubscribe from a stream

        Args:
            subscription_id: ID returned from subscribe method

        Returns:
            True if unsubscribed successfully
        """
        if subscription_id not in self.subscriptions:
            logger.warning(f"Subscription ID {subscription_id} not found")
            return False

        stream_name = self.subscriptions[subscription_id]

        # Send unsubscribe message
        unsubscribe_message = {
            "method": "UNSUBSCRIBE",
            "params": [stream_name],
            "id": int(subscription_id),
        }

        if self.event_loop and not self.event_loop.is_closed():
            asyncio.run_coroutine_threadsafe(
                self._send_message(json.dumps(unsubscribe_message)), self.event_loop
            )

        # Clean up
        del self.subscriptions[subscription_id]
        if stream_name in self.callbacks:
            del self.callbacks[stream_name]

        logger.info(f"Unsubscribed from stream: {stream_name} (ID: {subscription_id})")
        return True

    async def _send_message(self, message: str):
        """Send message to WebSocket"""
        try:
            if self.websocket and not self.websocket.closed:
                await self.websocket.send(message)
            else:
                logger.error("Cannot send message: WebSocket not connected")
        except Exception as e:
            logger.error(f"Error sending message: {e}")

    def get_connection_status(self) -> Dict:
        """Get current connection status and statistics"""
        return {
            "is_connected": self.is_connected,
            "is_running": self.is_running,
            "reconnect_attempts": self.reconnect_attempts,
            "active_subscriptions": len(self.subscriptions),
            "last_ping_time": self.last_ping_time,
            "stats": self.stats.copy(),
        }

    def list_subscriptions(self) -> Dict[str, str]:
        """Get list of active subscriptions"""
        return self.subscriptions.copy()

    def clear_all_subscriptions(self):
        """Clear all subscriptions"""
        for sub_id in list(self.subscriptions.keys()):
            self.unsubscribe(sub_id)

    def get_stream_url(self) -> str:
        """Get the WebSocket stream URL being used"""
        return self.testnet_url if self.config.BINANCE_TESTNET else self.base_url


# Example usage and helper functions


def create_ticker_handler(symbol: str) -> Callable[[Dict], None]:
    """Create a ticker data handler"""

    def handler(data: Dict) -> None:
        logger.info(
            f"Ticker for {symbol}: Price={data.get('c')}, Volume={data.get('v')}"
        )

    return handler


def create_kline_handler(symbol: str, interval: str) -> Callable[[Dict], None]:
    """Create a kline data handler"""

    def handler(data: Dict) -> None:
        kline = data.get("k", {})
        logger.info(
            f"Kline for {symbol} ({interval}): Open={kline.get('o')}, Close={kline.get('c')}"
        )

    return handler


def create_depth_handler(symbol: str) -> Callable[[Dict], None]:
    """Create a depth data handler"""

    def handler(data: Dict) -> None:
        bids = data.get("bids", [])
        asks = data.get("asks", [])
        if bids and asks:
            best_bid = bids[0][0] if bids else "N/A"
            best_ask = asks[0][0] if asks else "N/A"
            logger.info(f"Depth for {symbol}: Best Bid={best_bid}, Best Ask={best_ask}")

    return handler
