"""
Unit tests for repository classes.
"""

import pytest
import uuid
from decimal import Decimal
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

from src.database.repositories import (
    UserRepository, PortfolioRepository, PositionRepository,
    OrderRepository, TradingStrategyRepository, MarketDataRepository
)
from src.database.models import User, Portfolio, Position, Order, TradingStrategy, MarketData


@pytest.mark.unit
@pytest.mark.asyncio
class TestUserRepository:
    """Test UserRepository class."""

    async def test_create_user(self, test_session):
        """Test user creation."""
        repo = UserRepository(test_session)

        user_data = {
            "username": "newuser",
            "email": "newuser@example.com",
            "password_hash": "$2b$12$test_hash",
            "is_active": True
        }

        user = await repo.create(user_data)

        assert user.username == "newuser"
        assert user.email == "newuser@example.com"
        assert user.is_active is True
        assert user.id is not None

    async def test_create_duplicate_user(self, test_session):
        """Test creating user with duplicate username/email."""
        repo = UserRepository(test_session)

        user_data = {
            "username": "duplicate",
            "email": "duplicate@example.com",
            "password_hash": "$2b$12$test_hash"
        }

        # Create first user
        await repo.create(user_data)

        # Try to create duplicate - should raise ValueError
        with pytest.raises(ValueError, match="Username or email already exists"):
            await repo.create(user_data)

    async def test_get_by_id(self, test_session, test_user):
        """Test getting user by ID."""
        repo = UserRepository(test_session)

        found_user = await repo.get_by_id(test_user.id)

        assert found_user is not None
        assert found_user.id == test_user.id
        assert found_user.username == test_user.username

    async def test_get_by_username(self, test_session, test_user):
        """Test getting user by username."""
        repo = UserRepository(test_session)

        found_user = await repo.get_by_username(test_user.username)

        assert found_user is not None
        assert found_user.id == test_user.id
        assert found_user.username == test_user.username

    async def test_get_by_email(self, test_session, test_user):
        """Test getting user by email."""
        repo = UserRepository(test_session)

        found_user = await repo.get_by_email(test_user.email)

        assert found_user is not None
        assert found_user.id == test_user.id
        assert found_user.email == test_user.email

    async def test_update_user(self, test_session, test_user):
        """Test updating user."""
        repo = UserRepository(test_session)

        updates = {"email": "updated@example.com"}
        success = await repo.update(test_user.id, updates)

        assert success is True

        # Verify update
        updated_user = await repo.get_by_id(test_user.id)
        assert updated_user.email == "updated@example.com"

    async def test_update_last_login(self, test_session, test_user):
        """Test updating last login time."""
        repo = UserRepository(test_session)

        success = await repo.update_last_login(test_user.id)

        assert success is True

        # Verify update
        updated_user = await repo.get_by_id(test_user.id)
        assert updated_user.last_login is not None

    async def test_deactivate_user(self, test_session, test_user):
        """Test deactivating user."""
        repo = UserRepository(test_session)

        success = await repo.deactivate(test_user.id)

        assert success is True

        # Verify deactivation
        updated_user = await repo.get_by_id(test_user.id)
        assert updated_user.is_active is False


@pytest.mark.unit
@pytest.mark.asyncio
class TestPortfolioRepository:
    """Test PortfolioRepository class."""

    async def test_create_portfolio(self, test_session, test_user):
        """Test portfolio creation."""
        repo = PortfolioRepository(test_session)

        portfolio_data = {
            "user_id": test_user.id,
            "name": "New Portfolio",
            "description": "Test portfolio",
            "initial_balance": Decimal("5000.00"),
            "current_balance": Decimal("5000.00")
        }

        portfolio = await repo.create(portfolio_data)

        assert portfolio.name == "New Portfolio"
        assert portfolio.user_id == test_user.id
        assert portfolio.initial_balance == Decimal("5000.00")
        assert portfolio.id is not None

    async def test_get_by_id(self, test_session, test_portfolio):
        """Test getting portfolio by ID."""
        repo = PortfolioRepository(test_session)

        found_portfolio = await repo.get_by_id(test_portfolio.id)

        assert found_portfolio is not None
        assert found_portfolio.id == test_portfolio.id
        assert found_portfolio.name == test_portfolio.name

    async def test_get_user_portfolios(self, test_session, test_user, test_portfolio):
        """Test getting user portfolios."""
        repo = PortfolioRepository(test_session)

        # Create another portfolio
        portfolio_data = {
            "user_id": test_user.id,
            "name": "Second Portfolio",
            "initial_balance": Decimal("3000.00"),
            "current_balance": Decimal("3000.00")
        }
        await repo.create(portfolio_data)

        portfolios = await repo.get_user_portfolios(test_user.id)

        assert len(portfolios) == 2
        assert all(p.user_id == test_user.id for p in portfolios)

    async def test_update_balance(self, test_session, test_portfolio):
        """Test updating portfolio balance."""
        repo = PortfolioRepository(test_session)

        new_balance = Decimal("12000.00")
        success = await repo.update_balance(test_portfolio.id, new_balance)

        assert success is True

        # Verify update
        updated_portfolio = await repo.get_by_id(test_portfolio.id)
        assert updated_portfolio.current_balance == new_balance

    async def test_update_pnl(self, test_session, test_portfolio):
        """Test updating portfolio PnL."""
        repo = PortfolioRepository(test_session)

        pnl_change = Decimal("500.00")
        success = await repo.update_pnl(test_portfolio.id, pnl_change)

        assert success is True

        # Verify update
        updated_portfolio = await repo.get_by_id(test_portfolio.id)
        assert updated_portfolio.total_pnl == pnl_change

    async def test_get_portfolio_summary(self, test_session, test_portfolio, test_position):
        """Test getting portfolio summary."""
        repo = PortfolioRepository(test_session)

        summary = await repo.get_portfolio_summary(test_portfolio.id)

        assert summary is not None
        assert "portfolio" in summary
        assert "position_value" in summary
        assert "open_positions" in summary
        assert "recent_orders" in summary
        assert "total_value" in summary

        assert summary["portfolio"].id == test_portfolio.id
        assert summary["open_positions"] == 1


@pytest.mark.unit
@pytest.mark.asyncio
class TestPositionRepository:
    """Test PositionRepository class."""

    async def test_create_position(self, test_session, test_portfolio):
        """Test position creation."""
        repo = PositionRepository(test_session)

        position_data = {
            "portfolio_id": test_portfolio.id,
            "symbol": "ETHUSDT",
            "side": "long",
            "quantity": Decimal("5.0"),
            "entry_price": Decimal("3000.00"),
            "is_open": True
        }

        position = await repo.create(position_data)

        assert position.symbol == "ETHUSDT"
        assert position.portfolio_id == test_portfolio.id
        assert position.quantity == Decimal("5.0")
        assert position.is_open is True
        assert position.id is not None

    async def test_get_open_positions(self, test_session, test_portfolio, test_position):
        """Test getting open positions."""
        repo = PositionRepository(test_session)

        # Create another open position
        position_data = {
            "portfolio_id": test_portfolio.id,
            "symbol": "ETHUSDT",
            "side": "long",
            "quantity": Decimal("2.0"),
            "entry_price": Decimal("3000.00"),
            "is_open": True
        }
        await repo.create(position_data)

        # Create closed position
        closed_position_data = {
            "portfolio_id": test_portfolio.id,
            "symbol": "ADAUSDT",
            "side": "long",
            "quantity": Decimal("1000.0"),
            "entry_price": Decimal("1.00"),
            "is_open": False
        }
        await repo.create(closed_position_data)

        open_positions = await repo.get_open_positions(test_portfolio.id)

        assert len(open_positions) == 2  # Only open positions
        assert all(pos.is_open for pos in open_positions)

    async def test_get_open_positions_by_symbol(self, test_session, test_portfolio, test_position):
        """Test getting open positions for specific symbol."""
        repo = PositionRepository(test_session)

        positions = await repo.get_open_positions(test_portfolio.id, "BTCUSDT")

        assert len(positions) == 1
        assert positions[0].symbol == "BTCUSDT"

    async def test_update_current_price(self, test_session, test_position):
        """Test updating position's current price."""
        repo = PositionRepository(test_session)

        new_price = Decimal("55000.00")
        success = await repo.update_current_price(test_position.id, new_price)

        assert success is True

        # Verify update
        updated_position = await repo.get_by_id(test_position.id)
        assert updated_position.current_price == new_price

    async def test_close_position(self, test_session, test_position):
        """Test closing a position."""
        repo = PositionRepository(test_session)

        exit_price = Decimal("53000.00")
        success = await repo.close_position(test_position.id, exit_price)

        assert success is True

        # Verify closure
        updated_position = await repo.get_by_id(test_position.id)
        assert updated_position.is_open is False
        assert updated_position.current_price == exit_price
        assert updated_position.closed_at is not None

    async def test_get_portfolio_exposure(self, test_session, test_portfolio, test_position):
        """Test getting portfolio exposure."""
        repo = PositionRepository(test_session)

        # Create another position with same symbol
        position_data = {
            "portfolio_id": test_portfolio.id,
            "symbol": "BTCUSDT",
            "side": "long",
            "quantity": Decimal("0.05"),
            "entry_price": Decimal("51000.00"),
            "is_open": True
        }
        await repo.create(position_data)

        exposure = await repo.get_portfolio_exposure(test_portfolio.id)

        assert "BTCUSDT" in exposure
        assert exposure["BTCUSDT"]["quantity"] == 0.15  # 0.1 + 0.05
        assert exposure["BTCUSDT"]["count"] == 2


@pytest.mark.unit
@pytest.mark.asyncio
class TestOrderRepository:
    """Test OrderRepository class."""

    async def test_create_order(self, test_session, test_portfolio):
        """Test order creation."""
        repo = OrderRepository(test_session)

        order_data = {
            "portfolio_id": test_portfolio.id,
            "symbol": "ETHUSDT",
            "side": "buy",
            "type": "limit",
            "quantity": Decimal("2.0"),
            "price": Decimal("3000.00"),
            "status": "pending"
        }

        order = await repo.create(order_data)

        assert order.symbol == "ETHUSDT"
        assert order.portfolio_id == test_portfolio.id
        assert order.quantity == Decimal("2.0")
        assert order.client_order_id is not None  # Auto-generated
        assert order.id is not None

    async def test_get_by_client_id(self, test_session, test_order):
        """Test getting order by client ID."""
        repo = OrderRepository(test_session)

        found_order = await repo.get_by_client_id(test_order.client_order_id)

        assert found_order is not None
        assert found_order.id == test_order.id
        assert found_order.client_order_id == test_order.client_order_id

    async def test_update_status(self, test_session, test_order):
        """Test updating order status."""
        repo = OrderRepository(test_session)

        success = await repo.update_status(
            test_order.id,
            "filled",
            executed_at=datetime.utcnow()
        )

        assert success is True

        # Verify update
        updated_order = await repo.get_by_id(test_order.id)
        assert updated_order.status == "filled"
        assert updated_order.executed_at is not None

    async def test_add_fill(self, test_session, test_order):
        """Test adding fill to order."""
        repo = OrderRepository(test_session)

        fill_data = {
            "quantity": Decimal("0.05"),
            "price": Decimal("50100.00"),
            "fee": Decimal("0.001"),
            "fee_currency": "BNB"
        }

        fill = await repo.add_fill(test_order.id, fill_data)

        assert fill.quantity == Decimal("0.05")
        assert fill.order_id == test_order.id

        # Verify order filled quantity updated
        updated_order = await repo.get_by_id(test_order.id)
        assert updated_order.filled_quantity == Decimal("0.05")

    async def test_get_portfolio_orders(self, test_session, test_portfolio, test_order):
        """Test getting portfolio orders."""
        repo = OrderRepository(test_session)

        # Create another order
        order_data = {
            "portfolio_id": test_portfolio.id,
            "client_order_id": "test_order_2",
            "symbol": "ETHUSDT",
            "side": "sell",
            "type": "market",
            "quantity": Decimal("1.0"),
            "status": "filled"
        }
        await repo.create(order_data)

        orders = await repo.get_portfolio_orders(test_portfolio.id)

        assert len(orders) == 2
        assert all(order.portfolio_id == test_portfolio.id for order in orders)

    async def test_get_portfolio_orders_by_status(self, test_session, test_portfolio, test_order):
        """Test getting portfolio orders by status."""
        repo = OrderRepository(test_session)

        orders = await repo.get_portfolio_orders(test_portfolio.id, status="pending")

        assert len(orders) == 1
        assert orders[0].status == "pending"


@pytest.mark.unit
@pytest.mark.asyncio
class TestTradingStrategyRepository:
    """Test TradingStrategyRepository class."""

    async def test_create_strategy(self, test_session, test_portfolio):
        """Test strategy creation."""
        repo = TradingStrategyRepository(test_session)

        strategy_data = {
            "portfolio_id": test_portfolio.id,
            "name": "New Test Strategy",
            "strategy_type": "mean_reversion",
            "description": "Test mean reversion strategy",
            "parameters": {
                "rsi_period": 14,
                "rsi_overbought": 70,
                "rsi_oversold": 30
            },
            "symbols": ["BTCUSDT"],
            "timeframe": "4h",
            "status": "active"
        }

        strategy = await repo.create(strategy_data)

        assert strategy.name == "New Test Strategy"
        assert strategy.strategy_type == "mean_reversion"
        assert strategy.portfolio_id == test_portfolio.id
        assert strategy.parameters["rsi_period"] == 14
        assert strategy.id is not None

    async def test_get_active_strategies(self, test_session, test_strategy):
        """Test getting active strategies."""
        repo = TradingStrategyRepository(test_session)

        # Create inactive strategy
        inactive_strategy_data = {
            "portfolio_id": test_strategy.portfolio_id,
            "name": "Inactive Strategy",
            "strategy_type": "scalping",
            "parameters": {},
            "status": "stopped"
        }
        await repo.create(inactive_strategy_data)

        active_strategies = await repo.get_active_strategies()

        assert len(active_strategies) == 1
        assert active_strategies[0].status == "active"

    async def test_update_performance(self, test_session, test_strategy):
        """Test updating strategy performance."""
        repo = TradingStrategyRepository(test_session)

        performance_data = {
            "total_trades": 10,
            "winning_trades": 7,
            "total_pnl": Decimal("500.00"),
            "max_drawdown": 0.05,
            "sharpe_ratio": 1.2
        }

        success = await repo.update_performance(test_strategy.id, performance_data)

        assert success is True

        # Verify update
        updated_strategy = await repo.get_by_id(test_strategy.id)
        assert updated_strategy.total_trades == 10
        assert updated_strategy.winning_trades == 7
        assert updated_strategy.total_pnl == Decimal("500.00")

    async def test_add_signal(self, test_session, test_strategy):
        """Test adding trading signal."""
        repo = TradingStrategyRepository(test_session)

        signal_data = {
            "strategy_id": test_strategy.id,
            "symbol": "BTCUSDT",
            "signal_type": "buy",
            "confidence": 0.85,
            "entry_price": Decimal("50000.00"),
            "timeframe": "1h",
            "indicators": {"rsi": 65.0}
        }

        signal = await repo.add_signal(signal_data)

        assert signal.symbol == "BTCUSDT"
        assert signal.signal_type == "buy"
        assert signal.confidence == 0.85
        assert signal.strategy_id == test_strategy.id

        # Verify strategy last_signal updated
        updated_strategy = await repo.get_by_id(test_strategy.id)
        assert updated_strategy.last_signal is not None


@pytest.mark.unit
@pytest.mark.asyncio
class TestMarketDataRepository:
    """Test MarketDataRepository class."""

    async def test_upsert_new_data(self, test_session):
        """Test inserting new market data."""
        repo = MarketDataRepository(test_session)

        market_data = {
            "symbol": "BTCUSDT",
            "timeframe": "1h",
            "timestamp": datetime.utcnow(),
            "open_price": Decimal("50000.00"),
            "high_price": Decimal("51000.00"),
            "low_price": Decimal("49000.00"),
            "close_price": Decimal("50500.00"),
            "volume": Decimal("1000.0")
        }

        data_point = await repo.upsert_ohlcv(market_data)

        assert data_point.symbol == "BTCUSDT"
        assert data_point.close_price == Decimal("50500.00")
        assert data_point.id is not None

    async def test_upsert_existing_data(self, test_session):
        """Test updating existing market data."""
        repo = MarketDataRepository(test_session)

        timestamp = datetime.utcnow()

        # Insert initial data
        initial_data = {
            "symbol": "BTCUSDT",
            "timeframe": "1h",
            "timestamp": timestamp,
            "open_price": Decimal("50000.00"),
            "high_price": Decimal("51000.00"),
            "low_price": Decimal("49000.00"),
            "close_price": Decimal("50500.00"),
            "volume": Decimal("1000.0")
        }

        first_point = await repo.upsert_ohlcv(initial_data)
        first_id = first_point.id

        # Update with new data
        updated_data = {
            "symbol": "BTCUSDT",
            "timeframe": "1h",
            "timestamp": timestamp,
            "open_price": Decimal("50000.00"),
            "high_price": Decimal("52000.00"),  # Updated
            "low_price": Decimal("48000.00"),   # Updated
            "close_price": Decimal("51000.00"), # Updated
            "volume": Decimal("1200.0")         # Updated
        }

        updated_point = await repo.upsert_ohlcv(updated_data)

        # Should be same record, just updated
        assert updated_point.id == first_id
        assert updated_point.high_price == Decimal("52000.00")
        assert updated_point.close_price == Decimal("51000.00")
        assert updated_point.volume == Decimal("1200.0")

    async def test_get_ohlcv(self, test_session, sample_ohlcv_data):
        """Test getting OHLCV data."""
        repo = MarketDataRepository(test_session)

        # Insert sample data
        for data in sample_ohlcv_data:
            data.update({"symbol": "BTCUSDT", "timeframe": "1h"})
            await repo.upsert_ohlcv(data)

        start_time = sample_ohlcv_data[0]["timestamp"]
        end_time = sample_ohlcv_data[-1]["timestamp"]

        ohlcv_data = await repo.get_ohlcv("BTCUSDT", "1h", start_time, end_time)

        assert len(ohlcv_data) == len(sample_ohlcv_data)
        assert all(data.symbol == "BTCUSDT" for data in ohlcv_data)
        assert all(data.timeframe == "1h" for data in ohlcv_data)

    async def test_get_latest_price(self, test_session, sample_ohlcv_data):
        """Test getting latest price."""
        repo = MarketDataRepository(test_session)

        # Insert sample data
        for data in sample_ohlcv_data:
            data.update({"symbol": "BTCUSDT", "timeframe": "1m"})
            await repo.upsert_ohlcv(data)

        latest_price = await repo.get_latest_price("BTCUSDT", "1m")

        assert latest_price is not None
        # Should be the close price of the last (most recent) data point
        expected_price = sample_ohlcv_data[-1]["close_price"]
        assert latest_price == expected_price
