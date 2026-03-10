"""
Comprehensive tests for paper trading safety mechanisms
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from src.safety.paper_trading import (
    PaperTradingSafetyGuard, SafetyConfig, TradingMode, SafetyLevel,
    SafeTradingContext, PaperOrderResult
)
from src.database.models import OrderSide, OrderType, OrderStatus


class TestPaperTradingSafetyGuard:
    """Test paper trading safety guard"""

    @pytest.fixture
    def safety_config(self):
        """Default safety configuration for tests"""
        return SafetyConfig(
            trading_mode=TradingMode.PAPER,
            safety_level=SafetyLevel.HIGH,
            paper_initial_balance=10000.0,
            max_order_size_usd=1000.0,
            max_daily_trades=50,
            emergency_stop_active=False
        )

    @pytest.fixture
    def safety_guard(self, safety_config):
        """Create safety guard with test configuration"""
        return PaperTradingSafetyGuard(safety_config)

    def test_safety_guard_initialization(self, safety_guard):
        """Test safety guard initialization"""

        assert safety_guard.config.trading_mode == TradingMode.PAPER
        assert safety_guard.paper_balance == 10000.0
        assert safety_guard.safety_engaged == True
        assert safety_guard.emergency_stop == False
        assert len(safety_guard.paper_positions) == 0

    def test_force_paper_mode_on_wrong_config(self):
        """Test forcing paper mode when wrong mode is configured"""

        config = SafetyConfig(trading_mode=TradingMode.LIVE)  # Wrong mode
        safety_guard = PaperTradingSafetyGuard(config)

        # Should be forced to paper mode
        assert safety_guard.config.trading_mode == TradingMode.PAPER

    def test_valid_order_safety_validation(self, safety_guard):
        """Test validation of a valid order"""

        result = safety_guard.validate_order_safety(
            symbol="BTCUSDT",
            side="BUY",
            quantity=0.01,
            price=45000.0
        )

        assert result['safe'] == True
        assert len(result['reasons']) == 0
        assert result['mode_override'] is None

    def test_order_size_limit_validation(self, safety_guard):
        """Test order size limit validation"""

        result = safety_guard.validate_order_safety(
            symbol="BTCUSDT",
            side="BUY",
            quantity=1.0,  # Large quantity
            price=50000.0  # $50,000 total > $1,000 limit
        )

        assert result['safe'] == False
        assert any("exceeds limit" in reason for reason in result['reasons'])

    def test_insufficient_balance_validation(self, safety_guard):
        """Test insufficient balance validation"""

        # Use up most of the balance first
        safety_guard.paper_balance = 100.0

        result = safety_guard.validate_order_safety(
            symbol="BTCUSDT",
            side="BUY",
            quantity=0.01,
            price=50000.0  # $500 > $100 available
        )

        assert result['safe'] == False
        assert any("insufficient" in reason.lower() for reason in result['reasons'])

    def test_emergency_stop_blocks_orders(self, safety_guard):
        """Test that emergency stop blocks all orders"""

        # Engage emergency stop
        safety_guard.engage_emergency_stop("Test emergency stop")

        result = safety_guard.validate_order_safety(
            symbol="BTCUSDT",
            side="BUY",
            quantity=0.001,
            price=45000.0
        )

        assert result['safe'] == False
        assert any("emergency stop" in reason.lower() for reason in result['reasons'])

    def test_daily_trade_limit(self, safety_guard):
        """Test daily trade limit enforcement"""

        # Set daily count to limit
        safety_guard.daily_trade_count = safety_guard.config.max_daily_trades

        result = safety_guard.validate_order_safety(
            symbol="BTCUSDT",
            side="BUY",
            quantity=0.001,
            price=45000.0
        )

        assert result['safe'] == False
        assert any("daily trade limit" in reason.lower() for reason in result['reasons'])

    def test_daily_counter_reset(self, safety_guard):
        """Test daily counter resets on new day"""

        # Set high daily count
        safety_guard.daily_trade_count = 100
        safety_guard.last_trade_date = datetime.utcnow().date() - timedelta(days=1)

        # Should reset when validating order
        safety_guard._update_daily_counter()

        assert safety_guard.daily_trade_count == 0
        assert safety_guard.last_trade_date == datetime.utcnow().date()

    def test_paper_order_execution(self, safety_guard):
        """Test paper order execution"""

        result = safety_guard.execute_paper_order(
            symbol="BTCUSDT",
            side="BUY",
            quantity=0.01,
            price=45000.0
        )

        assert isinstance(result, PaperOrderResult)
        assert result.symbol == "BTCUSDT"
        assert result.side == OrderSide.BUY
        assert result.status == OrderStatus.FILLED
        assert result.simulated == True
        assert result.filled_quantity == 0.01
        assert result.fees > 0

    def test_paper_order_slippage(self, safety_guard):
        """Test slippage simulation in paper orders"""

        original_price = 45000.0

        result = safety_guard.execute_paper_order(
            symbol="BTCUSDT",
            side="BUY",
            quantity=0.01,
            price=original_price
        )

        # Buy order should have positive slippage (higher execution price)
        assert result.average_price > original_price
        assert result.slippage > 0

    def test_paper_portfolio_update_buy(self, safety_guard):
        """Test portfolio update after buy order"""

        initial_balance = safety_guard.paper_balance

        result = safety_guard.execute_paper_order(
            symbol="BTCUSDT",
            side="BUY",
            quantity=0.01,
            price=45000.0
        )

        # Balance should decrease
        expected_cost = result.filled_quantity * result.average_price + result.fees
        assert safety_guard.paper_balance == initial_balance - expected_cost

        # Should have position
        assert "BTCUSDT" in safety_guard.paper_positions
        position = safety_guard.paper_positions["BTCUSDT"]
        assert position['quantity'] == 0.01

    def test_paper_portfolio_update_sell(self, safety_guard):
        """Test portfolio update after sell order"""

        # First buy to create position
        safety_guard.execute_paper_order("BTCUSDT", "BUY", 0.02, 45000.0)

        initial_balance = safety_guard.paper_balance

        # Then sell half
        result = safety_guard.execute_paper_order(
            symbol="BTCUSDT",
            side="SELL",
            quantity=0.01,
            price=46000.0
        )

        # Balance should increase
        expected_income = result.filled_quantity * result.average_price - result.fees
        assert safety_guard.paper_balance == initial_balance + expected_income

        # Position should be reduced
        position = safety_guard.paper_positions["BTCUSDT"]
        assert position['quantity'] == 0.01  # 0.02 - 0.01

    def test_position_closure_on_full_sell(self, safety_guard):
        """Test position closure when fully sold"""

        # Buy position
        safety_guard.execute_paper_order("BTCUSDT", "BUY", 0.01, 45000.0)

        # Sell entire position
        safety_guard.execute_paper_order("BTCUSDT", "SELL", 0.01, 46000.0)

        # Position should be removed
        assert "BTCUSDT" not in safety_guard.paper_positions

    def test_drawdown_calculation(self, safety_guard):
        """Test drawdown calculation"""

        # Simulate loss
        safety_guard.paper_balance = 8000.0  # 20% loss

        drawdown = safety_guard._calculate_current_drawdown()

        assert drawdown == 0.2  # 20% drawdown

    def test_portfolio_value_calculation(self, safety_guard):
        """Test portfolio value calculation with positions"""

        # Execute some trades
        safety_guard.execute_paper_order("BTCUSDT", "BUY", 0.01, 45000.0)
        safety_guard.execute_paper_order("ETHUSDT", "BUY", 0.1, 3000.0)

        portfolio_value = safety_guard._calculate_portfolio_value()

        # Should include cash + position values
        assert portfolio_value > safety_guard.paper_balance

    def test_emergency_stop_engagement(self, safety_guard):
        """Test emergency stop engagement"""

        safety_guard.engage_emergency_stop("Test emergency")

        assert safety_guard.emergency_stop == True
        assert len(safety_guard.safety_events) > 0

        # Find emergency stop event
        stop_event = None
        for event in safety_guard.safety_events:
            if event['event_type'] == 'emergency_stop_engaged':
                stop_event = event
                break

        assert stop_event is not None
        assert stop_event['data']['reason'] == "Test emergency"

    def test_emergency_stop_disengagement(self, safety_guard):
        """Test emergency stop disengagement"""

        # Engage first
        safety_guard.engage_emergency_stop("Test")

        # Try invalid authorization
        result = safety_guard.disengage_emergency_stop("WRONG_CODE")
        assert result == False
        assert safety_guard.emergency_stop == True

        # Try valid authorization
        result = safety_guard.disengage_emergency_stop("SAFE_TO_RESUME_PAPER_TRADING")
        assert result == True
        assert safety_guard.emergency_stop == False

    def test_portfolio_reset(self, safety_guard):
        """Test portfolio reset functionality"""

        # Execute some trades to change state
        safety_guard.execute_paper_order("BTCUSDT", "BUY", 0.01, 45000.0)
        safety_guard.daily_trade_count = 10

        # Reset with invalid code
        result = safety_guard.reset_paper_portfolio("WRONG_CODE")
        assert result == False

        # Reset with valid code
        result = safety_guard.reset_paper_portfolio("RESET_PAPER_PORTFOLIO")
        assert result == True

        # Check reset state
        assert safety_guard.paper_balance == safety_guard.config.paper_initial_balance
        assert len(safety_guard.paper_positions) == 0
        assert safety_guard.daily_trade_count == 0

    def test_safety_status_reporting(self, safety_guard):
        """Test safety status reporting"""

        status = safety_guard.get_safety_status()

        required_fields = [
            'safety_engaged', 'trading_mode', 'emergency_stop',
            'paper_balance', 'portfolio_value', 'daily_trades'
        ]

        for field in required_fields:
            assert field in status

        assert status['safety_engaged'] == True
        assert status['trading_mode'] == TradingMode.PAPER.value

    def test_portfolio_summary(self, safety_guard):
        """Test portfolio summary generation"""

        # Execute some trades
        safety_guard.execute_paper_order("BTCUSDT", "BUY", 0.01, 45000.0)

        summary = safety_guard.get_paper_portfolio_summary()

        required_fields = [
            'cash_balance', 'positions', 'total_value',
            'pnl', 'pnl_percentage', 'drawdown'
        ]

        for field in required_fields:
            assert field in summary

        assert summary['cash_balance'] < safety_guard.config.paper_initial_balance
        assert len(summary['positions']) > 0

    def test_blocked_attempts_logging(self, safety_guard):
        """Test logging of blocked attempts"""

        # Engage emergency stop to block orders
        safety_guard.engage_emergency_stop("Test")

        # Try to validate order (should be blocked)
        safety_guard.validate_order_safety("BTCUSDT", "BUY", 0.01, 45000.0)

        # Check blocked attempts
        blocked_attempts = safety_guard.get_blocked_attempts_summary()

        assert len(blocked_attempts) > 0
        assert blocked_attempts[0]['reason'] == 'emergency_stop'

    def test_safety_log_export(self, safety_guard):
        """Test safety log export"""

        # Generate some activity
        safety_guard.execute_paper_order("BTCUSDT", "BUY", 0.01, 45000.0)

        export_data = safety_guard.export_safety_log()

        # Should be valid JSON
        import json
        parsed_data = json.loads(export_data)

        assert 'safety_status' in parsed_data
        assert 'portfolio_summary' in parsed_data
        assert 'safety_events' in parsed_data
        assert 'export_timestamp' in parsed_data


class TestSafeTradingContext:
    """Test safe trading context manager"""

    @pytest.fixture
    def safety_guard(self):
        """Create safety guard for context tests"""
        config = SafetyConfig(paper_initial_balance=10000.0)
        return PaperTradingSafetyGuard(config)

    def test_safe_context_successful_order(self, safety_guard):
        """Test successful order execution in safe context"""

        with SafeTradingContext(safety_guard) as context:
            result = context.execute_order("BTCUSDT", "BUY", 0.01, price=45000.0)

            assert isinstance(result, PaperOrderResult)
            assert result.status == OrderStatus.FILLED

        # Check that operation was logged
        assert len(context.operations) == 1
        assert context.operations[0]['type'] == 'executed_order'

    def test_safe_context_blocked_order(self, safety_guard):
        """Test blocked order in safe context"""

        # Engage emergency stop
        safety_guard.engage_emergency_stop("Test block")

        with pytest.raises(ValueError, match="blocked by safety guard"):
            with SafeTradingContext(safety_guard) as context:
                context.execute_order("BTCUSDT", "BUY", 0.01, price=45000.0)

    def test_safe_context_multiple_operations(self, safety_guard):
        """Test multiple operations in safe context"""

        with SafeTradingContext(safety_guard) as context:
            result1 = context.execute_order("BTCUSDT", "BUY", 0.01, price=45000.0)
            result2 = context.execute_order("ETHUSDT", "BUY", 0.1, price=3000.0)

            assert len(context.operations) == 2
            assert all(op['type'] == 'executed_order' for op in context.operations)


class TestSafetyConfigOptions:
    """Test different safety configuration options"""

    def test_maximum_safety_level(self):
        """Test maximum safety level configuration"""

        config = SafetyConfig(
            safety_level=SafetyLevel.MAXIMUM,
            max_order_size_usd=100.0,  # Very low limit
            max_daily_trades=5        # Very low limit
        )

        safety_guard = PaperTradingSafetyGuard(config)

        # Even small orders should be heavily restricted
        result = safety_guard.validate_order_safety(
            symbol="BTCUSDT",
            side="BUY",
            quantity=0.1,
            price=1000.0  # $100 exactly at limit
        )

        # Should still be valid at the limit
        assert result['safe'] == True

        # But slightly over should be blocked
        result2 = safety_guard.validate_order_safety(
            symbol="BTCUSDT",
            side="BUY",
            quantity=0.1,
            price=1100.0  # $110 > $100 limit
        )

        assert result2['safe'] == False

    def test_low_safety_level(self):
        """Test low safety level configuration"""

        config = SafetyConfig(
            safety_level=SafetyLevel.LOW,
            max_order_size_usd=10000.0,  # High limit
            max_daily_trades=1000        # High limit
        )

        safety_guard = PaperTradingSafetyGuard(config)

        # Large orders should be allowed
        result = safety_guard.validate_order_safety(
            symbol="BTCUSDT",
            side="BUY",
            quantity=0.2,
            price=45000.0  # $9000 < $10000 limit
        )

        assert result['safe'] == True

    def test_sandbox_trading_mode(self):
        """Test sandbox trading mode"""

        config = SafetyConfig(trading_mode=TradingMode.SANDBOX)
        safety_guard = PaperTradingSafetyGuard(config)

        # Should be forced to paper mode for safety
        assert safety_guard.config.trading_mode == TradingMode.PAPER


class TestPaperOrderResult:
    """Test paper order result data structure"""

    def test_paper_order_result_creation(self):
        """Test creating paper order result"""

        result = PaperOrderResult(
            order_id="test_123",
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=0.01,
            price=45000.0,
            status=OrderStatus.FILLED,
            filled_quantity=0.01,
            average_price=45050.0,
            fees=45.05,
            commission=45.05,
            timestamp=datetime.utcnow(),
            slippage=0.001,
            latency_ms=100
        )

        assert result.order_id == "test_123"
        assert result.simulated == True
        assert result.slippage == 0.001
        assert result.latency_ms == 100

    def test_paper_order_result_to_dict(self):
        """Test converting paper order result to dictionary"""

        timestamp = datetime.utcnow()

        result = PaperOrderResult(
            order_id="test_456",
            symbol="ETHUSDT",
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            quantity=0.1,
            price=3200.0,
            status=OrderStatus.FILLED,
            filled_quantity=0.1,
            average_price=3190.0,
            fees=3.19,
            commission=3.19,
            timestamp=timestamp
        )

        result_dict = result.to_dict()

        required_fields = [
            'orderId', 'symbol', 'side', 'type', 'origQty',
            'price', 'status', 'executedQty', 'avgPrice',
            'fees', 'simulated'
        ]

        for field in required_fields:
            assert field in result_dict

        assert result_dict['simulated'] == True
        assert result_dict['symbol'] == "ETHUSDT"
        assert result_dict['side'] == OrderSide.SELL.value


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
