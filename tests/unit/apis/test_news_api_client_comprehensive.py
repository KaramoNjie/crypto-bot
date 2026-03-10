"""
Comprehensive unit tests for NewsAPIClient class.
Tests all functionality including news fetching, filtering, categorization, and error handling.
"""
import pytest
import unittest.mock as mock
import requests
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict, Any, Optional
import time

from src.apis.news_api_client import NewsAPIClient


class TestNewsAPIClientInitialization:
    """Test NewsAPIClient initialization scenarios."""

    def test_init_with_valid_api_key(self):
        """Test initialization with valid API key."""
        client = NewsAPIClient("test_api_key")
        assert client.api_key == "test_api_key"
        assert client.base_url == "https://newsapi.org/v2"

    def test_init_with_empty_api_key(self):
        """Test initialization with empty API key raises ValueError."""
        with pytest.raises(ValueError, match="API key cannot be empty"):
            NewsAPIClient("")

    def test_init_with_none_api_key(self):
        """Test initialization with None API key raises ValueError."""
        with pytest.raises(ValueError, match="API key cannot be empty"):
            NewsAPIClient(None)


class TestNewsAPIClientFetching:
    """Test news fetching functionality."""

    @pytest.fixture
    def client(self):
        """Create test client instance."""
        return NewsAPIClient("test_api_key")

    @pytest.fixture
    def mock_news_response(self):
        """Mock successful news API response."""
        return {
            "status": "ok",
            "totalResults": 2,
            "articles": [
                {
                    "source": {"id": "reuters", "name": "Reuters"},
                    "author": "Test Author 1",
                    "title": "Bitcoin hits new high amid institutional adoption",
                    "description": "Bitcoin reached $50,000 as more institutions adopt cryptocurrency",
                    "url": "https://example.com/news1",
                    "urlToImage": "https://example.com/image1.jpg",
                    "publishedAt": "2024-01-15T10:00:00Z",
                    "content": "Bitcoin trading volume increased significantly..."
                },
                {
                    "source": {"id": "coindesk", "name": "CoinDesk"},
                    "author": "Test Author 2",
                    "title": "Ethereum network upgrade improves scalability",
                    "description": "New Ethereum upgrade reduces transaction costs",
                    "url": "https://example.com/news2",
                    "urlToImage": "https://example.com/image2.jpg",
                    "publishedAt": "2024-01-15T09:00:00Z",
                    "content": "Ethereum gas fees decreased after upgrade..."
                }
            ]
        }

    @patch('requests.get')
    def test_get_news_success(self, mock_get, client, mock_news_response):
        """Test successful news fetching."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_news_response
        mock_get.return_value = mock_response

        result = client.get_news("bitcoin")

        assert len(result) == 2
        assert result[0]["title"] == "Bitcoin hits new high amid institutional adoption"
        assert result[1]["title"] == "Ethereum network upgrade improves scalability"
        mock_get.assert_called_once()

    @patch('requests.get')
    def test_get_news_with_parameters(self, mock_get, client, mock_news_response):
        """Test news fetching with custom parameters."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_news_response
        mock_get.return_value = mock_response

        result = client.get_news(
            query="ethereum",
            language="en",
            sort_by="popularity",
            page_size=50,
            sources=["coindesk", "reuters"]
        )

        assert len(result) == 2
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        assert "q=ethereum" in kwargs["params"]
        assert kwargs["params"]["language"] == "en"
        assert kwargs["params"]["sortBy"] == "popularity"
        assert kwargs["params"]["pageSize"] == 50
        assert kwargs["params"]["sources"] == "coindesk,reuters"

    @patch('requests.get')
    def test_get_news_api_error(self, mock_get, client):
        """Test handling of API error response."""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            "status": "error",
            "code": "parameterInvalid",
            "message": "You are missing a required parameter"
        }
        mock_get.return_value = mock_response

        result = client.get_news("bitcoin")

        assert result == []

    @patch('requests.get')
    def test_get_news_network_error(self, mock_get, client):
        """Test handling of network errors."""
        mock_get.side_effect = requests.RequestException("Network error")

        result = client.get_news("bitcoin")

        assert result == []

    @patch('requests.get')
    def test_get_news_timeout(self, mock_get, client):
        """Test handling of request timeout."""
        mock_get.side_effect = requests.Timeout("Request timeout")

        result = client.get_news("bitcoin")

        assert result == []

    @patch('requests.get')
    def test_get_news_invalid_json(self, mock_get, client):
        """Test handling of invalid JSON response."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_get.return_value = mock_response

        result = client.get_news("bitcoin")

        assert result == []


class TestNewsAPIClientFiltering:
    """Test news filtering and categorization functionality."""

    @pytest.fixture
    def client(self):
        """Create test client instance."""
        return NewsAPIClient("test_api_key")

    def test_is_crypto_relevant_positive_cases(self, client):
        """Test crypto relevance detection for positive cases."""
        crypto_titles = [
            "Bitcoin hits new ATH",
            "Ethereum merge successful",
            "Cryptocurrency adoption grows",
            "BTC price surges",
            "ETH network upgrade",
            "Altcoin market rallies",
            "DeFi protocols expand",
            "NFT trading volume increases",
            "Blockchain technology advances",
            "Digital currency regulations"
        ]

        for title in crypto_titles:
            article = {"title": title, "description": "Test description"}
            assert client._is_crypto_relevant(article), f"Failed for title: {title}"

    def test_is_crypto_relevant_negative_cases(self, client):
        """Test crypto relevance detection for negative cases."""
        non_crypto_titles = [
            "Stock market opens higher",
            "Tech earnings exceed expectations",
            "Oil prices fluctuate",
            "Real estate market trends",
            "Banking sector analysis",
            "Economic indicators improve",
            "Weather forecast update",
            "Sports news headlines"
        ]

        for title in non_crypto_titles:
            article = {"title": title, "description": "Test description"}
            assert not client._is_crypto_relevant(article), f"Failed for title: {title}"

    def test_is_crypto_relevant_description_check(self, client):
        """Test crypto relevance based on description content."""
        article = {
            "title": "Market Update",
            "description": "Bitcoin and Ethereum prices show strong momentum today"
        }
        assert client._is_crypto_relevant(article)

        article = {
            "title": "Market Update",
            "description": "Traditional stocks perform well in today's session"
        }
        assert not client._is_crypto_relevant(article)

    def test_categorize_news_types(self, client):
        """Test news categorization into different types."""
        test_cases = [
            ({"title": "Bitcoin price surges to $50k", "description": "BTC hits new high"}, "price"),
            ({"title": "New crypto regulations announced", "description": "SEC releases guidelines"}, "regulation"),
            ({"title": "Major bank adopts Bitcoin", "description": "Institution adds BTC to portfolio"}, "adoption"),
            ({"title": "Ethereum network upgrade deployed", "description": "Protocol improvement goes live"}, "technology"),
            ({"title": "Crypto exchange hacked", "description": "Security breach reported"}, "security"),
            ({"title": "Bitcoin mining update", "description": "Hash rate increases"}, "mining"),
            ({"title": "DeFi protocol launches", "description": "New yield farming opportunity"}, "defi"),
            ({"title": "NFT marketplace opens", "description": "Digital art trading platform"}, "nft"),
            ({"title": "Crypto market analysis", "description": "General market overview"}, "market")
        ]

        for article, expected_category in test_cases:
            category = client._categorize_news(article)
            assert category == expected_category, f"Expected {expected_category}, got {category} for {article['title']}"

    @patch('requests.get')
    def test_get_crypto_news_filtering(self, mock_get, client):
        """Test filtering of crypto-relevant news."""
        mock_response_data = {
            "status": "ok",
            "totalResults": 3,
            "articles": [
                {
                    "title": "Bitcoin reaches new high",
                    "description": "Cryptocurrency markets surge",
                    "source": {"name": "CryptoNews"},
                    "publishedAt": "2024-01-15T10:00:00Z"
                },
                {
                    "title": "Stock market opens higher",
                    "description": "Traditional markets perform well",
                    "source": {"name": "MarketWatch"},
                    "publishedAt": "2024-01-15T09:00:00Z"
                },
                {
                    "title": "Ethereum upgrade successful",
                    "description": "Network improvements deployed",
                    "source": {"name": "EthNews"},
                    "publishedAt": "2024-01-15T08:00:00Z"
                }
            ]
        }

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_get.return_value = mock_response

        result = client.get_crypto_news("bitcoin", limit=10)

        # Should only return crypto-relevant articles (2 out of 3)
        assert len(result) == 2
        assert "Bitcoin" in result[0]["title"]
        assert "Ethereum" in result[1]["title"]


class TestNewsAPIClientPerformance:
    """Test NewsAPIClient performance and resource usage."""

    @pytest.fixture
    def client(self):
        """Create test client instance."""
        return NewsAPIClient("test_api_key")

    @patch('requests.get')
    def test_request_timeout_configuration(self, mock_get, client):
        """Test that requests include proper timeout configuration."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ok", "articles": []}
        mock_get.return_value = mock_response

        client.get_news("bitcoin")

        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        assert kwargs.get("timeout") is not None
        assert kwargs["timeout"] > 0

    @patch('requests.get')
    def test_large_response_handling(self, mock_get, client):
        """Test handling of large response with many articles."""
        # Create mock response with 100 articles
        articles = []
        for i in range(100):
            articles.append({
                "title": f"Bitcoin news article {i}",
                "description": f"Description {i}",
                "source": {"name": "TestSource"},
                "publishedAt": "2024-01-15T10:00:00Z"
            })

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ok", "articles": articles}
        mock_get.return_value = mock_response

        start_time = time.time()
        result = client.get_news("bitcoin")
        end_time = time.time()

        assert len(result) == 100
        # Should process 100 articles in reasonable time (< 1 second)
        assert (end_time - start_time) < 1.0


class TestNewsAPIClientEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.fixture
    def client(self):
        """Create test client instance."""
        return NewsAPIClient("test_api_key")

    @patch('requests.get')
    def test_empty_response(self, mock_get, client):
        """Test handling of empty response."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ok", "articles": []}
        mock_get.return_value = mock_response

        result = client.get_news("bitcoin")

        assert result == []

    @patch('requests.get')
    def test_malformed_articles(self, mock_get, client):
        """Test handling of malformed article data."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "ok",
            "articles": [
                {"title": "Valid article", "description": "Valid description"},
                {"title": None, "description": "Missing title"},  # Invalid
                {"description": "Missing title field"},  # Invalid
                {}  # Empty article
            ]
        }
        mock_get.return_value = mock_response

        result = client.get_news("bitcoin")

        # Should only return valid articles
        assert len(result) == 1
        assert result[0]["title"] == "Valid article"

    def test_special_characters_in_query(self, client):
        """Test handling of special characters in search query."""
        special_queries = [
            "bitcoin & ethereum",
            "crypto-currency",
            "BTC/USD",
            "test@example.com",
            "crypto#hashtag",
            "bitcoin%20price"
        ]

        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"status": "ok", "articles": []}
            mock_get.return_value = mock_response

            for query in special_queries:
                result = client.get_news(query)
                assert isinstance(result, list)
                mock_get.assert_called()

    @patch('requests.get')
    def test_rate_limit_handling(self, mock_get, client):
        """Test handling of rate limit responses."""
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.json.return_value = {
            "status": "error",
            "code": "rateLimited",
            "message": "You have made too many requests"
        }
        mock_get.return_value = mock_response

        result = client.get_news("bitcoin")

        assert result == []

    def test_unicode_content_handling(self, client):
        """Test handling of Unicode content in articles."""
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "status": "ok",
                "articles": [
                    {
                        "title": "Bitcoin 价格上涨 💰",
                        "description": "加密货币市场表现良好 🚀",
                        "source": {"name": "TestSource"},
                        "publishedAt": "2024-01-15T10:00:00Z"
                    }
                ]
            }
            mock_get.return_value = mock_response

            result = client.get_news("bitcoin")

            assert len(result) == 1
            assert "💰" in result[0]["title"]
            assert "🚀" in result[0]["description"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
