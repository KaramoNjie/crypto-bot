#!/usr/bin/env python3
"""
scripts/eval_harness.py — Multi-strategy eval harness for strategy autoresearch.

DO NOT MODIFY THIS FILE. The autoresearch loop is not permitted to edit it.

Tests multiple trading strategies. Strategy mode is read from
config/strategy.yaml `strategy_mode` field, or overridden via --strategy CLI flag.

Available strategies:
  rsi           — RSI mean-reversion (baseline)
  ensemble      — Weighted 5-indicator ensemble (RSI+MACD+BB+EMA+Volume)
  multi_confirm — Require N indicators to agree before entry
  momentum      — N-period high/low breakout + volume confirmation
  squeeze       — Bollinger squeeze → breakout with direction
  vwap          — VWAP reversion with RSI confirmation
  vwap_rsi      — Hybrid: VWAP entry + RSI exit
  squeeze_vwap  — Squeeze breakout entry + VWAP take profit

EVAL_SCORE = mean(per-coin scores) * coverage_factor * feedback_factor
  per-coin     = sharpe * (1 - drawdown/100) * min(n_trades/10, 1.0)
  coverage     = fraction of coins that produced ≥1 trade
  feedback     = live trade adjustment: 1 + (win_rate - 0.5) * 0.2  (±10%, needs ≥3 live trades)

Prints exactly one line to stdout: EVAL_SCORE: <float>

Usage:
    python scripts/eval_harness.py --days 90 --strategy vwap
    python scripts/eval_harness.py --days 90 --timeframe 1h --output-json loops/latest_eval.json
    python scripts/eval_harness.py --days 90 --compare-all
    python scripts/eval_harness.py --days 90 --fees                    # Include 0.15% transaction costs
    python scripts/eval_harness.py --days 90 --fees --walk-forward     # Honest eval: fees + out-of-sample
    python scripts/eval_harness.py --days 90 --walk-forward --test-ratio 0.4  # Custom test split
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
DEFAULT_FEE_RATE = 0.001  # 0.1% per trade (Binance maker+taker ~0.1%)
DEFAULT_SLIPPAGE = 0.0005  # 0.05% slippage estimate

_CANDLES_PER_DAY = {"15m": 96, "30m": 48, "1h": 24, "4h": 6, "1d": 1}
# Crypto trades 24/7/365 — use 365.25 days, not 252 (stock market)
_ANN_FACTOR = {"15m": 365 * 96, "30m": 365 * 48, "1h": 365 * 24, "4h": 365 * 6, "1d": 365}

STRATEGIES = ["rsi", "ensemble", "multi_confirm", "momentum", "squeeze", "vwap",
              "vwap_rsi", "squeeze_vwap"]


def _candle_count(days: int, timeframe: str) -> int:
    """Calculate candle count. No longer capped at 1000 — pagination handles it."""
    return days * _CANDLES_PER_DAY.get(timeframe, 24)


# ---------------------------------------------------------------------------
# Technical indicator functions
# ---------------------------------------------------------------------------

def _rsi(prices, period=14):
    """RSI using Wilder's exponential smoothing (matches TradingView/standard)."""
    if len(prices) < period + 1:
        return None
    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    # Wilder's smoothing: seed with SMA, then exponential
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
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

def _backtest_rsi(closes, strat, fee_rate=0.0):
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
            position = balance * (1 - fee_rate) / price
            entry_price = price
            balance = 0.0
            trades.append({"type": "BUY", "price": price, "idx": i})
        elif rsi > overbought and position > 0:
            pnl_pct = ((price / entry_price) - 1) * 100
            balance = position * price * (1 - fee_rate)
            trades.append({"type": "SELL", "price": price, "pnl_pct": pnl_pct, "idx": i})
            position = 0.0

    return balance, position, trades, warmup


def _backtest_ensemble(closes, volumes, strat, fee_rate=0.0, highs=None, lows=None):
    """Full 7-indicator weighted ensemble — matches signals.py weights."""
    ind = strat.get("indicators", {})
    rsi_cfg = ind.get("rsi", {})
    macd_cfg = ind.get("macd", {})
    bb_cfg = ind.get("bollinger", {})
    vwap_cfg = strat.get("vwap", {})
    mom_cfg = strat.get("momentum", {})

    rsi_period = rsi_cfg.get("period", 14)
    rsi_oversold = rsi_cfg.get("oversold", 30)
    rsi_overbought = rsi_cfg.get("overbought", 70)
    macd_fast = macd_cfg.get("fast", 12)
    macd_slow = macd_cfg.get("slow", 26)
    macd_signal = macd_cfg.get("signal", 9)
    bb_period = bb_cfg.get("period", 20)
    bb_std = bb_cfg.get("std", 2.0)
    vol_lookback = ind.get("volume_lookback", 20)
    vwap_window = vwap_cfg.get("window", 24)
    vwap_deviation = vwap_cfg.get("deviation_pct", 2.45)
    breakout_period = mom_cfg.get("breakout_period", 10)
    mom_vol_confirm = mom_cfg.get("volume_confirm", 1.5)

    # Match signals.py 7-strategy weights exactly
    weights = {"rsi": 0.20, "macd": 0.15, "bb": 0.15,
               "ema": 0.10, "vol": 0.05, "vwap": 0.25, "momentum": 0.10}
    sig_cfg = strat.get("signal", {})
    buy_threshold = sig_cfg.get("buy_threshold", 0.15)
    sell_threshold = sig_cfg.get("sell_threshold", -0.15)

    warmup = max(macd_slow + macd_signal, bb_period, rsi_period + 1,
                 vwap_window + 1, breakout_period + 1, 30)
    balance = STARTING_BALANCE
    position = 0.0
    entry_price = 0.0
    trades = []

    # Pre-compute full arrays
    ema9 = _ema(closes, 9)
    ema21 = _ema(closes, 21)
    macd_line, signal_line, histogram = _macd(closes, macd_fast, macd_slow, macd_signal)

    # Use closes as fallback for highs/lows if not provided
    if highs is None:
        highs = closes
    if lows is None:
        lows = closes

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

        # VWAP reversion (new — matches signals.py vwap_signal)
        if i >= vwap_window:
            w_start = max(0, i - vwap_window + 1)
            typical = (highs[w_start:i + 1] + lows[w_start:i + 1] + closes[w_start:i + 1]) / 3.0
            vols = volumes[w_start:i + 1]
            cum_vol = np.sum(vols)
            vwap_val = np.sum(typical * vols) / cum_vol if cum_vol > 0 else price
            dev_pct = (price - vwap_val) / vwap_val * 100 if vwap_val > 0 else 0
            if dev_pct < -vwap_deviation:
                depth = abs(dev_pct) / vwap_deviation
                scores["vwap"] = min(depth * 0.5, 1.0)
            elif dev_pct > vwap_deviation:
                depth = dev_pct / vwap_deviation
                scores["vwap"] = -min(depth * 0.5, 1.0)
            else:
                scores["vwap"] = -dev_pct / vwap_deviation * 0.2

        # Momentum breakout (new — matches signals.py momentum_breakout_signal)
        if i >= breakout_period:
            window_high = np.max(highs[i - breakout_period:i])
            window_low = np.min(lows[i - breakout_period:i])
            avg_vol = np.mean(volumes[i - breakout_period:i])
            vol_ratio = volumes[i] / avg_vol if avg_vol > 0 else 1.0
            vol_confirmed = vol_ratio >= mom_vol_confirm
            if price > window_high and vol_confirmed:
                scores["momentum"] = min(0.6 + (price - window_high) / window_high * 100 * 0.1, 1.0)
            elif price < window_low and vol_confirmed:
                scores["momentum"] = -min(0.6 + (window_low - price) / window_low * 100 * 0.1, 1.0)
            else:
                scores["momentum"] = 0.0

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
            position = balance * (1 - fee_rate) / price
            entry_price = price
            balance = 0.0
            trades.append({"type": "BUY", "price": price, "idx": i, "score": ensemble_score})
        elif ensemble_score < sell_threshold and position > 0:
            pnl_pct = ((price / entry_price) - 1) * 100
            balance = position * price * (1 - fee_rate)
            trades.append({"type": "SELL", "price": price, "pnl_pct": pnl_pct, "idx": i, "score": ensemble_score})
            position = 0.0

    return balance, position, trades, warmup


def _backtest_multi_confirm(closes, volumes, strat, fee_rate=0.0):
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
            position = balance * (1 - fee_rate) / price
            entry_price = price
            balance = 0.0
            trades.append({"type": "BUY", "price": price, "idx": i,
                           "votes": effective_buy})
        elif effective_sell >= require_agree and position > 0:
            pnl_pct = ((price / entry_price) - 1) * 100
            balance = position * price * (1 - fee_rate)
            trades.append({"type": "SELL", "price": price, "pnl_pct": pnl_pct, "idx": i,
                           "votes": effective_sell})
            position = 0.0

    return balance, position, trades, warmup


def _backtest_momentum(closes, volumes, strat, fee_rate=0.0):
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
                balance = position * price * (1 - fee_rate)
                trades.append({"type": "SELL", "price": price, "pnl_pct": pnl_pct, "idx": i})
                position = 0.0

        elif position == 0 and balance > 0:
            # Buy on breakout above N-period high with volume confirmation
            if price > period_high and vol_ratio >= volume_confirm:
                position = balance * (1 - fee_rate) / price
                entry_price = price
                peak_price = price
                balance = 0.0
                trades.append({"type": "BUY", "price": price, "idx": i,
                               "vol_ratio": round(vol_ratio, 2)})

    return balance, position, trades, warmup


def _backtest_squeeze(closes, volumes, strat, fee_rate=0.0):
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
                    position = balance * (1 - fee_rate) / price
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
                balance = position * price * (1 - fee_rate)
                trades.append({"type": "SELL", "price": price, "pnl_pct": pnl_pct, "idx": i})
                position = 0.0

    return balance, position, trades, warmup


def _backtest_vwap(closes, highs, lows, volumes, strat, fee_rate=0.0):
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
                position = balance * (1 - fee_rate) / price
                entry_price = price
                balance = 0.0
                trades.append({"type": "BUY", "price": price, "idx": i,
                               "vwap": round(vwap_val, 2), "dev": round(dev_pct, 2)})

        elif position > 0:
            # SELL: price above VWAP + RSI overbought, or back to VWAP from below
            if (dev_pct > deviation and rsi > rsi_overbought) or \
               (dev_pct > 0 and rsi > 55):  # take profit at VWAP reversion
                pnl_pct = ((price / entry_price) - 1) * 100
                balance = position * price * (1 - fee_rate)
                trades.append({"type": "SELL", "price": price, "pnl_pct": pnl_pct, "idx": i,
                               "vwap": round(vwap_val, 2), "dev": round(dev_pct, 2)})
                position = 0.0

    return balance, position, trades, warmup


def _backtest_vwap_rsi(closes, highs, lows, volumes, strat, fee_rate=0.0):
    """Hybrid: VWAP for entry timing, RSI for exit confirmation.

    Entry: price < VWAP * (1 - deviation) AND RSI < oversold (VWAP entry)
    Exit:  RSI > overbought (RSI exit — let profits run until RSI says stop)
    This combines VWAP's superior entry timing with RSI's trend-following exits.
    """
    vwap_cfg = strat.get("vwap", {})
    rsi_cfg = strat.get("indicators", {}).get("rsi", {})
    hybrid_cfg = strat.get("vwap_rsi", {})

    deviation = hybrid_cfg.get("entry_deviation", vwap_cfg.get("deviation_pct", 2.5))
    vwap_window = hybrid_cfg.get("vwap_window", vwap_cfg.get("window", 24))
    entry_rsi_threshold = hybrid_cfg.get("entry_rsi", vwap_cfg.get("rsi_oversold", 44))
    exit_rsi_threshold = hybrid_cfg.get("exit_rsi", rsi_cfg.get("overbought", 69))
    rsi_period = rsi_cfg.get("period", 17)

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
        vwap_val = np.sum(typical * vols) / cum_vol if cum_vol > 0 else price

        dev_pct = (price - vwap_val) / vwap_val * 100 if vwap_val > 0 else 0

        # RSI
        rsi = _rsi(closes[:i + 1], period=rsi_period)
        if rsi is None:
            continue

        # ENTRY: VWAP deviation + RSI oversold
        if position == 0 and balance > 0:
            if dev_pct < -deviation and rsi < entry_rsi_threshold:
                position = balance * (1 - fee_rate) / price
                entry_price = price
                balance = 0.0
                trades.append({"type": "BUY", "price": price, "idx": i,
                               "vwap": round(vwap_val, 2), "rsi": round(rsi, 1)})

        # EXIT: RSI overbought (let profits run)
        elif position > 0:
            if rsi > exit_rsi_threshold:
                pnl_pct = ((price / entry_price) - 1) * 100
                balance = position * price * (1 - fee_rate)
                trades.append({"type": "SELL", "price": price, "pnl_pct": pnl_pct,
                               "idx": i, "rsi": round(rsi, 1)})
                position = 0.0

    return balance, position, trades, warmup


def _backtest_squeeze_vwap(closes, highs, lows, volumes, strat, fee_rate=0.0):
    """Selective high-conviction: squeeze breakout entries, VWAP exit.

    Entry: Bollinger squeeze detected → breakout above SMA + volume confirm
    Exit:  Price reverts to VWAP (take profit) or drops below entry - stop_pct
    Fewer trades but each should be high quality.
    """
    bb_cfg = strat.get("indicators", {}).get("bollinger", {})
    sq_cfg = strat.get("squeeze", {})
    vwap_cfg = strat.get("vwap", {})
    sv_cfg = strat.get("squeeze_vwap", {})

    bb_period = bb_cfg.get("period", 20)
    bb_std = bb_cfg.get("std", 1.5)
    squeeze_threshold = sv_cfg.get("width_threshold", sq_cfg.get("width_threshold", 0.03))
    squeeze_candles = sv_cfg.get("squeeze_candles", sq_cfg.get("squeeze_candles", 3))
    vwap_window = sv_cfg.get("vwap_window", vwap_cfg.get("window", 24))
    stop_pct = sv_cfg.get("stop_pct", 3.0)
    vol_lookback = strat.get("indicators", {}).get("volume_lookback", 20)

    warmup = max(bb_period + squeeze_candles, vol_lookback + 1, vwap_window + 1, 35)
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
            widths.append((2 * bb_std * std) / sma if sma > 0 else 999.0)
    widths = np.array(widths)

    for i in range(warmup, len(closes)):
        price = closes[i]

        if position == 0 and balance > 0:
            # Check for squeeze → breakout
            recent_widths = widths[i - squeeze_candles:i]
            was_squeezed = np.all(recent_widths < squeeze_threshold)
            expanding = widths[i] > squeeze_threshold and was_squeezed

            if expanding:
                window_c = closes[i - bb_period + 1:i + 1]
                sma = np.mean(window_c)
                if price > sma:
                    # Volume confirmation
                    avg_vol = np.mean(volumes[max(0, i - vol_lookback):i])
                    if avg_vol > 0 and volumes[i] / avg_vol >= 1.3:
                        position = balance * (1 - fee_rate) / price
                        entry_price = price
                        balance = 0.0
                        trades.append({"type": "BUY", "price": price, "idx": i,
                                       "width": round(widths[i], 4)})

        elif position > 0:
            # Rolling VWAP for exit
            w_start = max(0, i - vwap_window + 1)
            typical = (highs[w_start:i + 1] + lows[w_start:i + 1] + closes[w_start:i + 1]) / 3.0
            vols = volumes[w_start:i + 1]
            cum_vol = np.sum(vols)
            vwap_val = np.sum(typical * vols) / cum_vol if cum_vol > 0 else price

            # Exit: price above VWAP (profit taken) or stop loss
            stop_hit = price < entry_price * (1 - stop_pct / 100)
            profit_at_vwap = price > vwap_val and price > entry_price

            if stop_hit or profit_at_vwap:
                pnl_pct = ((price / entry_price) - 1) * 100
                balance = position * price * (1 - fee_rate)
                trades.append({"type": "SELL", "price": price, "pnl_pct": pnl_pct,
                               "idx": i, "reason": "stop" if stop_hit else "vwap_tp"})
                position = 0.0

    return balance, position, trades, warmup


# ---------------------------------------------------------------------------
# Unified backtest runner
# ---------------------------------------------------------------------------

def _run_strategy(closes, volumes, highs, lows, strat, strategy_mode, fee_rate=0.0):
    """Dispatch to the correct backtest strategy function."""
    if strategy_mode == "rsi":
        return _backtest_rsi(closes, strat, fee_rate)
    elif strategy_mode == "ensemble":
        return _backtest_ensemble(closes, volumes, strat, fee_rate, highs=highs, lows=lows)
    elif strategy_mode == "multi_confirm":
        return _backtest_multi_confirm(closes, volumes, strat, fee_rate)
    elif strategy_mode == "momentum":
        return _backtest_momentum(closes, volumes, strat, fee_rate)
    elif strategy_mode == "squeeze":
        return _backtest_squeeze(closes, volumes, strat, fee_rate)
    elif strategy_mode == "vwap":
        return _backtest_vwap(closes, highs, lows, volumes, strat, fee_rate)
    elif strategy_mode == "vwap_rsi":
        return _backtest_vwap_rsi(closes, highs, lows, volumes, strat, fee_rate)
    elif strategy_mode == "squeeze_vwap":
        return _backtest_squeeze_vwap(closes, highs, lows, volumes, strat, fee_rate)
    else:
        raise ValueError(f"Unknown strategy mode: {strategy_mode}")


def run_backtest(symbol: str, days: int, strat: dict,
                 timeframe: str = "1h", strategy_mode: str = "rsi",
                 fee_rate: float = 0.0, walk_forward: bool = False,
                 test_ratio: float = 0.33) -> dict:
    """Run backtest for one symbol using the specified strategy mode.

    Args:
        fee_rate: Transaction cost per trade (0.001 = 0.1%). Applied on both buy and sell.
        walk_forward: If True, only score trades in the out-of-sample test window.
                      The strategy still runs on all data for indicator warmup,
                      but only trades in the last `test_ratio` of candles count.
        test_ratio: Fraction of data used as out-of-sample test (default 33%).
    """
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

    # Run full backtest (indicators need full data for warmup)
    balance, position, trades, warmup = _run_strategy(
        closes, volumes, highs, lows, strat, strategy_mode, fee_rate)

    # Walk-forward: only count trades in the test window
    test_start_idx = int(len(closes) * (1 - test_ratio)) if walk_forward else 0
    if walk_forward:
        trades_scored = [t for t in trades if t["idx"] >= test_start_idx]
    else:
        trades_scored = trades

    # Force-close any open position at end (apply fees for realism)
    if position > 0:
        close_value = position * closes[-1] * (1 - fee_rate)
        balance += close_value
        trades.append({"type": "SELL", "price": float(closes[-1]),
                       "pnl_pct": ((closes[-1] / trades[-1].get("price", closes[-1])) - 1) * 100
                       if trades else 0,
                       "idx": len(closes) - 1, "reason": "end_of_backtest"})
        position = 0.0

    # Common metrics
    final_value = balance + (position * closes[-1])
    total_pnl_pct = ((final_value / STARTING_BALANCE) - 1) * 100

    # Reconstruct portfolio values for drawdown + Sharpe
    values = _reconstruct_values(closes, volumes, highs, lows, strat, warmup,
                                 strategy_mode, fee_rate)

    # For walk-forward, only measure Sharpe/drawdown in the test window
    if walk_forward and test_start_idx > warmup:
        wf_offset = test_start_idx - warmup
        if wf_offset < len(values):
            values_scored = values[wf_offset:]
        else:
            values_scored = values
    else:
        values_scored = values

    peak = np.maximum.accumulate(values_scored)
    drawdown = ((values_scored - peak) / peak) * 100
    max_drawdown_pct = float(abs(np.min(drawdown)))

    sells = [t for t in trades_scored if t["type"] == "SELL"]
    n_trades = len(sells)
    win_rate = sum(1 for t in sells if t.get("pnl_pct", 0) > 0) / n_trades if n_trades > 0 else 0.0

    ann_factor = _ANN_FACTOR.get(timeframe, 252 * 24)
    period_returns = np.diff(values_scored) / values_scored[:-1]
    sharpe = 0.0
    if len(period_returns) > 1 and np.std(period_returns) > 0:
        sharpe = float((np.mean(period_returns) / np.std(period_returns)) * np.sqrt(ann_factor))

    trade_factor = min(n_trades / 10.0, 1.0)
    drawdown_penalty = 1 - (max_drawdown_pct / 100)
    coin_score = sharpe * drawdown_penalty * trade_factor

    result = {
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
    if walk_forward:
        result["walk_forward"] = True
        result["test_start_idx"] = test_start_idx
        result["test_candles"] = len(closes) - test_start_idx
    if fee_rate > 0:
        result["fee_rate"] = fee_rate

    return result


def _reconstruct_values(closes, volumes, highs, lows, strat, warmup,
                        strategy_mode, fee_rate=0.0):
    """Replay strategy to get portfolio value series for Sharpe/drawdown."""
    try:
        balance, position, trades, _ = _run_strategy(
            closes, volumes, highs, lows, strat, strategy_mode, fee_rate)
    except ValueError:
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
                tp = tb * (1 - fee_rate) / price
                ep = price
                tb = 0.0
            elif t["type"] == "SELL" and tp > 0:
                tb = tp * price * (1 - fee_rate)
                tp = 0.0
        values.append(tb + tp * price)

    return np.array(values)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Multi-strategy eval harness")
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
    parser.add_argument("--fees", action="store_true",
                        help="Include transaction costs (0.1%% fee + 0.05%% slippage per trade)")
    parser.add_argument("--walk-forward", action="store_true",
                        help="Walk-forward validation: score only on out-of-sample test window")
    parser.add_argument("--test-ratio", type=float, default=0.33,
                        help="Fraction of data for out-of-sample test (default: 0.33)")
    args = parser.parse_args()

    fee_rate = (DEFAULT_FEE_RATE + DEFAULT_SLIPPAGE) if args.fees else 0.0

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]

    try:
        strat = load_strategy()

        if args.compare_all:
            _compare_all(symbols, args.days, strat, args.timeframe, args.output_json,
                         fee_rate=fee_rate, walk_forward=args.walk_forward,
                         test_ratio=args.test_ratio)
            return

        if args.fees or args.walk_forward:
            mode_desc = []
            if args.fees:
                mode_desc.append(f"fees={fee_rate:.2%}")
            if args.walk_forward:
                mode_desc.append(f"walk-forward(test={args.test_ratio:.0%})")
            print(f"  Mode: {', '.join(mode_desc)}", file=sys.stderr)

        strategy_mode = args.strategy or strat.get("strategy_mode", "rsi")

        results = []
        errors = []

        for symbol in symbols:
            try:
                metrics = run_backtest(symbol, args.days, strat,
                                       timeframe=args.timeframe,
                                       strategy_mode=strategy_mode,
                                       fee_rate=fee_rate,
                                       walk_forward=args.walk_forward,
                                       test_ratio=args.test_ratio)
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


def _compare_all(symbols, days, strat, timeframe, output_json,
                 fee_rate=0.0, walk_forward=False, test_ratio=0.33):
    """Run all strategies and print comparison table."""
    mode_label = ""
    if fee_rate > 0:
        mode_label += f" [fees={fee_rate:.2%}]"
    if walk_forward:
        mode_label += f" [walk-forward test={test_ratio:.0%}]"

    print(f"\n{'Strategy':<16} {'EVAL_SCORE':>10} {'Sharpe':>8} {'Trades':>7} "
          f"{'PnL%':>8} {'MaxDD%':>8} {'Coverage':>9}{mode_label}", file=sys.stderr)
    print("-" * 72, file=sys.stderr)

    all_results = {}
    for strategy_mode in STRATEGIES:
        results = []
        for symbol in symbols:
            try:
                metrics = run_backtest(symbol, days, strat,
                                       timeframe=timeframe,
                                       strategy_mode=strategy_mode,
                                       fee_rate=fee_rate,
                                       walk_forward=walk_forward,
                                       test_ratio=test_ratio)
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
