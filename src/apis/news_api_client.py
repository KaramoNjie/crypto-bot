"""
News API client with proper error handling and retry logic (Fix: Bug #2 - Made synchronous)
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import requests
from dataclasses import dataclass

# Add the src directory to the Python path


@dataclass
class NewsArticle:
    """News article data structure"""

    title: str
    description: str
    content: str
    url: str
    source: str
    published_at: datetime
    author: Optional[str] = None
    image_url: Optional[str] = None


class NewsAPIClient:
    """
    Enhanced News API client with multiple sources and robust error handling
    Fixed: Bug #2 - Made synchronous to match usage patterns
    """

    def __init__(self, config) -> None:
        self.config = config
        self.logger = logging.getLogger(__name__)

        # API keys
        self.newsapi_key = getattr(config, "NEWSAPI_KEY", None)
        self.cryptopanic_key = getattr(config, "CRYPTOPANIC_API_KEY", None)

        # Rate limiting
        self.last_request = {}
        self.min_interval = 1.0  # 1 second between requests

        # Health tracking
        self.is_healthy = True
        self.error_count = 0

        # Session for connection pooling
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "CryptoTradingBot/1.0"})

    def get_news(
        self,
        query: str,
        language: str = "en",
        sort_by: str = "publishedAt",
        page_size: int = 20,
        sources: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get news articles from multiple sources (Fix: Bug #2 - Made synchronous)

        Args:
            query: Search query
            language: Language code
            sort_by: Sort order (publishedAt, relevancy, popularity)
            page_size: Number of articles to return
            sources: List of sources to search

        Returns:
            List of news articles
        """
        all_articles = []

        try:
            # Try NewsAPI first
            if self.newsapi_key:
                newsapi_articles = self._get_newsapi_articles(
                    query=query,
                    language=language,
                    sort_by=sort_by,
                    page_size=page_size,
                    sources=sources,
                )
                all_articles.extend(newsapi_articles)

            # Try CryptoPanic for crypto-specific news
            if self.cryptopanic_key and self._is_crypto_query(query):
                crypto_articles = self._get_cryptopanic_articles(
                    query=query, page_size=page_size
                )
                all_articles.extend(crypto_articles)

            # Fallback to free sources if no API keys
            if not all_articles and not self.newsapi_key:
                free_articles = self._get_free_news_sources(query, page_size)
                all_articles.extend(free_articles)

            # Remove duplicates and sort by publication date
            unique_articles = self._deduplicate_articles(all_articles)
            sorted_articles = sorted(
                unique_articles, key=lambda x: x.get("publishedAt", ""), reverse=True
            )

            self.logger.info(
                f"Retrieved {len(sorted_articles)} unique articles for query: {query}"
            )

            return sorted_articles[:page_size]

        except Exception as e:
            self.logger.error(f"Error getting news: {e}")
            self.error_count += 1
            return []

    def _get_newsapi_articles(
        self,
        query: str,
        language: str,
        sort_by: str,
        page_size: int,
        sources: Optional[List[str]],
    ) -> List[Dict[str, Any]]:
        """Get articles from NewsAPI.org"""
        try:
            self._rate_limit("newsapi")

            url = "https://newsapi.org/v2/everything"

            params = {
                "q": query,
                "language": language,
                "sortBy": sort_by,
                "pageSize": min(page_size, 100),  # NewsAPI limit
                "apiKey": self.newsapi_key,
            }

            if sources:
                params["sources"] = ",".join(sources)

            response = self.session.get(url, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "ok":
                    return self._format_newsapi_articles(data.get("articles", []))
                else:
                    self.logger.warning(f"NewsAPI error: {data.get('message')}")
            else:
                self.logger.warning(f"NewsAPI HTTP error: {response.status_code}")

            return []

        except Exception as e:
            self.logger.error(f"Error getting NewsAPI articles: {e}")
            return []

    def _get_cryptopanic_articles(
        self, query: str, page_size: int
    ) -> List[Dict[str, Any]]:
        """Get articles from CryptoPanic"""
        try:
            self._rate_limit("cryptopanic")

            url = "https://cryptopanic.com/api/developer/v2/posts/"

            params = {
                "auth_token": self.cryptopanic_key,
                "public": "true",
                "kind": "news",
                "filter": "hot",
            }

            # Add currency filter if query matches known cryptocurrencies
            crypto_map = {
                "bitcoin": "BTC", "btc": "BTC",
                "ethereum": "ETH", "eth": "ETH",
                "cardano": "ADA", "ada": "ADA",
                "polkadot": "DOT", "dot": "DOT",
                "solana": "SOL", "sol": "SOL",
                "ripple": "XRP", "xrp": "XRP",
                "dogecoin": "DOGE", "doge": "DOGE",
                "avalanche": "AVAX", "avax": "AVAX",
                "chainlink": "LINK", "link": "LINK",
                "bnb": "BNB", "binance": "BNB",
            }

            query_lower = query.lower()
            for crypto_name, symbol in crypto_map.items():
                if crypto_name in query_lower:
                    params["currencies"] = symbol
                    break

            response = self.session.get(url, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                return self._format_cryptopanic_articles(data.get("results", []))
            else:
                self.logger.warning(f"CryptoPanic HTTP error: {response.status_code}")

            return []

        except Exception as e:
            self.logger.error(f"Error getting CryptoPanic articles: {e}")
            return []

    def _get_free_news_sources(
        self, query: str, page_size: int
    ) -> List[Dict[str, Any]]:
        """Get articles from free RSS sources"""
        try:
            # Use actual RSS feeds for free news sources
            rss_sources = [
                {
                    "url": "https://cointelegraph.com/rss",
                    "source_name": "Cointelegraph",
                },
                {
                    "url": "https://coindesk.com/arc/outboundfeeds/rss/",
                    "source_name": "CoinDesk",
                },
                {
                    "url": "https://cryptonews.com/news/feed/",
                    "source_name": "Crypto News",
                },
            ]

            all_articles = []

            for rss_source in rss_sources:
                try:
                    # Fetch RSS feed
                    response = self.session.get(rss_source["url"], timeout=10)
                    if response.status_code == 200:
                        # Parse RSS and extract articles
                        articles = self._parse_rss_feed(response.content, rss_source["source_name"], query)
                        all_articles.extend(articles)
                except Exception as e:
                    self.logger.warning(f"Failed to fetch from {rss_source['source_name']}: {e}")
                    continue

            # Filter by query relevance and limit results
            relevant_articles = self._filter_articles_by_relevance(all_articles, query)
            return relevant_articles[:page_size]

        except Exception as e:
            self.logger.error(f"Error getting free news sources: {e}")
            return []

    def _parse_rss_feed(self, rss_content: bytes, source_name: str, query: str) -> List[Dict[str, Any]]:
        """Parse RSS feed content"""
        try:
            import xml.etree.ElementTree as ET

            articles = []
            root = ET.fromstring(rss_content)

            # Find all item elements
            for item in root.findall(".//item"):
                try:
                    title = item.find("title")
                    description = item.find("description")
                    link = item.find("link")
                    pub_date = item.find("pubDate")

                    if title is not None and link is not None:
                        article = {
                            "title": title.text or "",
                            "description": description.text or "" if description is not None else "",
                            "url": link.text or "",
                            "source": {"name": source_name},
                            "publishedAt": pub_date.text or "" if pub_date is not None else datetime.now().isoformat(),
                            "author": source_name,
                        }

                        # Only include if relevant to query
                        if self._is_article_relevant(article, query):
                            articles.append(article)

                except Exception as e:
                    self.logger.warning(f"Error parsing RSS item: {e}")
                    continue

            return articles

        except Exception as e:
            self.logger.error(f"Error parsing RSS feed: {e}")
            return []

    def _filter_articles_by_relevance(self, articles: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
        """Filter articles by relevance to query"""
        try:
            query_terms = query.lower().split()
            relevant_articles = []

            for article in articles:
                relevance_score = 0
                text_to_check = f"{article.get('title', '')} {article.get('description', '')}".lower()

                # Calculate relevance score
                for term in query_terms:
                    if term in text_to_check:
                        relevance_score += 1

                # Include if at least one query term matches
                if relevance_score > 0:
                    article["relevance_score"] = relevance_score
                    relevant_articles.append(article)

            # Sort by relevance score
            relevant_articles.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
            return relevant_articles

        except Exception as e:
            self.logger.error(f"Error filtering articles by relevance: {e}")
            return articles

    def _is_article_relevant(self, article: Dict[str, Any], query: str) -> bool:
        """Check if article is relevant to the query"""
        try:
            text_to_check = f"{article.get('title', '')} {article.get('description', '')}".lower()
            query_lower = query.lower()

            # Check for direct query match
            if query_lower in text_to_check:
                return True

            # Check for crypto-related keywords if query is crypto-related
            if self._is_crypto_query(query):
                return self._is_crypto_relevant(article)

            # Check for any query term match
            query_terms = query_lower.split()
            return any(term in text_to_check for term in query_terms)

        except Exception as e:
            self.logger.warning(f"Error checking article relevance: {e}")
            return False

    def _format_newsapi_articles(self, articles: List[Dict]) -> List[Dict[str, Any]]:
        """Format NewsAPI articles to standard format"""
        formatted = []
        for article in articles:
            try:
                formatted.append(
                    {
                        "title": article.get("title", ""),
                        "description": article.get("description", ""),
                        "content": article.get("content", ""),
                        "url": article.get("url", ""),
                        "source": article.get("source", {}).get("name", ""),
                        "publishedAt": article.get("publishedAt", ""),
                        "author": article.get("author", ""),
                        "urlToImage": article.get("urlToImage", ""),
                    }
                )
            except Exception as e:
                self.logger.warning(f"Error formatting NewsAPI article: {e}")
                continue
        return formatted

    def _format_cryptopanic_articles(
        self, articles: List[Dict]
    ) -> List[Dict[str, Any]]:
        """Format CryptoPanic articles to standard format"""
        formatted = []
        for article in articles:
            try:
                # v2 API returns description directly; source may be string or dict
                source = article.get("source", "CryptoPanic")
                if isinstance(source, dict):
                    source = source.get("title", "CryptoPanic")
                formatted.append(
                    {
                        "title": article.get("title", ""),
                        "description": article.get("description", article.get("title", "")),
                        "content": article.get("description", ""),
                        "url": article.get("url", ""),
                        "source": source or "CryptoPanic",
                        "publishedAt": article.get("published_at", article.get("created_at", "")),
                        "author": "",
                        "urlToImage": "",
                    }
                )
            except Exception as e:
                self.logger.warning(f"Error formatting CryptoPanic article: {e}")
                continue
        return formatted

    def _deduplicate_articles(
        self, articles: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Remove duplicate articles based on URL"""
        seen_urls = set()
        unique_articles = []

        for article in articles:
            url = article.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_articles.append(article)

        return unique_articles

    def _is_crypto_query(self, query: str) -> bool:
        """Check if query is related to cryptocurrency"""
        crypto_keywords = [
            "bitcoin",
            "ethereum",
            "crypto",
            "cryptocurrency",
            "blockchain",
            "btc",
            "eth",
            "ada",
            "dot",
            "sol",
            "bnb",
            "trading",
            "defi",
        ]
        query_lower = query.lower()
        return any(keyword in query_lower for keyword in crypto_keywords)

    def _is_crypto_relevant(self, article: Dict[str, Any]) -> bool:
        """
        Check if an article is relevant to cryptocurrency (Fix: Issue #2 - Missing method)

        Args:
            article: Article dictionary

        Returns:
            bool: True if article is crypto-relevant
        """
        try:
            # Check title and description for crypto keywords
            text_to_check = " ".join(
                [
                    article.get("title", ""),
                    article.get("description", ""),
                    article.get("content", ""),
                ]
            ).lower()

            crypto_keywords = [
                "bitcoin",
                "ethereum",
                "crypto",
                "cryptocurrency",
                "blockchain",
                "btc",
                "eth",
                "ada",
                "dot",
                "sol",
                "bnb",
                "trading",
                "defi",
                "altcoin",
                "mining",
                "wallet",
                "exchange",
                "ico",
                "nft",
            ]

            return any(keyword in text_to_check for keyword in crypto_keywords)
        except Exception as e:
            self.logger.warning(f"Error checking crypto relevance: {e}")
            return False

    def _categorize_news(
        self, articles: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Categorize news articles by type (Fix: Issue #2 - Missing method)

        Args:
            articles: List of articles to categorize

        Returns:
            Dict with categories as keys and article lists as values
        """
        try:
            categories = {
                "market": [],
                "technology": [],
                "regulation": [],
                "adoption": [],
                "other": [],
            }

            for article in articles:
                text = " ".join(
                    [article.get("title", ""), article.get("description", "")]
                ).lower()

                if any(
                    word in text
                    for word in ["price", "market", "trading", "bull", "bear"]
                ):
                    categories["market"].append(article)
                elif any(
                    word in text
                    for word in ["technology", "blockchain", "protocol", "upgrade"]
                ):
                    categories["technology"].append(article)
                elif any(
                    word in text
                    for word in ["regulation", "government", "law", "sec", "legal"]
                ):
                    categories["regulation"].append(article)
                elif any(
                    word in text
                    for word in ["adoption", "partnership", "integration", "accept"]
                ):
                    categories["adoption"].append(article)
                else:
                    categories["other"].append(article)

            return categories
        except Exception as e:
            self.logger.error(f"Error categorizing news: {e}")
            return {"other": articles}

    def _rate_limit(self, source: str):
        """Simple rate limiting"""
        try:
            current_time = time.time()
            last_time = self.last_request.get(source, 0)

            time_since_last = current_time - last_time
            if time_since_last < self.min_interval:
                sleep_time = self.min_interval - time_since_last
                time.sleep(sleep_time)

            self.last_request[source] = time.time()
        except Exception as e:
            self.logger.warning(f"Error in rate limiting: {e}")

    def get_health_status(self) -> Dict[str, Any]:
        """Get health status of the news client"""
        return {
            "is_healthy": self.is_healthy,
            "error_count": self.error_count,
            "has_newsapi_key": bool(self.newsapi_key),
            "has_cryptopanic_key": bool(self.cryptopanic_key),
        }

    def reset_error_count(self):
        """Reset error count"""
        self.error_count = 0
        self.is_healthy = True

    def test_connection(self) -> Dict[str, Any]:
        """Test news API connection"""
        try:
            # Test if we can fetch a simple query
            test_articles = self.get_news("bitcoin", page_size=1)

            if test_articles:
                return {
                    "status": "healthy",
                    "message": f"Connected (found {len(test_articles)} articles)",
                    "has_newsapi": bool(self.newsapi_key),
                    "has_cryptopanic": bool(self.cryptopanic_key),
                }
            else:
                return {
                    "status": "warning",
                    "message": "Connected but no articles found",
                    "has_newsapi": bool(self.newsapi_key),
                    "has_cryptopanic": bool(self.cryptopanic_key),
                }

        except Exception as e:
            self.logger.error(f"News API connection test failed: {e}")
            return {
                "status": "error",
                "message": f"Connection failed: {str(e)}",
                "has_newsapi": bool(self.newsapi_key),
                "has_cryptopanic": bool(self.cryptopanic_key),
            }

    def close(self):
        """Close the session"""
        try:
            self.session.close()
        except Exception as e:
            self.logger.warning(f"Error closing session: {e}")
