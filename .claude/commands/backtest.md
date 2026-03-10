Run a simple RSI mean-reversion backtest. Arguments: SYMBOL DAYS (e.g. BTCUSDT 30)

Execute:
```
cd /home/amo/Documents/crypto-bot && python -m src.cli backtest $ARGUMENTS
```
Default: BTCUSDT 30 days.

Interpret the results:
- Compare strategy return vs buy-and-hold
- Comment on number of trades (too few = RSI rarely hit extremes)
- Max drawdown context
- Whether the strategy would have been profitable in this period
