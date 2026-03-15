"""Trade outcome feedback — logs entry/exit and scores active strategy params.

Stores outcomes in data/trade_outcomes.json.
Used by eval_harness.py to apply a live performance adjustment to EVAL_SCORE.
"""

import json
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
OUTCOMES_FILE = DATA_DIR / "trade_outcomes.json"


def _load_outcomes() -> list:
    if not OUTCOMES_FILE.exists():
        return []
    try:
        return json.loads(OUTCOMES_FILE.read_text())
    except Exception as e:
        logger.warning(f"Could not load trade_outcomes.json: {e}")
        return []


def _save_outcomes(outcomes: list) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    try:
        data = json.dumps(outcomes, indent=2, default=str)
        fd, tmp_path = tempfile.mkstemp(dir=DATA_DIR, suffix=".tmp")
        try:
            os.write(fd, data.encode())
            os.fsync(fd)
            os.close(fd)
            os.replace(tmp_path, str(OUTCOMES_FILE))
        except Exception:
            try:
                os.close(fd)
            except OSError:
                pass
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise
    except Exception as e:
        logger.error(f"Could not save trade_outcomes.json: {e}")


def _load_strategy_snapshot() -> dict:
    """Snapshot current RSI params from config/strategy.yaml."""
    try:
        import yaml
        path = Path(__file__).resolve().parent.parent.parent / "config" / "strategy.yaml"
        with open(path) as f:
            cfg = yaml.safe_load(f)
        rsi = cfg.get("indicators", {}).get("rsi", {})
        return {
            "rsi_period": rsi.get("period", 14),
            "oversold": rsi.get("oversold", 30),
            "overbought": rsi.get("overbought", 70),
            "timeframe": cfg.get("timeframe", "1h"),
        }
    except Exception as e:
        logger.warning(f"Could not load strategy snapshot: {e}")
        return {"rsi_period": 14, "oversold": 30, "overbought": 70, "timeframe": "1h"}


def log_trade_entry(order_id: str, symbol: str, quantity: float, price: float) -> None:
    """Record a BUY with the active strategy params. Call after a FILLED BUY."""
    outcomes = _load_outcomes()
    outcomes.append({
        "order_id": order_id,
        "symbol": symbol,
        "side": "BUY",
        "entry_price": price,
        "quantity": quantity,
        "strategy": _load_strategy_snapshot(),
        "timestamp_entry": datetime.now().isoformat(),
        "status": "open",
        "exit_price": None,
        "pnl_pct": None,
        "timestamp_exit": None,
    })
    _save_outcomes(outcomes)
    logger.debug(f"Feedback: entry logged {symbol} @ {price}")


def log_trade_exit(symbol: str, exit_price: float, quantity: float,
                   order_id: str = None) -> None:
    """Match open BUY for symbol by order_id (or closest quantity), compute P&L, mark closed."""
    outcomes = _load_outcomes()
    best_match = None

    for trade in outcomes:
        if (trade.get("symbol") == symbol
                and trade.get("side") == "BUY"
                and trade.get("status") == "open"):
            # Prefer exact order_id match
            if order_id and trade.get("order_id") == order_id:
                best_match = trade
                break
            # Otherwise match by closest quantity
            if best_match is None:
                best_match = trade
            elif abs(trade.get("quantity", 0) - quantity) < abs(best_match.get("quantity", 0) - quantity):
                best_match = trade

    if best_match:
        best_match["exit_price"] = exit_price
        best_match["timestamp_exit"] = datetime.now().isoformat()
        best_match["status"] = "closed"
        entry = best_match.get("entry_price", 0)
        if entry and entry > 0:
            pnl_pct = ((exit_price / entry) - 1) * 100
            best_match["pnl_pct"] = round(pnl_pct, 4)
            logger.debug(f"Feedback: exit logged {symbol} pnl={pnl_pct:+.2f}%")
        else:
            best_match["pnl_pct"] = None
            logger.warning(f"Feedback: exit logged {symbol} but entry_price was 0")

    _save_outcomes(outcomes)


def get_live_stats() -> dict:
    """Return live trade stats from closed outcomes."""
    closed = [t for t in _load_outcomes() if t.get("status") == "closed"
              and t.get("pnl_pct") is not None]
    if not closed:
        return {"closed_trades": 0, "win_rate": None, "avg_pnl": None}
    wins = sum(1 for t in closed if t["pnl_pct"] > 0)
    return {
        "closed_trades": len(closed),
        "win_rate": round(wins / len(closed), 4),
        "avg_pnl": round(sum(t["pnl_pct"] for t in closed) / len(closed), 4),
    }


def get_feedback_score(base_score: float) -> float:
    """Apply live win rate adjustment to base_score.

    Adjustment = base_score * (1 + (win_rate - 0.5) * 0.2)
    Max ±10%. Only applied with ≥3 closed trades.
    """
    stats = get_live_stats()
    if stats["closed_trades"] < 3 or stats["win_rate"] is None:
        return base_score
    feedback_factor = (stats["win_rate"] - 0.5) * 0.2
    adjusted = round(base_score * (1 + feedback_factor), 4)
    logger.debug(f"Feedback: {stats['closed_trades']} trades, "
                 f"win_rate={stats['win_rate']:.0%}, "
                 f"score {base_score:.4f} → {adjusted:.4f}")
    return adjusted
