"""Market data gathering — no LLM calls, just structured data."""

import json
import requests
import logging
from datetime import datetime
from typing import Optional

from .config import get_binance_client

logger = logging.getLogger(__name__)


def get_ticker(symbol: str) -> dict:
    """Get current price, 24h stats for a trading pair.

    Returns dict with: price, change_24h, change_24h_pct, volume_24h,
    high_24h, low_24h, bid, ask.
    """
    client = get_binance_client()
    try:
        ticker = client.get_ticker(symbol)
        return {
            "symbol": symbol,
            "price": ticker.get("last", ticker.get("close", 0)),
            "bid": ticker.get("bid", 0),
            "ask": ticker.get("ask", 0),
            "change_24h": ticker.get("change", 0),
            "change_24h_pct": ticker.get("percentage", 0),
            "volume_24h": ticker.get("quoteVolume", ticker.get("baseVolume", 0)),
            "high_24h": ticker.get("high", 0),
            "low_24h": ticker.get("low", 0),
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"get_ticker({symbol}) failed: {e}")
        return {"symbol": symbol, "error": str(e)}


def get_klines(
    symbol: str, interval: str = "1h", limit: int = 100
) -> list:
    """Get OHLCV candles. Returns list of [timestamp, open, high, low, close, volume]."""
    client = get_binance_client()
    try:
        df = client.get_klines(symbol, interval, limit)
        # BinanceClient returns a pandas DataFrame
        if df is not None and not df.empty:
            return df.values.tolist()
        return []
    except Exception as e:
        logger.error(f"get_klines({symbol}) failed: {e}")
        return []


def get_orderbook(symbol: str, limit: int = 20) -> dict:
    """Get order book snapshot with bid/ask spread metrics."""
    client = get_binance_client()
    try:
        book = client.exchange.fetch_order_book(symbol.replace("USDT", "/USDT"), limit)
        bids = book.get("bids", [])[:10]
        asks = book.get("asks", [])[:10]

        best_bid = bids[0][0] if bids else 0
        best_ask = asks[0][0] if asks else 0
        spread = best_ask - best_bid if best_bid and best_ask else 0
        spread_pct = (spread / best_ask * 100) if best_ask > 0 else 0

        return {
            "symbol": symbol,
            "best_bid": best_bid,
            "best_ask": best_ask,
            "spread": round(spread, 6),
            "spread_pct": round(spread_pct, 4),
            "bid_volume": sum(b[1] for b in bids),
            "ask_volume": sum(a[1] for a in asks),
            "top_bids": bids[:5],
            "top_asks": asks[:5],
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"get_orderbook({symbol}) failed: {e}")
        return {"symbol": symbol, "error": str(e)}


def get_fear_greed() -> dict:
    """Get Crypto Fear & Greed Index from alternative.me."""
    try:
        resp = requests.get("https://api.alternative.me/fng/", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("data"):
                entry = data["data"][0]
                return {
                    "value": int(entry["value"]),
                    "classification": entry["value_classification"],
                    "timestamp": datetime.now().isoformat(),
                }
        return {"value": None, "classification": "unavailable", "error": "API failed"}
    except Exception as e:
        logger.error(f"get_fear_greed() failed: {e}")
        return {"value": None, "classification": "unavailable", "error": str(e)}
