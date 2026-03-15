#!/usr/bin/env python3
"""
scripts/eval_harness_v2.py — Multi-strategy eval harness.

Tests multiple trading strategies beyond RSI-only.
Strategy mode is read from config/strategy.yaml `strategy_mode` field,
or overridden via --strategy CLI flag.

Available strategies:
  rsi           — RSI mean-reversion (original, baseline)
  ensemble      — Weighted 5-indicator ensemble (RSI+MACD+BB+EMA+Volume)
  multi_confirm — Require N indicators to agree before entry
  momentum      — N-period high/low breakout + volume confirmation
  squeeze       — Bollinger squeeze → breakout with direction
  vwap          — VWAP reversion with RSI confirmation

Same scoring formula as v1 for fair comparison:
  per-coin  = sharpe * (1 - drawdown/100) * min(n_trades/10, 1.0)
  EVAL_SCORE = mean(per-coin) * coverage * feedback

Usage:
    python scripts/eval_harness_v2.py --days 90 --strategy ensemble
    python scripts/eval_harness_v2.py --days 90 --strategy multi_confirm --output-json loops/latest_eval.json
"""

import argparse
import json
import sys
import os
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

FIXED_SEED = 42
STARTING_BALANCE = 1000.0
DEFAULT_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]

_CANDLES_PER_DAY = {"15m": 96, "30m": 48, "1h": 24, "4h": 6, "1d": 1}
_ANN_FACTOR = {"15m": 252 * 96, "30m": 252 * 48, "1h": 252 * 24, "4h": 252 * 6, "1d": 252}

STRATEGIES = ["rsi", "ensemble", "multi_confirm", "momentum", "squeeze", "vwap"]


def _candle_count(days: int, timeframe: str) -> int:
    return min(days * _CANDLES_PER_DAY.get(timeframe, 24), 1000)


# ---------------------------------------------------------------------------
# Technical indicator functions
# ---------------------------------------------------------------------------

def _rsi(prices, period=14):
    if len(prices) < period + 1:
        return None
    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    avg_gain = np.mean(gains[-period:])
    avg_loss = np.mean(losses[-period:])
    if avg_loss == 0:
        return 100.0
    return float(100 - (100 / (1 + avg_gain / avg_loss)))


def _ema(data, period):
    """Exponential moving average over full array."""
    alpha = 2.0 / (period + 1)
    out = np.zeros(len(data), dtype=float)
    out[0] = data[0]
    for i in range(1, len(data)):
        out[i] = alpha * data[i] + (1 - alpha) * out[i - 1]
    return out


def _macd(closes, fast=12, slow=26, signal=9):
    """Returns (macd_line, signal_line, histogram) as arrays."""
    if len(closes) < slow + signal:
        return None, None, None
    ema_fast = _ema(closes, fast)
    ema_slow = _ema(closes, slow)
    macd_line = ema_fast - ema_slow
    signal_line = _ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def _bollinger(closes, period=20, std_mult=2.0):
    """Returns (upper, middle, lower) at the last index."""
    if len(closes) < period:
        return None, None, None
    sma = np.mean(closes[-period:])
    std = np.std(closes[-period:])
    return sma + std_mult * std, sma, sma - std_mult * std


def _bb_width(closes, period=20, std_mult=2.0):
    """Bollinger band width (upper-lower)/middle."""
    upper, middle, lower = _bollinger(closes, period, std_mult)
    if middle is None or middle == 0:
        return None
    return (upper - lower) / middle


def _vwap(highs, lows, closes, volumes, window=None):
    """Cumulative VWAP. If window is set, rolling VWAP over that many candles."""
    typical = (highs + lows + closes) / 3.0
    if window:
        cum_tp_vol = np.convolve(typical * volumes, np.ones(window), 'valid')
        cum_vol = np.convolve(volumes, np.ones(window), 'valid')
        # Return last value
        if cum_vol[-1] == 0:
            return closes[-1]
        return float(cum_tp_vol[-1] / cum_vol[-1])
    else:
        cum_tp_vol = np.cumsum(typical * volumes)
        cum_vol = np.cumsum(volumes)
        if cum_vol[-1] == 0:
            return closes[-1]
        return float(cum_tp_vol[-1] / cum_vol[-1])


# ---------------------------------------------------------------------------
# Strategy config loader
# ---------------------------------------------------------------------------

def load_strategy():
    try:
        import yaml
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "config", "strategy.yaml")
        with open(path) as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"Warning: could not load strategy.yaml ({e}), using defaults", file=sys.stderr)
        return {}


# ---------------------------------------------------------------------------
# Backtest engines per strategy
# ---------------------------------------------------------------------------

def _backtest_rsi(closes, strat):
    """Original RSI mean-reversion."""
    ind = strat.get("indicators", {})
    rsi_cfg = ind.get("rsi", {})
    period = rsi_cfg.get("period", 14)
    oversold = rsi_cfg.get("oversold", 30)
    overbought = rsi_cfg.get("overbought", 70)

    balance = STARTING_BALANCE
    position = 0.0
    entry_price = 0.0
    trades = []
    warmup = max(period + 1, 20)

    for i in range(warmup, len(closes)):
        price = closes[i]
        rsi = _rsi(closes[:i + 1], period=period)
        if rsi is None:
            continue
        if rsi < oversold and position == 0 and balance > 0:
            position = balance / price
            entry_price = price
            balance = 0.0
            trades.append({"type": "BUY", "price": price, "idx": i})
        elif rsi > overbought and position > 0:
            pnl_pct = ((price / entry_price) - 1) * 100
            balance = position * price
            trades.append({"type": "SELL", "price": price, "pnl_pct": pnl_pct, "idx": i})
            position = 0.0

    return balance, position, trades, warmup


def _backtest_ensemble(closes, volumes, strat):
    """Full 5-indicator weighted ensemble."""
    ind = strat.get("indicators", {})
    rsi_cfg = ind.get("rsi", {})
    macd_cfg = ind.get("macd", {})
    bb_cfg = ind.get("bollinger", {})

    rsi_period = rsi_cfg.get("period", 14)
    rsi_oversold = rsi_cfg.get("oversold", 30)
    rsi_overbought = rsi_cfg.get("overbought", 70)
    macd_fast = macd_cfg.get("fast", 12)
    macd_slow = macd_cfg.get("slow", 26)
    macd_signal = macd_cfg.get("signal", 9)
    bb_period = bb_cfg.get("period", 20)
    bb_std = bb_cfg.get("std", 2.0)
    vol_lookback = ind.get("volume_lookback", 20)

    weights = {"rsi": 0.30, "macd": 0.25, "bb": 0.20, "ema": 0.15, "vol": 0.10}
    sig_cfg = strat.get("signal", {})
    buy_threshold = sig_cfg.get("buy_threshold", 0.15)
    sell_threshold = sig_cfg.get("sell_threshold", -0.15)

    warmup = max(macd_slow + macd_signal, bb_period, rsi_period + 1, 30)
    balance = STARTING_BALANCE
    position = 0.0
    entry_price = 0.0
    trades = []

    # Pre-compute full arrays
    ema9 = _ema(closes, 9)
    ema21 = _ema(closes, 21)
    macd_line, signal_line, histogram = _macd(closes, macd_fast, macd_slow, macd_signal)

    for i in range(warmup, len(closes)):
        price = closes[i]
        scores = {}

        # RSI
        rsi = _rsi(closes[:i + 1], period=rsi_period)
        if rsi is not None:
            if rsi < rsi_oversold:
                depth = (rsi_oversold - rsi) / rsi_oversold
                scores["rsi"] = min(depth * 2, 1.0)
            elif rsi > rsi_overbought:
                depth = (rsi - rsi_overbought) / (100 - rsi_overbought)
                scores["rsi"] = -min(depth * 2, 1.0)
            else:
                mid = (rsi_oversold + rsi_overbought) / 2
                scores["rsi"] = (mid - rsi) / (rsi_overbought - rsi_oversold) * 0.3

        # MACD
        if histogram is not None and i >= 1:
            hist_now = histogram[i]
            hist_prev = histogram[i - 1]
            macd_cross_up = macd_line[i] > signal_line[i] and macd_line[i - 1] <= signal_line[i - 1]
            macd_cross_down = macd_line[i] < signal_line[i] and macd_line[i - 1] >= signal_line[i - 1]
            norm_hist = hist_now / price * 1000
            if macd_cross_up:
                scores["macd"] = min(0.8 + abs(norm_hist) * 0.1, 1.0)
            elif macd_cross_down:
                scores["macd"] = -min(0.8 + abs(norm_hist) * 0.1, 1.0)
            elif hist_now > 0 and hist_now > hist_prev:
                scores["macd"] = min(norm_hist * 0.3, 0.6)
            elif hist_now < 0 and hist_now < hist_prev:
                scores["macd"] = max(norm_hist * 0.3, -0.6)
            else:
                scores["macd"] = float(np.clip(norm_hist * 0.1, -0.3, 0.3))

        # Bollinger
        if i >= bb_period:
            window = closes[i - bb_period + 1:i + 1]
            sma = np.mean(window)
            std = np.std(window)
            upper = sma + bb_std * std
            lower = sma - bb_std * std
            if upper != lower:
                bb_pos = (price - lower) / (upper - lower)
            else:
                bb_pos = 0.5
            if bb_pos < 0.0:
                scores["bb"] = min(abs(bb_pos) * 0.5 + 0.5, 1.0)
            elif bb_pos < 0.2:
                scores["bb"] = 0.3
            elif bb_pos > 1.0:
                scores["bb"] = -min((bb_pos - 1) * 0.5 + 0.5, 1.0)
            elif bb_pos > 0.8:
                scores["bb"] = -0.3
            else:
                scores["bb"] = 0.0

        # EMA crossover
        if i >= 2:
            diff_now = ema9[i] - ema21[i]
            diff_prev = ema9[i - 1] - ema21[i - 1]
            if diff_now > 0 and diff_prev <= 0:
                scores["ema"] = 0.8
            elif diff_now < 0 and diff_prev >= 0:
                scores["ema"] = -0.8
            else:
                norm_diff = diff_now / price * 100
                scores["ema"] = float(np.clip(norm_diff * 0.5, -0.5, 0.5))

        # Volume
        if i >= vol_lookback + 1:
            avg_vol = np.mean(volumes[i - vol_lookback:i])
            vol_ratio = volumes[i] / avg_vol if avg_vol > 0 else 1.0
            pchange = (closes[i] - closes[i - 1]) / closes[i - 1] if closes[i - 1] > 0 else 0
            if vol_ratio > 2.0 and pchange > 0.005:
                scores["vol"] = min(vol_ratio * 0.3, 1.0)
            elif vol_ratio > 2.0 and pchange < -0.005:
                scores["vol"] = -min(vol_ratio * 0.3, 1.0)
            else:
                scores["vol"] = 0.0

        # Weighted ensemble score
        total_w = 0
        w_score = 0
        for name, s in scores.items():
            w = weights.get(name, 0.1)
            w_score += s * w
            total_w += w
        ensemble_score = w_score / total_w if total_w > 0 else 0.0

        # Trade decision
        if ensemble_score > buy_threshold and position == 0 and balance > 0:
            position = balance / price
            entry_price = price
            balance = 0.0
            trades.append({"type": "BUY", "price": price, "idx": i, "score": ensemble_score})
        elif ensemble_score < sell_threshold and position > 0:
            pnl_pct = ((price / entry_price) - 1) * 100
            balance = position * price
            trades.append({"type": "SELL", "price": price, "pnl_pct": pnl_pct, "idx": i, "score": ensemble_score})
            position = 0.0

    return balance, position, trades, warmup


def _backtest_multi_confirm(closes, volumes, strat):
    """Require N indicators to agree before entry."""
    ind = strat.get("indicators", {})
    rsi_cfg = ind.get("rsi", {})
    macd_cfg = ind.get("macd", {})
    bb_cfg = ind.get("bollinger", {})
    mc_cfg = strat.get("multi_confirm", {})

    rsi_period = rsi_cfg.get("period", 14)
    rsi_oversold = rsi_cfg.get("oversold", 30)
    rsi_overbought = rsi_cfg.get("overbought", 70)
    macd_fast = macd_cfg.get("fast", 12)
    macd_slow = macd_cfg.get("slow", 26)
    macd_signal_p = macd_cfg.get("signal", 9)
    bb_period = bb_cfg.get("period", 20)
    bb_std = bb_cfg.get("std", 2.0)
    require_agree = mc_cfg.get("require_agree", 3)

    warmup = max(macd_slow + macd_signal_p, bb_period, rsi_period + 1, 30)
    balance = STARTING_BALANCE
    position = 0.0
    entry_price = 0.0
    trades = []

    ema9 = _ema(closes, 9)
    ema21 = _ema(closes, 21)
    macd_line, signal_line, histogram = _macd(closes, macd_fast, macd_slow, macd_signal_p)

    for i in range(warmup, len(closes)):
        price = closes[i]
        buy_votes = 0
        sell_votes = 0
        total_indicators = 0

        # RSI vote
        rsi = _rsi(closes[:i + 1], period=rsi_period)
        if rsi is not None:
            total_indicators += 1
            if rsi < rsi_oversold:
                buy_votes += 1
            elif rsi > rsi_overbought:
                sell_votes += 1

        # MACD vote
        if histogram is not None and i >= 1:
            total_indicators += 1
            if histogram[i] > 0 and histogram[i] > histogram[i - 1]:
                buy_votes += 1
            elif histogram[i] < 0 and histogram[i] < histogram[i - 1]:
                sell_votes += 1

        # Bollinger vote
        if i >= bb_period:
            total_indicators += 1
            window = closes[i - bb_period + 1:i + 1]
            sma = np.mean(window)
            std = np.std(window)
            lower = sma - bb_std * std
            upper = sma + bb_std * std
            if price < lower:
                buy_votes += 1
            elif price > upper:
                sell_votes += 1

        # EMA vote
        if i >= 2:
            total_indicators += 1
            if ema9[i] > ema21[i] and ema9[i - 1] <= ema21[i - 1]:
                buy_votes += 1
            elif ema9[i] < ema21[i] and ema9[i - 1] >= ema21[i - 1]:
                sell_votes += 1
            elif ema9[i] > ema21[i]:
                buy_votes += 0.5
            elif ema9[i] < ema21[i]:
                sell_votes += 0.5

        # Volume confirmation (adds weight, doesn't vote alone)
        vol_confirmed = False
        if i >= 21:
            avg_vol = np.mean(volumes[i - 20:i])
            if avg_vol > 0 and volumes[i] / avg_vol > 1.5:
                vol_confirmed = True

        effective_buy = buy_votes + (0.5 if vol_confirmed and buy_votes > sell_votes else 0)
        effective_sell = sell_votes + (0.5 if vol_confirmed and sell_votes > buy_votes else 0)

        if effective_buy >= require_agree and position == 0 and balance > 0:
            position = balance / price
            entry_price = price
            balance = 0.0
            trades.append({"type": "BUY", "price": price, "idx": i,
                           "votes": effective_buy})
        elif effective_sell >= require_agree and position > 0:
            pnl_pct = ((price / entry_price) - 1) * 100
            balance = position * price
            trades.append({"type": "SELL", "price": price, "pnl_pct": pnl_pct, "idx": i,
                           "votes": effective_sell})
            position = 0.0

    return balance, position, trades, warmup


def _backtest_momentum(closes, volumes, strat):
    """Momentum breakout — buy N-period high on volume, sell N-period low."""
    mom_cfg = strat.get("momentum", {})
    breakout_period = mom_cfg.get("breakout_period", 20)
    volume_confirm = mom_cfg.get("volume_confirm", 1.5)
    trailing_stop_pct = mom_cfg.get("trailing_stop_pct", 3.0)
    vol_lookback = strat.get("indicators", {}).get("volume_lookback", 20)

    warmup = max(breakout_period + 1, vol_lookback + 1, 25)
    balance = STARTING_BALANCE
    position = 0.0
    entry_price = 0.0
    peak_price = 0.0
    trades = []

    for i in range(warmup, len(closes)):
        price = closes[i]

        # Volume ratio
        avg_vol = np.mean(volumes[i - vol_lookback:i])
        vol_ratio = volumes[i] / avg_vol if avg_vol > 0 else 1.0

        # N-period high/low
        lookback_window = closes[i - breakout_period:i]
        period_high = np.max(lookback_window)
        period_low = np.min(lookback_window)

        if position > 0:
            peak_price = max(peak_price, price)
            # Trailing stop
            drawdown_from_peak = (peak_price - price) / peak_price * 100
            # Also sell on breakdown below N-period low
            if drawdown_from_peak > trailing_stop_pct or price < period_low:
                pnl_pct = ((price / entry_price) - 1) * 100
                balance = position * price
                trades.append({"type": "SELL", "price": price, "pnl_pct": pnl_pct, "idx": i})
                position = 0.0

        elif position == 0 and balance > 0:
            # Buy on breakout above N-period high with volume confirmation
            if price > period_high and vol_ratio >= volume_confirm:
                position = balance / price
                entry_price = price
                peak_price = price
                balance = 0.0
                trades.append({"type": "BUY", "price": price, "idx": i,
                               "vol_ratio": round(vol_ratio, 2)})

    return balance, position, trades, warmup


def _backtest_squeeze(closes, volumes, strat):
    """Bollinger squeeze → breakout."""
    bb_cfg = strat.get("indicators", {}).get("bollinger", {})
    sq_cfg = strat.get("squeeze", {})
    bb_period = bb_cfg.get("period", 20)
    bb_std = bb_cfg.get("std", 2.0)
    squeeze_threshold = sq_cfg.get("width_threshold", 0.03)
    squeeze_candles = sq_cfg.get("squeeze_candles", 5)
    vol_lookback = strat.get("indicators", {}).get("volume_lookback", 20)

    warmup = max(bb_period + squeeze_candles, vol_lookback + 1, 30)
    balance = STARTING_BALANCE
    position = 0.0
    entry_price = 0.0
    trades = []

    # Pre-compute BB widths
    widths = []
    for i in range(len(closes)):
        if i < bb_period:
            widths.append(999.0)
        else:
            window = closes[i - bb_period + 1:i + 1]
            sma = np.mean(window)
            std = np.std(window)
            if sma > 0:
                widths.append((2 * bb_std * std) / sma)
            else:
                widths.append(999.0)
    widths = np.array(widths)

    for i in range(warmup, len(closes)):
        price = closes[i]

        # Check for squeeze: N consecutive candles with narrow bands
        recent_widths = widths[i - squeeze_candles:i]
        was_squeezed = np.all(recent_widths < squeeze_threshold)
        expanding = widths[i] > squeeze_threshold and was_squeezed

        if expanding and position == 0 and balance > 0:
            # Determine breakout direction
            window = closes[i - bb_period + 1:i + 1]
            sma = np.mean(window)
            if price > sma:
                # Bullish breakout — BUY
                # Confirm with volume
                avg_vol = np.mean(volumes[max(0, i - vol_lookback):i])
                if avg_vol > 0 and volumes[i] / avg_vol >= 1.3:
                    position = balance / price
                    entry_price = price
                    balance = 0.0
                    trades.append({"type": "BUY", "price": price, "idx": i,
                                   "width": round(widths[i], 4)})

        elif position > 0:
            # Exit: price crosses back below SMA or new squeeze forms
            window = closes[i - bb_period + 1:i + 1]
            sma = np.mean(window)
            std = np.std(window)
            upper = sma + bb_std * std

            # Sell if price > upper band (overextended) or drops below SMA
            if price > upper or price < sma:
                pnl_pct = ((price / entry_price) - 1) * 100
                balance = position * price
                trades.append({"type": "SELL", "price": price, "pnl_pct": pnl_pct, "idx": i})
                position = 0.0

    return balance, position, trades, warmup


def _backtest_vwap(closes, highs, lows, volumes, strat):
    """VWAP reversion with RSI confirmation."""
    vwap_cfg = strat.get("vwap", {})
    rsi_cfg = strat.get("indicators", {}).get("rsi", {})
    deviation = vwap_cfg.get("deviation_pct", 1.5)
    vwap_window = vwap_cfg.get("window", 24)  # rolling VWAP window (candles)
    rsi_period = rsi_cfg.get("period", 14)
    rsi_oversold = vwap_cfg.get("rsi_oversold", 35)
    rsi_overbought = vwap_cfg.get("rsi_overbought", 65)

    warmup = max(vwap_window + 1, rsi_period + 1, 30)
    balance = STARTING_BALANCE
    position = 0.0
    entry_price = 0.0
    trades = []

    for i in range(warmup, len(closes)):
        price = closes[i]

        # Rolling VWAP
        w_start = max(0, i - vwap_window + 1)
        typical = (highs[w_start:i + 1] + lows[w_start:i + 1] + closes[w_start:i + 1]) / 3.0
        vols = volumes[w_start:i + 1]
        cum_vol = np.sum(vols)
        if cum_vol > 0:
            vwap_val = np.sum(typical * vols) / cum_vol
        else:
            vwap_val = price

        # RSI for confirmation
        rsi = _rsi(closes[:i + 1], period=rsi_period)
        if rsi is None:
            continue

        # Price deviation from VWAP
        dev_pct = (price - vwap_val) / vwap_val * 100 if vwap_val > 0 else 0

        if position == 0 and balance > 0:
            # BUY: price significantly below VWAP + RSI oversold
            if dev_pct < -deviation and rsi < rsi_oversold:
                position = balance / price
                entry_price = price
                balance = 0.0
                trades.append({"type": "BUY", "price": price, "idx": i,
                               "vwap": round(vwap_val, 2), "dev": round(dev_pct, 2)})

        elif position > 0:
            # SELL: price above VWAP + RSI overbought, or back to VWAP from below
            if (dev_pct > deviation and rsi > rsi_overbought) or \
               (dev_pct > 0 and rsi > 55):  # take profit at VWAP reversion
                pnl_pct = ((price / entry_price) - 1) * 100
                balance = position * price
                trades.append({"type": "SELL", "price": price, "pnl_pct": pnl_pct, "idx": i,
                               "vwap": round(vwap_val, 2), "dev": round(dev_pct, 2)})
                position = 0.0

    return balance, position, trades, warmup


# ---------------------------------------------------------------------------
# Unified backtest runner
# ---------------------------------------------------------------------------

def run_backtest(symbol: str, days: int, strat: dict,
                 timeframe: str = "1h", strategy_mode: str = "rsi") -> dict:
    """Run backtest for one symbol using the specified strategy mode."""
    np.random.seed(FIXED_SEED)

    from src.core.market_data import get_klines

    n_candles = _candle_count(days, timeframe)
    klines = get_klines(symbol, timeframe, n_candles)
    if not klines or len(klines) < 35:
        raise ValueError(f"Not enough data for {symbol} ({timeframe}): "
                         f"got {len(klines) if klines else 0} candles")

    closes = np.array([float(k[4]) for k in klines])
    volumes = np.array([float(k[5]) for k in klines])
    highs = np.array([float(k[2]) for k in klines])
    lows = np.array([float(k[3]) for k in klines])

    # Dispatch to strategy
    if strategy_mode == "rsi":
        balance, position, trades, warmup = _backtest_rsi(closes, strat)
    elif strategy_mode == "ensemble":
        balance, position, trades, warmup = _backtest_ensemble(closes, volumes, strat)
    elif strategy_mode == "multi_confirm":
        balance, position, trades, warmup = _backtest_multi_confirm(closes, volumes, strat)
    elif strategy_mode == "momentum":
        balance, position, trades, warmup = _backtest_momentum(closes, volumes, strat)
    elif strategy_mode == "squeeze":
        balance, position, trades, warmup = _backtest_squeeze(closes, volumes, strat)
    elif strategy_mode == "vwap":
        balance, position, trades, warmup = _backtest_vwap(closes, highs, lows, volumes, strat)
    else:
        raise ValueError(f"Unknown strategy mode: {strategy_mode}")

    # Common metrics
    final_value = balance + (position * closes[-1])
    total_pnl_pct = ((final_value / STARTING_BALANCE) - 1) * 100

    # Reconstruct portfolio values for drawdown + Sharpe
    values = _reconstruct_values(closes, volumes, highs, lows, strat, warmup, strategy_mode)

    peak = np.maximum.accumulate(values)
    drawdown = ((values - peak) / peak) * 100
    max_drawdown_pct = float(abs(np.min(drawdown)))

    sells = [t for t in trades if t["type"] == "SELL"]
    n_trades = len(sells)
    win_rate = sum(1 for t in sells if t.get("pnl_pct", 0) > 0) / n_trades if n_trades > 0 else 0.0

    ann_factor = _ANN_FACTOR.get(timeframe, 252 * 24)
    period_returns = np.diff(values) / values[:-1]
    sharpe = 0.0
    if len(period_returns) > 1 and np.std(period_returns) > 0:
        sharpe = float((np.mean(period_returns) / np.std(period_returns)) * np.sqrt(ann_factor))

    trade_factor = min(n_trades / 10.0, 1.0)
    drawdown_penalty = 1 - (max_drawdown_pct / 100)
    coin_score = sharpe * drawdown_penalty * trade_factor

    return {
        "symbol": symbol,
        "strategy": strategy_mode,
        "timeframe": timeframe,
        "days": days,
        "candles": len(closes),
        "total_pnl_pct": round(total_pnl_pct, 4),
        "sharpe": round(sharpe, 4),
        "max_drawdown_pct": round(max_drawdown_pct, 4),
        "n_trades": n_trades,
        "win_rate": round(win_rate, 4),
        "coin_score": round(coin_score, 4),
    }


def _reconstruct_values(closes, volumes, highs, lows, strat, warmup, strategy_mode):
    """Replay strategy to get portfolio value series for Sharpe/drawdown."""
    # We need to re-run the strategy to track values at each candle.
    # This duplicates logic but keeps metrics accurate.
    if strategy_mode == "rsi":
        balance, position, trades, _ = _backtest_rsi(closes, strat)
    elif strategy_mode == "ensemble":
        balance, position, trades, _ = _backtest_ensemble(closes, volumes, strat)
    elif strategy_mode == "multi_confirm":
        balance, position, trades, _ = _backtest_multi_confirm(closes, volumes, strat)
    elif strategy_mode == "momentum":
        balance, position, trades, _ = _backtest_momentum(closes, volumes, strat)
    elif strategy_mode == "squeeze":
        balance, position, trades, _ = _backtest_squeeze(closes, volumes, strat)
    elif strategy_mode == "vwap":
        balance, position, trades, _ = _backtest_vwap(closes, highs, lows, volumes, strat)
    else:
        return np.array([STARTING_BALANCE])

    # Build trade index for fast lookup
    trade_events = {}
    for t in trades:
        trade_events[t["idx"]] = t

    # Replay
    values = [STARTING_BALANCE]
    tb, tp, ep = STARTING_BALANCE, 0.0, 0.0
    for i in range(warmup, len(closes)):
        price = closes[i]
        if i in trade_events:
            t = trade_events[i]
            if t["type"] == "BUY" and tp == 0 and tb > 0:
                tp = tb / price
                ep = price
                tb = 0.0
            elif t["type"] == "SELL" and tp > 0:
                tb = tp * price
                tp = 0.0
        values.append(tb + tp * price)

    return np.array(values)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Multi-strategy eval harness v2")
    parser.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS))
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--timeframe", default="1h",
                        choices=["15m", "30m", "1h", "4h", "1d"])
    parser.add_argument("--strategy", default=None,
                        choices=STRATEGIES,
                        help="Override strategy mode (default: from strategy.yaml)")
    parser.add_argument("--output-json", default=None)
    parser.add_argument("--compare-all", action="store_true",
                        help="Run ALL strategies and compare scores")
    args = parser.parse_args()

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]

    try:
        strat = load_strategy()

        if args.compare_all:
            _compare_all(symbols, args.days, strat, args.timeframe, args.output_json)
            return

        strategy_mode = args.strategy or strat.get("strategy_mode", "rsi")

        results = []
        errors = []

        for symbol in symbols:
            try:
                metrics = run_backtest(symbol, args.days, strat,
                                       timeframe=args.timeframe,
                                       strategy_mode=strategy_mode)
                results.append(metrics)
                print(f"  {symbol} ({args.timeframe}/{strategy_mode}): "
                      f"score={metrics['coin_score']} sharpe={metrics['sharpe']} "
                      f"dd={metrics['max_drawdown_pct']}% trades={metrics['n_trades']} "
                      f"pnl={metrics['total_pnl_pct']:+.2f}% candles={metrics['candles']}",
                      file=sys.stderr)
            except Exception as e:
                errors.append(symbol)
                print(f"  {symbol}: ERROR — {e}", file=sys.stderr)

        if not results:
            print("EVAL_SCORE: ERROR")
            sys.exit(1)

        coins_with_trades = sum(1 for r in results if r["n_trades"] > 0)
        coverage_factor = coins_with_trades / len(symbols)
        mean_score = float(np.mean([r["coin_score"] for r in results]))
        raw_score = round(mean_score * coverage_factor, 4)

        # Apply live trade feedback
        eval_score = raw_score
        live_stats = {"closed_trades": 0, "win_rate": None, "avg_pnl": None}
        try:
            from src.core.feedback import get_feedback_score, get_live_stats
            live_stats = get_live_stats()
            eval_score = get_feedback_score(raw_score)
            if eval_score != raw_score:
                print(f"  feedback: {live_stats['closed_trades']} live trades, "
                      f"win_rate={live_stats['win_rate']:.0%} → "
                      f"score {raw_score} → {eval_score}", file=sys.stderr)
        except Exception as fb_err:
            print(f"  feedback: skipped ({fb_err})", file=sys.stderr)

        output = {
            "strategy_mode": strategy_mode,
            "symbols": symbols,
            "days": args.days,
            "timeframe": args.timeframe,
            "per_coin": results,
            "aggregate": {
                "eval_score": eval_score,
                "raw_score": raw_score,
                "mean_coin_score": round(mean_score, 4),
                "coverage_factor": round(coverage_factor, 4),
                "coins_with_trades": coins_with_trades,
                "total_trades": sum(r["n_trades"] for r in results),
                "avg_sharpe": round(float(np.mean([r["sharpe"] for r in results])), 4),
                "avg_drawdown_pct": round(float(np.mean([r["max_drawdown_pct"] for r in results])), 4),
                "avg_pnl_pct": round(float(np.mean([r["total_pnl_pct"] for r in results])), 4),
                "live_closed_trades": live_stats["closed_trades"],
                "live_win_rate": live_stats["win_rate"],
                "live_avg_pnl": live_stats["avg_pnl"],
            },
            "errors": errors,
        }

        if args.output_json:
            os.makedirs(os.path.dirname(args.output_json)
                        if os.path.dirname(args.output_json) else ".", exist_ok=True)
            with open(args.output_json, "w") as f:
                json.dump(output, f, indent=2)

        print(f"EVAL_SCORE: {eval_score}")
        print(f"  strategy={strategy_mode} coverage={coverage_factor:.0%} "
              f"({coins_with_trades}/{len(symbols)} coins) "
              f"avg_sharpe={output['aggregate']['avg_sharpe']} "
              f"total_trades={output['aggregate']['total_trades']}",
              file=sys.stderr)

    except Exception as e:
        print("EVAL_SCORE: ERROR")
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


def _compare_all(symbols, days, strat, timeframe, output_json):
    """Run all strategies and print comparison table."""
    print(f"\n{'Strategy':<16} {'EVAL_SCORE':>10} {'Sharpe':>8} {'Trades':>7} "
          f"{'PnL%':>8} {'MaxDD%':>8} {'Coverage':>9}", file=sys.stderr)
    print("-" * 72, file=sys.stderr)

    all_results = {}
    for strategy_mode in STRATEGIES:
        results = []
        for symbol in symbols:
            try:
                metrics = run_backtest(symbol, days, strat,
                                       timeframe=timeframe,
                                       strategy_mode=strategy_mode)
                results.append(metrics)
            except Exception:
                pass

        if not results:
            print(f"  {strategy_mode:<16} {'ERROR':>10}", file=sys.stderr)
            continue

        coins_with_trades = sum(1 for r in results if r["n_trades"] > 0)
        coverage_factor = coins_with_trades / len(symbols)
        mean_score = float(np.mean([r["coin_score"] for r in results]))
        eval_score = round(mean_score * coverage_factor, 4)
        avg_sharpe = round(float(np.mean([r["sharpe"] for r in results])), 2)
        total_trades = sum(r["n_trades"] for r in results)
        avg_pnl = round(float(np.mean([r["total_pnl_pct"] for r in results])), 2)
        avg_dd = round(float(np.mean([r["max_drawdown_pct"] for r in results])), 2)

        print(f"  {strategy_mode:<16} {eval_score:>10.4f} {avg_sharpe:>8.2f} "
              f"{total_trades:>7} {avg_pnl:>+7.2f}% {avg_dd:>7.2f}% "
              f"{coverage_factor:>8.0%}", file=sys.stderr)

        all_results[strategy_mode] = {
            "eval_score": eval_score,
            "avg_sharpe": avg_sharpe,
            "total_trades": total_trades,
            "avg_pnl_pct": avg_pnl,
            "avg_drawdown_pct": avg_dd,
            "coverage": coverage_factor,
            "per_coin": results,
        }

    best = max(all_results.items(), key=lambda x: x[1]["eval_score"])
    print(f"\n  BEST: {best[0]} (EVAL_SCORE={best[1]['eval_score']})", file=sys.stderr)
    print(f"EVAL_SCORE: {best[1]['eval_score']}")

    if output_json:
        os.makedirs(os.path.dirname(output_json)
                    if os.path.dirname(output_json) else ".", exist_ok=True)
        with open(output_json, "w") as f:
            json.dump(all_results, f, indent=2)


if __name__ == "__main__":
    main()
