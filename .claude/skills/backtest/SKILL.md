---
name: backtest
description: Run a simple RSI backtest over historical data
user-invocable: true
argument-hint: "<SYMBOL> [DAYS]"
allowed-tools: Bash, Read
---

# Backtest

Run a simple RSI mean-reversion backtest.

## Steps

1. Parse arguments: SYMBOL and optionally DAYS (default 30)
   Example: `/backtest BTCUSDT 60`

2. Run:
   ```
   cd /home/amo/Documents/crypto-bot && python -m src.cli backtest <SYMBOL> --days <DAYS>
   ```

3. Interpret results:
   - Compare strategy return vs buy-and-hold
   - Note max drawdown as a risk indicator
   - Win rate context (above 50% is decent for mean reversion)
   - Note this is a simple backtest — real performance may differ
