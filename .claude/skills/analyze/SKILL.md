---
name: analyze
description: Run full market analysis with technicals, news, and sentiment for a cryptocurrency
user-invocable: true
argument-hint: "[SYMBOL]"
allowed-tools: Bash, Read
---

# Market Analysis

Run a comprehensive analysis for a cryptocurrency trading pair.

## Steps

1. Run the analysis CLI command:
   ```
   cd /home/amo/Documents/crypto-bot && python -m src.cli analyze $ARGUMENTS
   ```
   Default symbol is BTCUSDT if none provided.

2. Interpret the results for the user:
   - **RSI**: Below 30 = oversold (potential buy), above 70 = overbought (potential sell)
   - **MACD**: Positive histogram = bullish momentum, negative = bearish
   - **Bollinger Bands**: BB Position near 0 = near lower band (oversold), near 1 = near upper band (overbought)
   - **Volume Ratio**: Above 1.5 = above-average volume (confirms moves)
   - **Fear & Greed**: Below 25 = extreme fear (contrarian buy signal), above 75 = extreme greed (caution)

3. Provide a clear summary: bullish, bearish, or neutral with key reasons.
