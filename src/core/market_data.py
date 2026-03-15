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
    """Get OHLCV candles. Returns list of [timestamp, open, high, low, close, volume].

    Supports >1000 candles via automatic pagination (Binance API limit is 1000/request).
    """
    client = get_binance_client()
    try:
        if limit <= 1000:
            df = client.get_klines(symbol, interval, limit)
            if df is not None and not df.empty:
                df = df.dropna()
                return df.values.tolist() if not df.empty else []
            return []

        # Pagination: fetch in chunks of 1000, working backwards from now
        all_candles = []
        remaining = limit
        since = None  # Will be set after first batch

        while remaining > 0:
            batch_size = min(remaining, 1000)
            if since is not None:
                # CCXT fetch_ohlcv with 'since' parameter
                ohlcv = client.exchange.fetch_ohlcv(
                    symbol.replace("USDT", "/USDT"), interval,
                    since=since, limit=batch_size)
            else:
                # First batch: most recent candles
                df = client.get_klines(symbol, interval, batch_size)
                if df is not None and not df.empty:
                    ohlcv = df.values.tolist()
                else:
                    break

            if not ohlcv:
                break

            all_candles = ohlcv + all_candles if since else list(ohlcv)
            remaining -= len(ohlcv)

            if remaining > 0 and len(ohlcv) > 0:
                # Move 'since' backwards: earliest timestamp minus one interval
                earliest_ts = int(ohlcv[0][0]) if isinstance(ohlcv[0][0], (int, float)) else int(ohlcv[0][0].timestamp() * 1000)
                interval_ms = _interval_to_ms(interval)
                since = earliest_ts - (batch_size * interval_ms)
            else:
                break

        return all_candles[-limit:]  # Trim to requested amount
    except Exception as e:
        logger.error(f"get_klines({symbol}) failed: {e}")
        return []


def _interval_to_ms(interval: str) -> int:
    """Convert interval string to milliseconds."""
    units = {"m": 60_000, "h": 3_600_000, "d": 86_400_000}
    num = int(interval[:-1])
    unit = interval[-1]
    return num * units.get(unit, 3_600_000)


def get_orderbook(symbol: str, limit: int = 20) -> dict:
    """Get order book snapshot with bid/ask spread metrics."""
    client = get_binance_client()
    try:
        ccxt_symbol = symbol if "/" in symbol else symbol.replace("USDT", "/USDT")
        book = client.exchange.fetch_order_book(ccxt_symbol, limit)
        bids = book.get("bids", [])[:10]
        asks = book.get("asks", [])[:10]

        best_bid = bids[0][0] if bids else 0
        best_ask = asks[0][0] if asks else 0
        spread = (best_ask - best_bid) if (best_bid > 0 and best_ask > 0) else 0
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
