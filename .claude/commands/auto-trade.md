Start the autonomous trading loop. Claude scans markets every 5 minutes and trades automatically when signals are strong enough.

## Default (paper mode, runs until stopped):
```
cd /home/amo/Documents/crypto-bot && python -m src.cli auto-trade
```

## Options:
- Dry run (signals only, no trades): `python -m src.cli auto-trade --dry-run`
- Set number of scans: `python -m src.cli auto-trade --iterations 50`
- Auto-discover best pairs: `python -m src.cli auto-trade --discover`
- Custom scan interval: `python -m src.cli auto-trade --interval 600` (10 min)
- Live mode: `python -m src.cli auto-trade --live` (requires confirmation)

## What it does each scan:
1. Checks all open positions for stop-loss (-5%) or take-profit (+10%)
2. Force-sells any position that hits those thresholds
3. Scans all coins for BUY/SELL signals
4. Executes trades when confidence > 50%
5. Logs daily P&L for consistency tracking
6. Records everything to the knowledge base

## Arguments from user:
If the user provides arguments like "dry run" or "10 iterations" or "live", map them to the appropriate flags.

$ARGUMENTS
