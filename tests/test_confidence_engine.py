"""
Comprehensive tests for confidence scoring engine
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from src.scoring.confidence_engine import (
    ConfidenceEngine, SignalInput, SignalSource,
    ConfidenceLevel, ConfidenceMetrics
)


class TestConfidenceEngine:
    """Test confidence scoring engine"""

    @pytest.fixture
    def config(self):
        """Default configuration for tests"""
        return {
            'weight_signal_strength': 0.25,
            'weight_market_factors': 0.20,
            'weight_risk_factors': 0.15,
            'weight_sentiment_factors': 0.15,
            'weight_historical_factors': 0.25,
            'min_confidence': 0.1,
            'max_confidence': 0.95,
            'volatility_window': 20
        }

    @pytest.fixture
    def confidence_engine(self, config):
        """Create confidence engine with test config"""
        return ConfidenceEngine(config)

    @pytest.fixture
    def sample_signal_input(self):
        """Sample signal input for testing"""
        return SignalInput(
            signal_id="test_001",
            symbol="BTCUSDT",
            direction="buy",
            source=SignalSource.TECHNICAL_ANALYSIS,
            base_score=0.75,
            indicators={
                'rsi': 0.3,
                'macd': 0.6,
                'bollinger': 0.8
            },
            price=45000.0,
            volume=1500000.0,
            volatility=45.0,
            news_sentiment=0.2,
            news_count=5,
            historical_accuracy=0.68
        )

    def test_confidence_engine_initialization(self, confidence_engine):
        """Test confidence engine initialization"""

        assert confidence_engine.min_confidence == 0.1
        assert confidence_engine.max_confidence == 0.95
        assert confidence_engine.weights['signal_strength'] == 0.25
        assert len(confidence_engine.signal_history) == 0

    def test_calculate_confidence_basic(self, confidence_engine, sample_signal_input):
        """Test basic confidence calculation"""

        metrics = confidence_engine.calculate_confidence(sample_signal_input)

        assert isinstance(metrics, ConfidenceMetrics)
        assert 0.0 <= metrics.adjusted_confidence <= 1.0
        assert metrics.confidence_level in ConfidenceLevel
        assert metrics.factors_count > 0

    def test_signal_strength_calculation(self, confidence_engine, sample_signal_input):
        """Test signal strength metrics calculation"""

        signal_metrics = confidence_engine._calculate_signal_strength(sample_signal_input)

        assert 'strength' in signal_metrics
        assert 'consistency' in signal_metrics
        assert 'convergence' in signal_metrics

        # Strength should be based on base_score
        assert signal_metrics['strength'] == abs(sample_signal_input.base_score)

        # Convergence should be calculated from indicators
        assert 0.0 <= signal_metrics['convergence'] <= 1.0

    def test_signal_strength_with_no_indicators(self, confidence_engine):
        """Test signal strength calculation with no indicators"""

        signal_input = SignalInput(
            signal_id="test_002",
            symbol="ETHUSDT",
            direction="sell",
            source=SignalSource.NEWS_ANALYSIS,
            base_score=0.6,
            indicators={}  # No indicators
        )

        signal_metrics = confidence_engine._calculate_signal_strength(signal_input)

        assert signal_metrics['strength'] == 0.6
        assert signal_metrics['consistency'] == 0.0
        assert signal_metrics['convergence'] == 0.0

    def test_market_factors_calculation(self, confidence_engine, sample_signal_input):
        """Test market factors calculation"""

        market_metrics = confidence_engine._calculate_market_factors(sample_signal_input)

        assert 'volatility' in market_metrics
        assert 'volume' in market_metrics
        assert 'trend' in market_metrics

        # All metrics should be between 0 and 1
        for metric in market_metrics.values():
            assert 0.0 <= metric <= 1.0

    def test_volatility_scoring(self, confidence_engine):
        """Test volatility scoring logic"""

        # Test optimal volatility (around 40%)
        signal_input = SignalInput(
            signal_id="test_vol_1",
            symbol="BTCUSDT",
            direction="buy",
            source=SignalSource.TECHNICAL_ANALYSIS,
            base_score=0.7,
            volatility=40.0  # Optimal range
        )

        market_metrics = confidence_engine._calculate_market_factors(signal_input)
        volatility_score = market_metrics['volatility']

        # Should get high score for optimal volatility
        assert volatility_score > 0.8

        # Test extreme volatility
        signal_input.volatility = 90.0  # Very high
        market_metrics = confidence_engine._calculate_market_factors(signal_input)
        volatility_score_high = market_metrics['volatility']

        # Should get lower score for extreme volatility
        assert volatility_score_high < volatility_score

    def test_sentiment_factors_calculation(self, confidence_engine, sample_signal_input):
        """Test sentiment factors calculation"""

        sentiment_metrics = confidence_engine._calculate_sentiment_factors(sample_signal_input)

        assert 'news' in sentiment_metrics
        assert 'social' in sentiment_metrics
        assert 'fundamental' in sentiment_metrics

        # News sentiment should be weighted by news count
        assert sentiment_metrics['news'] > 0

        # Social sentiment not provided, should be 0
        assert sentiment_metrics['social'] == 0.0

    def test_sentiment_with_negative_news(self, confidence_engine):
        """Test sentiment calculation with negative news"""

        signal_input = SignalInput(
            signal_id="test_sentiment",
            symbol="BTCUSDT",
            direction="sell",
            source=SignalSource.SENTIMENT_ANALYSIS,
            base_score=0.8,
            news_sentiment=-0.6,  # Negative sentiment
            news_count=10,
            social_sentiment=-0.3
        )

        sentiment_metrics = confidence_engine._calculate_sentiment_factors(signal_input)

        # Negative sentiment should result in low scores
        assert sentiment_metrics['news'] < 0.5
        assert sentiment_metrics['social'] < 0.5

    def test_historical_factors_calculation(self, confidence_engine, sample_signal_input):
        """Test historical performance factors"""

        historical_metrics = confidence_engine._calculate_historical_factors(sample_signal_input)

        assert 'accuracy' in historical_metrics
        assert 'performance' in historical_metrics

        # Should use provided historical accuracy
        assert historical_metrics['accuracy'] == sample_signal_input.historical_accuracy

    def test_historical_factors_with_defaults(self, confidence_engine):
        """Test historical factors with default values"""

        signal_input = SignalInput(
            signal_id="test_hist",
            symbol="ETHUSDT",
            direction="buy",
            source=SignalSource.TECHNICAL_ANALYSIS,
            base_score=0.7,
            # No historical data provided
        )

        historical_metrics = confidence_engine._calculate_historical_factors(signal_input)

        # Should use default accuracy
        assert historical_metrics['accuracy'] == 0.6
        assert historical_metrics['performance'] >= 0.0

    def test_confidence_adjustments(self, confidence_engine, sample_signal_input):
        """Test confidence adjustment logic"""

        base_confidence = 0.7
        metrics = ConfidenceMetrics()
        metrics.market_volatility = 0.9  # High volatility

        adjusted = confidence_engine._apply_confidence_adjustments(
            base_confidence, sample_signal_input, metrics
        )

        # High volatility should reduce confidence
        assert adjusted < base_confidence

    def test_confidence_level_mapping(self, confidence_engine):
        """Test confidence score to level mapping"""

        assert confidence_engine._get_confidence_level(0.9) == ConfidenceLevel.VERY_HIGH
        assert confidence_engine._get_confidence_level(0.7) == ConfidenceLevel.HIGH
        assert confidence_engine._get_confidence_level(0.5) == ConfidenceLevel.MODERATE
        assert confidence_engine._get_confidence_level(0.3) == ConfidenceLevel.LOW
        assert confidence_engine._get_confidence_level(0.1) == ConfidenceLevel.VERY_LOW

    def test_signal_outcome_update(self, confidence_engine, sample_signal_input):
        """Test updating signal outcomes for learning"""

        # First calculate confidence to store signal
        metrics = confidence_engine.calculate_confidence(sample_signal_input)

        # Update outcome
        confidence_engine.update_signal_outcome(
            signal_id="test_001",
            outcome="success",
            performance_score=0.85
        )

        # Check that outcome was recorded
        signal_found = False
        for record in confidence_engine.signal_history:
            if record['signal_id'] == "test_001":
                assert record['outcome'] == "success"
                assert record['performance_score'] == 0.85
                signal_found = True
                break

        assert signal_found

        # Check that performance cache was updated
        cache_key = f"{sample_signal_input.source.value}_{sample_signal_input.symbol}"
        assert cache_key in confidence_engine.performance_cache

    def test_recent_performance_calculation(self, confidence_engine):
        """Test recent performance calculation"""

        # Add some historical signals
        base_time = datetime.utcnow()

        for i in range(5):
            record = {
                'signal_id': f'test_{i}',
                'symbol': 'BTCUSDT',
                'source': SignalSource.TECHNICAL_ANALYSIS.value,
                'timestamp': base_time - timedelta(days=i),
                'outcome': 'success' if i % 2 == 0 else 'failure'
            }
            confidence_engine.signal_history.append(record)

        # Calculate recent performance
        performance = confidence_engine._calculate_recent_performance(
            SignalSource.TECHNICAL_ANALYSIS,
            'BTCUSDT',
            days=7
        )

        # Should be 0.6 (3 successes out of 5)
        assert performance == 0.6

    def test_confidence_statistics(self, confidence_engine, sample_signal_input):
        """Test confidence statistics generation"""

        # Generate some signals
        for i in range(5):
            signal_input = SignalInput(
                signal_id=f"test_{i}",
                symbol="BTCUSDT",
                direction="buy",
                source=SignalSource.TECHNICAL_ANALYSIS,
                base_score=0.7 + i * 0.05
            )
            confidence_engine.calculate_confidence(signal_input)

        # Get statistics
        stats = confidence_engine.get_confidence_statistics()

        assert 'total_signals' in stats
        assert 'recent_signals' in stats
        assert 'avg_confidence' in stats
        assert 'confidence_levels' in stats

        assert stats['total_signals'] >= 5
        assert stats['avg_confidence'] > 0.0

    def test_different_signal_sources(self, confidence_engine):
        """Test confidence calculation for different signal sources"""

        sources = [
            SignalSource.TECHNICAL_ANALYSIS,
            SignalSource.SENTIMENT_ANALYSIS,
            SignalSource.NEWS_ANALYSIS,
            SignalSource.FUNDAMENTAL_ANALYSIS
        ]

        results = {}

        for source in sources:
            signal_input = SignalInput(
                signal_id=f"test_{source.value}",
                symbol="BTCUSDT",
                direction="buy",
                source=source,
                base_score=0.75
            )

            metrics = confidence_engine.calculate_confidence(signal_input)
            results[source] = metrics.adjusted_confidence

        # Different sources should produce different confidence scores
        # due to source-specific adjustments
        unique_scores = set(results.values())
        assert len(unique_scores) > 1

    def test_confidence_bounds(self, confidence_engine):
        """Test that confidence scores stay within bounds"""

        # Test with extreme values
        signal_input = SignalInput(
            signal_id="extreme_test",
            symbol="BTCUSDT",
            direction="buy",
            source=SignalSource.TECHNICAL_ANALYSIS,
            base_score=2.0,  # Extreme value
            indicators={'rsi': 5.0},  # Extreme value
            volatility=200.0  # Extreme value
        )

        metrics = confidence_engine.calculate_confidence(signal_input)

        # Should be within configured bounds
        assert confidence_engine.min_confidence <= metrics.adjusted_confidence <= confidence_engine.max_confidence

    def test_error_handling_in_confidence_calculation(self, confidence_engine):
        """Test error handling during confidence calculation"""

        # Create signal input that might cause errors
        signal_input = SignalInput(
            signal_id="error_test",
            symbol="INVALID_SYMBOL",
            direction="invalid_direction",
            source=SignalSource.TECHNICAL_ANALYSIS,
            base_score=0.0
        )

        # Should handle errors gracefully and return default metrics
        metrics = confidence_engine.calculate_confidence(signal_input)

        assert isinstance(metrics, ConfidenceMetrics)
        assert metrics.adjusted_confidence > 0.0
        assert metrics.confidence_level == ConfidenceLevel.MODERATE

    def test_factor_counting(self, confidence_engine, sample_signal_input):
        """Test counting of active factors"""

        metrics = confidence_engine.calculate_confidence(sample_signal_input)

        # Should count factors that contributed to the calculation
        assert metrics.factors_count > 0

        # Factor count should be reasonable (not all factors for this test)
        assert metrics.factors_count <= 10


class TestSignalInput:
    """Test SignalInput data class"""

    def test_signal_input_creation(self):
        """Test creating SignalInput instances"""

        signal = SignalInput(
            signal_id="test",
            symbol="BTCUSDT",
            direction="buy",
            source=SignalSource.TECHNICAL_ANALYSIS,
            base_score=0.8
        )

        assert signal.signal_id == "test"
        assert signal.symbol == "BTCUSDT"
        assert signal.direction == "buy"
        assert signal.source == SignalSource.TECHNICAL_ANALYSIS
        assert signal.base_score == 0.8

        # Test defaults
        assert signal.price == 0.0
        assert signal.volume == 0.0
        assert len(signal.indicators) == 0
        assert len(signal.metadata) == 0

    def test_signal_input_with_indicators(self):
        """Test SignalInput with technical indicators"""

        indicators = {
            'rsi': 0.3,
            'macd': 0.7,
            'bollinger_upper': 0.9
        }

        signal = SignalInput(
            signal_id="test_indicators",
            symbol="ETHUSDT",
            direction="sell",
            source=SignalSource.TECHNICAL_ANALYSIS,
            base_score=0.6,
            indicators=indicators
        )

        assert len(signal.indicators) == 3
        assert signal.indicators['rsi'] == 0.3
        assert signal.indicators['macd'] == 0.7


class TestConfidenceEngineIntegration:
    """Integration tests for confidence engine"""

    def test_complete_confidence_workflow(self):
        """Test complete confidence scoring workflow"""

        # Create engine
        config = {'min_confidence': 0.2, 'max_confidence': 0.9}
        engine = ConfidenceEngine(config)

        # Create comprehensive signal
        signal = SignalInput(
            signal_id="integration_test",
            symbol="BTCUSDT",
            direction="buy",
            source=SignalSource.TECHNICAL_ANALYSIS,
            base_score=0.8,
            indicators={
                'rsi': 0.25,
                'macd': 0.65,
                'bollinger': 0.80,
                'ema_cross': 0.70
            },
            price=45000.0,
            volume=2000000.0,
            volatility=35.0,
            news_sentiment=0.3,
            news_count=8,
            social_sentiment=0.1,
            historical_accuracy=0.72,
            recent_performance=0.68
        )

        # Calculate confidence
        metrics = engine.calculate_confidence(signal)

        # Verify comprehensive result
        assert isinstance(metrics, ConfidenceMetrics)
        assert 0.2 <= metrics.adjusted_confidence <= 0.9
        assert metrics.confidence_level in ConfidenceLevel
        assert metrics.factors_count >= 5  # Should use many factors

        # Verify individual factor scores
        assert metrics.signal_strength > 0
        assert metrics.signal_consistency > 0
        assert metrics.signal_convergence > 0
        assert metrics.strategy_accuracy > 0

        # Update outcome and verify learning
        engine.update_signal_outcome("integration_test", "success", 0.85)

        # Get statistics
        stats = engine.get_confidence_statistics()
        assert stats['total_signals'] >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
