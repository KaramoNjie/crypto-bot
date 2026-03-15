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


def vwap_signal(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray,
                volumes: np.ndarray, window: int = 24,
                deviation_pct: float = 2.5) -> dict:
    """VWAP reversion signal — buy below VWAP, sell above."""
    if len(closes) < window + 1:
        return {"score": 0.0, "confidence": 0.0, "reason": "insufficient data"}

    # Rolling VWAP
    typical = (highs[-window:] + lows[-window:] + closes[-window:]) / 3.0
    vols = volumes[-window:]
    cum_vol = np.sum(vols)
    if cum_vol > 0:
        vwap_val = float(np.sum(typical * vols) / cum_vol)
    else:
        vwap_val = float(closes[-1])

    price = float(closes[-1])
    dev_pct = (price - vwap_val) / vwap_val * 100 if vwap_val > 0 else 0

    if dev_pct < -deviation_pct:
        # Price well below VWAP — buy signal
        depth = abs(dev_pct) / deviation_pct
        score = min(depth * 0.5, 1.0)
        confidence = min(0.5 + depth * 0.2, 0.9)
        reason = f"Price {dev_pct:+.1f}% below VWAP ({vwap_val:.2f})"
    elif dev_pct > deviation_pct:
        # Price well above VWAP — sell signal
        depth = dev_pct / deviation_pct
        score = -min(depth * 0.5, 1.0)
        confidence = min(0.5 + depth * 0.2, 0.9)
        reason = f"Price {dev_pct:+.1f}% above VWAP ({vwap_val:.2f})"
    elif abs(dev_pct) < deviation_pct * 0.3:
        # Near VWAP — neutral
        score = 0.0
        confidence = 0.1
        reason = f"Price at VWAP ({dev_pct:+.1f}%)"
    else:
        # Between thresholds
        score = -dev_pct / deviation_pct * 0.3
        confidence = 0.25
        reason = f"Price {dev_pct:+.1f}% from VWAP"

    return {"score": round(float(score), 4), "confidence": round(float(confidence), 4),
            "vwap": round(vwap_val, 2), "deviation_pct": round(float(dev_pct), 2),
            "reason": reason}


def momentum_breakout_signal(closes: np.ndarray, volumes: np.ndarray,
                             breakout_period: int = 10,
                             volume_confirm: float = 1.5,
                             vol_lookback: int = 20) -> dict:
    """Momentum breakout — signal on N-period high/low with volume."""
    if len(closes) < max(breakout_period, vol_lookback) + 2:
        return {"score": 0.0, "confidence": 0.0, "reason": "insufficient data"}

    price = float(closes[-1])
    lookback = closes[-breakout_period - 1:-1]
    period_high = float(np.max(lookback))
    period_low = float(np.min(lookback))

    avg_vol = float(np.mean(volumes[-vol_lookback - 1:-1]))
    vol_ratio = float(volumes[-1] / avg_vol) if avg_vol > 0 else 1.0
    vol_confirmed = vol_ratio >= volume_confirm

    if price > period_high:
        strength = (price - period_high) / period_high * 100
        score = min(0.5 + strength * 0.3, 1.0)
        confidence = 0.5 + (0.3 if vol_confirmed else 0.0)
        reason = f"Breakout above {breakout_period}-period high ({period_high:.2f})"
        if vol_confirmed:
            reason += f" vol={vol_ratio:.1f}x"
    elif price < period_low:
        strength = (period_low - price) / period_low * 100
        score = -min(0.5 + strength * 0.3, 1.0)
        confidence = 0.5 + (0.3 if vol_confirmed else 0.0)
        reason = f"Breakdown below {breakout_period}-period low ({period_low:.2f})"
    else:
        # Inside range
        pos = (price - period_low) / (period_high - period_low) if period_high != period_low else 0.5
        score = (pos - 0.5) * 0.2
        confidence = 0.15
        reason = f"Inside range ({pos:.0%} position)"

    return {"score": round(float(score), 4), "confidence": round(float(confidence), 4),
            "vol_ratio": round(vol_ratio, 2), "vol_confirmed": vol_confirmed,
            "reason": reason}


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
    highs = np.array([float(k[2]) for k in klines])
    lows = np.array([float(k[3]) for k in klines])
    volumes = np.array([float(k[5]) for k in klines])
    price = float(closes[-1])

    vwap_cfg = strat.get("vwap", {})
    mom_cfg = strat.get("momentum", {})

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
        "vwap": vwap_signal(highs, lows, closes, volumes,
                            window=vwap_cfg.get("window", 24),
                            deviation_pct=vwap_cfg.get("deviation_pct", 2.5)),
        "momentum": momentum_breakout_signal(closes, volumes,
                                              breakout_period=mom_cfg.get("breakout_period", 10),
                                              volume_confirm=mom_cfg.get("volume_confirm", 1.5)),
    }

    # Ensemble weights (strategy importance)
    weights = {"rsi": 0.20, "macd": 0.15, "bollinger": 0.15,
               "ema_cross": 0.10, "volume": 0.05,
               "vwap": 0.25, "momentum": 0.10}

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


def discover_top_pairs(min_volume_usd: float = 5_000_000, max_pairs: int = 10) -> list:
    """Dynamically discover top trading pairs from Binance by volume and momentum.

    Filters:
      - USDT pairs only (stablecoins excluded)
      - Minimum 24h volume
      - Ranked by a composite of volume + absolute price change (momentum)

    Returns list of dicts: [{symbol, price, volume_24h, change_pct, momentum_score}]
    """
    EXCLUDE = {"USDCUSDT", "FDUSDUSDT", "EURUSDT", "TUSDUSDT", "BUSDUSDT",
               "DAIUSDT", "WBTCUSDT"}  # stablecoins & wrapped

    try:
        from .config import get_binance_client
        client = get_binance_client()
        tickers = client.exchange.fetch_tickers()
    except Exception as e:
        logger.error(f"Failed to fetch tickers for pair discovery: {e}")
        # Fallback to defaults
        return [{"symbol": s, "price": 0, "volume_24h": 0, "change_pct": 0,
                 "momentum_score": 0}
                for s in ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]]

    candidates = []
    for sym, t in tickers.items():
        if not sym.endswith("/USDT"):
            continue
        symbol = sym.replace("/", "")
        if symbol in EXCLUDE:
            continue

        vol = t.get("quoteVolume", 0) or 0
        if vol < min_volume_usd:
            continue

        change = abs(t.get("percentage", 0) or 0)
        price = t.get("last", 0) or 0

        # Momentum score: log(volume) * abs(change_pct)
        # Rewards high-volume coins with big moves
        import math
        momentum = math.log10(max(vol, 1)) * (1 + change / 10)

        candidates.append({
            "symbol": symbol,
            "price": round(price, 8),
            "volume_24h": round(vol),
            "change_pct": round(t.get("percentage", 0) or 0, 2),
            "momentum_score": round(momentum, 2),
        })

    # Sort by momentum score
    candidates.sort(key=lambda x: x["momentum_score"], reverse=True)
    return candidates[:max_pairs]


def scan_all(symbols=None, timeframe="1h", auto_discover=False,
             max_pairs: int = 8) -> list:
    """Scan multiple symbols and rank by signal strength.

    Args:
        symbols: Explicit list of symbols (overrides auto_discover)
        timeframe: Candle timeframe
        auto_discover: If True, dynamically find top pairs from Binance
        max_pairs: Max pairs to scan when auto_discover=True

    Returns list of signal dicts sorted by absolute ensemble_score descending.
    """
    if symbols is None:
        if auto_discover:
            discovered = discover_top_pairs(max_pairs=max_pairs)
            symbols = [p["symbol"] for p in discovered]
            logger.info(f"Auto-discovered {len(symbols)} pairs: {symbols}")
        else:
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
