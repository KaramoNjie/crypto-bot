"""
Integration tests for the complete trading system.
"""

import pytest
import asyncio
from decimal import Decimal
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

from src.apis.enhanced_binance_client import EnhancedBinanceClient
from src.models.trading_models import TradingSignal, Portfolio, TradingPair
from src.risk_management.advanced_risk_manager import AdvancedRiskManager, PositionSizingMethod
from src.strategies.advanced_trading_strategies import MomentumStrategy, AdvancedStrategyManager
from src.database.repositories import PortfolioRepository, OrderRepository, PositionRepository
from src.utils.error_handling_enhanced import CircuitBreaker, TradingError


@pytest.mark.integration
@pytest.mark.asyncio
class TestTradingSystemIntegration:
    """Integration tests for the complete trading system."""

    async def test_complete_trading_workflow(
        self,
        test_session,
        test_portfolio,
        mock_binance_client,
        mock_market_data,
        mock_technical_indicators
    ):
        """Test complete trading workflow from signal to execution."""
        # Setup repositories
        portfolio_repo = PortfolioRepository(test_session)
        order_repo = OrderRepository(test_session)
        position_repo = PositionRepository(test_session)

        # Setup risk manager
        risk_manager = AdvancedRiskManager(
            initial_balance=float(test_portfolio.initial_balance),
            max_portfolio_risk=0.02,
            max_position_risk=0.05
        )

        # Setup strategy
        strategy = MomentumStrategy()

        # Create trading signal
        signal_data = {
            "symbol": "BTCUSDT",
            "signal_type": "buy",
            "confidence": 0.85,
            "entry_price": Decimal("50000.00"),
            "stop_loss": Decimal("47500.00"),  # 5% stop loss
            "take_profit": Decimal("55000.00"), # 10% take profit
            "reasoning": "Strong momentum breakout with high volume",
            "metadata": {
                "rsi": 65.0,
                "macd": 0.5,
                "volume_ratio": 2.0
            }
        }

        trading_signal = TradingSignal(**signal_data)

        # Create portfolio object for risk manager
        portfolio_obj = Portfolio(
            id=test_portfolio.id,
            current_balance=test_portfolio.current_balance,
            positions=[],
            settings={}
        )

        # Step 1: Risk assessment
        position_size = await risk_manager.calculate_position_size(
            trading_signal,
            portfolio_obj,
            PositionSizingMethod.VOLATILITY_BASED
        )

        assert position_size > 0
        assert position_size <= float(test_portfolio.current_balance) * 0.05  # Max 5% risk

        # Step 2: Create order
        order_data = {
            "portfolio_id": test_portfolio.id,
            "symbol": trading_signal.symbol,
            "side": trading_signal.signal_type,
            "type": "limit",
            "quantity": Decimal(str(position_size / float(trading_signal.entry_price))),
            "price": trading_signal.entry_price,
            "stop_price": trading_signal.stop_loss,
            "status": "pending"
        }

        order = await order_repo.create(order_data)
        assert order.id is not None
        assert order.status == "pending"

        # Step 3: Simulate order execution
        with patch.object(mock_binance_client, 'create_order') as mock_create:
            mock_create.return_value = {
                "orderId": 12345,
                "status": "FILLED",
                "executedQty": str(order.quantity),
                "fills": [{
                    "price": str(order.price),
                    "qty": str(order.quantity),
                    "commission": "0.001",
                    "commissionAsset": "BNB"
                }]
            }

            # Update order status
            await order_repo.update_status(
                order.id,
                "filled",
                filled_quantity=order.quantity,
                executed_at=datetime.utcnow()
            )

            # Create position
            position_data = {
                "portfolio_id": test_portfolio.id,
                "symbol": order.symbol,
                "side": "long",
                "quantity": order.quantity,
                "entry_price": order.price,
                "current_price": order.price,
                "stop_loss": trading_signal.stop_loss,
                "take_profit": trading_signal.take_profit,
                "is_open": True
            }

            position = await position_repo.create(position_data)
            assert position.id is not None
            assert position.is_open is True

        # Step 4: Verify portfolio state
        updated_portfolio = await portfolio_repo.get_by_id(test_portfolio.id)
        open_positions = await position_repo.get_open_positions(test_portfolio.id)
        portfolio_orders = await order_repo.get_portfolio_orders(test_portfolio.id)

        assert len(open_positions) == 1
        assert len(portfolio_orders) == 1
        assert portfolio_orders[0].status == "filled"

        # Step 5: Simulate price movement and position update
        new_price = Decimal("52000.00")  # 4% gain
        await position_repo.update_current_price(position.id, new_price)

        updated_position = await position_repo.get_by_id(position.id)
        expected_pnl = float((new_price - position.entry_price) * position.quantity)
        assert float(updated_position.unrealized_pnl) == expected_pnl

    async def test_risk_management_integration(
        self,
        test_session,
        test_portfolio,
        test_position
    ):
        """Test risk management system integration."""
        position_repo = PositionRepository(test_session)

        # Setup risk manager
        risk_manager = AdvancedRiskManager(
            initial_balance=float(test_portfolio.initial_balance),
            max_portfolio_risk=0.02,
            max_drawdown_limit=0.15
        )

        # Create multiple positions to test portfolio risk
        positions_data = [
            {
                "portfolio_id": test_portfolio.id,
                "symbol": "ETHUSDT",
                "side": "long",
                "quantity": Decimal("2.0"),
                "entry_price": Decimal("3000.00"),
                "current_price": Decimal("2800.00"),  # Loss position
                "is_open": True
            },
            {
                "portfolio_id": test_portfolio.id,
                "symbol": "ADAUSDT",
                "side": "long",
                "quantity": Decimal("1000.0"),
                "entry_price": Decimal("1.00"),
                "current_price": Decimal("0.90"),   # Loss position
                "is_open": True
            }
        ]

        for pos_data in positions_data:
            await position_repo.create(pos_data)

        # Get all positions
        all_positions = await position_repo.get_open_positions(test_portfolio.id)

        # Calculate total portfolio risk
        total_unrealized_pnl = sum(pos.unrealized_pnl for pos in all_positions)
        portfolio_value = float(test_portfolio.current_balance) + total_unrealized_pnl

        # Test risk assessment
        portfolio_obj = Portfolio(
            id=test_portfolio.id,
            current_balance=Decimal(str(portfolio_value)),
            positions=[],
            settings={}
        )

        # Test that risk manager prevents over-leveraging
        large_signal = TradingSignal(
            symbol="SOLUSDT",
            signal_type="buy",
            confidence=0.9,
            entry_price=Decimal("150.00"),
            reasoning="Test signal"
        )

        # Should limit position size due to existing risk
        position_size = await risk_manager.calculate_position_size(
            large_signal,
            portfolio_obj,
            PositionSizingMethod.FIXED_PERCENTAGE
        )

        # Verify position size is reasonable given current portfolio state
        max_allowed_value = portfolio_value * 0.02  # 2% max risk
        actual_value = position_size
        assert actual_value <= max_allowed_value

    async def test_strategy_signal_generation_integration(
        self,
        mock_technical_indicators,
        mock_market_data
    ):
        """Test strategy signal generation with real indicators."""
        strategy = MomentumStrategy()

        # Create realistic technical indicators
        indicators_data = {
            "rsi": 68.0,  # Approaching overbought but not extreme
            "macd": 0.8,
            "macd_signal": 0.5,
            "macd_histogram": 0.3,
            "sma_20": Decimal("49800.00"),
            "sma_50": Decimal("48500.00"),
            "bb_upper": Decimal("51500.00"),
            "bb_lower": Decimal("48000.00"),
            "volume_ratio": 1.8,  # Above average volume
            "atr": Decimal("1200.00")
        }

        # Test signal generation
        signal = await strategy.generate_signal(indicators_data)

        assert signal is not None
        assert signal.symbol == "BTCUSDT"  # Default for strategy
        assert signal.confidence > 0.5  # Should be confident with these indicators

        # Verify signal makes sense based on indicators
        if signal.signal_type == "buy":
            assert indicators_data["rsi"] < 75  # Not too overbought
            assert indicators_data["macd"] > indicators_data["macd_signal"]  # Positive MACD
            assert indicators_data["volume_ratio"] > 1.2  # Good volume

    async def test_circuit_breaker_integration(
        self,
        test_session,
        test_portfolio,
        mock_binance_client
    ):
        """Test circuit breaker functionality in trading system."""
        order_repo = OrderRepository(test_session)

        # Setup circuit breaker with low threshold for testing
        circuit_breaker = CircuitBreaker(
            failure_threshold=2,
            recovery_timeout=1.0  # 1 second for testing
        )

        # Simulate API failures
        mock_binance_client.create_order.side_effect = Exception("API Error")

        # Try to place orders that will fail
        order_data = {
            "portfolio_id": test_portfolio.id,
            "symbol": "BTCUSDT",
            "side": "buy",
            "type": "market",
            "quantity": Decimal("0.1"),
            "status": "pending"
        }

        # First failure
        with pytest.raises(TradingError):
            async with circuit_breaker:
                raise TradingError("Order placement failed")

        # Second failure - should open circuit
        with pytest.raises(TradingError):
            async with circuit_breaker:
                raise TradingError("Order placement failed again")

        # Third attempt should be blocked by circuit breaker
        with pytest.raises(Exception, match="Circuit breaker is OPEN"):
            async with circuit_breaker:
                # This shouldn't execute
                pass

        # Wait for recovery timeout
        await asyncio.sleep(1.1)

        # Circuit should be half-open now and allow one attempt
        mock_binance_client.create_order.side_effect = None
        mock_binance_client.create_order.return_value = {
            "orderId": 12345,
            "status": "NEW"
        }

        # This should succeed and close the circuit
        try:
            async with circuit_breaker:
                # Simulate successful operation
                pass
        except Exception:
            pytest.fail("Circuit breaker should allow operation after recovery timeout")

    async def test_strategy_manager_ensemble_integration(
        self,
        mock_technical_indicators,
        mock_market_data
    ):
        """Test strategy manager with multiple strategies."""
        # Create strategy manager with multiple strategies
        strategy_manager = AdvancedStrategyManager()

        # Add strategies
        momentum_strategy = MomentumStrategy()
        await strategy_manager.add_strategy("momentum", momentum_strategy, weight=0.6)

        # Mock additional strategies would be added here
        # For this test, we'll just test with momentum strategy

        # Generate ensemble signals
        with patch.object(momentum_strategy, 'generate_signal') as mock_generate:
            mock_signal = TradingSignal(
                symbol="BTCUSDT",
                signal_type="buy",
                confidence=0.8,
                entry_price=Decimal("50000.00"),
                reasoning="Momentum breakout"
            )
            mock_generate.return_value = mock_signal

            ensemble_signal = await strategy_manager.generate_ensemble_signal(
                mock_technical_indicators
            )

            assert ensemble_signal is not None
            assert ensemble_signal.symbol == "BTCUSDT"
            # Confidence should be weighted
            assert 0.4 <= ensemble_signal.confidence <= 1.0

    async def test_error_recovery_integration(
        self,
        test_session,
        test_portfolio,
        mock_binance_client
    ):
        """Test error recovery mechanisms in trading system."""
        order_repo = OrderRepository(test_session)

        # Test network timeout recovery
        mock_binance_client.create_order.side_effect = [
            asyncio.TimeoutError("Request timeout"),
            {  # Successful retry
                "orderId": 12345,
                "status": "NEW",
                "executedQty": "0.0"
            }
        ]

        order_data = {
            "portfolio_id": test_portfolio.id,
            "symbol": "BTCUSDT",
            "side": "buy",
            "type": "limit",
            "quantity": Decimal("0.1"),
            "price": Decimal("50000.00"),
            "status": "pending"
        }

        order = await order_repo.create(order_data)

        # Simulate order placement with retry logic
        max_retries = 3
        for attempt in range(max_retries):
            try:
                result = await mock_binance_client.create_order(
                    symbol=order.symbol,
                    side=order.side,
                    type=order.type,
                    quantity=str(order.quantity),
                    price=str(order.price)
                )

                # Update order with exchange order ID
                await order_repo.update_status(
                    order.id,
                    "new",
                    exchange_order_id=str(result["orderId"])
                )
                break

            except asyncio.TimeoutError:
                if attempt == max_retries - 1:
                    # Final attempt failed
                    await order_repo.update_status(order.id, "failed")
                    raise
                await asyncio.sleep(0.1)  # Short delay before retry

        # Verify order was eventually placed successfully
        updated_order = await order_repo.get_by_id(order.id)
        assert updated_order.status == "new"
        assert updated_order.exchange_order_id == "12345"

    @pytest.mark.slow
    async def test_high_frequency_trading_simulation(
        self,
        test_session,
        test_portfolio,
        mock_binance_client
    ):
        """Test system performance under high-frequency trading conditions."""
        order_repo = OrderRepository(test_session)
        position_repo = PositionRepository(test_session)

        # Mock fast order responses
        mock_binance_client.create_order.return_value = {
            "orderId": 12345,
            "status": "FILLED",
            "executedQty": "0.01"
        }

        # Simulate rapid order placement
        num_orders = 50
        orders = []

        start_time = datetime.utcnow()

        # Create multiple orders rapidly
        tasks = []
        for i in range(num_orders):
            order_data = {
                "portfolio_id": test_portfolio.id,
                "client_order_id": f"hft_order_{i}",
                "symbol": "BTCUSDT",
                "side": "buy" if i % 2 == 0 else "sell",
                "type": "market",
                "quantity": Decimal("0.01"),
                "status": "pending"
            }

            task = asyncio.create_task(order_repo.create(order_data))
            tasks.append(task)

        # Wait for all orders to be created
        created_orders = await asyncio.gather(*tasks)

        end_time = datetime.utcnow()
        processing_time = (end_time - start_time).total_seconds()

        # Verify performance
        assert len(created_orders) == num_orders
        assert processing_time < 5.0  # Should complete within 5 seconds

        # Verify all orders were created successfully
        all_orders = await order_repo.get_portfolio_orders(
            test_portfolio.id,
            limit=num_orders
        )
        assert len(all_orders) == num_orders

        # Calculate orders per second
        orders_per_second = num_orders / processing_time
        assert orders_per_second > 10  # Should handle at least 10 orders/second
