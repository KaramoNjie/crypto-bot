"""Multi-strategy ensemble signal engine.

Combines 5 independent strategies into a single weighted signal:
  1. RSI Mean Reversion — buy oversold, sell overbought
  2. MACD Momentum — histogram direction and crossovers
  3. Bollinger Band Squeeze — price at band extremes
  4. EMA Crossover — trend following (fast/slow EMA)
  5. Volume Spike — unusual volume confirms breakouts

Each strategy outputs a score in [-1, +1] and a confidence in [0, 1].
The ensemble averages them with configurable weights.
"""

import logging
import numpy as np
from typing import Optional

from .config import load_strategy
from .market_data import get_klines, get_ticker, get_fear_greed

logger = logging.getLogger(__name__)


def _compute_rsi(closes: np.ndarray, period: int = 14) -> Optional[float]:
    if len(closes) < period + 1:
        return None
    deltas = np.diff(closes)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    avg_gain = np.mean(gains[-period:])
    avg_loss = np.mean(losses[-period:])
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return float(100 - (100 / (1 + rs)))


def _compute_ema(data: np.ndarray, period: int) -> np.ndarray:
    """Exponential moving average."""
    alpha = 2.0 / (period + 1)
    ema = np.zeros_like(data, dtype=float)
    ema[0] = data[0]
    for i in range(1, len(data)):
        ema[i] = alpha * data[i] + (1 - alpha) * ema[i - 1]
    return ema


def _compute_macd(closes: np.ndarray, fast=12, slow=26, signal=9):
    """Returns (macd_line, signal_line, histogram)."""
    if len(closes) < slow + signal:
        return None, None, None
    ema_fast = _compute_ema(closes, fast)
    ema_slow = _compute_ema(closes, slow)
    macd_line = ema_fast - ema_slow
    signal_line = _compute_ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def _compute_bollinger(closes: np.ndarray, period=20, std_mult=2.0):
    """Returns (upper, middle, lower, bb_position)."""
    if len(closes) < period:
        return None, None, None, None
    sma = np.mean(closes[-period:])
    std = np.std(closes[-period:])
    upper = sma + std_mult * std
    lower = sma - std_mult * std
    price = closes[-1]
    if upper == lower:
        bb_pos = 0.5
    else:
        bb_pos = (price - lower) / (upper - lower)
    return upper, sma, lower, bb_pos


def rsi_signal(closes: np.ndarray, period=14, oversold=35, overbought=60) -> dict:
    """RSI mean-reversion signal."""
    rsi = _compute_rsi(closes, period)
    if rsi is None:
        return {"score": 0.0, "confidence": 0.0, "rsi": None, "reason": "insufficient data"}

    if rsi < oversold:
        # Deeper oversold = stronger buy
        depth = (oversold - rsi) / oversold
        score = min(depth * 2, 1.0)
        confidence = 0.5 + depth * 0.5
        reason = f"RSI {rsi:.1f} < {oversold} (oversold)"
    elif rsi > overbought:
        depth = (rsi - overbought) / (100 - overbought)
        score = -min(depth * 2, 1.0)
        confidence = 0.5 + depth * 0.5
        reason = f"RSI {rsi:.1f} > {overbought} (overbought)"
    else:
        # Neutral zone — slight bias based on position
        mid = (oversold + overbought) / 2
        score = (mid - rsi) / (overbought - oversold) * 0.3
        confidence = 0.2
        reason = f"RSI {rsi:.1f} neutral"

    return {"score": round(score, 4), "confidence": round(confidence, 4),
            "rsi": round(rsi, 2), "reason": reason}


def macd_signal(closes: np.ndarray, fast=12, slow=26, signal_period=9) -> dict:
    """MACD momentum signal."""
    macd_line, signal_line, histogram = _compute_macd(closes, fast, slow, signal_period)
    if histogram is None:
        return {"score": 0.0, "confidence": 0.0, "reason": "insufficient data"}

    hist_now = histogram[-1]
    hist_prev = histogram[-2] if len(histogram) > 1 else 0

    # Histogram direction and crossover
    hist_rising = hist_now > hist_prev
    macd_cross_up = macd_line[-1] > signal_line[-1] and macd_line[-2] <= signal_line[-2]
    macd_cross_down = macd_line[-1] < signal_line[-1] and macd_line[-2] >= signal_line[-2]

    # Normalize histogram relative to price
    price = closes[-1]
    norm_hist = hist_now / price * 1000  # scale to readable range

    if macd_cross_up:
        score = min(0.8 + abs(norm_hist) * 0.1, 1.0)
        confidence = 0.7
        reason = f"MACD bullish crossover (hist={hist_now:.2f})"
    elif macd_cross_down:
        score = -min(0.8 + abs(norm_hist) * 0.1, 1.0)
        confidence = 0.7
        reason = f"MACD bearish crossover (hist={hist_now:.2f})"
    elif hist_now > 0 and hist_rising:
        score = min(norm_hist * 0.3, 0.6)
        confidence = 0.4
        reason = f"MACD positive & rising (hist={hist_now:.2f})"
    elif hist_now < 0 and not hist_rising:
        score = max(norm_hist * 0.3, -0.6)
        confidence = 0.4
        reason = f"MACD negative & falling (hist={hist_now:.2f})"
    else:
        score = norm_hist * 0.1
        confidence = 0.2
        reason = f"MACD mixed (hist={hist_now:.2f})"

    return {"score": round(float(score), 4), "confidence": round(float(confidence), 4),
            "histogram": round(float(hist_now), 4), "reason": reason}


def bollinger_signal(closes: np.ndarray, period=20, std_mult=2.0) -> dict:
    """Bollinger Band squeeze/breakout signal."""
    upper, middle, lower, bb_pos = _compute_bollinger(closes, period, std_mult)
    if bb_pos is None:
        return {"score": 0.0, "confidence": 0.0, "reason": "insufficient data"}

    # Band width relative to price (squeeze detection)
    band_width = (upper - lower) / middle if middle > 0 else 0
    is_squeeze = band_width < 0.03  # tight bands = pending breakout

    if bb_pos < 0.0:
        # Below lower band — strong buy
        score = min(abs(bb_pos) * 0.5 + 0.5, 1.0)
        confidence = 0.6 + (0.2 if is_squeeze else 0)
        reason = f"Below lower BB (pos={bb_pos:.2f})"
    elif bb_pos < 0.2:
        # Near lower band — buy
        score = 0.3 + (0.2 if is_squeeze else 0)
        confidence = 0.5
        reason = f"Near lower BB (pos={bb_pos:.2f})"
    elif bb_pos > 1.0:
        # Above upper band — strong sell
        score = -min((bb_pos - 1) * 0.5 + 0.5, 1.0)
        confidence = 0.6 + (0.2 if is_squeeze else 0)
        reason = f"Above upper BB (pos={bb_pos:.2f})"
    elif bb_pos > 0.8:
        # Near upper band — sell
        score = -0.3 - (0.2 if is_squeeze else 0)
        confidence = 0.5
        reason = f"Near upper BB (pos={bb_pos:.2f})"
    else:
        score = 0.0
        confidence = 0.1
        reason = f"BB neutral (pos={bb_pos:.2f})"

    return {"score": round(float(score), 4), "confidence": round(float(confidence), 4),
            "bb_position": round(float(bb_pos), 4),
            "band_width": round(float(band_width), 4),
            "squeeze": is_squeeze, "reason": reason}


def ema_crossover_signal(closes: np.ndarray, fast_period=9, slow_period=21) -> dict:
    """EMA crossover trend-following signal."""
    if len(closes) < slow_period + 2:
        return {"score": 0.0, "confidence": 0.0, "reason": "insufficient data"}

    ema_fast = _compute_ema(closes, fast_period)
    ema_slow = _compute_ema(closes, slow_period)

    diff_now = ema_fast[-1] - ema_slow[-1]
    diff_prev = ema_fast[-2] - ema_slow[-2]

    cross_up = diff_now > 0 and diff_prev <= 0
    cross_down = diff_now < 0 and diff_prev >= 0

    # Normalize difference
    norm_diff = diff_now / closes[-1] * 100

    if cross_up:
        score = 0.8
        confidence = 0.65
        reason = f"EMA golden cross ({fast_period}/{slow_period})"
    elif cross_down:
        score = -0.8
        confidence = 0.65
        reason = f"EMA death cross ({fast_period}/{slow_period})"
    elif diff_now > 0:
        score = min(norm_diff * 0.5, 0.5)
        confidence = 0.3
        reason = f"EMA bullish trend ({norm_diff:+.2f}%)"
    else:
        score = max(norm_diff * 0.5, -0.5)
        confidence = 0.3
        reason = f"EMA bearish trend ({norm_diff:+.2f}%)"

    return {"score": round(float(score), 4), "confidence": round(float(confidence), 4),
            "ema_diff_pct": round(float(norm_diff), 4), "reason": reason}


def volume_signal(volumes: np.ndarray, closes: np.ndarray, lookback=20) -> dict:
    """Volume spike detection — confirms breakout moves."""
    if len(volumes) < lookback + 1:
        return {"score": 0.0, "confidence": 0.0, "reason": "insufficient data"}

    avg_vol = np.mean(volumes[-lookback - 1:-1])
    current_vol = volumes[-1]
    vol_ratio = current_vol / avg_vol if avg_vol > 0 else 1.0

    price_change = (closes[-1] - closes[-2]) / closes[-2] if closes[-2] > 0 else 0

    if vol_ratio > 2.0 and price_change > 0.005:
        score = min(vol_ratio * 0.3, 1.0)
        confidence = min(vol_ratio * 0.2, 0.8)
        reason = f"High volume bullish ({vol_ratio:.1f}x avg, +{price_change:.2%})"
    elif vol_ratio > 2.0 and price_change < -0.005:
        score = -min(vol_ratio * 0.3, 1.0)
        confidence = min(vol_ratio * 0.2, 0.8)
        reason = f"High volume bearish ({vol_ratio:.1f}x avg, {price_change:.2%})"
    elif vol_ratio > 1.5:
        score = 0.2 if price_change > 0 else -0.2
        confidence = 0.3
        reason = f"Elevated volume ({vol_ratio:.1f}x avg)"
    else:
        score = 0.0
        confidence = 0.1
        reason = f"Normal volume ({vol_ratio:.1f}x avg)"

    return {"score": round(float(score), 4), "confidence": round(float(confidence), 4),
            "vol_ratio": round(float(vol_ratio), 4), "reason": reason}


def generate_signal(symbol: str, timeframe: str = "1h", n_candles: int = 100) -> dict:
    """Generate ensemble trading signal for a symbol.

    Returns:
        dict with keys: action (BUY/SELL/HOLD), confidence (0-1),
        ensemble_score (-1 to +1), strategies (per-strategy details),
        price, symbol, timeframe
    """
    strat = load_strategy()
    ind = strat.get("indicators", {})
    rsi_cfg = ind.get("rsi", {})
    macd_cfg = ind.get("macd", {})
    bb_cfg = ind.get("bollinger", {})

    # Fetch candles
    klines = get_klines(symbol, timeframe, n_candles)
    if not klines or len(klines) < 30:
        return {"action": "HOLD", "confidence": 0.0, "error": "insufficient data",
                "symbol": symbol, "timeframe": timeframe}

    closes = np.array([float(k[4]) for k in klines])
    volumes = np.array([float(k[5]) for k in klines])
    price = float(closes[-1])

    # Run all strategies
    strategies = {
        "rsi": rsi_signal(closes,
                          period=rsi_cfg.get("period", 14),
                          oversold=rsi_cfg.get("oversold", 35),
                          overbought=rsi_cfg.get("overbought", 60)),
        "macd": macd_signal(closes,
                            fast=macd_cfg.get("fast", 12),
                            slow=macd_cfg.get("slow", 26),
                            signal_period=macd_cfg.get("signal", 9)),
        "bollinger": bollinger_signal(closes,
                                      period=bb_cfg.get("period", 20),
                                      std_mult=bb_cfg.get("std", 2.0)),
        "ema_cross": ema_crossover_signal(closes, fast_period=9, slow_period=21),
        "volume": volume_signal(volumes, closes,
                                lookback=ind.get("volume_lookback", 20)),
    }

    # Ensemble weights (strategy importance)
    weights = {"rsi": 0.30, "macd": 0.25, "bollinger": 0.20,
               "ema_cross": 0.15, "volume": 0.10}

    # Weighted score
    total_weight = 0
    weighted_score = 0
    weighted_confidence = 0
    for name, sig in strategies.items():
        w = weights.get(name, 0.1)
        weighted_score += sig["score"] * w
        weighted_confidence += sig["confidence"] * w
        total_weight += w

    if total_weight > 0:
        ensemble_score = weighted_score / total_weight
        ensemble_confidence = weighted_confidence / total_weight
    else:
        ensemble_score = 0.0
        ensemble_confidence = 0.0

    # Agreement bonus — if most strategies agree, boost confidence
    signs = [1 if s["score"] > 0.1 else (-1 if s["score"] < -0.1 else 0)
             for s in strategies.values()]
    agreement = abs(sum(signs)) / len(signs)
    ensemble_confidence = min(ensemble_confidence * (1 + agreement * 0.5), 1.0)

    # Decision thresholds
    min_conf = strat.get("signal", {}).get("min_confidence", 0.4)

    if ensemble_score > 0.15 and ensemble_confidence >= min_conf:
        action = "BUY"
    elif ensemble_score < -0.15 and ensemble_confidence >= min_conf:
        action = "SELL"
    else:
        action = "HOLD"

    # Fear & Greed overlay — extreme fear boosts buy, extreme greed boosts sell
    try:
        fg = get_fear_greed()
        fg_value = fg.get("value", 50)
        fg_label = fg.get("classification", "Neutral")
        if fg_value < 25 and action == "BUY":
            ensemble_confidence = min(ensemble_confidence * 1.15, 1.0)
        elif fg_value > 75 and action == "SELL":
            ensemble_confidence = min(ensemble_confidence * 1.15, 1.0)
    except Exception:
        fg_value = None
        fg_label = "unavailable"

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "price": round(price, 2),
        "action": action,
        "ensemble_score": round(float(ensemble_score), 4),
        "confidence": round(float(ensemble_confidence), 4),
        "strategies": strategies,
        "fear_greed": {"value": fg_value, "label": fg_label},
    }


def scan_all(symbols=None, timeframe="1h") -> list:
    """Scan multiple symbols and rank by signal strength.

    Returns list of signal dicts sorted by absolute ensemble_score descending.
    """
    if symbols is None:
        symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]

    results = []
    for symbol in symbols:
        try:
            sig = generate_signal(symbol, timeframe)
            results.append(sig)
        except Exception as e:
            logger.warning(f"Signal generation failed for {symbol}: {e}")
            results.append({"symbol": symbol, "action": "ERROR",
                            "error": str(e), "ensemble_score": 0, "confidence": 0})

    # Sort by absolute score (strongest signals first)
    results.sort(key=lambda x: abs(x.get("ensemble_score", 0)), reverse=True)
    return results
