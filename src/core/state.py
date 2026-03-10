"""Persistent paper trading state backed by JSON file.

Each CLI invocation: load_state() -> do work -> save_state().
Uses a simple JSON file rather than full SQLAlchemy to keep CLI fast.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..safety.paper_trading import PaperTradingSafetyGuard, SafetyConfig, TradingMode

logger = logging.getLogger(__name__)

STATE_DIR = Path(__file__).resolve().parent.parent.parent / "data"
STATE_FILE = STATE_DIR / "paper_state.json"


def _ensure_dir():
    STATE_DIR.mkdir(parents=True, exist_ok=True)


def save_state(guard: PaperTradingSafetyGuard) -> None:
    """Persist paper portfolio to disk."""
    _ensure_dir()
    state = {
        "paper_balance": guard.paper_balance,
        "paper_positions": guard.paper_positions,
        "daily_trade_count": guard.daily_trade_count,
        "last_trade_date": str(guard.last_trade_date),
        "trade_history": getattr(guard, "trade_history", []),
        "saved_at": datetime.now().isoformat(),
    }
    try:
        STATE_FILE.write_text(json.dumps(state, indent=2, default=str))
        logger.debug(f"Paper state saved: balance=${guard.paper_balance:.2f}")
    except Exception as e:
        logger.error(f"Failed to save paper state: {e}")


def load_state() -> PaperTradingSafetyGuard:
    """Load paper portfolio from disk, or create fresh one."""
    config = SafetyConfig(trading_mode=TradingMode.PAPER)
    guard = PaperTradingSafetyGuard(config)

    if STATE_FILE.exists():
        try:
            state = json.loads(STATE_FILE.read_text())
            guard.paper_balance = state.get("paper_balance", config.paper_initial_balance)
            guard.paper_positions = state.get("paper_positions", {})
            guard.daily_trade_count = state.get("daily_trade_count", 0)
            guard.trade_history = state.get("trade_history", [])
            logger.debug(f"Paper state loaded: balance=${guard.paper_balance:.2f}, {len(guard.paper_positions)} positions")
        except Exception as e:
            logger.warning(f"Failed to load paper state, using fresh: {e}")

    return guard


def reset_state() -> PaperTradingSafetyGuard:
    """Reset paper trading to initial state."""
    if STATE_FILE.exists():
        STATE_FILE.unlink()
    guard = load_state()
    save_state(guard)
    return guard
