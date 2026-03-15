Show recent trade history for the current trading mode.

1. Check current mode:
   ```
   cd /home/amo/Documents/crypto-bot && python -m src.cli trading-mode
   ```

2. Show trades:
   ```
   cd /home/amo/Documents/crypto-bot && python -m src.cli history
   ```

Summarize:
- Current mode (PAPER or LIVE)
- Total trades, wins vs losses, average trade size
- Any stop-loss or take-profit triggers that fired
- Overall P&L from completed trades
