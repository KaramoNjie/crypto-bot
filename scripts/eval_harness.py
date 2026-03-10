#!/usr/bin/env python3
"""
scripts/eval_harness.py — IMMUTABLE eval harness for strategy autoresearch.

DO NOT MODIFY THIS FILE. The autoresearch loop is not permitted to edit it.

Usage:
    python scripts/eval_harness.py --days 90
    python scripts/eval_harness.py --days 90 --output-json loops/latest_eval.json
    python scripts/eval_harness.py --symbols BTCUSDT,ETHUSDT --days 90

Tests strategy across multiple coins by default (BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT).

EVAL_SCORE = mean(per-coin scores) * coverage_factor
  per-coin  = sharpe * (1 - drawdown/100) * min(n_trades/10, 1.0)
  coverage  = fraction of coins that produced at least 1 trade
              (penalises strategies that only work on one coin)

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
DEFAULT_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]


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
    """Run RSI mean-reversion backtest for one symbol. Returns metrics dict."""
    np.random.seed(FIXED_SEED)

    from src.core.market_data import get_klines

    ind = strat.get("indicators", {})
    rsi_cfg = ind.get("rsi", {})
    rsi_period = rsi_cfg.get("period", 14)
    rsi_oversold = rsi_cfg.get("oversold", 30)
    rsi_overbought = rsi_cfg.get("overbought", 70)

    klines = get_klines(symbol, "1d", min(days, 365))
    if not klines or len(klines) < rsi_period + 5:
        raise ValueError(f"Not enough data for {symbol}: got {len(klines) if klines else 0} candles")

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

    # Per-coin EVAL_SCORE
    trade_factor = min(n_trades / 10.0, 1.0)
    drawdown_penalty = 1 - (max_drawdown_pct / 100)
    coin_score = sharpe * drawdown_penalty * trade_factor

    return {
        "symbol": symbol,
        "days": days,
        "total_pnl_pct": round(total_pnl_pct, 4),
        "sharpe": round(sharpe, 4),
        "max_drawdown_pct": round(max_drawdown_pct, 4),
        "n_trades": n_trades,
        "win_rate": round(win_rate, 4),
        "coin_score": round(coin_score, 4),
        "rsi_period": rsi_period,
        "rsi_oversold": rsi_oversold,
        "rsi_overbought": rsi_overbought,
    }


def main():
    parser = argparse.ArgumentParser(description="Multi-coin eval harness for strategy autoresearch")
    parser.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS),
                        help="Comma-separated list of symbols (default: BTC,ETH,SOL,BNB)")
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--output-json", default=None)
    args = parser.parse_args()

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]

    try:
        strat = load_strategy()
        results = []
        errors = []

        for symbol in symbols:
            try:
                metrics = run_backtest(symbol, args.days, strat)
                results.append(metrics)
                print(f"  {symbol}: score={metrics['coin_score']} sharpe={metrics['sharpe']} "
                      f"dd={metrics['max_drawdown_pct']}% trades={metrics['n_trades']} "
                      f"pnl={metrics['total_pnl_pct']:+.2f}%", file=sys.stderr)
            except Exception as e:
                errors.append(symbol)
                print(f"  {symbol}: ERROR — {e}", file=sys.stderr)

        if not results:
            print("EVAL_SCORE: ERROR")
            print("All symbols failed", file=sys.stderr)
            sys.exit(1)

        # Aggregate score
        # coverage_factor penalises strategies that only work on some coins
        coins_with_trades = sum(1 for r in results if r["n_trades"] > 0)
        coverage_factor = coins_with_trades / len(symbols)  # 0.25 if only BTC trades
        mean_score = float(np.mean([r["coin_score"] for r in results]))
        eval_score = round(mean_score * coverage_factor, 4)

        # Summary metrics
        total_trades = sum(r["n_trades"] for r in results)
        avg_sharpe = round(float(np.mean([r["sharpe"] for r in results])), 4)
        avg_drawdown = round(float(np.mean([r["max_drawdown_pct"] for r in results])), 4)
        avg_pnl = round(float(np.mean([r["total_pnl_pct"] for r in results])), 4)

        output = {
            "symbols": symbols,
            "days": args.days,
            "per_coin": results,
            "aggregate": {
                "eval_score": eval_score,
                "mean_coin_score": round(mean_score, 4),
                "coverage_factor": round(coverage_factor, 4),
                "coins_with_trades": coins_with_trades,
                "total_trades": total_trades,
                "avg_sharpe": avg_sharpe,
                "avg_drawdown_pct": avg_drawdown,
                "avg_pnl_pct": avg_pnl,
            },
            "errors": errors,
        }

        if args.output_json:
            os.makedirs(os.path.dirname(args.output_json) if os.path.dirname(args.output_json) else ".", exist_ok=True)
            with open(args.output_json, "w") as f:
                json.dump(output, f, indent=2)

        print(f"EVAL_SCORE: {eval_score}")
        print(f"  coverage={coverage_factor:.0%} ({coins_with_trades}/{len(symbols)} coins) "
              f"avg_sharpe={avg_sharpe} avg_dd={avg_drawdown}% total_trades={total_trades}",
              file=sys.stderr)

    except Exception as e:
        print("EVAL_SCORE: ERROR")
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
