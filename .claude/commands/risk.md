Run a risk assessment for a cryptocurrency pair.

Execute:
```
cd /home/amo/Documents/crypto-bot && python -m src.cli risk $ARGUMENTS
```
Default symbol is BTCUSDT if none provided.

Explain the output:
- Risk level and what it means for position sizing
- Volatility context (daily and annualized)
- VaR: the expected max loss with 95% confidence over 1 day
- Recommended stop loss and take profit levels
