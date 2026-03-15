Execute a trade. Arguments: BUY|SELL SYMBOL AMOUNT (e.g. BUY BTCUSDT 25)

Uses the current trading mode (paper or live). Check mode with `/trading-mode`.

IMPORTANT: Always confirm with the user before executing. Show them what will happen first.

1. Check current trading mode:
   ```
   cd /home/amo/Documents/crypto-bot && python -m src.cli trading-mode
   ```
2. Show the user the proposed trade and current mode, ask for confirmation.
3. After confirmation, execute:
   ```
   cd /home/amo/Documents/crypto-bot && python -m src.cli trade $ARGUMENTS
   ```
   To force live mode for a single trade, add `--live`:
   ```
   cd /home/amo/Documents/crypto-bot && python -m src.cli trade $ARGUMENTS --live
   ```
4. Show the result and updated portfolio summary:
   ```
   cd /home/amo/Documents/crypto-bot && python -m src.cli portfolio
   ```
