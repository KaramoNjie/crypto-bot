"""
Integration tests for the complete trading system
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch

from src.orchestration.trading_workflow import TradingWorkflow, WorkflowStatus
from src.execution.trade_validator import TradeValidator, OrderValidator
from src.scoring.confidence_engine import ConfidenceEngine, SignalInput, SignalSource
from src.safety.paper_trading import PaperTradingSafetyGuard, SafetyConfig
from src.monitoring.metrics import TradingMetrics


class TestTradingSystemIntegration:
    """Integration tests for the complete trading system"""

    @pytest.fixture
    def mock_agents(self):
        """Mock trading agents for testing"""
        return {
            'market_analyzer': Mock(),
            'news_analyzer': Mock(),
            'risk_manager': Mock(),
            'trading_executor': Mock()
        }

    @pytest.fixture
    def trading_workflow(self, mock_agents):
        """Create trading workflow with mocked agents"""
        config = {
            'min_confidence_score': 0.7,
            'max_concurrent_signals': 3,
            'signal_timeout_minutes': 30
        }

        return TradingWorkflow(
            market_analyzer=mock_agents['market_analyzer'],
            news_analyzer=mock_agents['news_analyzer'],
            risk_manager=mock_agents['risk_manager'],
            trading_executor=mock_agents['trading_executor'],
            config=config
        )

    @pytest.fixture
    def confidence_engine(self):
        """Create confidence engine for testing"""
        config = {
            'min_confidence': 0.1,
            'max_confidence': 0.95
        }
        return ConfidenceEngine(config)

    @pytest.fixture
    def safety_guard(self):
        """Create safety guard for testing"""
        config = SafetyConfig(paper_initial_balance=10000.0)
        return PaperTradingSafetyGuard(config)

    @pytest.fixture
    def trading_metrics(self):
        """Create trading metrics for testing"""
        config = {
            'metrics_port': 8001,
            'start_metrics_server': False  # Don't start server in tests
        }
        return TradingMetrics(config)

    @pytest.mark.asyncio
    async def test_complete_trading_pipeline(
        self,
        trading_workflow,
        confidence_engine,
        safety_guard,
        trading_metrics
    ):
        """Test complete trading pipeline from signal to execution"""

        # 1. Create trading signal
        signal_input = SignalInput(
            signal_id="integration_test_001",
            symbol="BTCUSDT",
            direction="buy",
            source=SignalSource.TECHNICAL_ANALYSIS,
            base_score=0.8,
            indicators={
                'rsi': 0.25,
                'macd': 0.7,
                'bollinger': 0.85
            },
            price=45000.0,
            volume=2000000.0,
            volatility=35.0,
            news_sentiment=0.3,
            news_count=5,
            historical_accuracy=0.75
        )

        # 2. Calculate confidence score
        confidence_metrics = confidence_engine.calculate_confidence(signal_input)

        assert confidence_metrics.adjusted_confidence > 0.0
        assert confidence_metrics.factors_count > 0

        # 3. Validate order safety
        safety_result = safety_guard.validate_order_safety(
            symbol=signal_input.symbol,
            side=signal_input.direction,
            quantity=0.01,
            price=signal_input.price
        )

        assert safety_result['safe'] == True

        # 4. Execute paper order if safe
        if safety_result['safe']:
            paper_result = safety_guard.execute_paper_order(
                symbol=signal_input.symbol,
                side=signal_input.direction.upper(),
                quantity=0.01,
                price=signal_input.price
            )

            assert paper_result.simulated == True
            assert paper_result.filled_quantity > 0

            # 5. Record metrics
            trading_metrics.record_trade(
                symbol=signal_input.symbol,
                side=signal_input.direction,
                status="FILLED",
                strategy="integration_test",
                execution_time=0.5,
                pnl=50.0
            )

            trading_metrics.record_signal(
                symbol=signal_input.symbol,
                direction=signal_input.direction,
                source=signal_input.source.value,
                status="approved",
                confidence=confidence_metrics.adjusted_confidence
            )

        # 6. Update confidence engine with outcome
        confidence_engine.update_signal_outcome(
            signal_id=signal_input.signal_id,
            outcome="success",
            performance_score=0.85
        )

        # Verify the complete pipeline worked
        assert len(confidence_engine.signal_history) > 0
        assert safety_guard.daily_trade_count > 0
        assert safety_guard.paper_balance < 10000.0  # Balance should decrease after buy

    @pytest.mark.asyncio
    async def test_workflow_execution_end_to_end(self, trading_workflow):
        """Test workflow execution from start to finish"""

        # Mock workflow methods to simulate actual agent behavior
        async def mock_get_market_data(symbol):
            return {
                'symbol': symbol,
                'price': 45000.0,
                'volume': 1500000.0,
                'change_24h': 2.5
            }

        async def mock_generate_market_signals(symbol, data):
            return [{
                'id': f'market_{symbol}_001',
                'symbol': symbol,
                'direction': 'buy',
                'confidence': 0.75,
                'source': 'technical_analysis'
            }]

        async def mock_get_news_articles(symbol):
            return [{
                'title': f'{symbol} shows strong momentum',
                'sentiment': 0.3,
                'published_at': datetime.utcnow()
            }]

        async def mock_generate_sentiment_signals(symbol, articles):
            return [{
                'id': f'sentiment_{symbol}_001',
                'symbol': symbol,
                'direction': 'buy',
                'confidence': 0.68,
                'sentiment_score': 0.3
            }]

        # Patch workflow methods
        trading_workflow._get_market_data = mock_get_market_data
        trading_workflow._generate_market_signals = mock_generate_market_signals
        trading_workflow._get_news_articles = mock_get_news_articles
        trading_workflow._generate_sentiment_signals = mock_generate_sentiment_signals

        # Execute workflow
        result = await trading_workflow.execute_workflow(['BTCUSDT', 'ETHUSDT'])

        assert result.status == WorkflowStatus.COMPLETED
        assert result.signals_processed >= 0
        assert result.execution_time_seconds is not None
        assert len(result.errors) == 0

    @pytest.mark.asyncio
    async def test_risk_management_integration(self, safety_guard, confidence_engine):
            """Test integration between risk management and confidence scoring"""

            # Create high-risk signal (low confidence)
            risky_signal = SignalInput(
                signal_id="risky_001",
                symbol="BTCUSDT",
                direction="buy",
                source=SignalSource.NEWS_ANALYSIS,
                base_score=0.4,  # Low base score
                news_sentiment=-0.2,  # Negative sentiment
                historical_accuracy=0.45  # Poor historical performance
            )

            # Calculate confidence
            confidence_metrics = confidence_engine.calculate_confidence(risky_signal)

            # Should result in low confidence
            assert confidence_metrics.adjusted_confidence < 0.6

            # Safety validation should warn about large positions for low confidence
            safety_result = safety_guard.validate_order_safety(
                symbol="BTCUSDT",
                side="BUY",
                quantity=0.1,  # Large position
                price=45000.0  # $4500 total
            )

            # Should have warnings about position size
            assert len(safety_result['warnings']) > 0 or not safety_result['safe']

    def test_metrics_integration_with_trading_components(self, trading_metrics):
        """Test metrics integration across trading components"""

        # Simulate trading activity
        symbols = ['BTCUSDT', 'ETHUSDT', 'ADAUSDT']

        for i, symbol in enumerate(symbols):
            # Record various metrics
            trading_metrics.record_trade(
                symbol=symbol,
                side='BUY',
                status='FILLED',
                strategy='test_strategy',
                execution_time=0.1 + i * 0.05,
                pnl=10.0 + i * 5.0
            )

            trading_metrics.record_signal(
                symbol=symbol,
                direction='buy',
                source='technical_analysis',
                status='approved',
                confidence=0.7 + i * 0.05
            )

            trading_metrics.record_api_request(
                api_name='binance',
                endpoint='/api/v3/order',
                status_code=200,
                duration=0.2
            )

        # Update portfolio metrics
        trading_metrics.record_portfolio_update(
            total_value=10500.0,
            available_balance=8500.0,
            unrealized_pnl=150.0,
            daily_pnl=75.0,
            open_positions_count=3,
            drawdown_pct=0.02
        )

        # Verify metrics were recorded
        # Note: In a real test, we would check actual Prometheus metric values
        # For this integration test, we verify the methods don't throw exceptions
        assert True  # If we get here, all metrics were recorded successfully

    @pytest.mark.asyncio
    async def test_error_handling_across_components(
        self,
        trading_workflow,
        confidence_engine,
        safety_guard
    ):
        """Test error handling integration across components"""

        # Test workflow with invalid symbols
        result = await trading_workflow.execute_workflow(['INVALID_SYMBOL'])

        # Workflow should complete but with errors
        assert result.status in [WorkflowStatus.COMPLETED, WorkflowStatus.FAILED]
        # Errors might be present depending on implementation

        # Test confidence engine with invalid data
        invalid_signal = SignalInput(
            signal_id="invalid_test",
            symbol="",  # Empty symbol
            direction="invalid_direction",
            source=SignalSource.TECHNICAL_ANALYSIS,
            base_score=float('inf')  # Invalid score
        )

        # Should handle gracefully
        metrics = confidence_engine.calculate_confidence(invalid_signal)
        assert isinstance(metrics.adjusted_confidence, float)
        assert 0.0 <= metrics.adjusted_confidence <= 1.0

        # Test safety guard with extreme values
        safety_result = safety_guard.validate_order_safety(
            symbol="BTCUSDT",
            side="BUY",
            quantity=-1.0,  # Negative quantity
            price=-100.0   # Negative price
        )

        # Should reject invalid order
        assert safety_result['safe'] == False

    def test_configuration_consistency_across_components(self):
        """Test that configuration is consistent across components"""

        # Test that components can be configured with consistent parameters
        base_config = {
            'min_confidence': 0.2,
            'max_risk_per_trade': 0.02,
            'paper_trading': True,
            'max_positions': 5
        }

        # Confidence engine config
        confidence_config = {
            'min_confidence': base_config['min_confidence'],
            'max_confidence': 0.95
        }
        confidence_engine = ConfidenceEngine(confidence_config)

        # Safety guard config
        safety_config = SafetyConfig(
            paper_initial_balance=10000.0,
            max_positions=base_config['max_positions']
        )
        safety_guard = PaperTradingSafetyGuard(safety_config)

        # Verify consistent configuration
        assert confidence_engine.min_confidence == base_config['min_confidence']
        assert safety_guard.config.max_positions == base_config['max_positions']
        assert safety_guard.config.trading_mode.value == "paper"

    @pytest.mark.asyncio
    async def test_performance_under_load(self, confidence_engine, safety_guard):
        """Test system performance under simulated load"""

        import time

        # Generate many signals quickly
        start_time = time.time()

        for i in range(100):
            signal = SignalInput(
                signal_id=f"load_test_{i}",
                symbol="BTCUSDT",
                direction="buy",
                source=SignalSource.TECHNICAL_ANALYSIS,
                base_score=0.7,
                price=45000.0 + i
            )

            # Calculate confidence
            confidence_engine.calculate_confidence(signal)

            # Validate safety (every 10th signal)
            if i % 10 == 0:
                safety_guard.validate_order_safety(
                    symbol="BTCUSDT",
                    side="BUY",
                    quantity=0.001,
                    price=45000.0 + i
                )

        end_time = time.time()
        execution_time = end_time - start_time

        # Should complete in reasonable time (less than 10 seconds)
        assert execution_time < 10.0

        # Should have processed all signals
        assert len(confidence_engine.signal_history) >= 100

        # Safety guard should still be functional
        status = safety_guard.get_safety_status()
        assert status['safety_engaged'] == True

    def test_data_consistency_across_components(self, confidence_engine, safety_guard):
        """Test data consistency when shared between components"""

        # Create signal and calculate confidence
        signal = SignalInput(
            signal_id="consistency_test",
            symbol="BTCUSDT",
            direction="buy",
            source=SignalSource.TECHNICAL_ANALYSIS,
            base_score=0.8,
            price=45000.0,
            indicators={'rsi': 0.3, 'macd': 0.7}
        )

        confidence_metrics = confidence_engine.calculate_confidence(signal)

        # Execute paper trade based on signal
        if confidence_metrics.adjusted_confidence > 0.7:
            paper_result = safety_guard.execute_paper_order(
                symbol=signal.symbol,
                side=signal.direction.upper(),
                quantity=0.01,
                price=signal.price
            )

            # Update confidence engine with result
            outcome = "success" if paper_result.status.value == "FILLED" else "failure"
            confidence_engine.update_signal_outcome(
                signal_id=signal.signal_id,
                outcome=outcome,
                performance_score=0.8
            )

            # Verify data consistency
            # Signal should be in confidence engine history
            signal_found = False
            for record in confidence_engine.signal_history:
                if record['signal_id'] == signal.signal_id:
                    assert record['outcome'] == outcome
                    signal_found = True
                    break

            assert signal_found

            # Portfolio should reflect the trade
            portfolio_summary = safety_guard.get_paper_portfolio_summary()
            assert portfolio_summary['cash_balance'] < 10000.0  # Should have decreased

    @pytest.mark.asyncio
    async def test_graceful_shutdown_integration(self, trading_workflow, safety_guard):
        """Test graceful shutdown across all components"""

        # Start a workflow
        workflow_task = asyncio.create_task(
            trading_workflow.execute_workflow(['BTCUSDT'])
        )

        # Let it run briefly
        await asyncio.sleep(0.1)

        # Engage emergency stop
        safety_guard.engage_emergency_stop("Integration test shutdown")

        # Cancel workflow
        workflow_task.cancel()

        try:
            await workflow_task
        except asyncio.CancelledError:
            pass

        # Verify emergency stop is active
        assert safety_guard.emergency_stop == True

        # Verify new orders are blocked
        safety_result = safety_guard.validate_order_safety(
            symbol="BTCUSDT",
            side="BUY",
            quantity=0.001,
            price=45000.0
        )

        assert safety_result['safe'] == False


class TestSystemReliability:
    """Test system reliability and fault tolerance"""

    def test_component_isolation(self):
        """Test that component failures don't cascade"""

        # Create components
        confidence_engine = ConfidenceEngine({'min_confidence': 0.1})
        safety_guard = PaperTradingSafetyGuard(SafetyConfig())

        # Simulate failure in confidence engine
        with patch.object(confidence_engine, 'calculate_confidence', side_effect=Exception("Test failure")):

            # Safety guard should still work
            result = safety_guard.validate_order_safety("BTCUSDT", "BUY", 0.01, 45000.0)
            assert isinstance(result, dict)
            assert 'safe' in result

        # Simulate failure in safety guard
        with patch.object(safety_guard, 'validate_order_safety', side_effect=Exception("Test failure")):

            # Confidence engine should still work
            signal = SignalInput("test", "BTCUSDT", "buy", SignalSource.TECHNICAL_ANALYSIS, 0.7)
            metrics = confidence_engine.calculate_confidence(signal)
            assert isinstance(metrics.adjusted_confidence, float)

    def test_state_recovery(self):
        """Test state recovery after failures"""

        safety_guard = PaperTradingSafetyGuard(SafetyConfig())

        # Execute some trades
        initial_result = safety_guard.execute_paper_order("BTCUSDT", "BUY", 0.01, 45000.0)
        initial_balance = safety_guard.paper_balance

        # Simulate restart by creating new instance with same config
        new_config = SafetyConfig(paper_initial_balance=initial_balance)  # Start with current balance
        new_safety_guard = PaperTradingSafetyGuard(new_config)

        # Should be able to continue trading
        new_result = new_safety_guard.execute_paper_order("ETHUSDT", "BUY", 0.1, 3000.0)
        assert new_result.status.value == "FILLED"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
