"""Paper trade execution with safety checks."""

import logging
import math
from datetime import datetime

from .config import get_binance_client
from .state import load_state, save_state
from .market_data import get_ticker
from .feedback import log_trade_entry, log_trade_exit

logger = logging.getLogger(__name__)


def _price_decimals(price: float) -> int:
    """Dynamic precision: 2 decimals for BTC-size, up to 8 for micro-cap."""
    if price <= 0:
        return 2
    return max(2, min(8, -int(math.floor(math.log10(price))) + 2))


def execute_paper_trade(symbol: str, side: str, amount_usdt: float) -> dict:
    """Execute a paper trade.

    Args:
        symbol: Trading pair e.g. "BTCUSDT"
        side: "BUY" or "SELL"
        amount_usdt: Dollar amount to trade

    Returns:
        dict with order result or rejection reason
    """
    side = side.upper()
    if side not in ("BUY", "SELL"):
        return {"status": "REJECTED", "error": f"Invalid side: {side}. Must be BUY or SELL."}

    if amount_usdt <= 0:
        return {"status": "REJECTED", "error": "Amount must be positive."}

    # Get current price
    ticker = get_ticker(symbol)
    if "error" in ticker:
        return {"status": "REJECTED", "error": f"Cannot get price: {ticker['error']}"}

    price = float(ticker["price"])
    if price <= 0:
        return {"status": "REJECTED", "error": f"Invalid price: {price}"}

    quantity = amount_usdt / price

    # Load persistent state
    guard = load_state()

    # Safety validation
    safety = guard.validate_order_safety(symbol, side, quantity, price)
    if not safety["safe"]:
        return {
            "status": "REJECTED",
            "reasons": safety["reasons"],
            "warnings": safety.get("warnings", []),
        }

    # Execute paper order
    try:
        result = guard.execute_paper_order(symbol, side, quantity, price)
        order_dict = result.to_dict()

        # Record in trade history
        if not hasattr(guard, "trade_history"):
            guard.trade_history = []
        guard.trade_history.append({
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "price": price,
            "amount_usdt": amount_usdt,
            "order_id": order_dict.get("orderId", ""),
            "fees": order_dict.get("fees", "0"),
            "timestamp": datetime.now().isoformat(),
        })

        # Persist updated state
        save_state(guard)

        # Feedback loop — log entry/exit for strategy learning
        price_dec = _price_decimals(price)
        try:
            if side == "BUY":
                log_trade_entry(
                    order_id=order_dict.get("orderId", ""),
                    symbol=symbol,
                    quantity=round(quantity, 8),
                    price=round(price, price_dec),
                )
            elif side == "SELL":
                log_trade_exit(
                    symbol=symbol,
                    exit_price=round(price, price_dec),
                    quantity=round(quantity, 8),
                )
        except Exception as fb_err:
            logger.warning(f"Feedback logging failed (non-fatal): {fb_err}")

        return {
            "status": "FILLED",
            "symbol": symbol,
            "side": side,
            "quantity": round(quantity, 8),
            "price": round(price, price_dec),
            "amount_usdt": round(amount_usdt, 2),
            "fees": order_dict.get("fees", "0"),
            "slippage": order_dict.get("slippage", 0),
            "order_id": order_dict.get("orderId", ""),
            "balance_after": round(guard.paper_balance, 2),
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Paper trade execution failed: {e}")
        return {"status": "ERROR", "error": str(e)}
