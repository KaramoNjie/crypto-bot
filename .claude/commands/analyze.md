Run a comprehensive market analysis for a cryptocurrency trading pair.

1. Execute the command:
   ```
   cd /home/amo/Documents/crypto-bot && python -m src.cli analyze $ARGUMENTS
   ```
   Default symbol is BTCUSDT if none provided.

2. Interpret the results:
   - **RSI**: Below 30 = oversold (potential buy), above 70 = overbought (potential sell)
   - **MACD Histogram**: Positive = bullish momentum, negative = bearish
   - **BB Position**: Near 0 = near lower band (oversold), near 1 = near upper band (overbought)
   - **Volume Ratio**: Above 1.5 = above-average volume (confirms price moves)
   - **Fear & Greed**: Below 25 = extreme fear (contrarian buy), above 75 = extreme greed (caution)

3. Provide a clear summary: bullish, bearish, or neutral with specific reasons from the data.
