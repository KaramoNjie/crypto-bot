"""Autonomous trading loop — scans signals and executes paper trades.

Run: python -m src.core.auto_trader
Or via CLI: python -m src.cli auto-trade

Scans all coins every interval, executes when confidence > threshold.
"""

import json
import logging
import time
from datetime import datetime, date
from pathlib import Path

from .signals import generate_signal, scan_all, discover_top_pairs
from .trading import execute_paper_trade
from .portfolio import get_portfolio_summary
from .knowledge import log_trade_learning, log_learning
from .config import load_strategy
from .market_data import get_ticker

logger = logging.getLogger(__name__)

DEFAULT_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]
DAILY_PNL_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "daily_pnl.json"


def _position_size(portfolio_value: float, confidence: float,
                   risk_pct: float = 2.0) -> float:
    """Calculate position size based on confidence and risk budget.

    Higher confidence = larger allocation, capped at risk_pct of portfolio.
    """
    # Base: risk_pct% of portfolio per trade
    base = portfolio_value * (risk_pct / 100)
    # Scale by confidence (0.4-1.0 range mapped to 0.5-1.0x)
    scale = 0.5 + confidence * 0.5
    size = base * scale
    # Clamp to $5 min, $100 max (safety limit)
    return max(5.0, min(size, 100.0))


def _check_stop_loss_take_profit(portfolio, strat):
    """Check all open positions for stop-loss or take-profit triggers.

    Returns list of forced sell actions taken.
    """
    positions = portfolio.get("positions", {})
    if isinstance(positions, list):
        pos_dict = {p.get("symbol"): p for p in positions}
    elif isinstance(positions, dict):
        pos_dict = positions
    else:
        return []

    sl_pct = strat.get("position_sizing", {}).get("stop_loss_pct", 5.0)
    tp_pct = strat.get("position_sizing", {}).get("take_profit_pct", 10.0)

    actions = []
    for symbol, pos in pos_dict.items():
        if not pos or pos.get("quantity", 0) <= 0:
            continue

        entry_price = pos.get("avg_price", 0)
        if entry_price <= 0:
            continue

        try:
            ticker = get_ticker(symbol)
            current_price = float(ticker.get("price", 0))
        except Exception as e:
            logger.warning(f"Could not get price for {symbol} stop-loss check: {e}")
            continue

        if current_price <= 0:
            continue

        pnl_pct = ((current_price / entry_price) - 1) * 100

        # Stop-loss: force sell if loss exceeds threshold
        if pnl_pct <= -sl_pct:
            reason = f"STOP-LOSS triggered at {pnl_pct:+.2f}% (threshold: -{sl_pct}%)"
            logger.warning(f"{symbol}: {reason}")
            try:
                sell_value = pos["quantity"] * current_price
                if sell_value > 1:
                    result = execute_paper_trade(symbol, "SELL", sell_value)
                    actions.append({
                        "symbol": symbol, "signal": "SELL", "reason": "stop_loss",
                        "pnl_pct": round(pnl_pct, 2), "executed": True,
                        "trade": result, "timestamp": datetime.now().isoformat(),
                    })
                    log_trade_learning(
                        symbol=symbol, action="SELL", outcome="stop_loss",
                        lesson=f"Stop-loss {symbol} @ ${current_price:.2f} "
                               f"(entry=${entry_price:.2f}, P&L={pnl_pct:+.2f}%)",
                    )
            except Exception as e:
                logger.error(f"Stop-loss sell failed for {symbol}: {e}")

        # Take-profit: force sell if gain exceeds threshold
        elif pnl_pct >= tp_pct:
            reason = f"TAKE-PROFIT triggered at {pnl_pct:+.2f}% (threshold: +{tp_pct}%)"
            logger.info(f"{symbol}: {reason}")
            try:
                sell_value = pos["quantity"] * current_price
                if sell_value > 1:
                    result = execute_paper_trade(symbol, "SELL", sell_value)
                    actions.append({
                        "symbol": symbol, "signal": "SELL", "reason": "take_profit",
                        "pnl_pct": round(pnl_pct, 2), "executed": True,
                        "trade": result, "timestamp": datetime.now().isoformat(),
                    })
                    log_trade_learning(
                        symbol=symbol, action="SELL", outcome="take_profit",
                        lesson=f"Take-profit {symbol} @ ${current_price:.2f} "
                               f"(entry=${entry_price:.2f}, P&L={pnl_pct:+.2f}%)",
                    )
            except Exception as e:
                logger.error(f"Take-profit sell failed for {symbol}: {e}")

    return actions


def _log_daily_pnl(portfolio):
    """Log daily portfolio value for consistency tracking."""
    today = date.today().isoformat()
    total_value = portfolio.get("total_value", 0)

    try:
        if DAILY_PNL_PATH.exists():
            data = json.loads(DAILY_PNL_PATH.read_text())
        else:
            data = []
    except Exception:
        data = []

    # Update today's entry or add new one
    existing = next((d for d in data if d["date"] == today), None)
    if existing:
        existing["value"] = round(total_value, 4)
        existing["updated"] = datetime.now().isoformat()
    else:
        entry = {
            "date": today,
            "value": round(total_value, 4),
            "cash": round(portfolio.get("cash", 0), 4),
            "positions": len(portfolio.get("positions", {})),
            "updated": datetime.now().isoformat(),
        }
        # Add daily change if we have previous data
        if data:
            prev_value = data[-1].get("value", total_value)
            entry["daily_pnl"] = round(total_value - prev_value, 4)
            entry["daily_pnl_pct"] = round(
                ((total_value / prev_value) - 1) * 100, 4) if prev_value > 0 else 0
        data.append(entry)

    DAILY_PNL_PATH.parent.mkdir(parents=True, exist_ok=True)
    DAILY_PNL_PATH.write_text(json.dumps(data, indent=2))


def check_and_trade(symbols=None, min_confidence: float = 0.5,
                    dry_run: bool = False,
                    auto_discover: bool = False) -> list:
    """Scan all symbols and execute trades when signals are strong.

    Args:
        symbols: List of symbols to scan (None = defaults or auto-discover)
        min_confidence: Minimum confidence to execute (0-1)
        dry_run: If True, generate signals but don't execute trades
        auto_discover: If True, dynamically find top pairs from Binance

    Returns:
        List of actions taken (signals + trade results)
    """
    if symbols is None:
        if auto_discover:
            discovered = discover_top_pairs(max_pairs=8)
            symbols = [p["symbol"] for p in discovered]
            logger.info(f"Auto-discovered pairs: {symbols}")
        else:
            symbols = DEFAULT_SYMBOLS

    strat = load_strategy()
    risk_pct = strat.get("position_sizing", {}).get("risk_per_trade_pct", 2.0)
    timeframe = strat.get("timeframe", "1h")

    # Get portfolio state
    try:
        portfolio = get_portfolio_summary()
        portfolio_value = portfolio.get("total_value", 100.0)
        cash = portfolio.get("cash", 0)
        open_positions = portfolio.get("positions", {})
        if isinstance(open_positions, list):
            held_symbols = {p.get("symbol") for p in open_positions}
        else:
            held_symbols = set(open_positions.keys()) if isinstance(open_positions, dict) else set()
    except Exception as e:
        logger.error(f"Failed to get portfolio: {e}")
        portfolio_value = 100.0
        cash = 0
        held_symbols = set()

    actions = []
    timestamp = datetime.now().isoformat()

    # Phase 2: Check stop-loss/take-profit on existing positions first
    if not dry_run and open_positions:
        sl_tp_actions = _check_stop_loss_take_profit(portfolio, strat)
        actions.extend(sl_tp_actions)
        # Update held_symbols after forced sells
        if sl_tp_actions:
            sold_symbols = {a["symbol"] for a in sl_tp_actions if a.get("executed")}
            held_symbols -= sold_symbols
            # Refresh cash after sells
            try:
                portfolio = get_portfolio_summary()
                cash = portfolio.get("cash", 0)
            except Exception:
                pass

    # Log daily P&L
    try:
        _log_daily_pnl(portfolio)
    except Exception as e:
        logger.debug(f"Daily P&L log failed: {e}")

    for symbol in symbols:
        try:
            sig = generate_signal(symbol, timeframe)
            action_entry = {
                "timestamp": timestamp,
                "symbol": symbol,
                "signal": sig["action"],
                "score": sig.get("ensemble_score", 0),
                "confidence": sig.get("confidence", 0),
                "price": sig.get("price", 0),
                "executed": False,
            }

            # Should we trade?
            should_buy = (sig["action"] == "BUY"
                          and sig.get("confidence", 0) >= min_confidence
                          and symbol not in held_symbols
                          and cash > 5)

            should_sell = (sig["action"] == "SELL"
                           and sig.get("confidence", 0) >= min_confidence
                           and symbol in held_symbols)

            if should_buy and not dry_run:
                size = _position_size(portfolio_value, sig["confidence"], risk_pct)
                size = min(size, cash * 0.9)  # Keep 10% cash reserve
                if size >= 5:
                    result = execute_paper_trade(symbol, "BUY", size)
                    action_entry["trade"] = result
                    action_entry["executed"] = True
                    action_entry["amount"] = round(size, 2)

                    if result.get("status") == "FILLED":
                        log_trade_learning(
                            symbol=symbol, action="BUY",
                            outcome="executed",
                            signals_used=sig.get("strategies"),
                            lesson=f"Auto BUY {symbol} @ ${sig['price']} "
                                   f"(score={sig['ensemble_score']:.3f}, "
                                   f"conf={sig['confidence']:.0%}): "
                                   + "; ".join(s.get("reason", "")
                                               for s in sig.get("strategies", {}).values()),
                        )

            elif should_sell and not dry_run:
                # Sell entire position
                pos = open_positions.get(symbol, {})
                if isinstance(pos, dict):
                    qty = pos.get("quantity", 0)
                    sell_value = qty * sig.get("price", 0)
                else:
                    sell_value = 50  # fallback
                if sell_value > 1:
                    result = execute_paper_trade(symbol, "SELL", sell_value)
                    action_entry["trade"] = result
                    action_entry["executed"] = True

                    if result.get("status") == "FILLED":
                        log_trade_learning(
                            symbol=symbol, action="SELL",
                            outcome="executed",
                            signals_used=sig.get("strategies"),
                            lesson=f"Auto SELL {symbol} @ ${sig['price']} "
                                   f"(score={sig['ensemble_score']:.3f}): "
                                   + "; ".join(s.get("reason", "")
                                               for s in sig.get("strategies", {}).values()),
                        )

            actions.append(action_entry)

        except Exception as e:
            logger.error(f"Error processing {symbol}: {e}")
            actions.append({"symbol": symbol, "error": str(e), "timestamp": timestamp})

    # Log scan summary
    executed = [a for a in actions if a.get("executed")]
    if executed:
        log_learning(
            category="trade",
            title=f"Auto-trade scan: {len(executed)} trades executed",
            detail=f"Scanned {len(symbols)} symbols, executed {len(executed)} trades",
            source="auto_trader",
            tags=["auto-trade", "scan"],
            data={"actions": [{"symbol": a["symbol"], "signal": a["signal"],
                               "amount": a.get("amount")} for a in executed]},
        )

    return actions


def run_loop(interval_seconds: int = 300, symbols=None,
             min_confidence: float = 0.5, max_iterations: int = 0,
             auto_discover: bool = False):
    """Run continuous trading loop.

    Args:
        interval_seconds: Seconds between scans (default 5 min)
        symbols: Symbols to scan (None = use defaults or auto-discover)
        min_confidence: Min confidence to trade
        max_iterations: Stop after N iterations (0 = infinite)
        auto_discover: If True, re-discover top pairs each scan
    """
    mode = "AUTO-DISCOVER" if auto_discover else "FIXED"
    print(f"Starting auto-trader loop (interval={interval_seconds}s, "
          f"min_conf={min_confidence:.0%}, mode={mode})")
    if not auto_discover:
        print(f"Symbols: {', '.join(symbols or DEFAULT_SYMBOLS)}")
    else:
        print("Pairs: auto-discovering top volume/momentum pairs each scan")
    print("-" * 60)

    iteration = 0
    while True:
        iteration += 1
        if max_iterations and iteration > max_iterations:
            print(f"Reached max iterations ({max_iterations}). Stopping.")
            break

        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Scan #{iteration}")
        try:
            actions = check_and_trade(symbols, min_confidence,
                                      auto_discover=auto_discover)
            for a in actions:
                status = ""
                if a.get("executed"):
                    trade = a.get("trade", {})
                    status = f" -> {trade.get('status', 'UNKNOWN')} ${a.get('amount', '?')}"
                elif a.get("error"):
                    status = f" -> ERROR: {a['error']}"
                print(f"  {a.get('symbol', '?')}: {a.get('signal', '?')} "
                      f"(score={a.get('score', 0):+.3f}, "
                      f"conf={a.get('confidence', 0):.0%}){status}")
        except Exception as e:
            print(f"  Scan error: {e}")

        if max_iterations and iteration >= max_iterations:
            break

        print(f"  Next scan in {interval_seconds}s...")
        time.sleep(interval_seconds)


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    interval = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    run_loop(interval_seconds=interval)
