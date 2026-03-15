# /scan — Multi-Coin Market Scanner

Scan multiple coins using the 7-strategy ensemble engine and rank by signal strength.
Use at the start of each trading session to find the best setup.

## Default coins
BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT

## Steps

1. Run the ensemble signal scanner:
   ```bash
   cd /home/amo/Documents/crypto-bot && python -m src.cli signals
   ```
   This scans all coins through the 7-strategy ensemble (VWAP, RSI, MACD, BB, Momentum, EMA, Volume).

   For auto-discovering top pairs by volume/momentum:
   ```bash
   cd /home/amo/Documents/crypto-bot && python -m src.cli signals --discover
   ```

2. Also check trading mode and portfolio:
   ```bash
   cd /home/amo/Documents/crypto-bot && python -m src.cli trading-mode
   cd /home/amo/Documents/crypto-bot && python -m src.cli portfolio
   ```

3. Present results as a ranked table showing:
   - Each coin's ensemble score and confidence
   - Per-strategy breakdown (VWAP, RSI, MACD, BB, EMA, Volume)
   - BUY / SELL / HOLD action

4. Recommend the top 1-2 coins to trade with reasoning.
   - Consider diversification
   - Note current mode (paper/live)
   - Account for stop-loss (-5%) and take-profit (+10%) levels

5. Suggest position sizes scaled to portfolio (max $100 per trade, keep 10% cash reserve).
