---
name: signal
description: Generate a trading signal with confidence score and risk assessment
user-invocable: true
argument-hint: "[SYMBOL]"
allowed-tools: Bash, Read
---

# Trading Signal Generation

Generate a trading signal by combining analysis and risk data.

## Steps

1. Run the signal CLI command:
   ```
   cd /home/amo/Documents/crypto-bot && python -m src.cli signal $ARGUMENTS
   ```
   Default symbol is BTCUSDT if none provided.

2. Based on the combined analysis and risk data, provide:
   - **Direction**: BUY, SELL, or HOLD
   - **Confidence**: Low / Medium / High with reasoning
   - **Position size**: From the risk assessment
   - **Stop loss and take profit levels**
   - **Key risks** to monitor

3. Be specific about WHY. Reference the actual indicator values.

4. All recommendations are for PAPER TRADING only. Never suggest real money trades.
