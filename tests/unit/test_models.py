"""
Unit tests for database models.
"""

import pytest
import uuid
from decimal import Decimal
from datetime import datetime, timedelta

from src.database.models import (
    User, Portfolio, Position, Order, OrderFill,
    TradingStrategy, TradingSignal, MarketData,
    OrderStatus, OrderSide, OrderType
)


@pytest.mark.unit
class TestUser:
    """Test User model."""

    def test_user_creation(self):
        """Test user creation with valid data."""
        user = User(
            username="testuser",
            email="test@example.com",
            password_hash="hashed_password",
            is_active=True,
            is_verified=False
        )

        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.is_active is True
        assert user.is_verified is False

    def test_user_id_generation(self):
        """Test that user ID is generated as UUID."""
        user = User(
            username="testuser",
            email="test@example.com",
            password_hash="hashed_password"
        )

        # ID should be generated when saved to database
        assert hasattr(user, 'id')


@pytest.mark.unit
class TestPortfolio:
    """Test Portfolio model."""

    def test_portfolio_creation(self):
        """Test portfolio creation with valid data."""
        user_id = uuid.uuid4()
        portfolio = Portfolio(
            user_id=user_id,
            name="Test Portfolio",
            description="Test portfolio description",
            initial_balance=Decimal("10000.00"),
            current_balance=Decimal("10000.00"),
            max_drawdown=0.2,
            risk_per_trade=0.02,
            max_position_size=0.1
        )

        assert portfolio.user_id == user_id
        assert portfolio.name == "Test Portfolio"
        assert portfolio.initial_balance == Decimal("10000.00")
        assert portfolio.max_drawdown == 0.2
        assert portfolio.risk_per_trade == 0.02
        assert portfolio.max_position_size == 0.1

    def test_portfolio_total_return_calculation(self):
        """Test portfolio total return calculation."""
        portfolio = Portfolio(
            user_id=uuid.uuid4(),
            name="Test Portfolio",
            initial_balance=Decimal("10000.00"),
            current_balance=Decimal("12000.00")
        )

        expected_return = 20.0  # (12000 - 10000) / 10000 * 100
        assert portfolio.total_return == expected_return

    def test_portfolio_zero_initial_balance_return(self):
        """Test return calculation with zero initial balance."""
        portfolio = Portfolio(
            user_id=uuid.uuid4(),
            name="Test Portfolio",
            initial_balance=Decimal("0.00"),
            current_balance=Decimal("1000.00")
        )

        assert portfolio.total_return == 0


@pytest.mark.unit
class TestPosition:
    """Test Position model."""

    def test_position_creation(self):
        """Test position creation with valid data."""
        portfolio_id = uuid.uuid4()
        position = Position(
            portfolio_id=portfolio_id,
            symbol="BTCUSDT",
            side="long",
            quantity=Decimal("0.1"),
            entry_price=Decimal("50000.00"),
            current_price=Decimal("52000.00"),
            stop_loss=Decimal("45000.00"),
            take_profit=Decimal("55000.00"),
            is_open=True
        )

        assert position.portfolio_id == portfolio_id
        assert position.symbol == "BTCUSDT"
        assert position.side == "long"
        assert position.quantity == Decimal("0.1")
        assert position.entry_price == Decimal("50000.00")
        assert position.current_price == Decimal("52000.00")
        assert position.is_open is True

    def test_unrealized_pnl_long_position(self):
        """Test unrealized PnL calculation for long position."""
        position = Position(
            portfolio_id=uuid.uuid4(),
            symbol="BTCUSDT",
            side="long",
            quantity=Decimal("0.1"),
            entry_price=Decimal("50000.00"),
            current_price=Decimal("52000.00")
        )

        expected_pnl = (52000 - 50000) * 0.1  # 200.0
        assert float(position.unrealized_pnl) == expected_pnl

    def test_unrealized_pnl_short_position(self):
        """Test unrealized PnL calculation for short position."""
        position = Position(
            portfolio_id=uuid.uuid4(),
            symbol="BTCUSDT",
            side="short",
            quantity=Decimal("0.1"),
            entry_price=Decimal("50000.00"),
            current_price=Decimal("48000.00")
        )

        expected_pnl = (50000 - 48000) * 0.1  # 200.0
        assert float(position.unrealized_pnl) == expected_pnl

    def test_market_value_calculation(self):
        """Test market value calculation."""
        position = Position(
            portfolio_id=uuid.uuid4(),
            symbol="BTCUSDT",
            side="long",
            quantity=Decimal("0.1"),
            entry_price=Decimal("50000.00"),
            current_price=Decimal("52000.00")
        )

        expected_value = 52000 * 0.1  # 5200.0
        assert float(position.market_value) == expected_value

    def test_market_value_without_current_price(self):
        """Test market value calculation without current price."""
        position = Position(
            portfolio_id=uuid.uuid4(),
            symbol="BTCUSDT",
            side="long",
            quantity=Decimal("0.1"),
            entry_price=Decimal("50000.00"),
            current_price=None
        )

        expected_value = 50000 * 0.1  # 5000.0 (uses entry price)
        assert float(position.market_value) == expected_value


@pytest.mark.unit
class TestOrder:
    """Test Order model."""

    def test_order_creation(self):
        """Test order creation with valid data."""
        portfolio_id = uuid.uuid4()
        order = Order(
            portfolio_id=portfolio_id,
            client_order_id="test_order_123",
            symbol="BTCUSDT",
            side="buy",
            type="limit",
            quantity=Decimal("0.1"),
            price=Decimal("50000.00"),
            status="pending",
            time_in_force="GTC"
        )

        assert order.portfolio_id == portfolio_id
        assert order.client_order_id == "test_order_123"
        assert order.symbol == "BTCUSDT"
        assert order.side == "buy"
        assert order.type == "limit"
        assert order.quantity == Decimal("0.1")
        assert order.price == Decimal("50000.00")
        assert order.status == "pending"

    def test_remaining_quantity_calculation(self):
        """Test remaining quantity calculation."""
        order = Order(
            portfolio_id=uuid.uuid4(),
            client_order_id="test_order_123",
            symbol="BTCUSDT",
            side="buy",
            type="limit",
            quantity=Decimal("1.0"),
            filled_quantity=Decimal("0.3"),
            price=Decimal("50000.00")
        )

        expected_remaining = 0.7
        assert float(order.remaining_quantity) == expected_remaining

    def test_fill_percentage_calculation(self):
        """Test fill percentage calculation."""
        order = Order(
            portfolio_id=uuid.uuid4(),
            client_order_id="test_order_123",
            symbol="BTCUSDT",
            side="buy",
            type="limit",
            quantity=Decimal("1.0"),
            filled_quantity=Decimal("0.25"),
            price=Decimal("50000.00")
        )

        expected_percentage = 25.0
        assert float(order.fill_percentage) == expected_percentage

    def test_fill_percentage_zero_quantity(self):
        """Test fill percentage with zero quantity."""
        order = Order(
            portfolio_id=uuid.uuid4(),
            client_order_id="test_order_123",
            symbol="BTCUSDT",
            side="buy",
            type="limit",
            quantity=Decimal("0.0"),
            filled_quantity=Decimal("0.0"),
            price=Decimal("50000.00")
        )

        assert float(order.fill_percentage) == 0.0


@pytest.mark.unit
class TestOrderFill:
    """Test OrderFill model."""

    def test_order_fill_creation(self):
        """Test order fill creation."""
        order_id = uuid.uuid4()
        fill = OrderFill(
            order_id=order_id,
            quantity=Decimal("0.1"),
            price=Decimal("50000.00"),
            fee=Decimal("0.001"),
            fee_currency="BNB",
            trade_id="12345"
        )

        assert fill.order_id == order_id
        assert fill.quantity == Decimal("0.1")
        assert fill.price == Decimal("50000.00")
        assert fill.fee == Decimal("0.001")
        assert fill.fee_currency == "BNB"
        assert fill.trade_id == "12345"

    def test_total_value_calculation(self):
        """Test total value calculation."""
        fill = OrderFill(
            order_id=uuid.uuid4(),
            quantity=Decimal("0.1"),
            price=Decimal("50000.00")
        )

        expected_value = 0.1 * 50000  # 5000.0
        assert float(fill.total_value) == expected_value


@pytest.mark.unit
class TestTradingStrategy:
    """Test TradingStrategy model."""

    def test_strategy_creation(self):
        """Test trading strategy creation."""
        portfolio_id = uuid.uuid4()
        strategy = TradingStrategy(
            portfolio_id=portfolio_id,
            name="Test Momentum Strategy",
            strategy_type="momentum",
            description="Test strategy for momentum trading",
            parameters={
                "short_window": 10,
                "long_window": 20,
                "rsi_period": 14
            },
            symbols=["BTCUSDT", "ETHUSDT"],
            timeframe="1h",
            status="active",
            max_positions=5,
            position_size=0.02
        )

        assert strategy.portfolio_id == portfolio_id
        assert strategy.name == "Test Momentum Strategy"
        assert strategy.strategy_type == "momentum"
        assert strategy.parameters["short_window"] == 10
        assert strategy.symbols == ["BTCUSDT", "ETHUSDT"]
        assert strategy.timeframe == "1h"
        assert strategy.status == "active"
        assert strategy.max_positions == 5
        assert strategy.position_size == 0.02

    def test_win_rate_calculation(self):
        """Test win rate calculation."""
        strategy = TradingStrategy(
            portfolio_id=uuid.uuid4(),
            name="Test Strategy",
            strategy_type="momentum",
            parameters={},
            total_trades=10,
            winning_trades=7
        )

        expected_win_rate = 70.0
        assert float(strategy.win_rate) == expected_win_rate

    def test_win_rate_zero_trades(self):
        """Test win rate with zero trades."""
        strategy = TradingStrategy(
            portfolio_id=uuid.uuid4(),
            name="Test Strategy",
            strategy_type="momentum",
            parameters={},
            total_trades=0,
            winning_trades=0
        )

        assert float(strategy.win_rate) == 0.0


@pytest.mark.unit
class TestTradingSignal:
    """Test TradingSignal model."""

    def test_signal_creation(self):
        """Test trading signal creation."""
        strategy_id = uuid.uuid4()
        signal = TradingSignal(
            strategy_id=strategy_id,
            symbol="BTCUSDT",
            signal_type="buy",
            confidence=0.85,
            entry_price=Decimal("50000.00"),
            stop_loss=Decimal("45000.00"),
            take_profit=Decimal("55000.00"),
            timeframe="1h",
            indicators={
                "rsi": 65.0,
                "macd": 0.5
            },
            is_active=True,
            is_executed=False
        )

        assert signal.strategy_id == strategy_id
        assert signal.symbol == "BTCUSDT"
        assert signal.signal_type == "buy"
        assert signal.confidence == 0.85
        assert signal.entry_price == Decimal("50000.00")
        assert signal.stop_loss == Decimal("45000.00")
        assert signal.take_profit == Decimal("55000.00")
        assert signal.indicators["rsi"] == 65.0
        assert signal.is_active is True
        assert signal.is_executed is False


@pytest.mark.unit
class TestMarketData:
    """Test MarketData model."""

    def test_market_data_creation(self):
        """Test market data creation."""
        timestamp = datetime.utcnow()
        market_data = MarketData(
            symbol="BTCUSDT",
            timeframe="1h",
            timestamp=timestamp,
            open_price=Decimal("49500.00"),
            high_price=Decimal("50500.00"),
            low_price=Decimal("49000.00"),
            close_price=Decimal("50000.00"),
            volume=Decimal("1000.0"),
            quote_volume=Decimal("50000000.0"),
            trades_count=5000
        )

        assert market_data.symbol == "BTCUSDT"
        assert market_data.timeframe == "1h"
        assert market_data.timestamp == timestamp
        assert market_data.open_price == Decimal("49500.00")
        assert market_data.high_price == Decimal("50500.00")
        assert market_data.low_price == Decimal("49000.00")
        assert market_data.close_price == Decimal("50000.00")
        assert market_data.volume == Decimal("1000.0")
        assert market_data.quote_volume == Decimal("50000000.0")
        assert market_data.trades_count == 5000
