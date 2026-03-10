---
name: risk
description: Run risk assessment with volatility, VaR, and position sizing
user-invocable: true
argument-hint: "[SYMBOL]"
allowed-tools: Bash, Read
---

# Risk Assessment

Analyze risk for a cryptocurrency trading pair.

## Steps

1. Run:
   ```
   cd /home/amo/Documents/crypto-bot && python -m src.cli risk $ARGUMENTS
   ```
   Default symbol is BTCUSDT if none provided.

2. Explain the risk metrics:
   - **Risk Level**: Classification based on daily volatility
   - **Daily/Annual Volatility**: How much price typically moves
   - **VaR (95%, 1-day)**: Maximum expected loss at 95% confidence
   - **Position Sizing**: How much to risk based on 2% portfolio risk rule
   - **Stop Loss / Take Profit**: Volatility-adjusted levels
   - **Fear & Greed**: Current market sentiment context

3. If risk is HIGH or VERY_HIGH, explicitly warn the user.
