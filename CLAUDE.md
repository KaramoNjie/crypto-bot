# Crypto Trading Bot — Claude Code Native Interface

## Architecture

Claude Code IS the trading interface. No Streamlit, no LangGraph agents needed.

```
User <-> Claude Code (reasoning + skills + MCP)
              |
              +-- /analyze, /signal, /trade, /portfolio, /risk, /backtest, /history, /bot-status
              +-- /signals, /scan, /autoexp   (multi-coin scanner, auto research)
              |       |
              |       +-- src/cli.py (Typer CLI backbone — 13 commands)
              |               |
              |               +-- src/core/signals.py     (7-strategy ensemble engine)
              |               +-- src/core/market_data.py  (Binance API data)
              |               +-- src/core/analysis.py     (technicals + news)
              |               +-- src/core/trading.py      (paper trade execution)
              |               +-- src/core/auto_trader.py   (autonomous trading loop)
              |               +-- src/core/portfolio.py    (portfolio queries)
              |               +-- src/core/risk.py         (risk assessment)
              |               +-- src/core/feedback.py     (trade outcome learning)
              |               +-- src/core/knowledge.py    (agent knowledge tracker)
              |               +-- src/core/state.py        (persistent paper state)
              |
              +-- src/dashboard/app.py  (Flask web dashboard at :5050)
              +-- MCP Servers (binance-mcp, trading-db-mcp)
              +-- Custom Agents (market-analyst, trade-executor)
```

## CLI Commands

```bash
# Analysis
python -m src.cli analyze BTCUSDT          # Full market analysis
python -m src.cli signal BTCUSDT           # Trading signal + risk
python -m src.cli signals                  # Multi-coin signal scanner (ensemble)

# Trading
python -m src.cli trade BUY BTCUSDT 25     # Paper trade ($25 USDT)
python -m src.cli auto-trade               # Autonomous trading loop
python -m src.cli auto-trade --dry-run     # Show signals without trading

# Portfolio
python -m src.cli portfolio                # Portfolio summary
python -m src.cli history                  # Recent trades
python -m src.cli reset-portfolio          # Reset to $100

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

## Web Dashboard

```bash
python -m src.cli dashboard   # Opens http://localhost:5050
```

Shows: portfolio, live signals, trades, agent knowledge, strategy config, eval results.
Auto-refreshes every 30 seconds.

## Self-Improvement Loop

The autoresearch system (`/autoexp`) follows the Karpathy pattern:
1. One mutable file: `config/strategy.yaml`
2. Eval harness: `scripts/eval_harness.py` (8 strategy modes, `--compare-all` for head-to-head)
3. Loop: hypothesis → edit → eval → keep if better, revert if worse
4. EVAL_SCORE = mean(per-coin) * coverage * feedback
5. Available strategies: rsi, ensemble, multi_confirm, momentum, squeeze, vwap, vwap_rsi, squeeze_vwap
6. Best strategy: VWAP reversion (EVAL_SCORE 3.81, 43% better than RSI 2.65)

Trade feedback loop (`src/core/feedback.py`):
- Logs every BUY entry and SELL exit
- Computes win rate from live paper trades
- Adjusts EVAL_SCORE by ±10% based on live performance

## Skills (Slash Commands)

- `/analyze [SYMBOL]` — Market analysis with technicals, news, fear/greed
- `/signal [SYMBOL]` — Trading signal with confidence and risk
- `/trade <SIDE> <SYMBOL> <AMOUNT>` — Execute paper trade
- `/portfolio` — View positions and P&L
- `/risk [SYMBOL]` — Risk assessment with VaR and sizing
- `/scan` — Multi-coin market scanner
- `/autoexp [N]` — Autonomous strategy experiment loop
- `/bot-status` — Check API connections
- `/history` — Recent trade history
- `/backtest <SYMBOL> [DAYS]` — RSI backtest

## Safety Rules

1. **PAPER TRADING ONLY** — No real money trades ever
2. Max single order: $100
3. Max open positions: 10
4. Max drawdown: 20% triggers safety stop
5. Always confirm before manual trades

## Key Files

| Path | Purpose |
|------|---------|
| `src/cli.py` | CLI backbone (13 commands) |
| `src/core/signals.py` | 7-strategy ensemble signal engine |
| `src/core/auto_trader.py` | Autonomous trading loop |
| `src/core/feedback.py` | Trade outcome learning |
| `src/core/knowledge.py` | Agent knowledge tracker |
| `src/dashboard/app.py` | Flask web dashboard |
| `config/strategy.yaml` | Tunable strategy parameters |
| `scripts/eval_harness.py` | Multi-strategy backtest eval (8 modes) |
| `loops/program.md` | Autoexp instructions |
| `src/safety/paper_trading.py` | Paper trading safety guard |
| `.claude/commands/` | Claude Code slash commands |
| `.claude/agents/` | Custom agents |
| `.mcp.json` | MCP server config |

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
