Run a backtest. Arguments: SYMBOL DAYS (e.g. BTCUSDT 30)

For a simple RSI backtest via CLI:
```
cd /home/amo/Documents/crypto-bot && python -m src.cli backtest $ARGUMENTS
```
Default: BTCUSDT 30 days.

For an honest multi-strategy eval with fees and walk-forward validation:
```
cd /home/amo/Documents/crypto-bot && python scripts/eval_harness.py --days 90 --strategy vwap --fees --walk-forward
```

To compare all 8 strategies head-to-head:
```
cd /home/amo/Documents/crypto-bot && python scripts/eval_harness.py --days 90 --compare-all --fees --walk-forward
```

Interpret the results:
- Compare strategy return vs buy-and-hold
- Comment on number of trades (too few = overfitting)
- Max drawdown context (stop-loss is -5%)
- Whether the strategy is profitable after fees (0.15% per trade)
- Walk-forward results show out-of-sample performance (more honest than in-sample)
- Available strategies: rsi, ensemble, multi_confirm, momentum, squeeze, vwap, vwap_rsi, squeeze_vwap
