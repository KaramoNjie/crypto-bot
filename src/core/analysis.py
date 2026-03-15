"""Technical + news analysis — pure computation, no LLM calls."""

import logging
import numpy as np
from datetime import datetime
from typing import Optional

from .market_data import get_ticker, get_klines, get_fear_greed
from .config import get_config, load_strategy

logger = logging.getLogger(__name__)


# --- Technical indicator calculations (extracted from toolkit.py, bugs fixed) ---


def _ema_series(prices: np.ndarray, period: int) -> Optional[np.ndarray]:
    """Full EMA series with SMA seed."""
    if len(prices) < period:
        return None
    mult = 2 / (period + 1)
    ema = np.empty(len(prices))
    ema[:period] = np.nan
    ema[period - 1] = np.mean(prices[:period])
    for i in range(period, len(prices)):
        ema[i] = prices[i] * mult + ema[i - 1] * (1 - mult)
    return ema


def _ema(prices: np.ndarray, period: int) -> Optional[float]:
    """Final EMA value."""
    s = _ema_series(prices, period)
    return float(s[-1]) if s is not None else None


def _rsi(prices: np.ndarray, period: int = 14) -> Optional[float]:
    """RSI indicator."""
    if len(prices) < period + 1:
        return None
    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    avg_gain = np.mean(gains[-period:])
    avg_loss = np.mean(losses[-period:])
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return float(100 - (100 / (1 + rs)))


def _macd(prices: np.ndarray) -> dict:
    """MACD (12/26/9) — fixed implementation."""
    if len(prices) < 26:
        return {"line": None, "signal": None, "histogram": None}
    ema12 = _ema_series(prices, 12)
    ema26 = _ema_series(prices, 26)
    if ema12 is None or ema26 is None:
        return {"line": None, "signal": None, "histogram": None}

    start = 25
    macd_series = ema12[start:] - ema26[start:]
    line = float(macd_series[-1])

    if len(macd_series) >= 9:
        sig_series = _ema_series(macd_series, 9)
        if sig_series is not None:
            sig = float(sig_series[-1])
            return {"line": round(line, 4), "signal": round(sig, 4), "histogram": round(line - sig, 4)}

    return {"line": round(line, 4), "signal": None, "histogram": None}


def _bollinger(prices: np.ndarray, period: int = 20, std_mult: float = 2.0) -> dict:
    """Bollinger Bands."""
    if len(prices) < period:
        return {"upper": None, "middle": None, "lower": None}
    recent = prices[-period:]
    mid = float(np.mean(recent))
    std = float(np.std(recent))
    return {
        "upper": round(mid + std * std_mult, 2),
        "middle": round(mid, 2),
        "lower": round(mid - std * std_mult, 2),
    }


def technical_analysis(symbol: str, interval: str = None) -> dict:
    """Compute all technical indicators for a symbol.

    Returns structured dict with RSI, MACD, Bollinger Bands, SMAs, EMAs.
    Reads parameters from config/strategy.yaml (falls back to defaults).
    """
    strat = load_strategy()
    ind = strat.get("indicators", {})
    if interval is None:
        interval = strat.get("timeframe", "1h")

    rsi_period = ind.get("rsi", {}).get("period", 14)
    bb_period = ind.get("bollinger", {}).get("period", 20)
    bb_std = ind.get("bollinger", {}).get("std", 2.0)
    sma_fast = ind.get("sma_fast", 20)
    sma_slow = ind.get("sma_slow", 50)
    vol_lookback = ind.get("volume_lookback", 20)
    macd_fast = ind.get("macd", {}).get("fast", 12)
    macd_slow = ind.get("macd", {}).get("slow", 26)

    klines = get_klines(symbol, interval, limit=100)
    if not klines:
        return {"symbol": symbol, "error": "No kline data available"}

    try:
        # Klines come as [timestamp, open, high, low, close, volume] from DataFrame.values.tolist()
        closes = np.array([float(k[4]) for k in klines if len(k) >= 6])
        highs = np.array([float(k[2]) for k in klines if len(k) >= 6])
        lows = np.array([float(k[3]) for k in klines if len(k) >= 6])
        volumes = np.array([float(k[5]) for k in klines if len(k) >= 6])
    except (IndexError, ValueError) as e:
        return {"symbol": symbol, "error": f"Data parse error: {e}"}

    current_price = float(closes[-1])
    sma20 = float(np.mean(closes[-sma_fast:])) if len(closes) >= sma_fast else None
    sma50 = float(np.mean(closes[-sma_slow:])) if len(closes) >= sma_slow else None
    avg_vol = float(np.mean(volumes[-vol_lookback:])) if len(volumes) >= vol_lookback else None
    vol_ratio = float(volumes[-1] / avg_vol) if avg_vol and avg_vol > 0 else None

    bb = _bollinger(closes, period=bb_period, std_mult=bb_std)
    bb_position = None
    if bb["upper"] is not None and bb["lower"] is not None and bb["upper"] > bb["lower"]:
        bb_position = round((current_price - bb["lower"]) / (bb["upper"] - bb["lower"]), 3)

    rsi_val = _rsi(closes, period=rsi_period)
    ema12 = _ema(closes, macd_fast)
    ema26 = _ema(closes, macd_slow)

    return {
        "symbol": symbol,
        "interval": interval,
        "current_price": current_price,
        "rsi": round(rsi_val, 2) if rsi_val is not None else None,
        "macd": _macd(closes),
        "bollinger": bb,
        "bb_position": bb_position,
        "sma_20": round(sma20, 2) if sma20 else None,
        "sma_50": round(sma50, 2) if sma50 else None,
        "ema_12": round(ema12, 2) if ema12 is not None else None,
        "ema_26": round(ema26, 2) if ema26 is not None else None,
        "volume_ratio": round(vol_ratio, 2) if vol_ratio else None,
        "price_range_24h": {
            "high": float(max(highs[-24:])) if len(highs) >= 24 else None,
            "low": float(min(lows[-24:])) if len(lows) >= 24 else None,
        },
        "data_points": len(closes),
        "timestamp": datetime.now().isoformat(),
    }


def news_analysis(symbol: str) -> dict:
    """Gather news from configured APIs. Returns articles + keyword sentiment."""
    try:
        from ..apis.news_api_client import NewsAPIClient

        config = get_config()
        client = NewsAPIClient(config)

        # Extract base currency name for search
        base = symbol.replace("USDT", "").replace("BTC", "").replace("ETH", "")
        if not base:
            base = symbol[:3]

        articles = client.get_news(query=f"cryptocurrency {base}", page_size=10)

        processed = []
        for art in articles:
            # Articles come as dicts from NewsAPIClient
            if isinstance(art, dict):
                title = art.get("title", "") or ""
                desc = art.get("description", "") or ""
                source = art.get("source", "unknown") or "unknown"
                published = art.get("publishedAt", "") or ""
            else:
                title = getattr(art, "title", "") or ""
                desc = getattr(art, "description", "") or ""
                source = getattr(art, "source", "unknown") or "unknown"
                published = getattr(art, "published_at", "") or ""

            text = f"{title} {desc}".lower()

            # Simple keyword sentiment
            pos_words = ["bull", "rise", "gain", "profit", "growth", "adoption", "breakthrough", "surge", "rally"]
            neg_words = ["bear", "fall", "crash", "decline", "ban", "hack", "loss", "regulation", "fraud"]
            pos = sum(1 for w in pos_words if w in text)
            neg = sum(1 for w in neg_words if w in text)
            sentiment = "positive" if pos > neg else "negative" if neg > pos else "neutral"

            processed.append({
                "title": title,
                "source": source,
                "published": published,
                "sentiment": sentiment,
            })

        return {
            "symbol": symbol,
            "articles_found": len(processed),
            "articles": processed[:10],
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"news_analysis({symbol}) failed: {e}")
        return {"symbol": symbol, "articles_found": 0, "articles": [], "error": str(e)}


def full_analysis(symbol: str) -> dict:
    """Combined market + technicals + news + fear/greed. One call, all data."""
    ticker = get_ticker(symbol)
    technicals = technical_analysis(symbol)
    news = news_analysis(symbol)
    fear_greed = get_fear_greed()

    return {
        "symbol": symbol,
        "market": ticker,
        "technicals": technicals,
        "news": news,
        "fear_greed": fear_greed,
        "timestamp": datetime.now().isoformat(),
    }
