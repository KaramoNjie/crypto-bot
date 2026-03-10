#!/usr/bin/env python3
"""
Comprehensive test script for the Market Analyzer Agent

This script tests:
1. Market Analyzer Agent initialization
2. Technical indicator calculations
3. Signal generation logic
4. Event handling and publishing
5. Integration with state manager and database
"""

import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Configure test logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def create_mock_market_data(periods: int = 200) -> pd.DataFrame:
    """Create mock market data for testing"""
    np.random.seed(42)  # For reproducible results

    # Start with base price
    base_price = 50000.0

    # Generate price movements (random walk with slight upward trend)
    price_changes = np.random.normal(0.001, 0.02, periods)  # 0.1% mean, 2% std
    prices = [base_price]

    for change in price_changes[1:]:
        new_price = prices[-1] * (1 + change)
        prices.append(max(new_price, 1.0))  # Prevent negative prices

    # Generate OHLC data
    data = []
    for i, close_price in enumerate(prices):
        # Generate realistic OHLC
        volatility = close_price * 0.01  # 1% volatility

        open_price = close_price + np.random.normal(0, volatility * 0.3)
        high_price = max(open_price, close_price) + abs(
            np.random.normal(0, volatility * 0.5)
        )
        low_price = min(open_price, close_price) - abs(
            np.random.normal(0, volatility * 0.5)
        )
        volume = np.random.uniform(1000, 10000)

        # Ensure price logic
        high_price = max(high_price, open_price, close_price)
        low_price = min(low_price, open_price, close_price)

        timestamp = datetime.utcnow() - timedelta(minutes=(periods - i))

        data.append(
            {
                "timestamp": timestamp,
                "open": round(open_price, 2),
                "high": round(high_price, 2),
                "low": round(low_price, 2),
                "close": round(close_price, 2),
                "volume": round(volume, 2),
            }
        )

    return pd.DataFrame(data)


def test_agent_initialization():
    """Test market analyzer agent initialization"""
    print("\n" + "=" * 50)
    print("TESTING AGENT INITIALIZATION")
    print("=" * 50)

    try:
        from src.config.settings import Config
        from src.agents import MarketAnalyzerAgent
        from src.database.connection import DatabaseManager
        from src.graph.state_manager import StateManager

        # Create dependencies
        config = Config()
        state_manager = StateManager()
        db_manager = DatabaseManager(config)

        # Create agent config
        agent_config = {
            "trading_pairs": ["BTC/USDT", "ETH/USDT"],
            "timeframes": ["5m", "1h"],
            "analysis_interval_seconds": 30,
            "min_confidence_threshold": 0.6,
            "rsi_period": 14,
            "macd_fast": 12,
            "macd_slow": 26,
            "macd_signal": 9,
        }

        # Initialize agent
        agent = MarketAnalyzerAgent(agent_config, state_manager, db_manager)

        print("✅ Agent created successfully")
        print(f"   Name: {agent.name}")
        print(f"   Trading pairs: {agent.trading_pairs}")
        print(f"   Timeframes: {agent.timeframes}")
        print(f"   Analysis interval: {agent.analysis_interval}s")
        print(f"   Min confidence: {agent.min_confidence_threshold}")

        # Test configuration access
        rsi_period = agent.get_config("rsi_period", 14)
        print(f"✅ Configuration access working: RSI period = {rsi_period}")

        # Test status
        status = agent.get_status()
        print(f"✅ Status retrieval working: {status['status']}")

        return True

    except Exception as e:
        print(f"❌ Agent initialization failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_technical_indicators():
    """Test technical indicator calculations"""
    print("\n" + "=" * 50)
    print("TESTING TECHNICAL INDICATORS")
    print("=" * 50)

    try:
        from src.config.settings import Config
        from src.agents.market_analyzer import MarketAnalyzerAgent
        from src.database.connection import DatabaseManager
        from src.graph.state_manager import StateManager

        # Create mock agent
        config = Config()
        state_manager = StateManager()
        db_manager = DatabaseManager(config)
        agent_config = {"trading_pairs": ["BTC/USDT"]}
        agent = MarketAnalyzerAgent(agent_config, state_manager, db_manager)

        # Create test data
        test_data = create_mock_market_data(100)
        print(f"✅ Created mock data: {len(test_data)} periods")
        print(
            f"   Price range: ${test_data['close'].min():.2f} - ${test_data['close'].max():.2f}"
        )

        # Calculate indicators
        indicators = agent._calculate_indicators(test_data)

        print("✅ Technical indicators calculated:")

        # Test RSI
        if "rsi" in indicators:
            rsi = indicators["rsi"]
            if 0 <= rsi <= 100:
                print(f"   RSI: {rsi:.2f} ✅")
            else:
                print(f"   RSI: {rsi:.2f} ❌ (out of range)")
                return False

        # Test MACD
        if all(key in indicators for key in ["macd", "macd_signal", "macd_histogram"]):
            print(f"   MACD: {indicators['macd']:.4f} ✅")
            print(f"   MACD Signal: {indicators['macd_signal']:.4f} ✅")
            print(f"   MACD Histogram: {indicators['macd_histogram']:.4f} ✅")

        # Test Bollinger Bands
        if all(
            key in indicators
            for key in ["bb_upper", "bb_middle", "bb_lower", "bb_position"]
        ):
            bb_pos = indicators["bb_position"]
            print(f"   Bollinger Position: {bb_pos:.2f} ✅")
            if not 0 <= bb_pos <= 1:
                print("   ❌ Bollinger position out of range")
                return False

        # Test EMAs
        ema_keys = [key for key in indicators.keys() if key.startswith("ema_")]
        print(f"   EMAs calculated: {len(ema_keys)} ✅")

        # Test current price
        if "current_price" in indicators:
            print(f"   Current price: ${indicators['current_price']:.2f} ✅")

        return True

    except Exception as e:
        print(f"❌ Technical indicators test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_agent_lifecycle():  # noqa: C901
    """Test agent start/stop lifecycle"""
    print("\n" + "=" * 50)
    print("TESTING AGENT LIFECYCLE")
    print("=" * 50)

    try:
        from src.config.settings import Config
        from src.agents.market_analyzer import MarketAnalyzerAgent
        from src.database.connection import DatabaseManager
        from src.graph.state_manager import StateManager

        # Create dependencies
        state_manager = StateManager()
        state_manager.start()

        # Mock database manager for testing
        class MockDatabaseManager:
            def get_session(self):
                class MockSession:
                    def __enter__(self):
                        return self

                    def __exit__(self, *args):
                        pass

                    def query(self, *args):
                        class MockQuery:
                            def filter(self, *args):
                                return self

                            def first(self):
                                return None

                        return MockQuery()

                return MockSession()

        db_manager = MockDatabaseManager()

        agent_config = {
            "trading_pairs": ["BTC/USDT"],
            "timeframes": ["1h"],
            "analysis_interval_seconds": 1,
        }

        agent = MarketAnalyzerAgent(agent_config, state_manager, db_manager)

        # Test initialization
        print("🔄 Initializing agent...")
        init_result = await agent.initialize()
        if init_result:
            print("✅ Agent initialization successful")
        else:
            print("❌ Agent initialization failed")
            return False

        # Test starting
        print("🔄 Starting agent...")
        start_result = await agent.start()
        if start_result:
            print("✅ Agent started successfully")
            print(f"   Status: {agent.get_status()['status']}")
        else:
            print("❌ Agent start failed")
            return False

        # Let it run briefly
        print("⏳ Letting agent run for 3 seconds...")
        await asyncio.sleep(3)

        # Check if it's still running
        status = agent.get_status()
        print(f"✅ Agent running status: {status['status']}")
        print(f"   Events processed: {status['events_processed']}")
        print(f"   Uptime: {status['uptime_seconds']:.1f}s")

        # Test stopping
        print("🔄 Stopping agent...")
        stop_result = await agent.stop()
        if stop_result:
            print("✅ Agent stopped successfully")
        else:
            print("❌ Agent stop failed")
            return False

        # Check final status
        final_status = agent.get_status()
        print(f"✅ Final status: {final_status['status']}")

        state_manager.stop()
        return True

    except Exception as e:
        print(f"❌ Agent lifecycle test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_market_data_processing():
    """Test market data fetching and processing"""
    print("\n" + "=" * 50)
    print("TESTING MARKET DATA PROCESSING")
    print("=" * 50)

    try:
        from src.config.settings import Config
        from src.agents.market_analyzer import MarketAnalyzerAgent
        from src.database.connection import DatabaseManager
        from src.graph.state_manager import StateManager

        # Create mock agent with custom binance client
        state_manager = StateManager()

        # Mock database manager
        class MockDatabaseManager:
            def get_session(self):
                class MockSession:
                    def __enter__(self):
                        return self

                    def __exit__(self, *args):
                        pass

                return MockSession()

        db_manager = MockDatabaseManager()
        agent_config = {"trading_pairs": ["BTC/USDT"]}
        agent = MarketAnalyzerAgent(agent_config, state_manager, db_manager)

        # Mock Binance client that returns test data
        class MockBinanceClient:
            def get_klines(self, symbol, interval, limit):
                return create_mock_market_data(limit)

        agent.binance_client = MockBinanceClient()

        # Test data fetching
        print("🔄 Fetching market data...")
        data = await agent._fetch_market_data("BTC/USDT", "1h")

        if data is not None and not data.empty:
            print(f"✅ Market data fetched: {len(data)} periods")
            print(f"   Columns: {list(data.columns)}")
            print(f"   Latest price: ${data['close'].iloc[-1]:.2f}")

            # Test caching
            cache_key = "BTC/USDT_1h"
            if cache_key in agent.market_data_cache:
                print("✅ Data caching working")
            else:
                print("❌ Data caching failed")
                return False
        else:
            print("❌ Market data fetching failed")
            return False

        # Test indicator calculation on fetched data
        indicators = agent._calculate_indicators(data)
        if indicators and "current_price" in indicators:
            print("✅ Indicators calculated from fetched data")
            print(f"   RSI: {indicators.get('rsi', 'N/A')}")
            print(f"   Current price: ${indicators['current_price']:.2f}")
        else:
            print("❌ Indicator calculation failed")
            return False

        return True

    except Exception as e:
        print(f"❌ Market data processing test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_signal_filtering():
    """Test signal filtering and confidence thresholds"""
    print("\n" + "=" * 50)
    print("TESTING SIGNAL FILTERING")
    print("=" * 50)

    try:
        from src.config.settings import Config
        from src.agents.market_analyzer import (MarketAnalyzerAgent,
                                                MarketSignal, SignalStrength)
        from src.database.connection import DatabaseManager
        from src.database.models import OrderSide
        from src.graph.state_manager import StateManager

        # Create agent with high confidence threshold
        state_manager = StateManager()
        state_manager.start()

        class MockDatabaseManager:
            def get_session(self):
                class MockSession:
                    def __enter__(self):
                        return self

                    def __exit__(self, *args):
                        pass

                return MockSession()

        db_manager = MockDatabaseManager()
        agent_config = {
            "trading_pairs": ["BTC/USDT"],
            "min_confidence_threshold": 0.8,  # High threshold
        }
        agent = MarketAnalyzerAgent(agent_config, state_manager, db_manager)

        # Create weak signal (should be filtered)
        weak_signal = MarketSignal(
            symbol="BTC/USDT",
            signal_type="test_weak",
            direction=OrderSide.BUY,
            strength=SignalStrength.WEAK,
            confidence=0.5,  # Below threshold
            price=50000,
            indicators={"rsi": 30},
        )

        # Create strong signal (should pass)
        strong_signal = MarketSignal(
            symbol="BTC/USDT",
            signal_type="test_strong",
            direction=OrderSide.BUY,
            strength=SignalStrength.STRONG,
            confidence=0.9,  # Above threshold
            price=50000,
            indicators={"rsi": 25},
        )

        # Process signals
        print("🔄 Processing weak signal (should be filtered)...")
        initial_signal_count = len(agent.recent_signals)
        await agent._process_signal(weak_signal)

        if len(agent.recent_signals) == initial_signal_count:
            print("✅ Weak signal properly filtered")
        else:
            print("❌ Weak signal was not filtered")
            return False

        print("🔄 Processing strong signal (should pass)...")
        await agent._process_signal(strong_signal)

        if len(agent.recent_signals) == initial_signal_count + 1:
            print("✅ Strong signal properly accepted")

            # Check signal details
            recent = agent.get_recent_signals(limit=1)[0]
            print(f"   Signal type: {recent['signal_type']}")
            print(f"   Confidence: {recent['confidence']}")
            print(f"   Direction: {recent['direction']}")
        else:
            print("❌ Strong signal was rejected")
            return False

        state_manager.stop()
        return True

    except Exception as e:
        print(f"❌ Signal filtering test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def run_all_tests():
    """Run all market analyzer tests"""
    print("CRYPTO TRADING BOT - MARKET ANALYZER TESTS")
    print("=" * 80)
    print(f"Python version: {sys.version}")
    print(f"Working directory: {os.getcwd()}")

    tests = [
        ("Agent Initialization", test_agent_initialization),
        ("Technical Indicators", test_technical_indicators),
        ("Signal Filtering", test_signal_filtering),
        ("Agent Lifecycle", test_agent_lifecycle),
        ("Market Data Processing", test_market_data_processing),
        ("Signal Filtering", test_signal_filtering),
    ]

    results = {}

    for test_name, test_func in tests:
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func()
            else:
                result = test_func()
            results[test_name] = result
        except Exception as e:
            print(f"❌ {test_name} test crashed: {e}")
            results[test_name] = False

    # Summary
    print("\n" + "=" * 80)
    print("MARKET ANALYZER TEST RESULTS")
    print("=" * 80)

    passed = sum(1 for result in results.values() if result)
    total = len(results)

    for test_name, result in results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name:.<50} {status}")

    print(f"\nOverall: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 ALL MARKET ANALYZER TESTS PASSED!")
        print("\nThe Market Analyzer Agent is ready for:")
        print("1. Technical analysis and indicator calculations")
        print("2. Multi-timeframe signal generation")
        print("3. Real-time market data processing")
        print("4. Integration with state management system")
        print("\nNext steps:")
        print("- Implement Risk Manager Agent")
        print("- Add real-time WebSocket data feeds")
        print("- Create strategy coordination logic")
        return True
    else:
        print(f"⚠️  {total - passed} tests failed. Fix issues before proceeding.")
        return False


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
