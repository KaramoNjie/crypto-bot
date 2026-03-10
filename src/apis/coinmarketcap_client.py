"""
CoinMarketCap API Client

This module provides an interface to the CoinMarketCap API for retrieving
cryptocurrency market data, global metrics, trending coins, and exchange information.
"""

import hashlib
import hmac
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import requests
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

logger = logging.getLogger(__name__)


class CoinMarketCapClient:
    """
    CoinMarketCap API client for cryptocurrency data

    Provides access to:
    - Cryptocurrency listings and quotes
    - Global market metrics
    - Trending cryptocurrencies
    - Exchange information
    - Historical data
    """

    def __init__(self, config) -> None:
        self.config = config
        self.api_key = config.COINMARKETCAP_API_KEY
        self.base_url = "https://pro-api.coinmarketcap.com"
        self.session = requests.Session()

        # Rate limiting
        self.requests_per_second = 10  # CMC free tier limit
        self.last_request_time = 0
        self.request_count = 0

        # Cache for rate limiting
        self.cache = {}
        self.cache_expiry = 60  # 1 minute cache

        if not self.api_key:
            logger.warning("CoinMarketCap API key not configured")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        retry=retry_if_exception_type(requests.exceptions.RequestException),
    )
    def _make_request(
        self, endpoint: str, params: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Make authenticated request to CoinMarketCap API"""
        try:
            # Rate limiting
            current_time = time.time()
            if current_time - self.last_request_time < 1.0 / self.requests_per_second:
                time.sleep(
                    1.0 / self.requests_per_second
                    - (current_time - self.last_request_time)
                )

            self.last_request_time = time.time()

            # Check cache first
            cache_key = f"{endpoint}_{str(params)}"
            if cache_key in self.cache:
                cached_data, cache_time = self.cache[cache_key]
                if time.time() - cache_time < self.cache_expiry:
                    return cached_data

            url = f"{self.base_url}{endpoint}"

            headers = {
                "Accepts": "application/json",
                "X-CMC_PRO_API_KEY": self.api_key or "",
            }

            response = self.session.get(url, headers=headers, params=params)
            response.raise_for_status()

            data = response.json()

            # Cache the response
            self.cache[cache_key] = (data, time.time())

            # Clean old cache entries
            self._clean_cache()

            return data

        except requests.exceptions.RequestException as e:
            logger.error(f"CoinMarketCap API request failed: {e}")
            raise  # Re-raise for tenacity retry
        except Exception as e:
            logger.error(f"Error making CoinMarketCap request: {e}")
            return None

    def _clean_cache(self):
        """Clean expired cache entries"""
        try:
            current_time = time.time()
            expired_keys = [
                key
                for key, (_, cache_time) in self.cache.items()
                if current_time - cache_time > self.cache_expiry
            ]

            for key in expired_keys:
                del self.cache[key]

        except Exception as e:
            logger.error(f"Error cleaning cache: {e}")

    def get_cryptocurrency_listings(
        self, limit: int = 100, convert: str = "USD"
    ) -> Optional[List[Dict[str, Any]]]:
        """Get cryptocurrency listings"""
        try:
            params = {"start": "1", "limit": str(limit), "convert": convert}

            data = self._make_request("/v1/cryptocurrency/listings/latest", params)

            if data and "data" in data:
                return data["data"]
            else:
                logger.error("Invalid response format for cryptocurrency listings")
                return None

        except Exception as e:
            logger.error(f"Error getting cryptocurrency listings: {e}")
            return None

    def get_cryptocurrency_quotes(
        self, symbols: List[str], convert: str = "USD"
    ) -> Optional[Dict[str, Any]]:
        """Get cryptocurrency quotes for specific symbols"""
        try:
            # Convert symbols to CoinMarketCap IDs
            symbol_to_id = self._get_symbol_to_id_mapping()

            ids = []
            for symbol in symbols:
                base_symbol = symbol.split("/")[0]  # Remove quote currency
                if base_symbol in symbol_to_id:
                    ids.append(str(symbol_to_id[base_symbol]))

            if not ids:
                logger.warning(f"No valid symbol IDs found for {symbols}")
                return None

            params = {"id": ",".join(ids), "convert": convert}

            data = self._make_request("/v2/cryptocurrency/quotes/latest", params)

            if data and "data" in data:
                return data["data"]
            else:
                logger.error("Invalid response format for cryptocurrency quotes")
                return None

        except Exception as e:
            logger.error(f"Error getting cryptocurrency quotes: {e}")
            return None

    def get_global_metrics(self, convert: str = "USD") -> Optional[Dict[str, Any]]:
        """Get global cryptocurrency market metrics"""
        try:
            params = {"convert": convert}

            data = self._make_request("/v1/global-metrics/quotes/latest", params)

            if data and "data" in data:
                return data["data"]
            else:
                logger.error("Invalid response format for global metrics")
                return None

        except Exception as e:
            logger.error(f"Error getting global metrics: {e}")
            return None

    def get_trending_cryptocurrencies(
        self, limit: int = 10
    ) -> Optional[List[Dict[str, Any]]]:
        """Get trending cryptocurrencies"""
        try:
            params = {"start": "1", "limit": str(limit)}

            data = self._make_request("/v1/cryptocurrency/trending/latest", params)

            if data and "data" in data:
                return data["data"]
            else:
                logger.error("Invalid response format for trending cryptocurrencies")
                return None

        except Exception as e:
            logger.error(f"Error getting trending cryptocurrencies: {e}")
            return None

    def get_cryptocurrency_metadata(
        self, symbols: List[str]
    ) -> Optional[Dict[str, Any]]:
        """Get cryptocurrency metadata"""
        try:
            # Convert symbols to IDs
            symbol_to_id = self._get_symbol_to_id_mapping()

            ids = []
            for symbol in symbols:
                base_symbol = symbol.split("/")[0]
                if base_symbol in symbol_to_id:
                    ids.append(str(symbol_to_id[base_symbol]))

            if not ids:
                return None

            params = {"id": ",".join(ids)}

            data = self._make_request("/v2/cryptocurrency/info", params)

            if data and "data" in data:
                return data["data"]
            else:
                logger.error("Invalid response format for cryptocurrency metadata")
                return None

        except Exception as e:
            logger.error(f"Error getting cryptocurrency metadata: {e}")
            return None

    def get_exchange_listings(self, limit: int = 100) -> Optional[List[Dict[str, Any]]]:
        """Get cryptocurrency exchanges"""
        try:
            params = {"start": "1", "limit": str(limit)}

            data = self._make_request("/v1/exchange/listings/latest", params)

            if data and "data" in data:
                return data["data"]
            else:
                logger.error("Invalid response format for exchange listings")
                return None

        except Exception as e:
            logger.error(f"Error getting exchange listings: {e}")
            return None

    def get_fear_and_greed_index(self) -> Optional[Dict[str, Any]]:
        """Get Fear & Greed Index"""
        try:
            data = self._make_request("/v3/fear-and-greed/latest")

            if data and "data" in data:
                return data["data"]
            else:
                logger.error("Invalid response format for Fear & Greed Index")
                return None

        except Exception as e:
            logger.error(f"Error getting Fear & Greed Index: {e}")
            return None

    def _get_symbol_to_id_mapping(self) -> Dict[str, int]:
        """Get mapping of symbols to CoinMarketCap IDs"""
        try:
            # Common cryptocurrency mappings
            mapping = {
                "BTC": 1,
                "ETH": 1027,
                "USDT": 825,
                "BNB": 1839,
                "ADA": 2010,
                "XRP": 52,
                "SOL": 5426,
                "DOT": 6636,
                "DOGE": 74,
                "AVAX": 5805,
                "LTC": 2,
                "LINK": 1975,
                "UNI": 7083,
                "MATIC": 3890,
                "ALGO": 4030,
                "VET": 3077,
                "ICP": 8916,
                "FIL": 2280,
                "TRX": 1958,
                "ETC": 1321,
                "XLM": 512,
                "THETA": 2416,
                "FTT": 4195,
                "HBAR": 4642,
                "NEAR": 6535,
                "FLOW": 4558,
                "MANA": 1966,
                "SAND": 6210,
                "AXS": 6783,
                "CHZ": 4066,
                "ENJ": 2130,
                "BAT": 1697,
                "OMG": 1808,
                "ZRX": 1896,
                "REP": 1104,
                "LRC": 1934,
                "ANT": 1680,
                "STORJ": 1772,
                "BTG": 2083,
                "ZEC": 1437,
                "DASH": 131,
                "XMR": 328,
                "LSK": 1214,
                "ARK": 1586,
                "STRAT": 1343,
                "XEM": 873,
                "QTUM": 1684,
                "BTX": 1654,
                "GAME": 1567,
                "CVC": 1816,
                "PAY": 1758,
                "FUN": 1757,
                "WAVES": 1274,
                "STR": 1343,
            }

            return mapping

        except Exception as e:
            logger.error(f"Error getting symbol to ID mapping: {e}")
            return {}

    def get_top_cryptocurrencies(
        self, limit: int = 10, convert: str = "USD"
    ) -> Optional[List[Dict[str, Any]]]:
        """Get top cryptocurrencies by market cap"""
        try:
            listings = self.get_cryptocurrency_listings(limit=limit, convert=convert)

            if listings:
                # Sort by market cap
                sorted_listings = sorted(
                    listings,
                    key=lambda x: x.get("quote", {})
                    .get(convert, {})
                    .get("market_cap", 0),
                    reverse=True,
                )
                return sorted_listings[:limit]

            return None

        except Exception as e:
            logger.error(f"Error getting top cryptocurrencies: {e}")
            return None

    def get_price_change_analysis(
        self, symbols: List[str], convert: str = "USD"
    ) -> Optional[Dict[str, Any]]:
        """Analyze price changes for given symbols"""
        try:
            quotes = self.get_cryptocurrency_quotes(symbols, convert)

            if not quotes:
                return None

            analysis = {}

            for symbol_id, quote_data in quotes.items():
                if not quote_data or not isinstance(quote_data, list):
                    continue

                coin_data = quote_data[0]
                quote_info = coin_data.get("quote", {}).get(convert, {})

                if not quote_info:
                    continue

                symbol = coin_data.get("symbol", f"ID_{symbol_id}")

                analysis[symbol] = {
                    "name": coin_data.get("name", ""),
                    "current_price": quote_info.get("price", 0),
                    "market_cap": quote_info.get("market_cap", 0),
                    "volume_24h": quote_info.get("volume_24h", 0),
                    "price_change_1h": quote_info.get("percent_change_1h", 0),
                    "price_change_24h": quote_info.get("percent_change_24h", 0),
                    "price_change_7d": quote_info.get("percent_change_7d", 0),
                    "price_change_30d": quote_info.get("percent_change_30d", 0),
                    "volatility": self._calculate_volatility(
                        [
                            quote_info.get("percent_change_1h", 0),
                            quote_info.get("percent_change_24h", 0),
                            quote_info.get("percent_change_7d", 0),
                        ]
                    ),
                }

            return analysis

        except Exception as e:
            logger.error(f"Error analyzing price changes: {e}")
            return None

    def _calculate_volatility(self, changes: List[float]) -> float:
        """Calculate volatility from price changes"""
        try:
            if not changes:
                return 0.0

            # Simple volatility calculation using standard deviation
            return abs(np.std(changes))

        except Exception:
            return 0.0

    def get_market_dominance(
        self, limit: int = 10, convert: str = "USD"
    ) -> Optional[Dict[str, Any]]:
        """Get market dominance analysis"""
        try:
            listings = self.get_cryptocurrency_listings(limit=limit, convert=convert)

            if not listings:
                return None

            total_market_cap = sum(
                coin.get("quote", {}).get(convert, {}).get("market_cap", 0)
                for coin in listings
            )

            dominance = {}
            for coin in listings:
                market_cap = coin.get("quote", {}).get(convert, {}).get("market_cap", 0)
                symbol = coin.get("symbol", "")

                if total_market_cap > 0:
                    dominance_pct = (market_cap / total_market_cap) * 100
                    dominance[symbol] = {
                        "name": coin.get("name", ""),
                        "market_cap": market_cap,
                        "dominance_pct": dominance_pct,
                    }

            return {
                "total_market_cap": total_market_cap,
                "dominance": dominance,
                "top_3_dominance": sum(
                    coin_data["dominance_pct"]
                    for coin_data in list(dominance.values())[:3]
                ),
            }

        except Exception as e:
            logger.error(f"Error getting market dominance: {e}")
            return None

    def get_fear_greed_signal(self) -> Optional[str]:
        """Get Fear & Greed Index signal"""
        try:
            fear_greed_data = self.get_fear_and_greed_index()

            if not fear_greed_data:
                return None

            value = fear_greed_data.get("value", 50)
            # classification value not used; kept for potential future use
            # _classification = fear_greed_data.get("value_classification", "")

            # Generate trading signal based on Fear & Greed Index
            if value <= 25:
                return "EXTREME_FEAR"  # Potential buying opportunity
            elif value <= 45:
                return "FEAR"  # Moderate buying opportunity
            elif value <= 55:
                return "NEUTRAL"  # No clear signal
            elif value <= 75:
                return "GREED"  # Moderate selling opportunity
            else:
                return "EXTREME_GREED"  # Potential selling opportunity

        except Exception as e:
            logger.error(f"Error getting Fear & Greed signal: {e}")
            return None

    def get_market_sentiment(self) -> Optional[Dict[str, Any]]:
        """Get overall market sentiment analysis"""
        try:
            # Get global metrics
            global_metrics = self.get_global_metrics()

            # Get Fear & Greed Index
            fear_greed = self.get_fear_and_greed_index()

            # Get trending coins
            trending = self.get_trending_cryptocurrencies(limit=5)

            sentiment = {
                "fear_greed_index": fear_greed.get("value", 50) if fear_greed else 50,
                "fear_greed_classification": (
                    fear_greed.get("value_classification", "Neutral")
                    if fear_greed
                    else "Neutral"
                ),
                "total_market_cap": (
                    global_metrics.get("quote", {})
                    .get("USD", {})
                    .get("total_market_cap", 0)
                    if global_metrics
                    else 0
                ),
                "market_cap_change_24h": (
                    global_metrics.get("quote", {})
                    .get("USD", {})
                    .get("total_market_cap_yesterday_percentage_change", 0)
                    if global_metrics
                    else 0
                ),
                "trending_coins": [
                    {
                        "symbol": coin.get("symbol", ""),
                        "name": coin.get("name", ""),
                        "price_change_24h": coin.get("quote", {})
                        .get("USD", {})
                        .get("percent_change_24h", 0),
                    }
                    for coin in (trending or [])
                ],
            }

            # Determine overall sentiment
            fg_index = sentiment["fear_greed_index"]
            market_change = sentiment["market_cap_change_24h"]

            if fg_index < 30 and market_change < -5:
                sentiment["overall_sentiment"] = "BEARISH_EXTREME"
            elif fg_index < 45 and market_change < -2:
                sentiment["overall_sentiment"] = "BEARISH"
            elif fg_index > 70 and market_change > 5:
                sentiment["overall_sentiment"] = "BULLISH_EXTREME"
            elif fg_index > 55 and market_change > 2:
                sentiment["overall_sentiment"] = "BULLISH"
            else:
                sentiment["overall_sentiment"] = "NEUTRAL"

            return sentiment

        except Exception as e:
            logger.error(f"Error getting market sentiment: {e}")
            return None


# Example usage and testing
def test_coinmarketcap_client():
    """Test function for CoinMarketCap client"""
    from ..config.settings import Config

    config = Config()
    client = CoinMarketCapClient(config)

    # Test basic functionality
    print("Testing CoinMarketCap API client...")

    # Test listings
    listings = client.get_cryptocurrency_listings(limit=5)
    if listings:
        print(f"Got {len(listings)} cryptocurrency listings")
        for coin in listings[:3]:
            print(
                f"- {coin.get('name')} ({coin.get('symbol')}): ${coin.get('quote', {}).get('USD', {}).get('price', 0):.2f}"
            )
    else:
        print("Failed to get cryptocurrency listings")

    # Test quotes
    quotes = client.get_cryptocurrency_quotes(["BTC", "ETH"])
    if quotes:
        print("Got cryptocurrency quotes")
        for coin_id, coin_data in quotes.items():
            if coin_data and isinstance(coin_data, list):
                coin = coin_data[0]
                price = coin.get("quote", {}).get("USD", {}).get("price", 0)
                print(f"- {coin.get('symbol')}: ${price:.2f}")
    else:
        print("Failed to get cryptocurrency quotes")

    # Test global metrics
    metrics = client.get_global_metrics()
    if metrics:
        print("Got global metrics")
        total_mcap = metrics.get("quote", {}).get("USD", {}).get("total_market_cap", 0)
        print(f"Total market cap: ${total_mcap:,.0f}")
    else:
        print("Failed to get global metrics")

    return client


if __name__ == "__main__":
    # Run test
    test_coinmarketcap_client()
