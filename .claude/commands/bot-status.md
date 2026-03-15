Check the health status of all bot systems and API connections.

1. Check system status:
   ```
   cd /home/amo/Documents/crypto-bot && python -m src.cli status
   ```

2. Also check trading mode:
   ```
   cd /home/amo/Documents/crypto-bot && python -m src.cli trading-mode
   ```

Report on:
- Binance API connectivity and current BTC price
- News API and Fear & Greed availability
- Current trading mode (paper/live) and wallet balances
- Paper trading safety guard status
- Any issues or warnings
