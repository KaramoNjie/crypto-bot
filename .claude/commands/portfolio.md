Show the portfolio summary for the current trading mode (paper or live).

1. Check current mode:
   ```
   cd /home/amo/Documents/crypto-bot && python -m src.cli trading-mode
   ```

2. Show portfolio:
   ```
   cd /home/amo/Documents/crypto-bot && python -m src.cli portfolio
   ```

3. Summarize:
   - Current mode (PAPER or LIVE) and which wallet is active
   - Total portfolio value and overall P&L
   - Each open position: entry vs current price, unrealized gain/loss
   - Cash available for new trades
   - Stop-loss (-5%) and take-profit (+10%) status on any open positions
