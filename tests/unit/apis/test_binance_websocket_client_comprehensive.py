"""
Comprehensive unit tests for BinanceWebSocketClient class.
Tests WebSocket connection, message handling, stream management, and error scenarios.
"""
import pytest
import asyncio
import json
import unittest.mock as mock
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from typing import Dict, Any, List, Optional, Callable
import time
import websockets
from websockets.exceptions import ConnectionClosed, ConnectionClosedError, ConnectionClosedOK

from src.apis.binance_websocket_client import BinanceWebSocketClient


class TestBinanceWebSocketClientInitialization:
    """Test BinanceWebSocketClient initialization scenarios."""

    def test_init_default_params(self):
        """Test initialization with default parameters."""
        client = BinanceWebSocketClient()
        assert client.base_url == "wss://stream.binance.com:9443/ws/"
        assert client.websocket is None
        assert client.is_connected is False
        assert client.callbacks == {}
        assert client._reconnect_attempts == 0
        assert client._max_reconnect_attempts == 5
        assert client._heartbeat_interval == 30

    def test_init_custom_params(self):
        """Test initialization with custom parameters."""
        custom_url = "wss://testnet.binance.vision/ws/"
        client = BinanceWebSocketClient(
            base_url=custom_url,
            max_reconnect_attempts=10,
            heartbeat_interval=60
        )
        assert client.base_url == custom_url
        assert client._max_reconnect_attempts == 10
        assert client._heartbeat_interval == 60

    def test_init_with_callbacks(self):
        """Test initialization with callback functions."""
        def on_ticker(data): pass
        def on_trade(data): pass

        callbacks = {
            "ticker": on_ticker,
            "trade": on_trade
        }

        client = BinanceWebSocketClient(callbacks=callbacks)
        assert client.callbacks == callbacks
        assert "ticker" in client.callbacks
        assert "trade" in client.callbacks


class TestBinanceWebSocketClientConnection:
    """Test WebSocket connection functionality."""

    @pytest.fixture
    def client(self):
        """Create test client instance."""
        return BinanceWebSocketClient()

    @pytest.mark.asyncio
    async def test_connect_success(self, client):
        """Test successful WebSocket connection."""
        with patch('websockets.connect') as mock_connect:
            mock_websocket = AsyncMock()
            mock_connect.return_value.__aenter__.return_value = mock_websocket

            await client.connect()

            assert client.is_connected is True
            assert client.websocket == mock_websocket
            mock_connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_failure(self, client):
        """Test WebSocket connection failure."""
        with patch('websockets.connect') as mock_connect:
            mock_connect.side_effect = ConnectionRefusedError("Connection refused")

            await client.connect()

            assert client.is_connected is False
            assert client.websocket is None

    @pytest.mark.asyncio
    async def test_disconnect_success(self, client):
        """Test successful WebSocket disconnection."""
        mock_websocket = AsyncMock()
        client.websocket = mock_websocket
        client.is_connected = True

        await client.disconnect()

        assert client.is_connected is False
        assert client.websocket is None
        mock_websocket.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_disconnect_when_not_connected(self, client):
        """Test disconnection when not connected."""
        await client.disconnect()

        assert client.is_connected is False
        assert client.websocket is None

    @pytest.mark.asyncio
    async def test_reconnect_logic(self, client):
        """Test automatic reconnection logic."""
        with patch('websockets.connect') as mock_connect, \
             patch('asyncio.sleep') as mock_sleep:

            # First attempt fails, second succeeds
            mock_websocket = AsyncMock()
            mock_connect.side_effect = [
                ConnectionRefusedError("Connection refused"),
                mock_websocket
            ]

            await client._reconnect()

            assert client.is_connected is True
            assert client._reconnect_attempts == 1
            assert mock_connect.call_count == 2
            mock_sleep.assert_called()

    @pytest.mark.asyncio
    async def test_max_reconnect_attempts(self, client):
        """Test maximum reconnection attempts limit."""
        client._max_reconnect_attempts = 2

        with patch('websockets.connect') as mock_connect, \
             patch('asyncio.sleep'):

            mock_connect.side_effect = ConnectionRefusedError("Connection refused")

            await client._reconnect()

            assert client.is_connected is False
            assert client._reconnect_attempts == 2
            assert mock_connect.call_count == 2


class TestBinanceWebSocketClientSubscriptions:
    """Test stream subscription functionality."""

    @pytest.fixture
    def client(self):
        """Create test client instance."""
        return BinanceWebSocketClient()

    @pytest.mark.asyncio
    async def test_subscribe_ticker_stream(self, client):
        """Test subscribing to ticker stream."""
        mock_websocket = AsyncMock()
        client.websocket = mock_websocket
        client.is_connected = True

        await client.subscribe_ticker("BTCUSDT")

        expected_message = json.dumps({
            "method": "SUBSCRIBE",
            "params": ["btcusdt@ticker"],
            "id": 1
        })
        mock_websocket.send.assert_called_with(expected_message)

    @pytest.mark.asyncio
    async def test_subscribe_kline_stream(self, client):
        """Test subscribing to kline stream."""
        mock_websocket = AsyncMock()
        client.websocket = mock_websocket
        client.is_connected = True

        await client.subscribe_kline("ETHUSDT", "1m")

        expected_message = json.dumps({
            "method": "SUBSCRIBE",
            "params": ["ethusdt@kline_1m"],
            "id": 1
        })
        mock_websocket.send.assert_called_with(expected_message)

    @pytest.mark.asyncio
    async def test_subscribe_trade_stream(self, client):
        """Test subscribing to trade stream."""
        mock_websocket = AsyncMock()
        client.websocket = mock_websocket
        client.is_connected = True

        await client.subscribe_trade("ADAUSDT")

        expected_message = json.dumps({
            "method": "SUBSCRIBE",
            "params": ["adausdt@trade"],
            "id": 1
        })
        mock_websocket.send.assert_called_with(expected_message)

    @pytest.mark.asyncio
    async def test_subscribe_depth_stream(self, client):
        """Test subscribing to depth stream."""
        mock_websocket = AsyncMock()
        client.websocket = mock_websocket
        client.is_connected = True

        await client.subscribe_depth("DOTUSDT", "5")

        expected_message = json.dumps({
            "method": "SUBSCRIBE",
            "params": ["dotusdt@depth5"],
            "id": 1
        })
        mock_websocket.send.assert_called_with(expected_message)

    @pytest.mark.asyncio
    async def test_subscribe_when_not_connected(self, client):
        """Test subscription when not connected."""
        client.is_connected = False

        result = await client.subscribe_ticker("BTCUSDT")

        assert result is False

    @pytest.mark.asyncio
    async def test_unsubscribe_stream(self, client):
        """Test unsubscribing from stream."""
        mock_websocket = AsyncMock()
        client.websocket = mock_websocket
        client.is_connected = True

        await client.unsubscribe("btcusdt@ticker")

        expected_message = json.dumps({
            "method": "UNSUBSCRIBE",
            "params": ["btcusdt@ticker"],
            "id": 1
        })
        mock_websocket.send.assert_called_with(expected_message)

    @pytest.mark.asyncio
    async def test_subscribe_multiple_streams(self, client):
        """Test subscribing to multiple streams."""
        mock_websocket = AsyncMock()
        client.websocket = mock_websocket
        client.is_connected = True

        streams = ["btcusdt@ticker", "ethusdt@kline_1m", "adausdt@trade"]
        await client.subscribe_multiple(streams)

        expected_message = json.dumps({
            "method": "SUBSCRIBE",
            "params": streams,
            "id": 1
        })
        mock_websocket.send.assert_called_with(expected_message)


class TestBinanceWebSocketClientMessageHandling:
    """Test message handling and processing."""

    @pytest.fixture
    def client(self):
        """Create test client instance."""
        return BinanceWebSocketClient()

    @pytest.mark.asyncio
    async def test_handle_ticker_message(self, client):
        """Test handling ticker message."""
        ticker_callback = AsyncMock()
        client.callbacks["ticker"] = ticker_callback

        ticker_data = {
            "stream": "btcusdt@ticker",
            "data": {
                "e": "24hrTicker",
                "s": "BTCUSDT",
                "c": "50000.00",
                "h": "51000.00",
                "l": "49000.00",
                "v": "1000.50"
            }
        }

        await client._handle_message(json.dumps(ticker_data))

        ticker_callback.assert_called_once_with(ticker_data["data"])

    @pytest.mark.asyncio
    async def test_handle_kline_message(self, client):
        """Test handling kline message."""
        kline_callback = AsyncMock()
        client.callbacks["kline"] = kline_callback

        kline_data = {
            "stream": "btcusdt@kline_1m",
            "data": {
                "e": "kline",
                "s": "BTCUSDT",
                "k": {
                    "t": 1640995200000,
                    "T": 1640995259999,
                    "s": "BTCUSDT",
                    "i": "1m",
                    "o": "50000.00",
                    "c": "50100.00",
                    "h": "50200.00",
                    "l": "49900.00",
                    "v": "100.50"
                }
            }
        }

        await client._handle_message(json.dumps(kline_data))

        kline_callback.assert_called_once_with(kline_data["data"])

    @pytest.mark.asyncio
    async def test_handle_trade_message(self, client):
        """Test handling trade message."""
        trade_callback = AsyncMock()
        client.callbacks["trade"] = trade_callback

        trade_data = {
            "stream": "btcusdt@trade",
            "data": {
                "e": "trade",
                "s": "BTCUSDT",
                "t": 123456789,
                "p": "50000.00",
                "q": "0.001",
                "T": 1640995200000,
                "m": True
            }
        }

        await client._handle_message(json.dumps(trade_data))

        trade_callback.assert_called_once_with(trade_data["data"])

    @pytest.mark.asyncio
    async def test_handle_depth_message(self, client):
        """Test handling depth message."""
        depth_callback = AsyncMock()
        client.callbacks["depth"] = depth_callback

        depth_data = {
            "stream": "btcusdt@depth5",
            "data": {
                "e": "depthUpdate",
                "s": "BTCUSDT",
                "b": [["50000.00", "0.001"], ["49999.00", "0.002"]],
                "a": [["50001.00", "0.001"], ["50002.00", "0.002"]]
            }
        }

        await client._handle_message(json.dumps(depth_data))

        depth_callback.assert_called_once_with(depth_data["data"])

    @pytest.mark.asyncio
    async def test_handle_invalid_json(self, client):
        """Test handling invalid JSON message."""
        error_callback = AsyncMock()
        client.callbacks["error"] = error_callback

        invalid_message = "invalid json message"

        await client._handle_message(invalid_message)

        # Should not crash and may call error callback
        if error_callback.called:
            error_callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_unknown_stream(self, client):
        """Test handling unknown stream type."""
        unknown_data = {
            "stream": "unknown@stream",
            "data": {"test": "data"}
        }

        # Should not crash
        await client._handle_message(json.dumps(unknown_data))

    @pytest.mark.asyncio
    async def test_handle_subscription_response(self, client):
        """Test handling subscription response messages."""
        response_data = {
            "result": None,
            "id": 1
        }

        # Should handle gracefully
        await client._handle_message(json.dumps(response_data))

    @pytest.mark.asyncio
    async def test_message_processing_with_callback_error(self, client):
        """Test message processing when callback raises error."""
        def failing_callback(data):
            raise Exception("Callback error")

        client.callbacks["ticker"] = failing_callback

        ticker_data = {
            "stream": "btcusdt@ticker",
            "data": {"e": "24hrTicker", "s": "BTCUSDT"}
        }

        # Should not crash the client
        await client._handle_message(json.dumps(ticker_data))


class TestBinanceWebSocketClientListening:
    """Test message listening and event loop functionality."""

    @pytest.fixture
    def client(self):
        """Create test client instance."""
        return BinanceWebSocketClient()

    @pytest.mark.asyncio
    async def test_listen_for_messages(self, client):
        """Test listening for WebSocket messages."""
        mock_websocket = AsyncMock()
        client.websocket = mock_websocket
        client.is_connected = True

        # Mock receiving two messages then disconnection
        messages = [
            json.dumps({"stream": "btcusdt@ticker", "data": {"e": "24hrTicker"}}),
            json.dumps({"stream": "ethusdt@trade", "data": {"e": "trade"}})
        ]
        mock_websocket.__aiter__.return_value = iter(messages)

        ticker_callback = AsyncMock()
        trade_callback = AsyncMock()
        client.callbacks["ticker"] = ticker_callback
        client.callbacks["trade"] = trade_callback

        # Run listen with timeout to prevent infinite loop
        try:
            await asyncio.wait_for(client.listen(), timeout=0.1)
        except asyncio.TimeoutError:
            pass

        assert ticker_callback.called
        assert trade_callback.called

    @pytest.mark.asyncio
    async def test_listen_connection_closed(self, client):
        """Test handling connection closed during listening."""
        mock_websocket = AsyncMock()
        client.websocket = mock_websocket
        client.is_connected = True

        # Mock connection closed exception
        mock_websocket.__aiter__.side_effect = ConnectionClosedOK(None, None)

        with patch.object(client, '_reconnect') as mock_reconnect:
            try:
                await asyncio.wait_for(client.listen(), timeout=0.1)
            except asyncio.TimeoutError:
                pass

            mock_reconnect.assert_called()

    @pytest.mark.asyncio
    async def test_listen_unexpected_error(self, client):
        """Test handling unexpected errors during listening."""
        mock_websocket = AsyncMock()
        client.websocket = mock_websocket
        client.is_connected = True

        # Mock unexpected exception
        mock_websocket.__aiter__.side_effect = Exception("Unexpected error")

        error_callback = AsyncMock()
        client.callbacks["error"] = error_callback

        try:
            await asyncio.wait_for(client.listen(), timeout=0.1)
        except asyncio.TimeoutError:
            pass

        # Should handle gracefully and may call error callback
        assert not client.is_connected


class TestBinanceWebSocketClientHeartbeat:
    """Test heartbeat and ping/pong functionality."""

    @pytest.fixture
    def client(self):
        """Create test client instance."""
        return BinanceWebSocketClient(heartbeat_interval=1)  # 1 second for testing

    @pytest.mark.asyncio
    async def test_heartbeat_ping(self, client):
        """Test sending heartbeat ping."""
        mock_websocket = AsyncMock()
        client.websocket = mock_websocket
        client.is_connected = True

        await client._send_ping()

        mock_websocket.ping.assert_called_once()

    @pytest.mark.asyncio
    async def test_heartbeat_when_disconnected(self, client):
        """Test heartbeat when disconnected."""
        client.is_connected = False

        # Should not crash
        await client._send_ping()

    @pytest.mark.asyncio
    async def test_heartbeat_loop(self, client):
        """Test heartbeat loop functionality."""
        mock_websocket = AsyncMock()
        client.websocket = mock_websocket
        client.is_connected = True

        with patch('asyncio.sleep') as mock_sleep:
            # Run heartbeat loop briefly
            task = asyncio.create_task(client._heartbeat_loop())
            await asyncio.sleep(0.01)  # Let it run briefly
            task.cancel()

            try:
                await task
            except asyncio.CancelledError:
                pass

            mock_websocket.ping.assert_called()


class TestBinanceWebSocketClientPerformance:
    """Test WebSocket client performance and resource usage."""

    @pytest.fixture
    def client(self):
        """Create test client instance."""
        return BinanceWebSocketClient()

    @pytest.mark.asyncio
    async def test_high_frequency_messages(self, client):
        """Test handling high frequency message processing."""
        message_count = 1000
        messages = []
        for i in range(message_count):
            messages.append(json.dumps({
                "stream": "btcusdt@ticker",
                "data": {"e": "24hrTicker", "s": "BTCUSDT", "i": i}
            }))

        processed_count = 0

        async def counter_callback(data):
            nonlocal processed_count
            processed_count += 1

        client.callbacks["ticker"] = counter_callback

        start_time = time.time()
        for message in messages:
            await client._handle_message(message)
        duration = time.time() - start_time

        assert processed_count == message_count
        # Should process 1000 messages in reasonable time (< 1 second)
        assert duration < 1.0

    @pytest.mark.asyncio
    async def test_memory_usage_with_callbacks(self, client):
        """Test memory usage doesn't grow with callback execution."""
        import gc
        import sys

        def test_callback(data):
            # Simple callback that doesn't accumulate data
            pass

        client.callbacks["ticker"] = test_callback

        # Get initial memory usage
        gc.collect()
        initial_objects = len(gc.get_objects())

        # Process many messages
        for i in range(1000):
            message = json.dumps({
                "stream": "btcusdt@ticker",
                "data": {"e": "24hrTicker", "i": i}
            })
            await client._handle_message(message)

        # Check memory usage hasn't grown significantly
        gc.collect()
        final_objects = len(gc.get_objects())

        # Allow some growth but not proportional to message count
        assert final_objects < initial_objects + 100


class TestBinanceWebSocketClientEdgeCases:
    """Test edge cases and error scenarios."""

    @pytest.fixture
    def client(self):
        """Create test client instance."""
        return BinanceWebSocketClient()

    @pytest.mark.asyncio
    async def test_empty_message(self, client):
        """Test handling empty message."""
        await client._handle_message("")
        # Should not crash

    @pytest.mark.asyncio
    async def test_null_message(self, client):
        """Test handling null message."""
        await client._handle_message(None)
        # Should not crash

    @pytest.mark.asyncio
    async def test_malformed_stream_data(self, client):
        """Test handling malformed stream data."""
        malformed_messages = [
            '{"stream": "btcusdt@ticker"}',  # Missing data
            '{"data": {"e": "24hrTicker"}}',  # Missing stream
            '{"stream": "", "data": {}}',     # Empty stream
            '{"stream": null, "data": null}', # Null values
        ]

        for message in malformed_messages:
            await client._handle_message(message)
            # Should not crash

    @pytest.mark.asyncio
    async def test_callback_registration_edge_cases(self, client):
        """Test callback registration edge cases."""
        # Test None callback
        client.callbacks["test"] = None
        message = json.dumps({"stream": "test@stream", "data": {}})
        await client._handle_message(message)

        # Test non-callable callback
        client.callbacks["test"] = "not_callable"
        await client._handle_message(message)

        # Should not crash in either case

    @pytest.mark.asyncio
    async def test_concurrent_operations(self, client):
        """Test concurrent WebSocket operations."""
        mock_websocket = AsyncMock()
        client.websocket = mock_websocket
        client.is_connected = True

        # Concurrent subscriptions
        tasks = [
            client.subscribe_ticker("BTCUSDT"),
            client.subscribe_kline("ETHUSDT", "1m"),
            client.subscribe_trade("ADAUSDT"),
            client.subscribe_depth("DOTUSDT", "5")
        ]

        await asyncio.gather(*tasks)

        # All subscriptions should have been sent
        assert mock_websocket.send.call_count == 4

    @pytest.mark.asyncio
    async def test_subscription_id_increment(self, client):
        """Test subscription ID increments correctly."""
        mock_websocket = AsyncMock()
        client.websocket = mock_websocket
        client.is_connected = True

        await client.subscribe_ticker("BTCUSDT")
        await client.subscribe_kline("ETHUSDT", "1m")

        calls = mock_websocket.send.call_args_list

        # Extract IDs from call arguments
        message1 = json.loads(calls[0][0][0])
        message2 = json.loads(calls[1][0][0])

        assert message1["id"] == 1
        assert message2["id"] == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
