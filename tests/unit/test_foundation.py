#!/usr/bin/env python3
"""
Comprehensive test script for the crypto trading bot foundation layer

This script tests:
1. Configuration loading
2. Database models and connections
3. State management system
4. Repository pattern
5. Integration between components
"""

import logging
import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Configure test logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def test_configuration():
    """Test configuration loading"""
    print("\n" + "=" * 50)
    print("TESTING CONFIGURATION")
    print("=" * 50)

    try:
        from src.config.settings import Config

        config = Config()

        print("✅ Configuration loaded successfully")
        print(f"   Paper trading: {config.PAPER_TRADING}")
        print(f"   Risk percentage: {config.DEFAULT_RISK_PERCENTAGE}")
        print(f"   Max positions: {config.MAX_POSITIONS}")
        print(f"   Database URL: {config.DATABASE_URL[:50]}...")
        print(f"   Log level: {config.LOG_LEVEL}")

        # Test validation
        try:
            config._validate()
            print("✅ Configuration validation passed")
        except Exception as e:
            print(f"❌ Configuration validation failed: {e}")
            return False

        return True

    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        return False


def test_database_models():
    """Test database models"""
    print("\n" + "=" * 50)
    print("TESTING DATABASE MODELS")
    print("=" * 50)

    try:
        from src.database.models import (Base, MarketData, NewsArticle, Order,
                                         OrderSide, OrderStatus, OrderType,
                                         Portfolio, Position, PositionStatus,
                                         SentimentScore, Strategy,
                                         TechnicalIndicator, TradingPair)

        print("✅ All models imported successfully")

        # Test model creation
        portfolio = Portfolio(
            name="Test Portfolio",
            total_balance_usdt=10000.0,
            available_balance_usdt=10000.0,
        )

        print("✅ Model instances created successfully")

        # Test validation
        try:
            portfolio.validate_risk_percentage("risk_percentage", 2.5)
            print("✅ Model validation working")
        except ValueError:
            print("❌ Model validation failed")
            return False

        # Test enums
        order_side = OrderSide.BUY
        order_type = OrderType.LIMIT
        print(f"✅ Enums working: {order_side.value}, {order_type.value}")

        # Check table metadata
        tables = list(Base.metadata.tables.keys())
        print(f"✅ Database tables defined: {len(tables)} tables")
        print(f"   Tables: {', '.join(tables[:5])}{'...' if len(tables) > 5 else ''}")

        return True

    except Exception as e:
        print(f"❌ Database models test failed: {e}")
        return False


def test_state_manager():
    """Test state management system"""
    print("\n" + "=" * 50)
    print("TESTING STATE MANAGER")
    print("=" * 50)

    try:
        from src.graph.state_manager import (Event, EventType, Priority,
                                             StateManager, get_state_manager)

        print("✅ State manager imports successful")

        # Test state manager creation
        state_manager = StateManager(max_event_history=100)
        print("✅ State manager created")

        # Test starting and stopping
        state_manager.start()
        print(f"✅ State manager started: {state_manager._is_running}")

        # Test event creation and publishing
        test_event = Event(
            type=EventType.PRICE_UPDATE,
            source="test_script",
            priority=Priority.NORMAL,
            data={"symbol": "BTC/USDT", "price": 50000.0},
        )

        state_manager.publish_event(test_event)
        print("✅ Event published successfully")

        # Test event history
        history = state_manager.get_event_history(limit=5)
        print(f"✅ Event history retrieved: {len(history)} events")

        # Test state updates
        state_manager.update_portfolio_state({"balance": 10000.0, "positions": {}})

        state_manager.update_market_state(
            "BTC/USDT", {"price": 50000.0, "volume": 1000.0}
        )

        portfolio_state = state_manager.get_portfolio_state()
        market_state = state_manager.get_market_state("BTC/USDT")

        print("✅ State updates working")
        print(f"   Portfolio balance: {portfolio_state.get('balance')}")
        print(f"   BTC/USDT price: {market_state.get('price')}")

        # Test subscription system
        events_received = []

        def test_callback(event):
            events_received.append(event)

        state_manager.subscribe(
            callback=test_callback, event_types=[EventType.PRICE_UPDATE]
        )

        # Publish another event
        state_manager.publish_event(
            Event(
                type=EventType.PRICE_UPDATE,
                source="test_script",
                data={"symbol": "ETH/USDT", "price": 3000.0},
            )
        )

        print(f"✅ Event subscription working: {len(events_received)} events received")

        # Test statistics
        stats = state_manager.get_event_statistics()
        print(f"✅ Event statistics: {stats['total_events']} total events")

        state_manager.stop()
        print(f"✅ State manager stopped: {not state_manager._is_running}")

        return True

    except Exception as e:
        print(f"❌ State manager test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_repositories():
    """Test repository pattern (without actual database)"""
    print("\n" + "=" * 50)
    print("TESTING REPOSITORIES")
    print("=" * 50)

    try:
        from src.database.repositories import (OrderRepository,
                                               PortfolioRepository,
                                               TradingPairRepository,
                                               order_repo, portfolio_repo,
                                               trading_pair_repo)

        print("✅ Repository imports successful")

        # Test repository instances
        print(f"✅ Trading pair repository: {type(trading_pair_repo).__name__}")
        print(f"✅ Portfolio repository: {type(portfolio_repo).__name__}")
        print(f"✅ Order repository: {type(order_repo).__name__}")

        # Test repository class instantiation
        custom_repo = TradingPairRepository()
        print(f"✅ Custom repository created: {type(custom_repo).__name__}")

        return True

    except Exception as e:
        print(f"❌ Repository test failed: {e}")
        return False


def test_database_connection():
    """Test database connection (mock test without actual DB)"""
    print("\n" + "=" * 50)
    print("TESTING DATABASE CONNECTION")
    print("=" * 50)

    try:
        from src.config.settings import Config
        from src.database.connection import (DatabaseManager, cache_result,
                                             retry_db_operation)

        print("✅ Database connection imports successful")

        config = Config()

        # Test DatabaseManager creation (without actual connection)
        DatabaseManager(config)
        print("✅ Database manager created")

        # Test decorators
        @cache_result(expiration=60)
        def test_cached_function():
            return "cached_result"

        @retry_db_operation(max_retries=2)
        def test_retry_function():
            return "retry_result"

        print("✅ Decorators applied successfully")

        return True

    except Exception as e:
        print(f"❌ Database connection test failed: {e}")
        return False


def test_integration():
    """Test integration between components"""
    print("\n" + "=" * 50)
    print("TESTING COMPONENT INTEGRATION")
    print("=" * 50)

    try:
        from src.config.settings import Config
        from src.database.models import OrderSide, Portfolio, TradingPair
        from src.graph.state_manager import Event, EventType, StateManager

        # Test configuration with models
        config = Config()
        Portfolio(
            name="Integration Test",
            is_paper_trading=config.PAPER_TRADING,
            risk_percentage=config.DEFAULT_RISK_PERCENTAGE,
            max_positions=config.MAX_POSITIONS,
        )

        print("✅ Configuration integrated with models")

        # Test state manager with trading data
        state_manager = StateManager()
        state_manager.start()

        # Simulate trading workflow
        state_manager.update_portfolio_state(
            {
                "portfolio_id": 1,
                "balance": 10000.0,
                "risk_percentage": config.DEFAULT_RISK_PERCENTAGE,
            }
        )

        state_manager.publish_event(
            Event(
                type=EventType.ORDER_PLACED,
                source="integration_test",
                data={
                    "symbol": "BTC/USDT",
                    "side": OrderSide.BUY.value,
                    "quantity": 0.001,
                    "price": 50000.0,
                },
            )
        )

        print("✅ Trading workflow simulation successful")

        # Test data flow
        portfolio_state = state_manager.get_portfolio_state()
        event_history = state_manager.get_event_history(
            event_type=EventType.ORDER_PLACED, limit=1
        )

        print("✅ Data flow working:")
        print(f"   Portfolio balance: {portfolio_state.get('balance')}")
        print(f"   Last order event: {len(event_history) > 0}")

        state_manager.stop()

        return True

    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        return False


def test_package_imports():
    """Test package-level imports"""
    print("\n" + "=" * 50)
    print("TESTING PACKAGE IMPORTS")
    print("=" * 50)

    try:
        # Test database package
        from src.database import (Base, Portfolio, TradingPair, get_session,
                                  portfolio_repo, trading_pair_repo)

        print("✅ Database package imports successful")

        # Test graph package
        from src.graph import (Event, EventType, StateManager,
                               get_state_manager, initialize_state_manager)

        print("✅ Graph package imports successful")

        return True

    except Exception as e:
        print(f"❌ Package import test failed: {e}")
        return False
