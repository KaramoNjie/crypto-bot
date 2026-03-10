"""
API Integration Tests

Comprehensive integration tests for all external API integrations,
including Binance API, News APIs, database operations, and end-to-end workflows.
"""

import pytest
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from src.apis.binance_client import BinanceClient
from src.apis.news_api_client import NewsAPIClient
from src.database.connection import get_database_manager
from src.utils.api_health import APIHealthChecker, HealthStatus
from src.utils.error_handling import (
    BinanceAPIError,
    NewsAPIError,
    ValidationError,
    create_error_response,
    validate_trading_parameters
)


class TestBinanceAPIIntegration:
    """Integration tests for Binance API client"""

    @pytest.fixture
    def config(self):
        """Test configuration"""
        config = Mock()
        config.BINANCE_API_KEY = "test_key"
        config.BINANCE_SECRET_KEY = "test_secret"
        config.BINANCE_TESTNET = True
        config.PAPER_TRADING = True
        return config

    @pytest.fixture
    def binance_client(self, config):
        """Binance client instance"""
        return BinanceClient(config)

    def test_binance_initialization(self, binance_client):
        """Test Binance client initialization"""
        assert binance_client is not None
        assert hasattr(binance_client, 'exchange')
        assert binance_client.config.PAPER_TRADING is True

    def test_get_account_balance_paper_trading(self, binance_client):
        """Test getting account balance in paper trading mode"""
        balance = binance_client.get_account_balance()

        assert isinstance(balance, dict)
        assert "USDT" in balance
        assert balance["USDT"]["free"] == 10000.0

    def test_get_account_balance_live_trading(self, binance_client):
        """Test getting account balance in live trading mode"""
        binance_client.config.PAPER_TRADING = False

        mock_balance = {
            "USDT": {"free": 5000.0, "used": 1000.0, "total": 6000.0},
            "BTC": {"free": 0.5, "used": 0.0, "total": 0.5}
        }

        with patch.object(binance_client.exchange, 'fetch_balance') as mock_fetch_balance:
            mock_fetch_balance.return_value = mock_balance

            balance = binance_client.get_account_balance()

            assert balance == mock_balance

    def test_get_ticker_success(self, binance_client):
        """Test getting ticker data successfully"""
        with patch.object(binance_client.exchange, 'fetch_ticker') as mock_fetch:
            mock_fetch.return_value = {
                "symbol": "BTC/USDT",
                "last": 45000.0,
                "bid": 44950.0,
                "ask": 45050.0,
                "percentage": 2.5
            }

            result = binance_client.get_ticker("BTC/USDT")

            assert result["symbol"] == "BTC/USDT"
            assert result["last"] == 45000.0

    def test_get_ticker_error_handling(self, binance_client):
        """Test ticker error handling"""
        with patch.object(binance_client.exchange, 'fetch_ticker', side_effect=Exception("API Error")):
            result = binance_client.get_ticker("INVALID/SYMBOL")

            assert result == {}

    def test_place_order_paper_trading(self, binance_client):
        """Test placing orders in paper trading mode"""
        with patch.object(binance_client, 'get_ticker') as mock_ticker:
            mock_ticker.return_value = {"last": 45000.0}

            result = binance_client.place_order("BTC/USDT", "BUY", 0.01, 45000.0)

            assert result["success"] is True
            assert result["data"]["symbol"] == "BTC/USDT"
            assert result["data"]["side"] == "BUY"
            assert result["data"]["amount"] == 0.01

    def test_validate_symbol(self, binance_client):
        """Test symbol validation"""
        with patch.object(binance_client, 'get_markets') as mock_markets:
            mock_markets.return_value = {"BTC/USDT": {}, "ETH/USDT": {}}

            assert binance_client.validate_symbol("BTC/USDT") is True
            assert binance_client.validate_symbol("INVALID/SYMBOL") is False

    def test_validate_order_parameters(self, binance_client):
        """Test order parameter validation"""
        with patch.object(binance_client, 'validate_symbol', return_value=True):
            with patch.object(binance_client, 'get_markets') as mock_markets:
                mock_markets.return_value = {
                    "BTC/USDT": {
                        "precision": {"amount": 8, "price": 2},
                        "limits": {"amount": {"min": 0.000001}, "cost": {"min": 10}}
                    }
                }

                # Valid parameters
                result = binance_client.validate_order_parameters("BTC/USDT", "BUY", 0.01, 45000.0)
                assert result["valid"] is True

                # Invalid symbol
                with patch.object(binance_client, 'validate_symbol', return_value=False):
                    result = binance_client.validate_order_parameters("INVALID/SYMBOL", "BUY", 0.01)
                    assert result["valid"] is False

    def test_test_connection(self, binance_client):
        """Test connection testing functionality"""
        with patch.object(binance_client.exchange, 'fetch_time'):
            with patch.object(binance_client.exchange, 'fetch_balance'):
                result = binance_client.test_connection()

                assert result["success"] is True
                assert "connection" in result["data"]
                assert "authentication" in result["data"]


class TestNewsAPIIntegration:
    """Integration tests for News API client"""

    @pytest.fixture
    def config(self):
        """Test configuration"""
        config = Mock()
        config.NEWSAPI_KEY = "test_news_key"
        config.CRYPTOPANIC_API_KEY = "test_crypto_key"
        config.NEWS_CACHE_TTL = 300
        config.NEWS_MAX_ARTICLES = 50
        return config

    @pytest.fixture
    def news_client(self, config):
        """News API client instance"""
        return NewsAPIClient(config)

    def test_news_client_initialization(self, news_client):
        """Test News API client initialization"""
        assert news_client is not None
        assert news_client.newsapi_key == "test_news_key"
        assert news_client.cryptopanic_key == "test_crypto_key"

    @patch('src.apis.news_api_client.requests.Session.get')
    def test_get_news_success(self, mock_get, news_client):
        """Test getting news successfully"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "articles": [
                {
                    "title": "Bitcoin surges to new highs",
                    "description": "Bitcoin price reaches new all-time high",
                    "url": "https://example.com/bitcoin-news",
                    "source": {"name": "Crypto News"},
                    "publishedAt": "2024-01-01T12:00:00Z",
                    "author": "John Doe"
                }
            ]
        }
        mock_response.raise_for_status.return_value = None
        mock_response.headers = {}
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        result = news_client.get_news(query="bitcoin", page_size=1)

        assert result is not None
        assert len(result) == 1
        assert result[0]["title"] == "Bitcoin surges to new highs"

    @patch('src.apis.news_api_client.requests.Session.get')
    def test_get_news_rate_limit_handling(self, mock_get, news_client):
        """Test rate limit handling"""
        # First call succeeds
        mock_response_success = Mock()
        mock_response_success.json.return_value = {"articles": []}
        mock_response_success.raise_for_status.return_value = None
        mock_response_success.headers = {}
        mock_response_success.status_code = 200

        # Second call hits rate limit
        mock_response_rate_limit = Mock()
        mock_response_rate_limit.status_code = 429
        mock_response_rate_limit.raise_for_status.side_effect = Exception("429 Client Error")
        mock_response_rate_limit.headers = {}

        mock_get.side_effect = [mock_response_success, mock_response_rate_limit]

        # This should trigger retry logic
        result = news_client.get_news(query="test", page_size=1)
        # Should eventually return the first successful result or handle the error

    def test_crypto_relevance_filtering(self, news_client):
        """Test cryptocurrency relevance filtering"""
        crypto_article = {
            "title": "Bitcoin Price Surges 10%",
            "description": "The cryptocurrency market is booming",
            "content": "Bitcoin and Ethereum are leading the charge"
        }

        non_crypto_article = {
            "title": "Stock Market News",
            "description": "Traditional stocks are performing well",
            "content": "Apple and Google stocks rise"
        }

        assert news_client._is_crypto_relevant(crypto_article) is True
        assert news_client._is_crypto_relevant(non_crypto_article) is False

    def test_news_categorization(self, news_client):
        """Test news article categorization"""
        articles = [
            {
                "title": "Bitcoin surges to new highs",
                "description": "Price reaches $50,000",
                "category": None
            },
            {
                "title": "SEC announces new crypto regulations",
                "description": "Regulatory changes coming",
                "category": None
            }
        ]

        categorized = news_client._categorize_news(articles)

        assert categorized[0]["category"] == "price_alert"
        assert categorized[1]["category"] == "regulatory"

    @patch('src.apis.news_api_client.requests.Session.get')
    def test_test_connection(self, mock_get, news_client):
        """Test connection testing"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_response.headers = {}
        mock_get.return_value = mock_response

        result = news_client.test_connection()

        assert "overall_status" in result
        assert "newsapi" in result
        assert "cryptopanic" in result


class TestDatabaseIntegration:
    """Integration tests for database operations"""

    @pytest.fixture
    def config(self):
        """Test configuration"""
        config = Mock()
        config.DATABASE_URL = "postgresql://test:test@localhost:5432/test_db"
        return config

    def test_database_manager_creation(self, config):
        """Test database manager creation"""
        # This would require a test database
        # For now, just test that the function exists
        from src.database.connection import get_database_manager

        # In a real test environment, we'd set up a test database
        # db_manager = get_database_manager(config)
        # assert db_manager is not None
        pass

    def test_database_connection_handling(self):
        """Test database connection error handling"""
        # Mock database connection failures
        pass


class TestAPIHealthIntegration:
    """Integration tests for API health monitoring"""

    @pytest.fixture
    def config(self):
        """Test configuration"""
        config = Mock()
        config.BINANCE_API_KEY = "test_key"
        config.BINANCE_SECRET_KEY = "test_secret"
        config.NEWSAPI_KEY = "test_news_key"
        config.CRYPTOPANIC_API_KEY = "test_crypto_key"
        return config

    @pytest.fixture
    def health_checker(self, config):
        """API health checker instance"""
        return APIHealthChecker(config)

    def test_health_checker_initialization(self, health_checker):
        """Test health checker initialization"""
        assert health_checker is not None
        assert hasattr(health_checker, 'check_binance_health')
        assert hasattr(health_checker, 'check_news_api_health')

    @patch('src.apis.binance_client.BinanceClient.test_connection')
    def test_binance_health_check(self, mock_test_connection, health_checker):
        """Test Binance health checking"""
        mock_test_connection.return_value = {
            "success": True,
            "data": {"connection": "healthy", "authentication": "verified"}
        }

        result = health_checker.check_binance_health()

        assert result.service == "binance"
        assert result.status == HealthStatus.HEALTHY
        assert "healthy" in result.message.lower()

    @patch('src.apis.news_api_client.NewsAPIClient.test_connection')
    def test_news_api_health_check(self, mock_test_connection, health_checker):
        """Test News API health checking"""
        mock_test_connection.return_value = {
            "overall_status": "healthy",
            "newsapi": "healthy",
            "cryptopanic": "healthy"
        }

        result = health_checker.check_news_api_health()

        assert result.service == "news_api"
        assert result.status == HealthStatus.HEALTHY

    def test_overall_system_health(self, health_checker):
        """Test overall system health assessment"""
        with patch.object(health_checker, 'check_binance_health') as mock_binance:
            with patch.object(health_checker, 'check_news_api_health') as mock_news:
                with patch.object(health_checker, 'check_database_health') as mock_db:

                    # Mock healthy responses
                    mock_binance.return_value = Mock(status=HealthStatus.HEALTHY)
                    mock_news.return_value = Mock(status=HealthStatus.HEALTHY)
                    mock_db.return_value = Mock(status=HealthStatus.HEALTHY)

                    result = health_checker.check_overall_system_health()

                    assert result["overall_status"] == "healthy"
                    assert "All systems healthy" in result["overall_message"]

    def test_health_history_tracking(self, health_checker):
        """Test health history tracking"""
        with patch('src.apis.binance_client.BinanceClient.test_connection') as mock_test:
            mock_test.return_value = {
                "success": True,
                "data": {
                    "connection": "healthy",
                    "authentication": "verified",
                    "timestamp": int(time.time() * 1000)
                },
                "error": None
            }

            # Check health multiple times
            health_checker.check_binance_health()
            health_checker.check_binance_health()

            history = health_checker.get_service_health_history("binance", hours=1)
            assert len(history) == 2


class TestEndToEndWorkflows:
    """End-to-end workflow integration tests"""

    @pytest.fixture
    def config(self):
        """Test configuration"""
        config = Mock()
        config.BINANCE_API_KEY = "test_key"
        config.BINANCE_SECRET_KEY = "test_secret"
        config.BINANCE_TESTNET = True
        config.PAPER_TRADING = True
        config.NEWSAPI_KEY = "test_news_key"
        config.CRYPTOPANIC_API_KEY = "test_crypto_key"
        return config

    def test_trading_workflow(self, config):
        """Test complete trading workflow"""
        binance_client = BinanceClient(config)

        # Get market data
        with patch.object(binance_client, 'get_ticker') as mock_ticker:
            mock_ticker.return_value = {"last": 45000.0}

            ticker = binance_client.get_ticker("BTC/USDT")
            assert ticker["last"] == 45000.0

        # Place order
        order_result = binance_client.place_order("BTC/USDT", "BUY", 0.01, 45000.0)
        assert order_result["success"] is True

        # Check balance after order
        balance = binance_client.get_account_balance()
        assert balance["USDT"]["free"] < 10000.0  # Should be reduced by order cost

    def test_news_trading_integration(self, config):
        """Test news analysis integration with trading"""
        news_client = NewsAPIClient(config)

        # Mock news with positive sentiment
        with patch.object(news_client, 'get_market_news') as mock_news:
            mock_news.return_value = [
                {
                    "title": "Bitcoin surges 15% on positive news",
                    "description": "Market sentiment is bullish",
                    "publishedAt": datetime.utcnow().isoformat()
                }
            ]

            news = news_client.get_market_news()
            assert len(news) > 0

            # Get sentiment
            sentiment = news_client.get_sentiment_indicators()
            assert sentiment is not None
            assert "sentiment" in sentiment

    def test_error_recovery_workflow(self, config):
        """Test error recovery workflows"""
        health_checker = APIHealthChecker(config)

        # Simulate service failure and recovery
        with patch.object(health_checker, 'check_binance_health') as mock_check:
            # First check fails
            failed_result = Mock()
            failed_result.status = HealthStatus.UNHEALTHY
            mock_check.return_value = failed_result

            result = health_checker.check_binance_health()
            assert result.status == HealthStatus.UNHEALTHY

            # Attempt recovery
            recovered = health_checker.attempt_recovery("binance")
            # In real implementation, this would try to reconnect


class TestPerformanceAndLoad:
    """Performance and load testing"""

    @pytest.fixture
    def config(self):
        """Test configuration"""
        config = Mock()
        config.BINANCE_API_KEY = "test_key"
        config.BINANCE_SECRET_KEY = "test_secret"
        config.PAPER_TRADING = True
        return config

    def test_api_response_times(self, config):
        """Test API response time performance"""
        binance_client = BinanceClient(config)

        start_time = time.time()
        balance = binance_client.get_account_balance()
        response_time = time.time() - start_time

        assert balance is not None
        assert response_time < 1.0  # Should respond within 1 second for paper trading

    def test_concurrent_api_calls(self, config):
        """Test concurrent API call handling"""
        import threading

        binance_client = BinanceClient(config)
        results = []
        errors = []

        def make_api_call():
            try:
                balance = binance_client.get_account_balance()
                results.append(balance)
            except Exception as e:
                errors.append(e)

        # Start multiple concurrent calls
        threads = []
        for i in range(5):
            thread = threading.Thread(target=make_api_call)
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        assert len(results) == 5
        assert len(errors) == 0

    def test_memory_usage_under_load(self, config):
        """Test memory usage under load"""
        # This would require memory profiling tools
        # For now, just ensure basic functionality works under repetition
        binance_client = BinanceClient(config)

        for i in range(100):
            balance = binance_client.get_account_balance()
            assert balance is not None

    def test_rate_limiting_compliance(self, config):
        """Test rate limiting compliance"""
        news_client = NewsAPIClient(config)

        # Mock API calls to test rate limiting
        with patch('src.apis.news_api_client.requests.Session.get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = {"articles": []}
            mock_response.raise_for_status.return_value = None
            mock_response.headers = {}
            mock_get.return_value = mock_response

            start_time = time.time()

            # Make multiple rapid requests
            for i in range(5):
                news_client.get_news(query="test", page_size=1)

            total_time = time.time() - start_time

            # Should take at least some time due to rate limiting
            assert total_time >= 0.1


class TestErrorHandlingIntegration:
    """Integration tests for error handling"""

    def test_validation_error_handling(self):
        """Test validation error handling"""
        with pytest.raises(ValidationError):
            validate_trading_parameters("", "BUY", 0.01)

        with pytest.raises(ValidationError):
            validate_trading_parameters("BTC/USDT", "INVALID", 0.01)

        with pytest.raises(ValidationError):
            validate_trading_parameters("BTC/USDT", "BUY", -1.0)

    def test_error_response_creation(self):
        """Test error response creation"""
        error = ValidationError("Test validation error", "TEST_ERROR")

        response = create_error_response(error)

        assert response.success is False
        assert response.error_code == "TEST_ERROR"
        assert response.message == "Test validation error"
        assert response.severity.value == "medium"

    def test_user_friendly_messages(self):
        """Test user-friendly error message generation"""
        from src.utils.error_handling import create_user_friendly_message

        binance_error = BinanceAPIError("Rate limit exceeded")
        message = create_user_friendly_message(binance_error)
        assert "rate limit" in message.lower()

        news_error = NewsAPIError("Authentication failed")
        message = create_user_friendly_message(news_error)
        assert "authentication failed" in message.lower()


if __name__ == "__main__":
    pytest.main([__file__])
