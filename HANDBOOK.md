# Crypto Trading Bot - Complete Handbook

**A plain-language guide for anyone, from beginners to experienced users.**

---

## Table of Contents

1. [Overview of the Application](#1-overview-of-the-application)
2. [Architecture Explained in Simple Terms](#2-architecture-explained-in-simple-terms)
3. [Tools and Technologies Used](#3-tools-and-technologies-used)
4. [Scripts and Commands](#4-scripts-and-commands)
5. [Terminal Output Explanation](#5-terminal-output-explanation)
6. [Self-Trading / Learning System](#6-self-trading--learning-system)
7. [Background Processes](#7-background-processes)
8. [Command System](#8-command-system)
9. [Configuration Files](#9-configuration-files)
10. [Evaluation System](#10-evaluation-system)
11. [Running the Project Locally](#11-running-the-project-locally)
12. [Claude Configuration](#12-claude-configuration)
13. [Practical Walkthrough](#13-practical-walkthrough)
14. [Prompt Library](#14-prompt-library---training-claude-to-improve-and-trade-daily)

---

## 1. Overview of the Application

### What Does This App Do?

This is a **cryptocurrency paper trading bot** -- a system that simulates buying and selling cryptocurrencies using fake money ($100 of play money) to test and improve trading strategies without any financial risk.

Think of it like a flight simulator for trading. Pilots use simulators to practise before flying real planes. This bot lets you practise trading strategies before ever risking real money.

### The Purpose of the Project

The project exists to answer one question: **"Can we build a system that automatically finds profitable trading strategies?"**

It does this by:
- **Watching the market** -- pulling live price data from Binance (the world's largest cryptocurrency exchange)
- **Analysing patterns** -- using mathematical indicators that professional traders use (like RSI, MACD, and Bollinger Bands)
- **Making decisions** -- deciding whether to buy, sell, or hold based on 7 different strategies working together
- **Learning from results** -- tracking what works and what doesn't, then adjusting
- **Self-improving** -- running hundreds of experiments automatically to find better settings

### The Major Components

The system has six main parts:

| Component | What It Does | Analogy |
|-----------|-------------|---------|
| **Claude Code** | The brain -- you talk to it, it runs everything | A very smart assistant at a trading desk |
| **Signal Engine** | Analyses markets using 7 strategies and says BUY, SELL, or HOLD | A panel of 7 expert advisors voting |
| **Paper Trading System** | Simulates trades with fake money and tracks your portfolio | A practice account at a brokerage |
| **Safety Guard** | Prevents dangerous actions (too big trades, too many trades, real money) | A safety harness on a rollercoaster |
| **Self-Improvement Loop** | Automatically tests strategy settings and keeps what works | A scientist running experiments in a lab |
| **Web Dashboard** | A visual display of everything happening in the system | A control room with monitors |

---

## 2. Architecture Explained in Simple Terms

### How Everything Connects

Imagine the system as a company with different departments. You (the user) talk to the receptionist (Claude Code), who coordinates everything behind the scenes.

```
YOU (the user)
  |
  v
CLAUDE CODE (the receptionist / coordinator)
  |
  +--- Slash Commands (/analyze, /signal, /trade, etc.)
  |       These are like quick-dial buttons for common tasks
  |
  +--- CLI Backbone (src/cli.py)
  |       This is the phone system that routes your requests
  |       to the right department
  |
  +--- Core Modules (src/core/)
  |    |
  |    +-- signals.py      -- The analysis team (7 strategies)
  |    +-- market_data.py   -- The data team (gets prices from Binance)
  |    +-- analysis.py      -- The research team (technicals + news)
  |    +-- trading.py       -- The execution team (places paper trades)
  |    +-- auto_trader.py   -- The autopilot (trades without you)
  |    +-- portfolio.py     -- The accounting team (tracks your money)
  |    +-- risk.py          -- The risk team (tells you how dangerous a trade is)
  |    +-- feedback.py      -- The performance review team (tracks wins/losses)
  |    +-- knowledge.py     -- The librarian (records what was learned)
  |    +-- state.py         -- The filing cabinet (saves your portfolio to disk)
  |
  +--- MCP Servers (src/mcp/)
  |    |
  |    +-- binance_server.py  -- Direct line to Binance for live data
  |    +-- db_server.py       -- Direct line to portfolio database
  |
  +--- Agents (.claude/agents/)
  |    |
  |    +-- market-analyst    -- A specialist that only reads and analyses
  |    +-- trade-executor    -- A specialist that only executes trades
  |
  +--- Dashboard (src/dashboard/app.py)
  |       A web page at localhost:5050 showing everything visually
  |
  +--- Safety Module (src/safety/paper_trading.py)
          The security guard that blocks anything dangerous
```

### How a Trade Actually Happens (Step by Step)

Let's say you type `/trade BUY BTCUSDT 25`. Here's what happens behind the scenes:

1. **Claude Code** receives your request and parses it
2. The **CLI** routes it to the `trade` command in `src/cli.py`
3. `trading.py` calls the **Safety Guard** to check:
   - Is paper trading mode on? (Must be YES)
   - Is $25 within the $100 max order limit? (YES)
   - Do you have enough fake money? (Checks balance)
   - Are you under the 10-position limit? (Checks positions)
   - Is the portfolio drawdown under 20%? (Checks losses)
4. If all checks pass, the system gets the **live price** from Binance
5. It simulates realistic execution with:
   - **Slippage**: Price moves slightly against you (0.1%), like in real trading
   - **Fees**: 0.1% commission, just like Binance charges
6. Your **portfolio state** is updated in `data/paper_state.json`
7. The **feedback system** logs this as a BUY entry for future performance tracking
8. The **knowledge base** records the trade with the signals that triggered it
9. You see a confirmation with the fill price, quantity, and updated balance

### How the Signal Engine Works

The signal engine is like a panel of 7 expert advisors, each using a different method. They all look at the same market data but interpret it differently:

**Expert 1: VWAP Reversion (25% vote weight)**
- Looks at the Volume Weighted Average Price -- the "fair price" based on where most trading happened
- If the current price is significantly below this fair price, it says BUY (the price should bounce back)
- If the price is above, it says SELL
- Think of it like: "If a house is priced well below what similar houses sold for, it's probably a good deal"

**Expert 2: RSI Mean Reversion (20% vote weight)**
- RSI (Relative Strength Index) measures if something has been bought too much (overbought) or sold too much (oversold)
- Range is 0-100. Below 22 = oversold (BUY signal). Above 69 = overbought (SELL signal)
- Think of it like: "If a rubber band is stretched too far, it'll snap back"

**Expert 3: MACD Momentum (15% vote weight)**
- MACD (Moving Average Convergence Divergence) tracks the speed and direction of price changes
- When momentum shifts from negative to positive, it says BUY
- Think of it like: "A ball thrown into the air -- MACD tells you when it stops rising and starts falling"

**Expert 4: Bollinger Bands (15% vote weight)**
- Creates an envelope around the price based on how volatile it's been
- Price touching the lower band = oversold. Upper band = overbought
- Also detects "squeezes" -- when bands get very tight, a big move is coming
- Think of it like: "A river between two banks -- when the banks narrow, the water speeds up"

**Expert 5: Momentum Breakout (10% vote weight)**
- Watches for price breaking above its highest point in the last 10 candles
- Requires above-average volume to confirm it's real
- Think of it like: "If a runner breaks their personal best with a crowd cheering, it's probably real improvement"

**Expert 6: EMA Crossover (10% vote weight)**
- Tracks two moving averages: a fast one (9-period) and a slow one (21-period)
- When the fast crosses above the slow, the trend is turning bullish
- Think of it like: "A speedboat overtaking a cruise ship -- the speedboat shows the new direction"

**Expert 7: Volume Spike (5% vote weight)**
- Flags when trading volume is unusually high compared to the average
- High volume confirms that a price move is genuine, not just noise
- Think of it like: "If one person shouts in a library, ignore it. If everyone starts talking, something happened"

**How they vote:**
Each expert gives a score from -1 (strong SELL) to +1 (strong BUY), plus a confidence level. The scores are combined using the weights above. If the combined score is above +0.15 with at least 40% confidence, the system says BUY. Below -0.15 = SELL. Between = HOLD.

When multiple experts agree, the confidence gets a bonus boost (like when multiple doctors give the same diagnosis, you trust it more).

---

## 3. Tools and Technologies Used

### Programming Language and Frameworks

| Tool | What It Is | Why It's Used |
|------|-----------|---------------|
| **Python** | The programming language | The entire bot is written in Python. It's the most popular language for data analysis, trading bots, and AI |
| **Typer** | Command-line framework | Creates all the CLI commands (`analyze`, `signal`, `trade`, etc.) with help text and argument parsing |
| **Rich** | Terminal formatting | Makes the terminal output beautiful with coloured tables, panels, and formatted text |
| **Flask** | Web framework | Powers the web dashboard at port 5050 |

### Data and Analysis

| Tool | What It Is | Why It's Used |
|------|-----------|---------------|
| **Pandas** | Data manipulation library | Handles candlestick data (price history) as tables for easy computation |
| **NumPy** | Number crunching library | Calculates RSI, MACD, moving averages, and other mathematical indicators |
| **PyYAML** | YAML file parser | Reads the strategy configuration file (`strategy.yaml`) |

### Cryptocurrency and Market Data

| Tool | What It Is | Why It's Used |
|------|-----------|---------------|
| **CCXT** | Crypto exchange library | Connects to Binance to fetch live prices, order books, and candle data |
| **Requests** | HTTP client | Calls external APIs like Fear & Greed Index, news APIs |

### Configuration and Settings

| Tool | What It Is | Why It's Used |
|------|-----------|---------------|
| **Pydantic** | Data validation | Ensures all configuration values are the right type and within valid ranges |
| **Pydantic Settings** | Environment config | Reads API keys and settings from the `.env` file |
| **python-dotenv** | Environment loader | Loads the `.env` file so your API keys are available to the code |

### AI and Agent Infrastructure

| Tool | What It Is | Why It's Used |
|------|-----------|---------------|
| **Claude Code** | Anthropic's AI coding assistant | The main interface -- you talk to Claude, and it operates the entire system |
| **MCP (Model Context Protocol)** | AI tool protocol | Lets Claude directly call Binance for data and execute trades through structured tool calls |

### Logging and Reliability

| Tool | What It Is | Why It's Used |
|------|-----------|---------------|
| **structlog** | Structured logging | Creates clean, parseable log messages for debugging |
| **python-json-logger** | JSON log formatting | Stores logs in JSON format for easy searching |
| **Tenacity** | Retry logic | Automatically retries failed API calls (e.g., if Binance briefly goes offline) |

### Database

| Tool | What It Is | Why It's Used |
|------|-----------|---------------|
| **SQLAlchemy** | Database toolkit | Powers the MCP database server for trade history queries |
| **aiosqlite** | Async SQLite | Allows the MCP server to query the database without blocking |

### Development

| Tool | What It Is | Why It's Used |
|------|-----------|---------------|
| **pytest** | Testing framework | Runs automated tests to make sure the code works correctly |
| **Git** | Version control | Tracks every experiment and code change, allows reverting failed experiments |

---

## 4. Scripts and Commands

### The Eval Harness (`scripts/eval_harness.py`)

**What it is:** The judge. This is the single most important script in the self-improvement system. It backtests (tests against historical data) a trading strategy and gives it a score.

**Why it exists:** Without an objective way to measure "is this strategy better?", you'd be guessing. The eval harness removes guesswork.

**What it does behind the scenes:**
1. Downloads 90 days of historical candle data (price history) for BTC, ETH, SOL, and BNB
2. Simulates trading using the strategy settings in `strategy.yaml`
3. For each coin, calculates:
   - **Sharpe ratio** -- risk-adjusted return (higher = better returns for the risk taken)
   - **Maximum drawdown** -- the worst peak-to-trough loss
   - **Number of trades** -- how many buy/sell cycles occurred
4. Combines these into a single EVAL_SCORE number
5. The autoresearch loop uses this score to decide: keep the change, or revert it?

**How to run it:**
```bash
# Test the current strategy
python scripts/eval_harness.py --days 90 --timeframe 1h

# Test a specific strategy
python scripts/eval_harness.py --days 90 --strategy vwap

# Compare all 8 strategies side by side
python scripts/eval_harness.py --days 90 --compare-all
```

**The 8 strategies it can test:**

| Strategy | Description |
|----------|-------------|
| `rsi` | RSI mean-reversion -- buy oversold, sell overbought |
| `ensemble` | All 5 base indicators voting together |
| `multi_confirm` | Requires N indicators to agree |
| `momentum` | Breakout trading -- buy at new highs with volume |
| `squeeze` | Bollinger Band squeeze breakout |
| `vwap` | VWAP reversion with RSI confirmation (current best) |
| `vwap_rsi` | VWAP entry + RSI exit hybrid |
| `squeeze_vwap` | Squeeze entry + VWAP exit hybrid |

### The CLI Backbone (`src/cli.py`)

**What it is:** The central switchboard. Every command you can run goes through this file.

**Why it exists:** Instead of remembering different Python scripts, you type one consistent command format: `python -m src.cli <command>`.

**What it does:** Routes your command to the right module, formats the output nicely, and displays it in your terminal.

---

## 5. Terminal Output Explanation

### When You Run `/autoexp`

Here's what you see and what it means:

```
Establishing baseline...
```
The system is running the eval harness with your current settings to get a starting score. This is the number it will try to beat.

```
EVAL_SCORE: 3.8112
```
Your current strategy scored 3.81. This is the number to beat. Higher is better. For reference:
- Below 1.0 = Poor (low Sharpe, high drawdown, or too few trades)
- 1.0-2.0 = Decent
- 2.0-3.0 = Good
- 3.0-5.0 = Very good (current VWAP strategy range)
- Above 5.0 = Exceptional (rare)

```
exp: VWAP deviation 2.5 -> 2.45 -- testing tighter entry threshold
```
This is the commit message. It tells you what was changed and why. "exp:" means experiment. The hypothesis was: "If we tighten the VWAP deviation from 2.5% to 2.45%, we might get slightly better entry points."

```
Running eval...
EVAL_SCORE: 3.8112
New score 3.8112 > previous best 3.7704 -> KEEP
```
The experiment worked. The new score (3.81) is higher than the old score (3.77), so the change is kept.

```
EVAL_SCORE: 1.5322
New score 1.5322 < previous best 3.8112 -> REVERT
```
This experiment failed. The score dropped from 3.81 to 1.53, so the change is automatically undone using `git reset --hard HEAD~1`.

```
Logged: b7f4db7  3.8112  kept  VWAP dev=2.45, os=44, win=24
```
Every experiment is recorded in `loops/results.tsv` for future reference.

### When You Run `/signal BTCUSDT`

```
Generating signal for BTCUSDT...
```
The system is fetching live data from Binance and running all 7 strategies.

```
+------- Signal: BTCUSDT -------+
| Price: $84,250.00              |
| RSI: 45.2  |  MACD Hist: -120  |
| Fear/Greed: 32 (Fear)          |
| Risk Level: MODERATE            |
| Suggested Position: $20         |
| Stop Loss: $82,100.00           |
| Take Profit: $88,400.00         |
+-------------------------------+
```
- **Price**: Current Bitcoin price
- **RSI 45.2**: Neutral territory (not oversold, not overbought)
- **MACD Hist -120**: Slightly bearish momentum
- **Fear/Greed 32 (Fear)**: The market is fearful (contrarian: this can be a buying opportunity)
- **Risk Level MODERATE**: Based on current volatility
- **Suggested Position $20**: How much to invest given the risk
- **Stop Loss / Take Profit**: Where to exit if the trade goes wrong (stop loss) or right (take profit)

### When You Run `/scan`

```
+------------ Multi-Coin Signal Scanner ------------+
| Symbol  | Price      | Action | Score  | Conf  |  ...
| BTCUSDT | $84,250.00 | HOLD   | -0.023 | 35%   |
| ETHUSDT | $3,180.00  | BUY    | +0.312 | 62%   |
| SOLUSDT | $142.50    | HOLD   | +0.089 | 28%   |
| BNBUSDT | $598.00    | SELL   | -0.245 | 55%   |
+---------------------------------------------------+

Top BUY: ETHUSDT (score=+0.312, conf=62%)
```
- **Score**: Combined signal from all 7 strategies (-1 to +1)
- **Conf**: Confidence level (how sure the system is)
- **Action**: BUY if score > 0.15 and confidence >= 40%, SELL if score < -0.15

### When You Run `/portfolio`

```
+-------- Paper Portfolio --------+
| Cash: $75.20                    |
| Positions: $24.80               |
| Total Value: $100.00            |
| P&L: +$0.00 (0.00%)            |
| Open Positions: 1               |
+---------------------------------+
```
- **Cash**: Unspent fake money
- **Positions**: Value of coins you currently hold
- **Total Value**: Cash + Positions
- **P&L**: Profit and Loss since starting ($100)

---

## 6. Self-Trading / Learning System

### How the Self-Learning System Works

The system improves itself through three interconnected loops:

#### Loop 1: The Experiment Loop (`/autoexp`)

This is the main improvement engine. It works like a scientist running experiments:

1. **Start with a baseline**: Run the eval harness to get the current score
2. **Form a hypothesis**: "If I change the RSI oversold threshold from 21 to 22, I might catch more buying opportunities"
3. **Make one small change**: Edit `strategy.yaml` (only one parameter at a time)
4. **Test it**: Run the eval harness on 90 days of historical data across 4 coins
5. **Compare**: Is the new score higher than the old score?
6. **Keep or revert**: If higher, keep the change. If not, undo it with Git
7. **Record**: Log the result in `loops/results.tsv`
8. **Repeat**: Go back to step 2 with a new hypothesis

**Why one change at a time?** If you change 3 things at once and the score improves, you don't know which change helped. By changing one thing at a time, you know exactly what worked.

**The evolution of this project:**
- Started with RSI-only strategy scoring 0.36
- After 63 RSI experiments, reached 2.65 (hit a ceiling -- diminishing returns)
- Introduced VWAP reversion strategy, immediately jumped to 3.77
- Fine-tuned VWAP to 3.81 (current best)
- Tested 8 different strategy modes to find the optimal approach

#### Loop 2: The Feedback Loop (`src/core/feedback.py`)

When you actually make paper trades (not just backtesting), the system learns from those too:

1. Every BUY is logged with the strategy settings that triggered it
2. When you SELL, the system calculates whether you made or lost money
3. After 3 or more completed trades, the system calculates your **live win rate**
4. This win rate adjusts the EVAL_SCORE by up to +/-10%
   - If your live win rate is 70%, the adjustment is: `1 + (0.7 - 0.5) * 0.2 = 1.04` (+4%)
   - If your live win rate is 30%, the adjustment is: `1 + (0.3 - 0.5) * 0.2 = 0.96` (-4%)

This means strategies that work in backtesting AND in live paper trading get a bonus, while strategies that only work in backtesting get penalised.

#### Loop 3: The Knowledge Base (`src/core/knowledge.py`)

Every action the system takes is recorded in a structured knowledge base (`data/knowledge.json`):

- **Strategy learnings**: "VWAP deviation of 2.45 works better than 2.5 because it catches slightly more entry opportunities without adding noise"
- **Trade learnings**: "BUY ETHUSDT @ $3,180 (score=+0.312, conf=62%): VWAP oversold, RSI confirming"
- **Bug learnings**: "Found that sed command corrupted YAML comments -- use Edit tool instead"

This knowledge base prevents the system from repeating mistakes and helps it build on what works.

### How Strategies Evolve Over Time

The improvement path looks like this:

```
Week 1: RSI only, score 0.36
  |  "Let me try different RSI settings..."
  v
Week 2: RSI tuned, score 2.65
  |  "RSI is hitting a ceiling. Let me try completely different strategies."
  v
Week 3: VWAP discovered, score 3.81
  |  "VWAP works great. Let me try hybrid strategies..."
  v
Week 4: VWAP+RSI hybrid tested at 3.67
  |  "Keep fine-tuning the winning strategy, test new ideas..."
  v
Ongoing: Continuous incremental improvement
```

The key insight: **don't just tune one strategy endlessly.** When improvements stall, try a fundamentally different approach. The jump from RSI (2.65) to VWAP (3.81) was a 43% improvement that no amount of RSI tuning could have achieved.

---

## 7. Background Processes

### Auto-Trader (`python -m src.cli auto-trade`)

**What it does:** Runs continuously in the background, scanning markets and making trades automatically.

**How it works:**
1. Every 5 minutes (configurable), it scans all configured coins
2. For each coin, it generates a signal using the 7-strategy ensemble
3. If the signal says BUY with high enough confidence (default 50%+):
   - Calculates position size based on portfolio value and confidence
   - Keeps 10% cash reserve (never goes all-in)
   - Executes the paper trade
4. If the signal says SELL and you hold that coin:
   - Sells the entire position
5. Logs everything to the knowledge base

**Safety guardrails during auto-trading:**
- Maximum $100 per trade
- Minimum $5 per trade (tiny trades aren't worth the fees)
- Never opens a position in a coin you already hold
- Stops if portfolio drawdown exceeds 20%
- Maximum 10 open positions at once
- Maximum 100 trades per day

**Auto-discover mode** (`--discover`): Instead of just watching 4 fixed coins (BTC, ETH, SOL, BNB), this mode scans ALL of Binance for the top pairs by volume and momentum, then trades those. It re-discovers the top pairs every scan cycle.

### MCP Servers

Two background servers that run when Claude Code starts:

**Binance MCP Server** (`src/mcp/binance_server.py`):
- Provides Claude with direct access to live market data
- Claude can call `get_ticker`, `get_technical_indicators`, `get_orderbook`, `get_news`, `get_fear_greed`, `assess_risk`, and `full_analysis` without going through the CLI
- This is how Claude gets data when you ask it questions conversationally

**Trading DB MCP Server** (`src/mcp/db_server.py`):
- Provides Claude with direct access to your portfolio and trade history
- Claude can call `get_portfolio`, `get_trade_history`, and `execute_paper_trade`
- This lets Claude manage trades during conversations

### Web Dashboard (`python -m src.cli dashboard`)

- Runs a Flask web server at `http://localhost:5050`
- Auto-refreshes every 30 seconds
- Shows: portfolio, live signals, trade history, agent knowledge, strategy config, eval results
- Exposes REST API endpoints that any tool can query:
  - `/api/portfolio` -- current portfolio
  - `/api/signals` -- current signals for all coins
  - `/api/signals/discover` -- auto-discover top pairs and show signals
  - `/api/trades` -- trade history
  - `/api/knowledge` -- knowledge base entries
  - `/api/strategy` -- current strategy config
  - `/api/eval` -- latest evaluation results
  - `/api/status` -- system health

---

## 8. Command System

### Every Command Explained

#### `/analyze [SYMBOL]` (default: BTCUSDT)

**What it does:** Runs a complete market analysis for a cryptocurrency.

**Why it exists:** Before trading, you want to understand the current market conditions. This gives you the full picture.

**When to use:** At the start of a trading session, or when you want to understand why a coin is moving.

**What happens internally:**
1. Fetches live price and 24h stats from Binance
2. Downloads recent candle data (usually 1h candles)
3. Calculates: RSI, MACD (line, signal, histogram), Bollinger Bands (upper, middle, lower, position), SMA 20 and 50, volume ratio
4. Fetches the Fear & Greed Index from alternative.me
5. Fetches recent crypto news from CryptoPanic or NewsAPI
6. Presents everything in a formatted table

---

#### `/signal [SYMBOL]` (default: BTCUSDT)

**What it does:** Generates a trading signal with a clear BUY/SELL/HOLD recommendation.

**Why it exists:** This is the decision-making command. It combines analysis with risk assessment to tell you what to do.

**When to use:** When you're deciding whether to make a specific trade.

**What happens internally:**
1. Runs a full analysis (same as `/analyze`)
2. Runs a risk assessment (same as `/risk`)
3. Combines them into a signal with: action (BUY/SELL/HOLD), confidence level, key reasons, entry price, stop loss, and take profit levels

---

#### `/trade <BUY|SELL> <SYMBOL> <AMOUNT>`

**Example:** `/trade BUY BTCUSDT 25`

**What it does:** Executes a paper trade (simulated, no real money).

**Why it exists:** To actually act on signals and build a paper trading track record.

**When to use:** When you've decided to make a trade based on your analysis.

**What happens internally:**
1. Claude shows you the proposed trade and asks for confirmation
2. After you confirm, it calls `execute_paper_trade()` in `trading.py`
3. The safety guard validates the order (size, balance, position limits, drawdown)
4. Gets the live price from Binance
5. Applies simulated slippage (0.1%) and fees (0.1%)
6. Updates your portfolio in `data/paper_state.json`
7. Logs the trade to the feedback system and knowledge base
8. Shows you the confirmation with fill details

---

#### `/portfolio`

**What it does:** Shows your current paper trading portfolio.

**Why it exists:** You need to know your current holdings, cash balance, and performance.

**When to use:** After trades, at the start of a session, or whenever you want a status check.

**What happens internally:**
1. Loads the portfolio state from `data/paper_state.json`
2. For each open position, fetches the current live price from Binance
3. Calculates unrealised P&L (profit/loss) for each position
4. Calculates total portfolio value (cash + positions)
5. Displays it in a formatted panel and table

---

#### `/risk [SYMBOL]` (default: BTCUSDT)

**What it does:** Runs a risk assessment for a cryptocurrency.

**Why it exists:** Before trading, you need to know how risky it is and how much to invest.

**When to use:** Before any trade, especially for unfamiliar coins.

**What happens internally:**
1. Downloads recent price history
2. Calculates daily and annualised volatility (how much the price swings)
3. Calculates Value at Risk (VaR) -- the maximum you'd expect to lose in a day with 95% confidence
4. Determines risk level: VERY_LOW, LOW, MODERATE, HIGH, VERY_HIGH
5. Recommends position size based on your portfolio and the risk
6. Calculates stop loss and take profit levels
7. Shows the risk/reward ratio

---

#### `/scan`

**What it does:** Scans multiple coins simultaneously and ranks them by signal strength.

**Why it exists:** Instead of checking coins one by one, this gives you the full market picture at once.

**When to use:** At the start of each trading session to find the best opportunity.

**What happens internally:**
1. Runs the 7-strategy ensemble signal for each of the 4 default coins (BTC, ETH, SOL, BNB)
2. Scores each coin from -1 to +1
3. Ranks them in a table
4. Highlights the top BUY and SELL candidates
5. Optionally auto-discovers top pairs from all of Binance (with `--discover`)

---

#### `/autoexp [N]`

**What it does:** Runs the autonomous strategy experiment loop for N iterations (default: 20).

**Why it exists:** This is the core self-improvement system. It automatically finds better strategy settings.

**When to use:** When you want to improve the trading strategy without manual intervention.

**What happens internally:**
1. Asks how many iterations to run
2. Validates that `strategy.yaml` is valid YAML
3. Establishes a baseline EVAL_SCORE
4. Creates (or switches to) an experiment git branch
5. For each iteration:
   - Forms a hypothesis (e.g., "lower RSI oversold from 22 to 21")
   - Edits `strategy.yaml`
   - Commits the change with a descriptive message
   - Runs the eval harness
   - If score improved: keeps the change
   - If score dropped: reverts with `git reset --hard HEAD~1`
   - Logs the result in `loops/results.tsv`
6. Summarises the session: best score, top changes, current config

---

#### `/backtest <SYMBOL> [DAYS]`

**Example:** `/backtest BTCUSDT 30`

**What it does:** Runs a simple RSI backtest over historical data.

**Why it exists:** Quick way to see how the RSI strategy would have performed recently.

**When to use:** When you want a quick historical performance check for a specific coin.

**What happens internally:**
1. Downloads daily candles for the specified period
2. Simulates buying when RSI < 30 and selling when RSI > 70
3. Tracks all trades, wins/losses, and portfolio value over time
4. Calculates total return, max drawdown, win rate
5. Compares against buy-and-hold (just buying and keeping)

---

#### `/bot-status`

**What it does:** Checks the health of all system components.

**Why it exists:** Before trading, you want to make sure everything is working.

**When to use:** When starting a session, or if something seems broken.

**What happens internally:**
1. Tests the Binance API connection (tries to fetch BTC price)
2. Tests the Fear & Greed API
3. Checks if API keys are configured
4. Confirms paper trading mode is active
5. Reports the status of each component (green = OK, red = error)

---

#### `/history`

**What it does:** Shows your recent paper trade history.

**Why it exists:** To review what trades you've made and their outcomes.

**When to use:** To review your trading performance, especially after running auto-trade.

**What happens internally:**
1. Loads trade history from the portfolio state file
2. Shows the last 20 trades in a table: time, symbol, side (BUY/SELL), amount, price
3. Claude summarises performance: total trades, wins vs losses, overall P&L

---

#### `/learnings`

**What it does:** Shows what the system has learned from trading, experiments, and bugs.

**Why it exists:** The knowledge base is the system's memory. This command lets you see what it knows.

**When to use:** When you want to understand what the system has tried, what worked, and what didn't.

**What happens internally:**
1. Loads entries from `data/knowledge.json`
2. Shows a summary: total entries and breakdown by category
3. Lists recent entries with their title, details, and tags
4. Categories include: strategy, trade, risk, market, bug, config
5. Also shows trade outcomes from `data/trade_outcomes.json` if available

---

## 9. Configuration Files

### `config/strategy.yaml` -- The Brain's Settings

This is the **only file** the autoresearch loop is allowed to modify. It controls how every trading strategy makes decisions.

**Structure:**

```yaml
indicators:           # Settings for technical indicators
  rsi:
    period: 17        # How many candles to look back (7-30)
    overbought: 69    # RSI above this = sell signal (60-85)
    oversold: 22      # RSI below this = buy signal (15-40)
  macd:
    fast: 12          # Fast EMA period (5-21)
    slow: 26          # Slow EMA period (15-50)
    signal: 9         # Signal line period (5-15)
  bollinger:
    period: 20        # Lookback for middle band (10-30)
    std: 1.5          # Width multiplier (1.5-3.0)

signal:
  min_confidence: 0.6 # Minimum confidence to generate a signal
  volume_filter: true # Require volume confirmation
  volume_multiplier: 1.5  # Volume must be 1.5x average

position_sizing:
  risk_per_trade_pct: 2.0   # Risk 2% of portfolio per trade
  stop_loss_vol_mult: 2.0   # Stop loss = 2x daily volatility below entry
  take_profit_vol_mult: 4.0 # Take profit = 4x daily volatility above entry

strategy_mode: "vwap"  # Which strategy the eval harness tests

# Strategy-specific settings follow (vwap, momentum, squeeze, etc.)
```

**How changes affect the system:**

| Change | Effect |
|--------|--------|
| Lower RSI oversold (e.g., 22 -> 18) | Fewer but higher-quality buy signals (only buys deep dips) |
| Raise RSI overbought (e.g., 69 -> 75) | Holds positions longer before selling |
| Increase VWAP deviation (e.g., 2.45 -> 3.0) | Only buys when price is further from fair value (fewer trades) |
| Decrease risk_per_trade_pct (e.g., 2.0 -> 1.0) | Smaller position sizes, lower risk per trade |
| Change strategy_mode | Completely different trading logic is used |

**Important:** Every parameter has bounds (shown in the comments). Going outside these bounds could cause the strategy to behave erratically. The autoresearch loop enforces these limits.

### `.env` -- Secrets and API Keys

```
BINANCE_API_KEY=your_key_here
BINANCE_SECRET_KEY=your_secret_here
PAPER_TRADING=true
NEWSAPI_KEY=optional_key
CRYPTOPANIC_API_KEY=optional_key
```

- **BINANCE_API_KEY / SECRET_KEY**: Required. These connect to Binance for live price data. You can use testnet keys (no real money access)
- **PAPER_TRADING=true**: This MUST stay true. The safety module enforces this
- **NEWSAPI_KEY / CRYPTOPANIC_API_KEY**: Optional. Enable news sentiment analysis

### `.mcp.json` -- MCP Server Configuration

Tells Claude Code which MCP servers to start:

```json
{
  "mcpServers": {
    "binance-mcp": {
      "command": "python",
      "args": ["-m", "src.mcp.binance_server"]
    },
    "trading-db-mcp": {
      "command": "python",
      "args": ["-m", "src.mcp.db_server"]
    }
  }
}
```

When Claude Code starts, it automatically launches these two servers, giving Claude direct access to market data and portfolio management.

### `.claude/settings.json` -- Permission Configuration

Controls what Claude Code is allowed to do without asking:

```json
{
  "permissions": {
    "allow": [
      "Bash(python -m src.cli *)",     // All CLI commands
      "Bash(python scripts/*)",         // Eval harness
      "Bash(git add *)",               // Git operations
      "Bash(git commit *)",
      ...
    ]
  }
}
```

This means Claude can run CLI commands, scripts, and git operations automatically. Anything not on this list requires your explicit approval.

### `loops/program.md` -- The Experiment Playbook

This file contains the exact instructions the autoresearch loop follows. It defines:
- The experiment process (hypothesis -> edit -> commit -> eval -> keep/revert)
- Parameter bounds (what values are allowed)
- The eval command to run
- Available strategies
- Stopping conditions (stop after 50 experiments with no improvement in the last 20)

### `loops/results.tsv` -- Experiment History

A tab-separated file logging every experiment ever run:

```
commit      eval_score  status   description
48b883a     2.6562      kept     RSI oversold 21->22 -- BTC 4->6 trades
874455a     3.7704      kept     VWAP reversion strategy: dev=2.5, window=24
b7f4db7     3.8112      kept     VWAP dev=2.45, os=44, win=24
```

This is the permanent record. It shows the evolution of the strategy over time and prevents repeating failed experiments.

---

## 10. Evaluation System

### What Is an Evaluation Score?

The EVAL_SCORE is a single number that answers: **"How good is this trading strategy?"**

It's like a school grade, but for trading strategies. A higher number means a better strategy.

### How It's Calculated

The formula has three layers:

**Layer 1: Per-Coin Score**
```
per_coin_score = sharpe_ratio * (1 - max_drawdown/100) * min(n_trades/10, 1.0)
```

Let's break this down:

- **Sharpe Ratio**: How much return you get per unit of risk. A Sharpe of 3.0 means you earned 3 units of return for every 1 unit of risk. Higher is better. Think of it as "bang for your buck."
  - Below 1.0 = mediocre
  - 1.0-2.0 = good
  - 2.0-3.0 = very good
  - Above 3.0 = excellent

- **Drawdown penalty**: `(1 - max_drawdown/100)`. If your worst loss was 10%, this becomes 0.90 (a 10% penalty). If it was 20%, it's 0.80 (a 20% penalty). This punishes strategies that risk large losses.

- **Trade count factor**: `min(n_trades/10, 1.0)`. If you made 10 or more trades, this is 1.0 (no penalty). If you made only 5 trades, this is 0.5 (50% penalty). This punishes strategies that rarely trade -- a strategy that only trades once might have been lucky.

**Layer 2: Coverage Factor**
```
coverage = number_of_coins_with_trades / total_coins
```
If your strategy only works on Bitcoin but does nothing on ETH, SOL, and BNB, the coverage is 0.25 (25%). This heavily penalises narrow strategies. A good strategy should work across multiple markets.

**Layer 3: Feedback Factor**
```
feedback = 1 + (live_win_rate - 0.5) * 0.2
```
This adjusts the score based on real paper trading performance. If your live win rate is 70%, you get a 4% bonus. If it's 30%, you get a 4% penalty. This only kicks in after 3 or more completed trades.

**Final Formula:**
```
EVAL_SCORE = mean(all per_coin_scores) * coverage * feedback
```

### Why It Matters

Without this score, you'd have no way to compare strategies objectively. It balances multiple goals:

- **High returns** (Sharpe ratio rewards this)
- **Low risk** (drawdown penalty punishes big losses)
- **Consistency** (trade count ensures the strategy actually trades)
- **Breadth** (coverage ensures it works on multiple coins)
- **Real-world performance** (feedback adjusts for live results)

A strategy that scores 3.81 (the current VWAP best) is meaningfully better than one scoring 2.65 (the best RSI) -- it earns more per unit of risk, across more coins, with lower drawdowns.

---

## 11. Running the Project Locally

### Prerequisites

You need the following installed on your computer:

1. **Python 3.10 or newer** -- the programming language
2. **Git** -- for version control and experiment tracking
3. **Claude Code** -- Anthropic's CLI tool (this is the interface)
4. **A Binance account** -- for market data API access (free testnet keys work)

### Step-by-Step Setup

**Step 1: Clone the repository**

Open your terminal and run:
```bash
git clone <repository-url>
cd crypto-bot
```

This downloads the entire project to your computer.

**Step 2: Install Python dependencies**

```bash
pip install -r requirements.txt
```

This installs all the libraries listed in Section 3 (Pandas, NumPy, Flask, CCXT, etc.).

**Step 3: Create your environment file**

Create a file called `.env` in the project root:
```bash
BINANCE_API_KEY=your_binance_api_key
BINANCE_SECRET_KEY=your_binance_secret_key
PAPER_TRADING=true
```

To get Binance testnet keys:
1. Go to https://testnet.binance.vision/
2. Log in with GitHub
3. Generate API keys
4. Copy the API Key and Secret Key into your `.env` file

These testnet keys give you access to live market data without any real money risk.

**Step 4: Verify the setup**

```bash
python -m src.cli status
```

You should see a table showing:
- binance_api: connected
- paper_trading: True
- btc_price: $XX,XXX.XX

If you see errors, check that your API keys are correct and your internet connection is working.

**Step 5: Start Claude Code**

```bash
claude
```

This launches Claude Code in your terminal. You're now ready to use all the slash commands.

### Quick Test

Try these commands to make sure everything works:

```
/bot-status           # Check all connections
/signal BTCUSDT       # Generate a Bitcoin signal
/scan                 # Scan all markets
/portfolio            # See your $100 starting balance
```

---

## 12. Claude Configuration

### What Is Configured in Claude Code Settings

Claude Code has several configuration layers that control how it interacts with this project:

#### Permission Settings (`.claude/settings.json`)

This file tells Claude what it's allowed to do automatically (without asking you):

- **Python commands**: All CLI commands (`python -m src.cli *`) and scripts (`python scripts/*`) run automatically
- **Git operations**: `git add`, `git commit`, `git checkout`, `git reset`, `git log`, `git status`, `git push` are all pre-approved
- **Utility commands**: `ls`, `cat`, `grep`, `echo`, `mkdir` for file exploration

Anything NOT on this list will prompt you for approval before Claude runs it. This is a safety mechanism.

#### Slash Commands (`.claude/commands/`)

Each `.md` file in this directory creates a slash command:
- `analyze.md` creates `/analyze`
- `signal.md` creates `/signal`
- `trade.md` creates `/trade`
- etc.

These files contain the instructions Claude follows when you invoke a command. They specify what CLI command to run, how to interpret the results, and what to tell you.

#### Custom Agents (`.claude/agents/`)

Two specialised agents are configured:

**Market Analyst Agent** (`market-analyst/AGENT.md`):
- Uses the **Haiku** model (faster, cheaper) since it only needs to read data
- Has access to: Read, Grep, Glob, Bash tools
- Can run: analyze, signal, risk, and status commands
- **Cannot** execute trades or modify files
- Outputs structured analysis: price action, technicals, sentiment, risk, outlook
- Maximum 5 turns per conversation

**Trade Executor Agent** (`trade-executor/AGENT.md`):
- Uses the **Sonnet** model (more capable) for trade decisions
- Has access to: Read, Bash tools only
- Can run: trade, portfolio, risk, and history commands
- Has strict safety rules: must run risk assessment first, must confirm with user, max $1,000 per order
- Maximum 8 turns per conversation

### How the Project Integrates with Claude

Claude Code is not just a tool that runs scripts -- it IS the trading interface. Here's how:

1. **MCP Servers**: When Claude Code starts, it launches two background servers (binance-mcp and trading-db-mcp) that give Claude direct access to market data and portfolio management through structured tool calls.

2. **Tool Calling**: Claude can call tools like `get_ticker("BTCUSDT")`, `get_technical_indicators("ETHUSDT")`, or `execute_paper_trade("BTCUSDT", "BUY", 25)` directly, without going through the CLI.

3. **Reasoning**: Claude analyses the data returned by these tools, applies its knowledge of trading and markets, and provides recommendations in plain language.

4. **Memory**: Claude maintains a memory system (in `.claude/projects/`) that persists across conversations, remembering your preferences, strategy results, and project context.

### Where to Place API Keys

API keys go in the `.env` file at the project root (`/home/amo/Documents/crypto-bot/.env`):

```
BINANCE_API_KEY=your_key_here        # Required: Binance API key
BINANCE_SECRET_KEY=your_secret_here  # Required: Binance secret key
PAPER_TRADING=true                   # Required: MUST be true
NEWSAPI_KEY=your_key_here            # Optional: NewsAPI.org key
CRYPTOPANIC_API_KEY=your_key_here    # Optional: CryptoPanic key
```

**For Binance testnet keys** (recommended for safety):
1. Visit https://testnet.binance.vision/
2. Log in via GitHub
3. Click "Generate HMAC_SHA256 Key"
4. Copy both keys into your `.env`

Testnet keys access real market data but cannot trade real money -- perfect for this paper trading system.

---

## 13. Practical Walkthrough

### Full Example: From Installation to Your First Trade

#### Step 1: Set Up

```bash
# Clone and install
git clone <repo-url>
cd crypto-bot
pip install -r requirements.txt

# Create .env file with your Binance testnet keys
echo "BINANCE_API_KEY=your_key" > .env
echo "BINANCE_SECRET_KEY=your_secret" >> .env
echo "PAPER_TRADING=true" >> .env

# Start Claude Code
claude
```

#### Step 2: Check Everything Works

Type in Claude Code:
```
/bot-status
```

Expected output: All systems green, BTC price showing.

#### Step 3: Scan the Market

```
/scan
```

You'll see a table of 4 coins with their signals. Let's say ETH shows a BUY signal with 62% confidence.

#### Step 4: Dig Deeper

```
/analyze ETHUSDT
```

Review the full analysis: RSI, MACD, Bollinger Bands, news sentiment, Fear & Greed.

#### Step 5: Check the Risk

```
/risk ETHUSDT
```

See the risk level, volatility, suggested position size, and stop/take profit levels.

#### Step 6: Make a Trade

```
/trade BUY ETHUSDT 20
```

Claude will show you the trade details and ask for confirmation. Confirm, and you'll see:
- Fill price (with slippage)
- Quantity of ETH you "bought"
- Fees charged
- Remaining cash balance

#### Step 7: Check Your Portfolio

```
/portfolio
```

You'll see your $80 cash, $20 ETH position, and overall P&L.

#### Step 8: Run Auto-Experiments

```
/autoexp 10
```

Watch as Claude automatically runs 10 experiments, testing different strategy settings, keeping what works, reverting what doesn't.

#### Step 9: Start the Dashboard

```
python -m src.cli dashboard
```

Open `http://localhost:5050` in your browser to see everything visually.

#### Step 10: Run Auto-Trading

```
/trade  (then tell Claude: "run auto-trade for 5 iterations in dry-run mode")
```

Or directly:
```bash
python -m src.cli auto-trade --iterations 5 --dry-run
```

This shows you what the system WOULD trade without actually executing.

---

## 14. Prompt Library - Training Claude to Improve and Trade Daily

These are the prompts you can use with Claude Code to operate the trading system effectively. Copy and paste these directly into your Claude Code terminal.

### Daily Trading Prompts

**Morning Market Scan:**
```
Scan all markets and give me a ranked summary of the best trading opportunities right now.
Show me which coins have the strongest signals and why.
```

**Deep Analysis:**
```
Give me a complete analysis of BTCUSDT. Include RSI, MACD, Bollinger Bands,
volume analysis, Fear & Greed, and any relevant news. What's your recommendation?
```

**Execute a Trade:**
```
/trade BUY ETHUSDT 25
```

**Portfolio Check:**
```
Show me my portfolio. For each position, explain whether I should hold or sell
based on current market conditions.
```

**Risk Check Before Trading:**
```
Before I trade SOLUSDT, run a risk assessment. Tell me the recommended position
size, stop loss, and whether now is a good time to enter.
```

### Strategy Improvement Prompts

**Run Experiments:**
```
/autoexp 20
```

**Compare All Strategies:**
```
Run a comparison of all 8 trading strategies over the last 90 days.
Show me which one performs best and why.
```

**Targeted Strategy Tuning:**
```
The VWAP strategy is our best performer at 3.81. Run 10 experiments focusing
only on VWAP parameters: try different deviation percentages, window sizes,
and RSI confirmation thresholds. Keep only improvements.
```

**Explore New Approaches:**
```
We've been tuning VWAP for a while. I want you to think creatively about
new trading approaches. What strategies haven't we tested yet? Propose 3
experiments with hypotheses for why they might work.
```

**Review Experiment History:**
```
Read loops/results.tsv and summarise what we've learned.
What were the top 5 most impactful changes? What patterns do you see
in what works vs what doesn't?
```

### System Management Prompts

**Health Check:**
```
/bot-status
```

**Start Auto-Trading:**
```
Start the auto-trader with 50% minimum confidence, 5-minute scan interval,
for 10 iterations. Use dry-run mode first so I can review the signals
before enabling live paper trading.
```

**Auto-Discover Mode:**
```
Run the auto-trader with --discover mode to automatically find the best
trading pairs across all of Binance. Scan the top 8 pairs by volume
and momentum.
```

**Reset Portfolio:**
```
Reset my portfolio to $100 fresh. I want to start a new paper trading
session with clean data.
```

**Check Learnings:**
```
/learnings
Show me everything the system has learned. What strategies work?
What should we avoid? What are the most important insights?
```

**Dashboard:**
```
Start the web dashboard so I can monitor everything visually.
```

### Advanced Prompts

**Backtest a Specific Scenario:**
```
Backtest BTCUSDT over the last 60 days. Then backtest ETHUSDT over the
same period. Compare the results -- which coin was more profitable
with our current strategy?
```

**Multi-Coin Strategy Validation:**
```
Run the eval harness with the VWAP strategy on 8 coins instead of 4.
Add XRP, DOGE, ADA, and AVAX. Does the strategy hold up on altcoins
or does it only work on large caps?
```

**Analyse a Losing Trade:**
```
Look at my most recent SELL trade. What signals triggered the entry?
What was the market doing when I bought? Why did it lose money?
What can we learn from this?
```

**Full Session Workflow:**
```
Let's do a complete trading session:
1. Check system status
2. Scan all markets
3. Deep-dive the top 2 opportunities
4. If any strong signals, suggest trades with position sizing
5. Run 5 autoexp iterations to try to improve our strategy
6. Show me the updated results
```

**Strategy Mode Comparison:**
```
I want to understand which strategy mode is best right now.
Run: python scripts/eval_harness.py --days 90 --compare-all
Then explain the results to me like I'm a beginner.
Which strategy should we be using and why?
```

---

*This handbook covers the complete Crypto Trading Bot system. For technical details, see `CLAUDE.md`. For experiment instructions, see `loops/program.md`. For strategy settings, see `config/strategy.yaml`.*
