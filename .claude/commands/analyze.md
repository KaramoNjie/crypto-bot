Run a comprehensive market analysis for a cryptocurrency trading pair.

1. Execute the command:
   ```
   cd /home/amo/Documents/crypto-bot && python -m src.cli analyze $ARGUMENTS
   ```
   Default symbol is BTCUSDT if none provided.

2. Interpret the results using all 7 strategies the ensemble engine tracks:
   - **VWAP** (25% weight): Price vs Volume-Weighted Average Price — below = undervalued
   - **RSI** (20%): Below 30 = oversold (buy), above 70 = overbought (sell)
   - **MACD** (15%): Positive histogram = bullish momentum, negative = bearish
   - **Bollinger Bands** (15%): Near lower band = oversold, near upper = overbought, squeeze = breakout coming
   - **Momentum** (10%): Breaking N-period highs with volume = strong trend
   - **EMA Cross** (10%): 9 EMA above 21 EMA = bullish trend
   - **Volume** (5%): Above 1.5x average = confirms price moves
   - **Fear & Greed**: Below 25 = extreme fear (contrarian buy), above 75 = extreme greed (caution)

3. Provide a clear summary: bullish, bearish, or neutral with specific reasons from the data.
