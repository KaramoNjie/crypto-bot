"""Persistent trading state backed by JSON files.

Each CLI invocation: load_state() -> do work -> save_state().
Uses simple JSON files rather than full SQLAlchemy to keep CLI fast.

Supports separate state files for paper and live modes:
  - data/paper_state.json  — paper trading wallet
  - data/live_state.json   — live trading wallet (separate balance)
  - data/trading_mode.json — which mode is active
"""

import json
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..safety.paper_trading import PaperTradingSafetyGuard, SafetyConfig, TradingMode

logger = logging.getLogger(__name__)

STATE_DIR = Path(__file__).resolve().parent.parent.parent / "data"
PAPER_STATE_FILE = STATE_DIR / "paper_state.json"
LIVE_STATE_FILE = STATE_DIR / "live_state.json"
MODE_FILE = STATE_DIR / "trading_mode.json"

# Back-compat alias
STATE_FILE = PAPER_STATE_FILE


def _ensure_dir():
    STATE_DIR.mkdir(parents=True, exist_ok=True)


def _state_file_for_mode(mode: str) -> Path:
    if mode == "live":
        return LIVE_STATE_FILE
    return PAPER_STATE_FILE


# ---------------------------------------------------------------------------
# Trading mode persistence
# ---------------------------------------------------------------------------

def get_trading_mode() -> str:
    """Return current trading mode: 'paper' or 'live'."""
    if MODE_FILE.exists():
        try:
            data = json.loads(MODE_FILE.read_text())
            return data.get("mode", "paper")
        except Exception:
            pass
    return "paper"


def set_trading_mode(mode: str) -> dict:
    """Switch trading mode. Returns previous and new mode."""
    if mode not in ("paper", "live"):
        raise ValueError(f"Invalid mode: {mode}. Must be 'paper' or 'live'.")
    _ensure_dir()
    prev = get_trading_mode()
    data = {
        "mode": mode,
        "switched_at": datetime.now().isoformat(),
        "previous_mode": prev,
    }
    MODE_FILE.write_text(json.dumps(data, indent=2))
    logger.info(f"Trading mode switched: {prev} -> {mode}")
    return {"previous": prev, "current": mode}


# ---------------------------------------------------------------------------
# State load / save (mode-aware)
# ---------------------------------------------------------------------------

def save_state(guard: PaperTradingSafetyGuard, mode: str = None) -> None:
    """Persist portfolio to disk for the given mode."""
    _ensure_dir()
    if mode is None:
        mode = get_trading_mode()
    state_file = _state_file_for_mode(mode)
    state = {
        "paper_balance": guard.paper_balance,
        "paper_positions": guard.paper_positions,
        "daily_trade_count": guard.daily_trade_count,
        "last_trade_date": str(guard.last_trade_date),
        "trade_history": getattr(guard, "trade_history", []),
        "mode": mode,
        "saved_at": datetime.now().isoformat(),
    }
    try:
        # Atomic write: write to temp file, then rename (prevents corruption on crash)
        data = json.dumps(state, indent=2, default=str)
        fd, tmp_path = tempfile.mkstemp(dir=STATE_DIR, suffix=".tmp")
        try:
            os.write(fd, data.encode())
            os.fsync(fd)
            os.close(fd)
            os.replace(tmp_path, str(state_file))
        except Exception:
            try:
                os.close(fd)
            except OSError:
                pass
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise
        logger.debug(f"{mode.upper()} state saved: balance=${guard.paper_balance:.2f}")
    except Exception as e:
        logger.error(f"Failed to save {mode} state: {e}")


def load_state(mode: str = None) -> PaperTradingSafetyGuard:
    """Load portfolio from disk for the given mode, or create fresh one."""
    if mode is None:
        mode = get_trading_mode()
    trading_mode = TradingMode.LIVE if mode == "live" else TradingMode.PAPER
    config = SafetyConfig(trading_mode=trading_mode)
    guard = PaperTradingSafetyGuard(config)

    state_file = _state_file_for_mode(mode)
    if state_file.exists():
        try:
            state = json.loads(state_file.read_text())
            guard.paper_balance = state.get("paper_balance", config.paper_initial_balance)
            guard.paper_positions = state.get("paper_positions", {})
            guard.daily_trade_count = state.get("daily_trade_count", 0)
            guard.trade_history = state.get("trade_history", [])
            logger.debug(f"{mode.upper()} state loaded: balance=${guard.paper_balance:.2f}, "
                         f"{len(guard.paper_positions)} positions")
        except Exception as e:
            logger.warning(f"Failed to load {mode} state, using fresh: {e}")

    return guard


def reset_state(mode: str = None) -> PaperTradingSafetyGuard:
    """Reset trading state to initial for the given mode."""
    if mode is None:
        mode = get_trading_mode()
    state_file = _state_file_for_mode(mode)
    if state_file.exists():
        state_file.unlink()
    guard = load_state(mode)
    save_state(guard, mode)
    return guard
