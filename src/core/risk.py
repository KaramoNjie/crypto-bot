"""Risk assessment — wraps technical analysis into risk metrics."""

import logging
import numpy as np
from datetime import datetime

from .market_data import get_klines, get_ticker, get_fear_greed
from .analysis import technical_analysis

logger = logging.getLogger(__name__)


def assess_risk(symbol: str) -> dict:
    """Run risk assessment for a symbol.

    Returns volatility, position sizing recommendation, risk level,
    and key levels (support/resistance).
    """
    try:
        # Get price data
        klines = get_klines(symbol, "1h", 100)
        if not klines:
            return {"symbol": symbol, "error": "No price data available"}

        closes = np.array([float(k[4]) for k in klines])
        ticker = get_ticker(symbol)
        current_price = float(ticker.get("price", closes[-1]))

        # Volatility (annualized from hourly returns)
        returns = np.diff(np.log(closes))
        hourly_vol = float(np.std(returns)) if len(returns) > 1 else 0
        daily_vol = hourly_vol * np.sqrt(24)
        annual_vol = daily_vol * np.sqrt(365)

        # Risk level classification
        if daily_vol > 0.05:
            risk_level = "VERY_HIGH"
        elif daily_vol > 0.03:
            risk_level = "HIGH"
        elif daily_vol > 0.015:
            risk_level = "MODERATE"
        elif daily_vol > 0.008:
            risk_level = "LOW"
        else:
            risk_level = "VERY_LOW"

        # Position sizing (risk 2% of $10K portfolio per trade)
        portfolio_value = 10000.0
        risk_per_trade = 0.02
        risk_amount = portfolio_value * risk_per_trade
        # Stop loss at 2x daily volatility
        stop_distance_pct = daily_vol * 2
        stop_loss_price = current_price * (1 - stop_distance_pct)
        take_profit_price = current_price * (1 + stop_distance_pct * 2)  # 2:1 R/R

        if stop_distance_pct > 0:
            position_size_usd = risk_amount / stop_distance_pct
            position_size_usd = min(position_size_usd, portfolio_value * 0.1)  # Max 10%
        else:
            position_size_usd = portfolio_value * 0.05  # Default 5%

        # Simple VaR (95% confidence, 1-day)
        if len(returns) > 10:
            var_95 = float(np.percentile(returns, 5)) * current_price
        else:
            var_95 = None

        # Support/resistance from recent highs/lows
        highs = np.array([float(k[2]) for k in klines])
        lows = np.array([float(k[3]) for k in klines])
        recent_high = float(np.max(highs[-24:])) if len(highs) >= 24 else None
        recent_low = float(np.min(lows[-24:])) if len(lows) >= 24 else None

        # Get technicals for signal context
        tech = technical_analysis(symbol)
        rsi = tech.get("rsi")

        # Fear & Greed for macro context
        fg = get_fear_greed()

        return {
            "symbol": symbol,
            "current_price": round(current_price, 2),
            "risk_level": risk_level,
            "volatility": {
                "hourly": round(hourly_vol * 100, 3),
                "daily": round(daily_vol * 100, 2),
                "annualized": round(annual_vol * 100, 1),
            },
            "position_sizing": {
                "recommended_usd": round(position_size_usd, 2),
                "recommended_pct": round((position_size_usd / portfolio_value) * 100, 1),
                "stop_loss": round(stop_loss_price, 2),
                "take_profit": round(take_profit_price, 2),
                "risk_reward_ratio": "1:2",
            },
            "var_95_1day": round(var_95, 2) if var_95 else None,
            "key_levels": {
                "resistance_24h": round(recent_high, 2) if recent_high else None,
                "support_24h": round(recent_low, 2) if recent_low else None,
            },
            "rsi": rsi,
            "fear_greed": fg.get("value"),
            "fear_greed_label": fg.get("classification"),
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"assess_risk({symbol}) failed: {e}")
        return {"symbol": symbol, "error": str(e)}
