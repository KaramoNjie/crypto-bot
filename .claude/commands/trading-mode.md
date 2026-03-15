Show or switch trading mode (paper/live). Each mode has its own separate wallet.

If no argument given, show current mode and both wallet balances:
```
cd /home/amo/Documents/crypto-bot && python -m src.cli trading-mode
```

If the user wants to switch:
```
cd /home/amo/Documents/crypto-bot && python -m src.cli trading-mode $ARGUMENTS
```

Arguments: `paper` or `live`

IMPORTANT:
- Switching to LIVE requires confirmation — always warn the user
- PAPER mode is the default and safe for testing
- Each mode has its own wallet with its own $100 balance
- Trades in one mode do NOT affect the other
