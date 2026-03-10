---
name: bot-status
description: Check system health including API connections and configuration
user-invocable: true
allowed-tools: Bash, Read
---

# System Status Check

Check the health of all trading bot components.

## Steps

1. Run:
   ```
   cd /home/amo/Documents/crypto-bot && python -m src.cli status
   ```

2. Report on each component:
   - Binance API: connected/error
   - Fear & Greed API: connected/error
   - Paper trading mode: enabled/disabled
   - API keys: configured/missing

3. Flag any issues that need attention.
