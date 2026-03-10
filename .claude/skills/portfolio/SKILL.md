---
name: portfolio
description: View paper trading portfolio summary with positions and P&L
user-invocable: true
allowed-tools: Bash, Read
---

# Portfolio Summary

Show the current paper trading portfolio.

## Steps

1. Run:
   ```
   cd /home/amo/Documents/crypto-bot && python -m src.cli portfolio
   ```

2. Present the results clearly:
   - Total value and P&L
   - Cash balance available
   - Each position with entry price, current price, and unrealized P&L
   - Any warnings about concentration or drawdown
