"""
Comprehensive integration tests for trading workflows.
Tests end-to-end trading scenarios, component integration, and real-world workflows.
"""
import pytest
import asyncio
import unittest.mock as mock
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from decimal import Decimal
import time
import json
from typing import Dict, Any, List
from sqlalchemy import text

from src.apis.binance_client import BinanceClient
from src.apis.news_api_client import NewsAPIClient
from src.apis.binance_websocket_client import BinanceWebSocketClient
from src.execution.trade_validator import TradeValidator
from src.database.connection import DatabaseManager
from src.config.settings import Config


class TestTradingWorkflowIntegration:
    """Test complete trading workflow integration."""

    @pytest.fixture
    def mock_binance_client(self):
        """Create mock Binance client."""
        client = Mock(spec=BinanceClient)
        client.get_account_balance.return_value = {
            "BTC": {"free": "1.0", "locked": "0.0"},
            "USDT": {"free": "50000.0", "locked": "0.0"}
        }
        client.get_symbol_info.return_value = {
            "symbol": "BTCUSDT",
            "status": "TRADING",
            "filters": [
                {"filterType": "LOT_SIZE", "minQty": "0.00001", "stepSize": "0.00001"},
                {"filterType": "PRICE_FILTER", "minPrice": "0.01", "tickSize": "0.01"},
                {"filterType": "MIN_NOTIONAL", "minNotional": "10.0"}
            ]
        }
        client.place_order.return_value = {
            "orderId": 12345,
            "symbol": "BTCUSDT",
            "status": "FILLED",
            "executedQty": "0.001",
            "cummulativeQuoteQty": "50.0"
        }
        return client

    @pytest.fixture
    def mock_news_client(self):
        """Create mock news API client."""
        client = Mock(spec=NewsAPIClient)
        client.get_crypto_news.return_value = [
            {
                "title": "Bitcoin hits new high",
                "description": "BTC reaches $50,000",
                "source": {"name": "CryptoNews"},
                "publishedAt": "2024-01-15T10:00:00Z",
                "category": "price"
            }
        ]
        return client

    @pytest.fixture
    def mock_websocket_client(self):
        """Create mock WebSocket client."""
        client = Mock(spec=BinanceWebSocketClient)
        client.connect = AsyncMock()
        client.subscribe_ticker = AsyncMock(return_value=True)
        client.is_connected = True
        return client

    @pytest.fixture
    def db_connection(self):
        """Create test database connection."""
        config = Config()
        config.DATABASE_URL = "sqlite:///:memory:"
        db_manager = DatabaseManager(config)
        db_manager.initialize()
        return db_manager

    @pytest.fixture
    def trade_validator(self, mock_binance_client):
        """Create trade validator."""
        return TradeValidator(mock_binance_client)

    def test_complete_buy_workflow(self, mock_binance_client, trade_validator, db_connection):
        """Test complete buy order workflow."""
        # Step 1: Validate order
        order = {
            "symbol": "BTCUSDT",
            "side": "BUY",
            "type": "LIMIT",
            "quantity": 0.001,
            "price": 50000.0
        }

        validation_result = trade_validator.validate_order(order)
        assert validation_result["valid"]

        # Step 2: Place order
        order_result = mock_binance_client.place_order(
            symbol=order["symbol"],
            side=order["side"],
            type=order["type"],
            quantity=order["quantity"],
            price=order["price"]
        )

        assert order_result["status"] == "FILLED"
        assert order_result["symbol"] == "BTCUSDT"

        # Step 3: Store trade in database
        with db_connection.get_session() as session:
            # Create test table
            session.execute(text("""
                CREATE TABLE IF NOT EXISTS test_trades (
                    id INTEGER PRIMARY KEY,
                    symbol TEXT,
                    side TEXT,
                    quantity TEXT,
                    price TEXT,
                    order_id TEXT
                )
            """))

            # Insert trade record
            session.execute(text("""
                INSERT INTO test_trades (symbol, side, quantity, price, order_id)
                VALUES (:symbol, :side, :quantity, :price, :order_id)
            """), {
                "symbol": order["symbol"],
                "side": order["side"],
                "quantity": str(order["quantity"]),
                "price": str(order["price"]),
                "order_id": str(order_result["orderId"])
            })
            session.commit()

            # Verify trade stored
            result = session.execute(text("SELECT symbol, side, order_id FROM test_trades WHERE order_id = :order_id"),
                                   {"order_id": str(order_result["orderId"])}).fetchone()
            assert result[0] == "BTCUSDT"
            assert result[1] == "BUY"
            assert result[2] == "12345"

    def test_signal_to_trade_workflow(self, mock_binance_client, mock_news_client,
                                    trade_validator, db_connection):
        """Test workflow from signal generation to trade execution."""
        # Step 1: Generate signal from news
        news = mock_news_client.get_crypto_news("bitcoin", limit=10)
        assert len(news) > 0

        # Step 2: Create trading signal
        with db_connection.get_session() as session:
            # Create signals table
            session.execute(text("""
                CREATE TABLE IF NOT EXISTS test_signals (
                    id INTEGER PRIMARY KEY,
                    symbol TEXT,
                    signal_type TEXT,
                    strength REAL,
                    source TEXT,
                    timestamp INTEGER
                )
            """))

            # Insert signal
            session.execute(text("""
                INSERT INTO test_signals (symbol, signal_type, strength, source, timestamp)
                VALUES (:symbol, :signal_type, :strength, :source, :timestamp)
            """), {
                "symbol": "BTCUSDT",
                "signal_type": "BUY",
                "strength": 0.8,
                "source": "news_analysis",
                "timestamp": int(time.time() * 1000)
            })
            session.commit()

            signal_id = session.execute(text("SELECT last_insert_rowid()")).scalar()

            # Step 3: Convert signal to order
            order = {
                "symbol": "BTCUSDT",
                "side": "BUY",
                "type": "MARKET",
                "quantity": 0.001
            }

            # Step 4: Validate and execute order
            validation = trade_validator.validate_order(order)
            assert validation["valid"]

            order_result = mock_binance_client.place_order(
                symbol=order["symbol"],
                side=order["side"],
                type=order["type"],
                quantity=order["quantity"]
            )

            # Step 5: Record trade execution
            session.execute(text("""
                CREATE TABLE IF NOT EXISTS test_trades (
                    id INTEGER PRIMARY KEY,
                    symbol TEXT,
                    side TEXT,
                    quantity TEXT,
                    price TEXT,
                    order_id TEXT,
                    signal_id INTEGER
                )
            """))

            session.execute(text("""
                INSERT INTO test_trades (symbol, side, quantity, price, order_id, signal_id)
                VALUES (:symbol, :side, :quantity, :price, :order_id, :signal_id)
            """), {
                "symbol": order["symbol"],
                "side": order["side"],
                "quantity": str(order["quantity"]),
                "price": "50000.0",
                "order_id": str(order_result["orderId"]),
                "signal_id": signal_id
            })
            session.commit()

            # Verify workflow completion
            signal_result = session.execute(text("SELECT symbol, signal_type FROM test_signals WHERE id = :id"),
                                          {"id": signal_id}).fetchone()
            trade_result = session.execute(text("SELECT symbol, side FROM test_trades WHERE signal_id = :id"),
                                         {"id": signal_id}).fetchone()
            assert signal_result[0] == trade_result[0]
            assert signal_result[1] == trade_result[1]

    @pytest.mark.asyncio
    async def test_real_time_trading_workflow(self, mock_binance_client, mock_websocket_client,
                                            trade_validator, db_connection):
        """Test real-time trading workflow with WebSocket data."""
        executed_trades = []

        def trade_callback(data):
            """Mock trade execution callback."""
            executed_trades.append(data)

        # Step 1: Connect to WebSocket
        await mock_websocket_client.connect()
        assert mock_websocket_client.is_connected

        # Step 2: Subscribe to ticker updates
        await mock_websocket_client.subscribe_ticker("BTCUSDT")

        # Step 3: Simulate incoming ticker data
        ticker_data = {
            "e": "24hrTicker",
            "s": "BTCUSDT",
            "c": "51000.00",  # Current price
            "h": "52000.00",  # High
            "l": "49000.00",  # Low
            "v": "1000.50"    # Volume
        }

        # Step 4: Process price update and make trading decision
        current_price = float(ticker_data["c"])
        if current_price > 50000:  # Simple trading logic
            order = {
                "symbol": "BTCUSDT",
                "side": "SELL",
                "type": "LIMIT",
                "quantity": 0.0005,
                "price": current_price
            }

            # Step 5: Validate and execute order
            validation = trade_validator.validate_order(order)
            assert validation["valid"]

            order_result = mock_binance_client.place_order(
                symbol=order["symbol"],
                side=order["side"],
                type=order["type"],
                quantity=order["quantity"],
                price=order["price"]
            )

            trade_callback(order_result)

            # Step 6: Store in database
            with db_connection.get_session() as session:
                session.execute(text("""
                    CREATE TABLE IF NOT EXISTS test_trades (
                        id INTEGER PRIMARY KEY,
                        symbol TEXT,
                        side TEXT,
                        quantity TEXT,
                        price TEXT,
                        order_id TEXT
                    )
                """))

                session.execute(text("""
                    INSERT INTO test_trades (symbol, side, quantity, price, order_id)
                    VALUES (:symbol, :side, :quantity, :price, :order_id)
                """), {
                    "symbol": order["symbol"],
                    "side": order["side"],
                    "quantity": str(order["quantity"]),
                    "price": str(order["price"]),
                    "order_id": str(order_result["orderId"])
                })
                session.commit()

        # Verify workflow execution
        assert len(executed_trades) == 1
        assert executed_trades[0]["symbol"] == "BTCUSDT"

    def test_portfolio_management_workflow(self, mock_binance_client, db_connection):
        """Test portfolio management and balance tracking workflow."""
        # Step 1: Get current balances
        balances = mock_binance_client.get_account_balance()

        # Step 2: Store portfolio state
        with db_connection.get_session() as session:
            session.execute(text("""
                CREATE TABLE IF NOT EXISTS test_portfolio (
                    id INTEGER PRIMARY KEY,
                    asset TEXT,
                    balance TEXT,
                    locked TEXT,
                    timestamp INTEGER
                )
            """))

            for asset, balance_info in balances.items():
                session.execute(text("""
                    INSERT INTO test_portfolio (asset, balance, locked, timestamp)
                    VALUES (:asset, :balance, :locked, :timestamp)
                """), {
                    "asset": asset,
                    "balance": balance_info["free"],
                    "locked": balance_info["locked"],
                    "timestamp": int(time.time() * 1000)
                })
            session.commit()

            # Step 3: Execute trade that affects portfolio
            order = {
                "symbol": "BTCUSDT",
                "side": "BUY",
                "type": "MARKET",
                "quantity": 0.001
            }

            order_result = mock_binance_client.place_order(
                symbol=order["symbol"],
                side=order["side"],
                type=order["type"],
                quantity=order["quantity"]
            )

            # Step 4: Update portfolio after trade
            session.execute(text("""
                UPDATE test_portfolio
                SET balance = :new_balance
                WHERE asset = 'BTC'
            """), {"new_balance": "1.001"})

            session.execute(text("""
                UPDATE test_portfolio
                SET balance = :new_balance
                WHERE asset = 'USDT'
            """), {"new_balance": "49950.0"})

            session.commit()

            # Step 5: Record trade
            session.execute(text("""
                CREATE TABLE IF NOT EXISTS test_trades (
                    id INTEGER PRIMARY KEY,
                    symbol TEXT,
                    side TEXT,
                    quantity TEXT,
                    price TEXT,
                    order_id TEXT
                )
            """))

            session.execute(text("""
                INSERT INTO test_trades (symbol, side, quantity, price, order_id)
                VALUES (:symbol, :side, :quantity, :price, :order_id)
            """), {
                "symbol": order["symbol"],
                "side": order["side"],
                "quantity": str(order["quantity"]),
                "price": "50000.0",
                "order_id": str(order_result["orderId"])
            })
            session.commit()

            # Verify portfolio update
            btc_balance = session.execute(text("SELECT balance FROM test_portfolio WHERE asset = 'BTC'")).scalar()
            usdt_balance = session.execute(text("SELECT balance FROM test_portfolio WHERE asset = 'USDT'")).scalar()
            assert btc_balance == "1.001"
            assert usdt_balance == "49950.0"


class TestErrorHandlingIntegration:
    """Test error handling across integrated components."""

    @pytest.fixture
    def mock_binance_client(self):
        """Create mock Binance client with error scenarios."""
        client = Mock(spec=BinanceClient)
        return client

    @pytest.fixture
    def db_connection(self):
        """Create test database connection."""
        config = Config()
        config.DATABASE_URL = "sqlite:///:memory:"
        db_manager = DatabaseManager(config)
        db_manager.initialize()
        return db_manager

    def test_api_error_handling_workflow(self, mock_binance_client, db_connection):
        """Test workflow when API errors occur."""
        # Configure client to simulate API error
        mock_binance_client.get_symbol_info.side_effect = Exception("API Error")
        mock_binance_client.place_order.side_effect = Exception("Order failed")

        trade_validator = TradeValidator(mock_binance_client)

        # Attempt trade validation - should handle gracefully
        validation = trade_validator.validate_quantity("BTCUSDT", 0.001)
        assert not validation["valid"]
        assert "error" in validation

        # Log error to database
        with db_connection.get_session() as session:
            session.execute(text("""
                CREATE TABLE IF NOT EXISTS test_errors (
                    id INTEGER PRIMARY KEY,
                    error_type TEXT,
                    message TEXT,
                    timestamp INTEGER
                )
            """))

            session.execute(text("""
                INSERT INTO test_errors (error_type, message, timestamp)
                VALUES (:error_type, :message, :timestamp)
            """), {
                "error_type": "API_ERROR",
                "message": "API connection failed",
                "timestamp": int(time.time() * 1000)
            })
            session.commit()

            # Verify error logged
            error_count = session.execute(text("SELECT COUNT(*) FROM test_errors WHERE error_type = 'API_ERROR'")).scalar()
            assert error_count == 1


class TestPerformanceIntegration:
    """Test performance of integrated workflows."""

    @pytest.fixture
    def mock_binance_client(self):
        """Create high-performance mock client."""
        client = Mock(spec=BinanceClient)
        client.get_symbol_info.return_value = {
            "symbol": "BTCUSDT",
            "filters": [
                {"filterType": "LOT_SIZE", "minQty": "0.00001", "stepSize": "0.00001"},
                {"filterType": "PRICE_FILTER", "minPrice": "0.01", "tickSize": "0.01"}
            ]
        }
        client.place_order.return_value = {"orderId": 12345, "status": "FILLED"}
        return client

    @pytest.fixture
    def db_connection(self):
        """Create test database connection."""
        config = Config()
        config.DATABASE_URL = "sqlite:///:memory:"
        db_manager = DatabaseManager(config)
        db_manager.initialize()
        return db_manager

    def test_high_frequency_trading_workflow(self, mock_binance_client, db_connection):
        """Test high-frequency trading workflow performance."""
        trade_validator = TradeValidator(mock_binance_client)

        start_time = time.time()

        with db_connection.get_session() as session:
            # Create tables
            session.execute(text("""
                CREATE TABLE IF NOT EXISTS test_signals (
                    id INTEGER PRIMARY KEY,
                    symbol TEXT,
                    signal_type TEXT,
                    timestamp INTEGER
                )
            """))

            session.execute(text("""
                CREATE TABLE IF NOT EXISTS test_trades (
                    id INTEGER PRIMARY KEY,
                    symbol TEXT,
                    side TEXT,
                    quantity TEXT,
                    order_id TEXT
                )
            """))

            for i in range(100):  # Simulate 100 rapid trades
                # Generate signal
                session.execute(text("""
                    INSERT INTO test_signals (symbol, signal_type, timestamp)
                    VALUES (:symbol, :signal_type, :timestamp)
                """), {
                    "symbol": "BTCUSDT",
                    "signal_type": "BUY" if i % 2 == 0 else "SELL",
                    "timestamp": int(time.time() * 1000) + i
                })

                # Validate and execute order
                order = {
                    "symbol": "BTCUSDT",
                    "side": "BUY" if i % 2 == 0 else "SELL",
                    "type": "MARKET",
                    "quantity": 0.001
                }

                validation = trade_validator.validate_order(order)
                if validation["valid"]:
                    order_result = mock_binance_client.place_order(
                        symbol=order["symbol"],
                        side=order["side"],
                        type=order["type"],
                        quantity=order["quantity"]
                    )

                    # Record trade
                    session.execute(text("""
                        INSERT INTO test_trades (symbol, side, quantity, order_id)
                        VALUES (:symbol, :side, :quantity, :order_id)
                    """), {
                        "symbol": order["symbol"],
                        "side": order["side"],
                        "quantity": str(order["quantity"]),
                        "order_id": f"{order_result['orderId']}_{i}"
                    })

            session.commit()

        duration = time.time() - start_time

        # Should process 100 trades in reasonable time (< 2 seconds)
        assert duration < 2.0

        # Verify all trades recorded
        with db_connection.get_session() as session:
            trade_count = session.execute(text("SELECT COUNT(*) FROM test_trades")).scalar()
            signal_count = session.execute(text("SELECT COUNT(*) FROM test_signals")).scalar()
            assert trade_count == 100
            assert signal_count == 100


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
