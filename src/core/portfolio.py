"""Portfolio queries — reads persistent paper trading state."""

import logging
from datetime import datetime

from .state import load_state
from .market_data import get_ticker

logger = logging.getLogger(__name__)


def get_portfolio_summary() -> dict:
    """Get paper portfolio: cash, positions, total value, P&L, drawdown."""
    guard = load_state()

    # Calculate position values with current prices
    positions = []
    total_position_value = 0.0

    for symbol, pos in guard.paper_positions.items():
        qty = pos.get("quantity", 0)
        entry_price = pos.get("avg_price") or pos.get("entry_price") or 0
        if qty <= 0:
            continue

        # Get current price
        ticker = get_ticker(symbol)
        current_price = float(ticker.get("price") or entry_price or 0)
        market_value = qty * current_price
        cost_basis = qty * entry_price
        unrealized_pnl = market_value - cost_basis
        pnl_pct = ((current_price / entry_price) - 1) * 100 if entry_price > 0 else 0

        positions.append({
            "symbol": symbol,
            "quantity": round(qty, 8),
            "entry_price": round(entry_price, 2),
            "current_price": round(current_price, 2),
            "market_value": round(market_value, 2),
            "unrealized_pnl": round(unrealized_pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
        })
        total_position_value += market_value

    total_value = guard.paper_balance + total_position_value
    initial_balance = guard.config.paper_initial_balance
    total_pnl = total_value - initial_balance
    total_pnl_pct = ((total_value / initial_balance) - 1) * 100 if initial_balance > 0 else 0

    return {
        "cash_balance": round(guard.paper_balance, 2),
        "total_position_value": round(total_position_value, 2),
        "total_value": round(total_value, 2),
        "initial_balance": initial_balance,
        "total_pnl": round(total_pnl, 2),
        "total_pnl_pct": round(total_pnl_pct, 2),
        "positions": positions,
        "position_count": len(positions),
        "daily_trades": guard.daily_trade_count,
        "timestamp": datetime.now().isoformat(),
    }


def get_trade_history(limit: int = 20) -> list:
    """Get recent trades from persistent state."""
    guard = load_state()
    history = getattr(guard, "trade_history", [])
    # Most recent first
    return list(reversed(history[-limit:]))
