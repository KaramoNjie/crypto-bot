"""Singleton config and client helpers for CLI / MCP / skills."""

import os
import functools
from ..config.settings import Config
from ..apis.binance_client import BinanceClient

_STRATEGY_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "config", "strategy.yaml")

_STRATEGY_DEFAULTS = {
    "indicators": {
        "rsi": {"period": 14, "overbought": 70, "oversold": 30},
        "macd": {"fast": 12, "slow": 26, "signal": 9},
        "bollinger": {"period": 20, "std": 2.0},
        "sma_fast": 20,
        "sma_slow": 50,
        "volume_lookback": 20,
    },
    "signal": {"min_confidence": 0.6, "volume_filter": True, "volume_multiplier": 1.5},
    "position_sizing": {
        "risk_per_trade_pct": 2.0,
        "stop_loss_vol_mult": 2.0,
        "take_profit_vol_mult": 4.0,
    },
    "timeframe": "1h",
}


def load_strategy() -> dict:
    """Load strategy params from config/strategy.yaml, falling back to defaults."""
    try:
        import yaml
        path = os.path.abspath(_STRATEGY_PATH)
        if os.path.exists(path):
            with open(path) as f:
                return yaml.safe_load(f) or _STRATEGY_DEFAULTS
    except Exception:
        pass
    return _STRATEGY_DEFAULTS

_config = None
_binance_client = None


def get_config() -> Config:
    """Get or create the singleton Config instance."""
    global _config
    if _config is None:
        _config = Config()
    return _config


def get_binance_client() -> BinanceClient:
    """Get or create the singleton BinanceClient instance."""
    global _binance_client
    if _binance_client is None:
        _binance_client = BinanceClient(get_config())
    return _binance_client


def reset():
    """Reset singletons (for testing)."""
    global _config, _binance_client
    _config = None
    _binance_client = None
