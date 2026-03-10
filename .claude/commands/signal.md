Generate a trading signal for a cryptocurrency pair with full analysis and risk assessment.

1. Execute:
   ```
   cd /home/amo/Documents/crypto-bot && python -m src.cli signal $ARGUMENTS
   ```
   Default symbol is BTCUSDT if none provided.

2. Interpret the data and give a clear BUY / SELL / HOLD recommendation with:
   - Confidence level (low/medium/high)
   - Key reasons from RSI, MACD, Bollinger Bands, news sentiment
   - Suggested entry price, stop loss, and take profit levels
   - Whether this aligns with Fear & Greed context
