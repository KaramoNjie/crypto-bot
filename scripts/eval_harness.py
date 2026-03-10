#!/usr/bin/env python3
"""
scripts/eval_harness.py — IMMUTABLE eval harness for strategy autoresearch.

DO NOT MODIFY THIS FILE. The autoresearch loop is not permitted to edit it.

Usage:
    python scripts/eval_harness.py --symbol BTCUSDT --days 90
    python scripts/eval_harness.py --symbol BTCUSDT --days 90 --output-json loops/latest_eval.json

Prints exactly one line to stdout: EVAL_SCORE: <float>
"""

import argparse
import json
import sys
import os
import numpy as np

# Add repo root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

FIXED_SEED = 42
STARTING_BALANCE = 1000.0  # Fixed — independent of paper_state.json


def _ema_series(prices, period):
    if len(prices) < period:
        return None
    mult = 2 / (period + 1)
    ema = np.empty(len(prices))
    ema[:period] = np.nan
    ema[period - 1] = np.mean(prices[:period])
    for i in range(period, len(prices)):
        ema[i] = prices[i] * mult + ema[i - 1] * (1 - mult)
    return ema


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


def load_strategy():
    """Load config/strategy.yaml."""
    try:
        import yaml
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "strategy.yaml")
        with open(path) as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"Warning: could not load strategy.yaml ({e}), using defaults", file=sys.stderr)
        return {}


def run_backtest(symbol: str, days: int, strat: dict) -> dict:
    """Run RSI mean-reversion backtest. Returns metrics dict."""
    np.random.seed(FIXED_SEED)

    from src.core.market_data import get_klines

    ind = strat.get("indicators", {})
    rsi_cfg = ind.get("rsi", {})
    rsi_period = rsi_cfg.get("period", 14)
    rsi_oversold = rsi_cfg.get("oversold", 30)
    rsi_overbought = rsi_cfg.get("overbought", 70)

    klines = get_klines(symbol, "1d", min(days, 365))
    if not klines or len(klines) < rsi_period + 5:
        raise ValueError(f"Not enough data: got {len(klines) if klines else 0} candles")

    closes = np.array([float(k[4]) for k in klines])

    balance = STARTING_BALANCE
    position = 0.0
    entry_price = 0.0
    trades = []

    warmup = max(rsi_period + 1, 20)
    for i in range(warmup, len(closes)):
        price = closes[i]
        rsi = _rsi(closes[:i + 1], period=rsi_period)
        if rsi is None:
            continue
        if rsi < rsi_oversold and position == 0 and balance > 0:
            position = balance / price
            entry_price = price
            balance = 0.0
            trades.append({"type": "BUY", "price": price, "rsi": rsi, "idx": i})
        elif rsi > rsi_overbought and position > 0:
            balance = position * price
            pnl_pct = ((price / entry_price) - 1) * 100
            trades.append({"type": "SELL", "price": price, "rsi": rsi, "pnl_pct": pnl_pct, "idx": i})
            position = 0.0

    final_value = balance + (position * closes[-1])
    total_pnl_pct = ((final_value / STARTING_BALANCE) - 1) * 100

    # Max drawdown
    values = [STARTING_BALANCE]
    tb, tp = STARTING_BALANCE, 0.0
    for i in range(warmup, len(closes)):
        price = closes[i]
        rsi = _rsi(closes[:i + 1], period=rsi_period)
        if rsi is not None and rsi < rsi_oversold and tp == 0 and tb > 0:
            tp = tb / price
            tb = 0.0
        elif rsi is not None and rsi > rsi_overbought and tp > 0:
            tb = tp * price
            tp = 0.0
        values.append(tb + tp * price)
    values = np.array(values)
    peak = np.maximum.accumulate(values)
    drawdown = ((values - peak) / peak) * 100
    max_drawdown_pct = float(abs(np.min(drawdown)))

    # Trade stats
    sells = [t for t in trades if t["type"] == "SELL"]
    n_trades = len(sells)
    win_rate = sum(1 for t in sells if t.get("pnl_pct", 0) > 0) / n_trades if n_trades > 0 else 0.0

    # Sharpe ratio (annualised, daily returns, 0 risk-free rate)
    daily_returns = np.diff(values) / values[:-1]
    sharpe = 0.0
    if len(daily_returns) > 1 and np.std(daily_returns) > 0:
        sharpe = float((np.mean(daily_returns) / np.std(daily_returns)) * np.sqrt(252))

    # EVAL_SCORE: rewards Sharpe, penalises drawdown, discounts <10 trades
    trade_factor = min(n_trades / 10.0, 1.0)
    drawdown_penalty = 1 - (max_drawdown_pct / 100)
    eval_score = sharpe * drawdown_penalty * trade_factor

    return {
        "symbol": symbol,
        "days": days,
        "total_pnl_pct": round(total_pnl_pct, 4),
        "sharpe": round(sharpe, 4),
        "max_drawdown_pct": round(max_drawdown_pct, 4),
        "n_trades": n_trades,
        "win_rate": round(win_rate, 4),
        "eval_score": round(eval_score, 4),
        "rsi_period": rsi_period,
        "rsi_oversold": rsi_oversold,
        "rsi_overbought": rsi_overbought,
    }


def main():
    parser = argparse.ArgumentParser(description="Eval harness for strategy autoresearch")
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--output-json", default=None)
    args = parser.parse_args()

    try:
        strat = load_strategy()
        metrics = run_backtest(args.symbol, args.days, strat)

        if args.output_json:
            os.makedirs(os.path.dirname(args.output_json) if os.path.dirname(args.output_json) else ".", exist_ok=True)
            with open(args.output_json, "w") as f:
                json.dump(metrics, f, indent=2)

        print(f"EVAL_SCORE: {metrics['eval_score']}")
        print(f"  sharpe={metrics['sharpe']} drawdown={metrics['max_drawdown_pct']}% trades={metrics['n_trades']} win_rate={metrics['win_rate']:.0%} pnl={metrics['total_pnl_pct']:+.2f}%", file=sys.stderr)

    except Exception as e:
        print(f"EVAL_SCORE: ERROR")
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
