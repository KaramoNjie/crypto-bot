#!/usr/bin/env python3
"""
scripts/eval_harness.py — IMMUTABLE eval harness for strategy autoresearch.

DO NOT MODIFY THIS FILE. The autoresearch loop is not permitted to edit it.

Usage:
    python scripts/eval_harness.py --days 90 --timeframe 1h
    python scripts/eval_harness.py --days 90 --timeframe 1h --output-json loops/latest_eval.json
    python scripts/eval_harness.py --symbols BTCUSDT,ETHUSDT --days 90 --timeframe 1h

Tests strategy across multiple coins (BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT) by default.

EVAL_SCORE = mean(per-coin scores) * coverage_factor * feedback_factor
  per-coin     = sharpe * (1 - drawdown/100) * min(n_trades/10, 1.0)
  coverage     = fraction of coins that produced ≥1 trade
  feedback     = live trade adjustment: 1 + (win_rate - 0.5) * 0.2  (±10%, needs ≥3 live trades)

Prints exactly one line to stdout: EVAL_SCORE: <float>
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

# Candles per day per timeframe
_CANDLES_PER_DAY = {"15m": 96, "30m": 48, "1h": 24, "4h": 6, "1d": 1}
# Annualisation factor (periods per year) for Sharpe
_ANN_FACTOR = {"15m": 252 * 96, "30m": 252 * 48, "1h": 252 * 24, "4h": 252 * 6, "1d": 252}


def _candle_count(days: int, timeframe: str) -> int:
    """Number of candles to request — capped at Binance API max of 1000."""
    return min(days * _CANDLES_PER_DAY.get(timeframe, 24), 1000)


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
    try:
        import yaml
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "strategy.yaml")
        with open(path) as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"Warning: could not load strategy.yaml ({e}), using defaults", file=sys.stderr)
        return {}


def run_backtest(symbol: str, days: int, strat: dict, timeframe: str = "1h") -> dict:
    """Run RSI mean-reversion backtest for one symbol on given timeframe."""
    np.random.seed(FIXED_SEED)

    from src.core.market_data import get_klines

    ind = strat.get("indicators", {})
    rsi_cfg = ind.get("rsi", {})
    rsi_period = rsi_cfg.get("period", 14)
    rsi_oversold = rsi_cfg.get("oversold", 30)
    rsi_overbought = rsi_cfg.get("overbought", 70)

    n_candles = _candle_count(days, timeframe)
    klines = get_klines(symbol, timeframe, n_candles)
    if not klines or len(klines) < rsi_period + 5:
        raise ValueError(f"Not enough data for {symbol} ({timeframe}): got {len(klines) if klines else 0} candles")

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

    sells = [t for t in trades if t["type"] == "SELL"]
    n_trades = len(sells)
    win_rate = sum(1 for t in sells if t.get("pnl_pct", 0) > 0) / n_trades if n_trades > 0 else 0.0

    # Sharpe — annualised for the given timeframe
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
        "timeframe": timeframe,
        "days": days,
        "candles": len(closes),
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
    parser.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS))
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--timeframe", default="1h",
                        choices=["15m", "30m", "1h", "4h", "1d"],
                        help="Candle timeframe (default: 1h)")
    parser.add_argument("--output-json", default=None)
    args = parser.parse_args()

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]

    try:
        strat = load_strategy()
        results = []
        errors = []

        for symbol in symbols:
            try:
                metrics = run_backtest(symbol, args.days, strat, timeframe=args.timeframe)
                results.append(metrics)
                print(f"  {symbol} ({args.timeframe}): score={metrics['coin_score']} "
                      f"sharpe={metrics['sharpe']} dd={metrics['max_drawdown_pct']}% "
                      f"trades={metrics['n_trades']} pnl={metrics['total_pnl_pct']:+.2f}% "
                      f"candles={metrics['candles']}", file=sys.stderr)
            except Exception as e:
                errors.append(symbol)
                print(f"  {symbol}: ERROR — {e}", file=sys.stderr)

        if not results:
            print("EVAL_SCORE: ERROR")
            print("All symbols failed", file=sys.stderr)
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
            os.makedirs(os.path.dirname(args.output_json) if os.path.dirname(args.output_json) else ".", exist_ok=True)
            with open(args.output_json, "w") as f:
                json.dump(output, f, indent=2)

        print(f"EVAL_SCORE: {eval_score}")
        print(f"  coverage={coverage_factor:.0%} ({coins_with_trades}/{len(symbols)} coins) "
              f"avg_sharpe={output['aggregate']['avg_sharpe']} "
              f"total_trades={output['aggregate']['total_trades']}",
              file=sys.stderr)

    except Exception as e:
        print("EVAL_SCORE: ERROR")
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
