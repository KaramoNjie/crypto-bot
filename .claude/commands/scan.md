# /scan — Multi-Coin Market Scanner

Scan multiple coins simultaneously and rank by signal strength. Use at the start
of each trading session to find the best setup.

## Default coins
BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT

## Steps

1. Run signals for all coins in parallel using the CLI:
   ```bash
   python -m src.cli signal BTCUSDT &
   python -m src.cli signal ETHUSDT &
   python -m src.cli signal SOLUSDT &
   python -m src.cli signal BNBUSDT &
   wait
   ```
   Or run them sequentially if parallel causes issues.

2. For each coin, extract and score:
   - RSI score: distance from 50 (closer to 30 = more bullish, closer to 70 = caution)
   - MACD score: histogram value (positive and rising = bullish)
   - BB score: position < 0.5 = near lower band (oversold opportunity)
   - Fear/Greed context (same for all coins)

3. Rank coins by composite signal strength (0-10 scale):
   - Score 8-10: Strong setup, worth trading
   - Score 5-7: Moderate, proceed with caution
   - Score 0-4: Weak or no setup

4. Present as a ranked table:

   | Rank | Symbol | Price | RSI | MACD Hist | BB Pos | Score | Signal |
   |------|--------|-------|-----|-----------|--------|-------|--------|
   | 1    | ...    | ...   | ... | ...       | ...    | ...   | BUY/SELL/HOLD |

5. Recommend the top 1-2 coins to trade with reasoning.
   - Consider diversification (don't always pick BTC if ETH has a better setup)
   - Note any coins to avoid and why

6. Suggest position sizes scaled to $100 account (30% max per position = $30).
