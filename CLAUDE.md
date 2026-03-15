# Crypto Trading Bot — Claude Code Native Interface

## Architecture

Claude Code IS the trading interface. No Streamlit, no LangGraph agents needed.

```
User <-> Claude Code (reasoning + slash commands + MCP)
              |
              +-- /analyze, /signal, /trade, /portfolio, /risk, /backtest
              +-- /scan, /auto-trade, /autoexp, /trading-mode
              +-- /history, /learnings, /bot-status
              |       |
              |       +-- src/cli.py (Typer CLI backbone — 14 commands)
              |               |
              |               +-- src/core/signals.py     (7-strategy ensemble engine)
              |               +-- src/core/market_data.py  (Binance API data)
              |               +-- src/core/analysis.py     (technicals + news)
              |               +-- src/core/trading.py      (paper/live trade execution)
              |               +-- src/core/auto_trader.py   (autonomous trading loop + stop-loss)
              |               +-- src/core/portfolio.py    (portfolio queries)
              |               +-- src/core/risk.py         (risk assessment)
              |               +-- src/core/feedback.py     (trade outcome learning)
              |               +-- src/core/knowledge.py    (agent knowledge tracker)
              |               +-- src/core/state.py        (persistent state, paper/live wallets)
              |
              +-- src/dashboard/app.py  (Flask web dashboard at :5050)
              +-- MCP Servers (binance-mcp, trading-db-mcp)
              +-- Custom Agents (market-analyst, trade-executor)
```

## Slash Commands (User Interface)

Users interact via `/` commands — Claude handles all Python execution.

| Command | What it does |
|---------|-------------|
| `/analyze [SYMBOL]` | Market analysis with technicals, news, fear/greed |
| `/signal [SYMBOL]` | Trading signal with confidence and risk |
| `/scan` | Multi-coin market scanner — find best setups |
| `/trade <SIDE> <SYMBOL> <AMOUNT>` | Execute a trade (confirms first, mode-aware) |
| `/auto-trade` | Start autonomous trading loop (stop-loss, P&L tracking) |
| `/portfolio` | View positions and P&L for current mode |
| `/history` | Recent trade history |
| `/trading-mode [paper\|live]` | Show/switch trading mode (separate wallets) |
| `/risk [SYMBOL]` | Risk assessment with VaR and sizing |
| `/backtest <SYMBOL> [DAYS]` | RSI backtest on historical data |
| `/autoexp [N]` | Autonomous strategy experiment loop |
| `/bot-status` | Check API connections |
| `/learnings` | What Claude has learned from trading |

## CLI Commands (Internal — run by Claude)

```bash
# Analysis
python -m src.cli analyze BTCUSDT          # Full market analysis
python -m src.cli signal BTCUSDT           # Trading signal + risk
python -m src.cli signals                  # Multi-coin signal scanner (ensemble)

# Trading
python -m src.cli trade BUY BTCUSDT 25     # Paper trade ($25 USDT)
python -m src.cli trade BUY BTCUSDT 25 --live  # Live wallet trade
python -m src.cli auto-trade               # Autonomous trading loop
python -m src.cli auto-trade --dry-run     # Show signals without trading
python -m src.cli auto-trade --live        # Auto-trade on live wallet

# Portfolio & Mode
python -m src.cli portfolio                # Portfolio summary (current mode)
python -m src.cli history                  # Recent trades
python -m src.cli trading-mode             # Show paper/live status + balances
python -m src.cli trading-mode live        # Switch to live wallet
python -m src.cli trading-mode paper       # Switch to paper wallet
python -m src.cli reset-portfolio          # Reset current mode to $100

# Risk & Strategy
python -m src.cli risk BTCUSDT             # Risk assessment
python -m src.cli backtest BTCUSDT --days 30  # RSI backtest

# System
python -m src.cli status                   # System health
python -m src.cli dashboard                # Start web dashboard
python -m src.cli learnings                # Agent knowledge base
```

## Signal Engine (7-Strategy Ensemble)

The signal engine in `src/core/signals.py` combines 7 independent strategies:

| Strategy | Weight | What it does |
|----------|--------|-------------|
| VWAP Reversion | 25% | Buy when price deviates below VWAP, sell on reversion |
| RSI Mean Reversion | 20% | Buy oversold, sell overbought |
| MACD Momentum | 15% | Histogram direction + crossovers |
| Bollinger Bands | 15% | Price at band extremes + squeeze detection |
| Momentum Breakout | 10% | N-period high/low breakout + volume confirmation |
| EMA Crossover | 10% | 9/21 EMA trend following |
| Volume Spike | 5% | Unusual volume confirms breakouts |

Output: BUY / SELL / HOLD with confidence (0-100%) and per-strategy breakdown.

## Auto-Trader Features

The autonomous trading loop (`/auto-trade`) includes:
- **Stop-loss enforcement**: Force-sells at -5% from entry (configurable)
- **Take-profit enforcement**: Force-sells at +10% from entry (configurable)
- **Daily P&L tracking**: Logs portfolio value daily to `data/daily_pnl.json`
- **Position sizing**: Kelly-like based on confidence and risk budget
- **10% cash reserve**: Always keeps some cash available
- **Knowledge logging**: Records every trade decision for learning

## Eval Harness (Backtesting)

```bash
# Basic eval
python scripts/eval_harness.py --days 90 --strategy vwap

# Honest eval with transaction costs
python scripts/eval_harness.py --days 90 --fees

# Walk-forward validation (out-of-sample scoring)
python scripts/eval_harness.py --days 90 --fees --walk-forward

# Compare all 8 strategies head-to-head
python scripts/eval_harness.py --days 90 --compare-all --fees --walk-forward
```

- **Transaction costs**: 0.15% per trade (Binance fees + slippage)
- **Walk-forward**: Scores only on last 33% of data (unseen/out-of-sample)
- **8 strategies**: rsi, ensemble, multi_confirm, momentum, squeeze, vwap, vwap_rsi, squeeze_vwap
- **EVAL_SCORE** = mean(per-coin scores) × coverage × feedback

## Paper/Live Trading

Two separate wallets with independent state:
- `data/paper_state.json` — paper trading wallet (default)
- `data/live_state.json` — live trading wallet
- `data/trading_mode.json` — which mode is active

Switch with `/trading-mode live` or `/trading-mode paper`. Live mode requires confirmation.

## Self-Improvement Loop

The autoresearch system (`/autoexp`) follows the Karpathy pattern:
1. One mutable file: `config/strategy.yaml`
2. Eval harness: `scripts/eval_harness.py` (8 strategy modes, `--compare-all`)
3. Loop: hypothesis → edit → eval → keep if better, revert if worse
4. Trade feedback loop adjusts EVAL_SCORE by ±10% based on live performance

## Web Dashboard

```bash
python -m src.cli dashboard   # Opens http://localhost:5050
```

Shows: portfolio, live signals, trades, agent knowledge, strategy config, eval results,
strategy comparison, daily P&L, feedback stats, trading mode.
Auto-refreshes every 30 seconds.

## Safety Rules

1. **PAPER TRADING BY DEFAULT** — Live mode requires explicit confirmation
2. Max single order: $100
3. Max open positions: 10
4. Max drawdown: 20% triggers safety stop
5. Stop-loss: -5% hard limit (configurable)
6. Take-profit: +10% hard limit (configurable)
7. Always confirm before manual trades
8. Separate wallets for paper and live

## Key Files

| Path | Purpose |
|------|---------|
| `src/cli.py` | CLI backbone (14 commands) |
| `src/core/signals.py` | 7-strategy ensemble signal engine |
| `src/core/auto_trader.py` | Autonomous trading loop + stop-loss/take-profit |
| `src/core/state.py` | Persistent state (paper/live wallets) |
| `src/core/feedback.py` | Trade outcome learning |
| `src/core/knowledge.py` | Agent knowledge tracker |
| `src/dashboard/app.py` | Flask web dashboard |
| `config/strategy.yaml` | Tunable strategy parameters |
| `scripts/eval_harness.py` | Multi-strategy eval (fees, walk-forward) |
| `loops/program.md` | Autoexp instructions |
| `src/safety/paper_trading.py` | Paper trading safety guard |
| `.claude/commands/` | 13 Claude Code slash commands |
| `.claude/agents/` | 2 custom agents (market-analyst, trade-executor) |
| `.mcp.json` | MCP server config |
| `data/paper_state.json` | Paper wallet state |
| `data/live_state.json` | Live wallet state |
| `data/daily_pnl.json` | Daily P&L tracking |
| `data/trade_outcomes.json` | Trade feedback data |

## Environment

Requires `.env` with:
- `BINANCE_API_KEY` / `BINANCE_SECRET_KEY` — Market data access
- `PAPER_TRADING=true` — Must stay true
- `NEWSAPI_KEY` / `CRYPTOPANIC_API_KEY` — News (optional)

## Development

```bash
pip install -r requirements.txt
python -m src.cli status              # Verify setup
python -m src.cli signals             # Test signal engine
python -m src.cli dashboard           # Start dashboard
```

## Deprecated

The following are kept for reference but NOT used:
- `src/graph/` — Old LangGraph multi-agent system
- `src/agents/crypto_agents.py` — Old 13-agent system
- `src/ui/main_app.py` — Old Streamlit dashboard
- `.claude/skills/` — Old skill format (removed, use `.claude/commands/`)
