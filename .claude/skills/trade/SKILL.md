---
name: trade
description: Execute a paper trade with safety checks
user-invocable: true
argument-hint: "<SIDE> <SYMBOL> <AMOUNT_USDT>"
allowed-tools: Bash, Read
---

# Paper Trade Execution

Execute a paper trade through the safety-checked trading system.

## CRITICAL: Always confirm before executing

1. Parse the arguments: SIDE (BUY/SELL), SYMBOL, AMOUNT in USDT
   Example: `/trade BUY BTCUSDT 100`

2. **Before executing**, show the user what will happen and ASK for confirmation:
   - Symbol and direction
   - Amount in USDT
   - Current price (run `cd /home/amo/Documents/crypto-bot && python -m src.cli status` to check)

3. Only after user confirms, execute:
   ```
   cd /home/amo/Documents/crypto-bot && python -m src.cli trade <SIDE> <SYMBOL> <AMOUNT>
   ```

4. After execution, show the portfolio:
   ```
   cd /home/amo/Documents/crypto-bot && python -m src.cli portfolio
   ```

5. This is PAPER TRADING only. No real money is involved. Max order size is $1000.
