Generate a trading signal for a cryptocurrency pair using the 7-strategy ensemble engine.

1. Execute:
   ```
   cd /home/amo/Documents/crypto-bot && python -m src.cli signal $ARGUMENTS
   ```
   Default symbol is BTCUSDT if none provided.

2. Interpret the data and give a clear BUY / SELL / HOLD recommendation with:
   - Confidence level (low/medium/high) based on ensemble score
   - Per-strategy breakdown: which of the 7 strategies agree (VWAP, RSI, MACD, BB, Momentum, EMA, Volume)
   - Suggested entry price, stop loss (-5% default), and take profit (+10% default) levels
   - Whether this aligns with Fear & Greed context

3. Note the current trading mode (paper/live) — check with:
   ```
   cd /home/amo/Documents/crypto-bot && python -m src.cli trading-mode
   ```
