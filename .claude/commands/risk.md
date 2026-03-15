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
- Recommended position size based on 2% risk budget
- Stop loss (-5% hard limit) and take profit (+10% hard limit) levels
- Current Fear & Greed sentiment context
- If risk is HIGH or VERY_HIGH, explicitly warn the user
