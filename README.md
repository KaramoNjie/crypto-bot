# Crypto Trading Bot

A Claude Code–native paper trading bot for cryptocurrency markets. Claude Code IS the trading interface — no dashboard, no separate UI needed.

## Architecture

```
User <-> Claude Code (reasoning + skills + MCP)
              |
              +-- Slash commands: /analyze, /signal, /trade, /portfolio, /risk, /scan, /autoexp
              |
              +-- python -m src.cli <command>
              |       |
              |       +-- src/core/        (market data, technicals, trading, portfolio)
              |       +-- src/apis/        (Binance CCXT, NewsAPI)
              |       +-- src/safety/      (paper trading guard)
              |       +-- src/mcp/         (MCP servers)
              |
              +-- MCP Servers (binance-mcp, trading-db-mcp)
              +-- Custom Agents (market-analyst, trade-executor)
```

## Features

- **Paper trading only** — $100 starting capital, realistic simulation
- **Multi-coin scanner** — rank BTC/ETH/SOL/BNB by signal strength
- **Autoresearch loop** — autonomous strategy optimization via backtests (Karpathy pattern)
- **Real-time monitoring** — 5-min auto signal + portfolio checks via cron
- **Technical indicators** — RSI, MACD, Bollinger Bands, SMA, EMA (params from `config/strategy.yaml`)
- **News + sentiment** — NewsAPI integration with fear/greed index

## Quick Start

```bash
# Clone and install
git clone https://github.com/KaramoNjie/crypto-bot.git
cd crypto-bot
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your Binance API keys (read-only market data access is enough)

# Verify setup
python -m src.cli status

# Start trading
python -m src.cli analyze BTCUSDT
```

## CLI Commands

```bash
python -m src.cli analyze BTCUSDT        # Full market analysis
python -m src.cli signal BTCUSDT         # Trading signal + risk
python -m src.cli trade BUY BTCUSDT 30   # Paper trade ($30)
python -m src.cli portfolio              # Portfolio summary
python -m src.cli risk BTCUSDT          # Risk assessment
python -m src.cli status                # System health
python -m src.cli history               # Recent trades
python -m src.cli backtest BTCUSDT --days 30  # RSI backtest
```

## Slash Commands (inside Claude Code)

| Command | Description |
|---------|-------------|
| `/analyze [SYMBOL]` | Market analysis with technicals, news, fear/greed |
| `/signal [SYMBOL]` | Trading signal with confidence and risk |
| `/scan` | Multi-coin scanner: BTC/ETH/SOL/BNB ranked by signal |
| `/trade <SIDE> <SYMBOL> <AMOUNT>` | Execute paper trade |
| `/portfolio` | View positions and P&L |
| `/risk [SYMBOL]` | Risk assessment with VaR and sizing |
| `/autoexp [N]` | Run N autonomous strategy experiments |
| `/history` | Recent trade history |
| `/backtest <SYMBOL> [DAYS]` | RSI backtest |
| `/bot-status` | Check API connections |

## Autoresearch Loop

Inspired by [karpathy/autoresearch](https://github.com/karpathy/autoresearch). Claude autonomously tunes `config/strategy.yaml` via backtests:

```
modify config/strategy.yaml → commit → run eval harness → keep if improved → repeat
```

```bash
# Run 20 overnight experiments
/autoexp 20

# Check results
cat loops/results.tsv
```

`EVAL_SCORE = mean(per-coin scores) * coverage_factor`
- Tested across BTC, ETH, SOL, BNB simultaneously
- Penalises strategies that only work on one coin

## Environment Variables

Copy `.env.example` to `.env` and fill in:

```
BINANCE_API_KEY=your_key
BINANCE_SECRET_KEY=your_secret
PAPER_TRADING=true
NEWSAPI_KEY=your_key         # optional
```

## Safety

- Paper trading only — `PAPER_TRADING=true` enforced at safety module level
- Max single order: $100
- Max open positions: 10
- Max drawdown: 20% triggers safety stop

## License

MIT — see LICENSE. For educational purposes only. Not financial advice.
