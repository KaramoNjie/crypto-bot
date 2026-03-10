"""
Pytest configuration and fixtures for the crypto trading bot tests.
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, Mock

import pytest
import pytest_asyncio
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from src.database.models import Base, User, Portfolio, Position, Order, TradingStrategy
from src.database import get_db_session_context
from src.config.production_settings import ProductionConfig


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def test_db_engine():
    """Create test database engine."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        echo=False
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    await engine.dispose()


@pytest.fixture
async def test_session(test_db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session."""
    async_session = async_sessionmaker(
        test_db_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    async with async_session() as session:
        yield session


@pytest.fixture
def test_config():
    """Create test configuration."""
    return ProductionConfig(
        environment="testing",
        debug=True,
        database=ProductionConfig.DatabaseConfig(
            url="sqlite:///:memory:",
            async_url="sqlite+aiosqlite:///:memory:",
            pool_size=1,
            max_overflow=0
        ),
        binance=ProductionConfig.BinanceConfig(
            api_key="test_api_key",
            secret_key="test_secret_key",
            testnet=True
        ),
        logging=ProductionConfig.LoggingConfig(
            level="DEBUG",
            format="json"
        )
    )


@pytest.fixture
async def test_user(test_session: AsyncSession) -> User:
    """Create test user."""
    user = User(
        username="testuser",
        email="test@example.com",
        password_hash="$2b$12$test_hash",
        is_active=True,
        is_verified=True
    )
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)
    return user


@pytest.fixture
async def test_portfolio(test_session: AsyncSession, test_user: User) -> Portfolio:
    """Create test portfolio."""
    portfolio = Portfolio(
        user_id=test_user.id,
        name="Test Portfolio",
        description="Test portfolio for testing",
        initial_balance=Decimal("10000.00"),
        current_balance=Decimal("10000.00"),
        max_drawdown=0.2,
        risk_per_trade=0.02,
        max_position_size=0.1
    )
    test_session.add(portfolio)
    await test_session.commit()
    await test_session.refresh(portfolio)
    return portfolio


@pytest.fixture
async def test_position(test_session: AsyncSession, test_portfolio: Portfolio) -> Position:
    """Create test position."""
    position = Position(
        portfolio_id=test_portfolio.id,
        symbol="BTCUSDT",
        side="long",
        quantity=Decimal("0.1"),
        entry_price=Decimal("50000.00"),
        current_price=Decimal("52000.00"),
        is_open=True
    )
    test_session.add(position)
    await test_session.commit()
    await test_session.refresh(position)
    return position


@pytest.fixture
async def test_order(test_session: AsyncSession, test_portfolio: Portfolio) -> Order:
    """Create test order."""
    order = Order(
        portfolio_id=test_portfolio.id,
        client_order_id=f"test_order_{uuid.uuid4().hex[:12]}",
        symbol="BTCUSDT",
        side="buy",
        type="limit",
        quantity=Decimal("0.1"),
        price=Decimal("50000.00"),
        status="pending"
    )
    test_session.add(order)
    await test_session.commit()
    await test_session.refresh(order)
    return order


@pytest.fixture
async def test_strategy(test_session: AsyncSession, test_portfolio: Portfolio) -> TradingStrategy:
    """Create test trading strategy."""
    strategy = TradingStrategy(
        portfolio_id=test_portfolio.id,
        name="Test Momentum Strategy",
        strategy_type="momentum",
        description="Test momentum strategy",
        parameters={
            "short_window": 10,
            "long_window": 20,
            "rsi_period": 14,
            "rsi_overbought": 70,
            "rsi_oversold": 30
        },
        symbols=["BTCUSDT", "ETHUSDT"],
        timeframe="1h",
        status="active",
        max_positions=5,
        position_size=0.02
    )
    test_session.add(strategy)
    await test_session.commit()
    await test_session.refresh(strategy)
    return strategy


@pytest.fixture
def mock_binance_client():
    """Mock Binance API client."""
    client = AsyncMock()

    # Mock market data
    client.get_ticker_price.return_value = {
        "symbol": "BTCUSDT",
        "price": "50000.00"
    }

    client.get_klines.return_value = [
        [1640995200000, "49000.00", "51000.00", "48000.00", "50000.00", "100.0"],
        [1640995260000, "50000.00", "52000.00", "49000.00", "51000.00", "120.0"],
    ]

    # Mock order operations
    client.create_order.return_value = {
        "orderId": 12345,
        "clientOrderId": "test_order_123",
        "symbol": "BTCUSDT",
        "status": "NEW",
        "executedQty": "0.0",
        "fills": []
    }

    client.get_order.return_value = {
        "orderId": 12345,
        "status": "FILLED",
        "executedQty": "0.1",
        "fills": [{
            "price": "50000.00",
            "qty": "0.1",
            "commission": "0.001",
            "commissionAsset": "BNB"
        }]
    }

    # Mock account info
    client.get_account.return_value = {
        "balances": [
            {"asset": "USDT", "free": "10000.0", "locked": "0.0"},
            {"asset": "BTC", "free": "0.1", "locked": "0.0"}
        ]
    }

    return client


@pytest.fixture
def mock_market_data():
    """Mock market data for testing."""
    return {
        "BTCUSDT": {
            "price": Decimal("50000.00"),
            "change_24h": 2.5,
            "volume": Decimal("1000000"),
            "high_24h": Decimal("52000.00"),
            "low_24h": Decimal("48000.00")
        },
        "ETHUSDT": {
            "price": Decimal("3000.00"),
            "change_24h": -1.2,
            "volume": Decimal("500000"),
            "high_24h": Decimal("3100.00"),
            "low_24h": Decimal("2900.00")
        }
    }


@pytest.fixture
def mock_technical_indicators():
    """Mock technical indicators data."""
    return {
        "rsi": 65.0,
        "macd": 0.5,
        "macd_signal": 0.3,
        "macd_histogram": 0.2,
        "sma_20": Decimal("49500.00"),
        "sma_50": Decimal("48000.00"),
        "bb_upper": Decimal("52000.00"),
        "bb_lower": Decimal("47000.00"),
        "volume_ratio": 1.5
    }


@pytest.fixture
def sample_ohlcv_data():
    """Sample OHLCV data for testing."""
    base_time = datetime.utcnow() - timedelta(hours=24)
    data = []

    for i in range(24):  # 24 hours of hourly data
        timestamp = base_time + timedelta(hours=i)
        price = 50000 + (i * 100)  # Trending up

        data.append({
            "timestamp": timestamp,
            "open_price": Decimal(str(price)),
            "high_price": Decimal(str(price + 200)),
            "low_price": Decimal(str(price - 200)),
            "close_price": Decimal(str(price + 100)),
            "volume": Decimal("1000.0")
        })

    return data


@pytest.fixture
def mock_risk_manager():
    """Mock risk manager for testing."""
    manager = Mock()

    manager.calculate_position_size.return_value = Decimal("0.02")  # 2% position size
    manager.check_risk_limits.return_value = True
    manager.calculate_stop_loss.return_value = Decimal("45000.00")
    manager.calculate_take_profit.return_value = Decimal("55000.00")

    return manager


@pytest.fixture
async def cleanup_database(test_session: AsyncSession):
    """Cleanup database after tests."""
    yield

    # Clean up all tables
    for table in reversed(Base.metadata.sorted_tables):
        await test_session.execute(table.delete())
    await test_session.commit()


# Pytest markers
pytest.mark.unit = pytest.mark.unit
pytest.mark.integration = pytest.mark.integration
pytest.mark.slow = pytest.mark.slow
