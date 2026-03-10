# Crypto Trading Bot — Claude Code Native Interface

## Architecture

Claude Code IS the trading interface. No Streamlit, no LangGraph agents needed.

```
User <-> Claude Code (reasoning + skills + MCP)
              |
              +-- /analyze, /signal, /trade, /portfolio, /risk, /backtest, /history, /bot-status
              |       |
              |       +-- src/cli.py (Typer CLI backbone)
              |               |
              |               +-- src/core/market_data.py   (Binance API data)
              |               +-- src/core/analysis.py      (technicals + news)
              |               +-- src/core/trading.py       (paper trade execution)
              |               +-- src/core/portfolio.py     (portfolio queries)
              |               +-- src/core/risk.py          (risk assessment)
              |               +-- src/core/state.py         (persistent paper state)
              |
              +-- MCP Servers (binance-mcp, trading-db-mcp)
              +-- Custom Agents (market-analyst, trade-executor)
```

## CLI Commands

```bash
python -m src.cli analyze BTCUSDT          # Full market analysis
python -m src.cli signal BTCUSDT           # Trading signal + risk
python -m src.cli trade BUY BTCUSDT 100    # Paper trade ($100 USDT)
python -m src.cli portfolio                # Portfolio summary
python -m src.cli risk BTCUSDT             # Risk assessment
python -m src.cli status                   # System health
python -m src.cli history                  # Recent trades
python -m src.cli backtest BTCUSDT --days 30  # RSI backtest
```

## Skills (Slash Commands)

- `/analyze [SYMBOL]` — Market analysis with technicals, news, fear/greed
- `/signal [SYMBOL]` — Trading signal with confidence and risk
- `/trade <SIDE> <SYMBOL> <AMOUNT>` — Execute paper trade (confirms first)
- `/portfolio` — View positions and P&L
- `/risk [SYMBOL]` — Risk assessment with VaR and sizing
- `/bot-status` — Check API connections
- `/history` — Recent trade history
- `/backtest <SYMBOL> [DAYS]` — Simple RSI backtest

## Safety Rules

1. **PAPER TRADING ONLY** — No real money trades ever
2. Max single order: $1,000
3. Max open positions: 10
4. Max drawdown: 20% triggers safety stop
5. Always confirm before executing trades

## Key Files

| Path | Purpose |
|------|---------|
| `src/cli.py` | CLI backbone (all commands) |
| `src/core/` | Data gathering + trading logic |
| `src/apis/binance_client.py` | CCXT Binance client |
| `src/safety/paper_trading.py` | Paper trading safety guard |
| `src/config/settings.py` | Config from .env |
| `.claude/skills/` | 8 Claude Code skills |
| `.claude/agents/` | 2 custom agents |
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
python -m src.cli analyze BTCUSDT     # Test analysis
```

## Deprecated

The following are kept for reference but NOT used:
- `src/graph/` — Old LangGraph multi-agent system
- `src/agents/crypto_agents.py` — Old 13-agent system
- `src/ui/main_app.py` — Old Streamlit dashboard
