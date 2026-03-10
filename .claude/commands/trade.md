Execute a paper trade. Arguments: BUY|SELL SYMBOL AMOUNT (e.g. BUY BTCUSDT 100)

IMPORTANT: Always confirm with the user before executing. Show them what will happen first.

1. Show the user the proposed trade and ask for confirmation.
2. After confirmation, execute:
   ```
   cd /home/amo/Documents/crypto-bot && python -m src.cli trade $ARGUMENTS
   ```
3. Show the result and updated portfolio summary:
   ```
   cd /home/amo/Documents/crypto-bot && python -m src.cli portfolio
   ```
