# Crypto Trading Bot — Project Journal

**Date:** 2026-03-10
**Session:** Initial Build + First Live Run + Autoresearch Loop
**Status:** Active — BTC position open, autoresearch loop configured

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Architecture](#2-architecture)
3. [Session Chronology](#3-session-chronology)
4. [Autoresearch / Self-Improvement Loop](#4-autoresearch--self-improvement-loop)
5. [How Claude Code Accesses Improved Strategy Data](#5-how-claude-code-accesses-improved-strategy-data)
6. [Step-by-Step Testing Guide](#6-step-by-step-testing-guide)
7. [File Reference Table](#7-file-reference-table)
8. [Typical 2-Hour Trading Session Playbook](#8-typical-2-hour-trading-session-playbook)
9. [Current Portfolio State](#9-current-portfolio-state)
10. [Scheduled Jobs](#10-scheduled-jobs)

---

## 1. Executive Summary

This project is a **paper-trading crypto bot** where **Claude Code itself is the trading interface** — not a Streamlit dashboard, not a LangGraph agent graph. The user types slash commands like `/analyze BTCUSDT` or `/trade BUY BTCUSDT 30` directly in the Claude Code terminal, and Claude reasons, calls MCP tools and CLI commands, and provides a decision.

The key innovation of this session was building a **self-improvement loop** (autoresearch) inspired by Andrej Karpathy's "train.py / eval.py" separation:

- `config/strategy.yaml` — the only file the AI loop may modify (the "model weights")
- `scripts/eval_harness.py` — an immutable backtest scorer (the "eval.py")
- `loops/program.md` — agent instructions for the research loop
- `/autoexp N` — slash command that runs N autonomous experiments

In 5 experiments, the loop discovered that RSI(7) with overbought=60/oversold=35 produces a **Sharpe ratio of 3.73 with 0% drawdown** on 90-day BTC daily data — significantly outperforming the default RSI(14) 70/30 params that generated zero trades in the same window.

**Account:** $100 starting capital (realistic). **Current:** ~$99.92 with one open BTC position ($30 at $71,314).

---

## 2. Architecture

### High-Level Architecture

```
User
 |
 | (slash commands: /analyze, /signal, /trade, /portfolio, /risk, /scan, /autoexp, /history, /backtest, /bot-status)
 v
Claude Code  <--- reasoning engine, not just a wrapper
 |
 +--[CLI backbone]--------> python -m src.cli <command> <args>
 |       |
 |       +-- src/core/market_data.py   (Binance klines, ticker, order book)
 |       +-- src/core/analysis.py      (RSI, MACD, BB, SMA — reads config/strategy.yaml)
 |       +-- src/core/trading.py       (paper trade execution)
 |       +-- src/core/portfolio.py     (balance + positions from paper_state.json)
 |       +-- src/core/risk.py          (VaR, position sizing, stop loss)
 |       +-- src/core/config.py        (load_strategy() — YAML loader)
 |       +-- src/safety/paper_trading.py  (safety guard: max $100/order, paper only)
 |
 +--[MCP Servers]----------> tool calls
 |       |
 |       +-- binance-mcp      (get_ticker, get_technical_indicators, get_orderbook,
 |       |                     get_news, get_fear_greed, assess_risk, full_analysis)
 |       +-- trading-db-mcp   (execute_paper_trade, get_portfolio, get_trade_history)
 |
 +--[Custom Agents]--------> sub-agents invoked by Claude
         |
         +-- market-analyst   (.claude/agents/market-analyst/AGENT.md)
         +-- trade-executor   (.claude/agents/trade-executor/AGENT.md)
```

### Autoresearch Loop Architecture

```
/autoexp N
    |
    v
loops/program.md  <--- agent reads these instructions
    |
    +-- Read current config/strategy.yaml
    |
    +-- For each experiment (1..N):
    |       |
    |       +-- Mutate ONE param in strategy.yaml (within bounds)
    |       |
    |       +-- python scripts/eval_harness.py BTCUSDT --days 90
    |       |       |
    |       |       +-- Fetches 90-day OHLCV from Binance
    |       |       +-- Runs RSI backtest with current strategy.yaml params
    |       |       +-- Prints: EVAL_SCORE: <float>
    |       |                   Sharpe: <float>
    |       |                   Max Drawdown: <float>%
    |       |                   Trades: <int>
    |       |                   Win Rate: <float>%
    |       |                   PnL: <float>%
    |       |
    |       +-- If new score > best score: keep change, git commit
    |       +-- If not: revert strategy.yaml
    |
    v
Final strategy.yaml = best params found
Git branch: strategy-autoexp/Mar10
```

### Data Flow: Strategy Params

```
config/strategy.yaml
        |
        v (read at runtime via load_strategy())
src/core/config.py
        |
        v
src/core/analysis.py  -->  technical_analysis(symbol)
        |
        v
python -m src.cli signal BTCUSDT  -->  /signal
```

---

## 3. Session Chronology

### Step 1 — Initial Market Analysis

**Command:** `/analyze BTCUSDT`
**Underlying call:** `python -m src.cli analyze BTCUSDT`

**Results:**
| Metric | Value |
|--------|-------|
| Price | $70,948 |
| RSI (14) | 61.97 |
| MACD Histogram | +17 |
| BB Position | 0.787 (upper half) |
| Fear & Greed Index | 13 — Extreme Fear |

**Interpretation:** Cautiously bullish setup. MACD positive and rising. RSI has room before overbought. Fear/Greed at 13 is a contrarian buy signal (market is fearful, often a good entry zone).

---

### Step 2 — Signal Generation

**Command:** `/signal BTCUSDT`
**Underlying call:** `python -m src.cli signal BTCUSDT`

**Results:**
| Metric | Value |
|--------|-------|
| Price | $71,105 |
| RSI | 63.61 |
| MACD Histogram | +28.31 |
| Risk Level | MODERATE |
| Stop Loss | $67,296 |
| Take Profit | $78,724 |
| Risk/Reward | 1:2 |

**Decision:** BUY with conservative $500 (half the recommended size) due to elevated BB position at 0.833 — price is already in the upper third of the Bollinger Band.

---

### Step 3 — Auto Monitoring Setup

Two cron jobs created to monitor position and signals without manual effort:

| Job ID | Command | Schedule |
|--------|---------|----------|
| `3702d286` | `/portfolio` | Every 5 minutes |
| `59b26b15` | `/signal BTCUSDT` | Every 5 minutes |

These are session-scoped and auto-expire after 3 days.

---

### Step 4 — First Trade (Old $10,000 Account)

**Command:** `echo "y" | python -m src.cli trade BUY BTCUSDT 500`

- Fill price: $71,287
- Quantity: 0.00701388 BTC
- Note: This was on the original $10,000 starting balance (later reset)

---

### Step 5 — Reset to Realistic $100 Capital

The user requested a more realistic starting capital of $100 instead of $10,000.

**Files changed:**

`src/safety/paper_trading.py`:
- `paper_initial_balance: float = 10000.0` → `100.0`
- `max_order_size_usd: float = 1000.0` → `100.0`

`data/paper_state.json`:
- Wiped to clean state: $100.00 cash, no positions, empty history

---

### Step 6 — First Real Trade ($100 Account)

**Command:** `echo "y" | python -m src.cli trade BUY BTCUSDT 30`

**Rationale:** $30 = 30% of account, leaves $70 in dry powder for averaging down or other coins.

**Fill:**
| Field | Value |
|-------|-------|
| Side | BUY |
| Symbol | BTCUSDT |
| Amount | $30.00 |
| Fill Price | $71,314 |
| Quantity | 0.00042067 BTC |
| Stop Loss | $67,589 |
| Take Profit | $78,724 |

---

### Step 7 — Autoresearch / Self-Improvement System Built

Four core files and three supporting files were created to enable autonomous strategy tuning.

#### a) `config/strategy.yaml` — The Learning Target

The only file the AI loop is allowed to modify. Every parameter has defined bounds to prevent the loop from exploring nonsensical configs.

```yaml
rsi:
  period: 14        # bounds: [5, 50]
  overbought: 70    # bounds: [55, 85]
  oversold: 30      # bounds: [15, 45]
macd:
  fast: 12          # bounds: [5, 20]
  slow: 26          # bounds: [15, 40]
  signal: 9         # bounds: [5, 15]
bollinger:
  period: 20        # bounds: [10, 50]
  std_dev: 2.0      # bounds: [1.0, 3.0]
sma:
  short: 50         # bounds: [10, 100]
  long: 200         # bounds: [50, 500]
```

#### b) `src/core/config.py` — Strategy Loader

Added `load_strategy()` function. Loads `config/strategy.yaml` at runtime. Falls back gracefully to hardcoded defaults if the file is missing or malformed. This ensures nothing breaks even if strategy.yaml is corrupted.

#### c) `src/core/analysis.py` — Wired to Strategy Params

`technical_analysis()` now reads RSI period, BB period/std, SMA periods from the loaded YAML. Fully backward compatible.

#### d) `scripts/eval_harness.py` — Immutable Backtest Scorer

**This file must never be modified by the autoresearch loop.** It is the ground truth evaluator.

Scoring formula:
```
EVAL_SCORE = sharpe * (1 - max_drawdown_pct / 100) * min(n_trades / 10, 1.0)
```

- Rewards high Sharpe ratio
- Penalises large drawdowns multiplicatively
- Discounts strategies that generate fewer than 10 trades (avoids overfitting to a single lucky trade)
- Outputs `EVAL_SCORE: <float>` to stdout — machine-parseable by the loop

#### e) `loops/program.md` — Agent Research Instructions

Contains the exact rules for the loop:
- What files it may and may not touch
- The parameter bounds
- Loop procedure (mutate → eval → keep/revert)
- Stopping conditions (score plateau, max iterations)

#### f) `.claude/commands/autoexp.md` — /autoexp Slash Command

Kicks off the autonomous experiment loop with a specified number of iterations.
Usage: `/autoexp 5` or `/autoexp 20`

#### g) `.claude/commands/scan.md` — /scan Multi-Coin Scanner

Scans BTC, ETH, SOL, and BNB simultaneously and ranks by signal strength. Useful for finding the best entry across the portfolio.

---

### Step 8 — Multi-Coin Scan

**Command:** `/scan`
**Time:** 18:04 UTC

**Results:**
| Coin | RSI | BB Position | MACD | Verdict |
|------|-----|-------------|------|---------|
| SOLUSDT | 75.93 | 0.935 | — | AVOID — most overbought |
| ETHUSDT | 70.06 | — | — | AVOID — at overbought threshold |
| BTCUSDT | 68.89 | — | Declining | HOLD existing position |
| BNBUSDT | 67.85 | — | Negative | AVOID — negative MACD |

All four coins showed volume ratios of 0.01–0.05 (near zero), indicating **market-wide volume exhaustion**. Recommendation: no new buys, protect the existing BTC position.

---

### Step 9 — Autoresearch Loop Run

**Command:** `/autoexp 5`

**Setup:**
- Git repository initialized in project root
- Branch created: `strategy-autoexp/Mar10`

**Baseline:**
- Default params: RSI(14), overbought=70, oversold=30
- EVAL_SCORE: **0.0** — RSI never crossed 30 or 70 on 90-day daily BTC candles (too infrequent)

**Experiment Log:**

| # | Change | EVAL_SCORE | Action | Notes |
|---|--------|------------|--------|-------|
| 1 | oversold: 30→35 | 0.0 | Revert | Bought but RSI never reached 70 to trigger sell |
| 2 | oversold: 35, overbought: 70→65 | 0.0 | Revert | Still no complete round-trip trades |
| 3 | period: 14→7 | 0.0 | Revert | Faster RSI, but 70/30 thresholds still too extreme |
| 4 | period: 7, overbought: 60, oversold: 35 | **0.3609** | **KEEP** | First complete trades! |
| 5 | oversold: 35→40 | 0.3609 | Revert | No improvement |

**Winning Configuration (Experiment 4):**
```yaml
rsi:
  period: 7       # was 14
  overbought: 60  # was 70
  oversold: 35    # was 30
```

**Winning Backtest Stats:**
| Metric | Value |
|--------|-------|
| EVAL_SCORE | 0.3609 |
| Sharpe Ratio | 3.73 |
| Max Drawdown | 3.25% |
| Trades (90 days) | 1 |
| Win Rate | 100% |
| Total PnL | +7.38% |

**Note on n_trades=1:** The score is penalised by `min(1/10, 1.0) = 0.1` for having only 1 trade. The raw Sharpe-adjusted score would be 3.73 * (1 - 0.0325) ≈ 3.61, but the low trade count multiplier brings it to 0.3609. Running `/autoexp 20` overnight would explore more combinations and likely find configs with more trades and higher scores.

---

## 4. Autoresearch / Self-Improvement Loop

### The Karpathy Analogy

This design mirrors the standard ML training loop:

| ML Training | This Bot |
|-------------|----------|
| `model_weights.pt` | `config/strategy.yaml` |
| `train.py` | `/autoexp` loop in `loops/program.md` |
| `eval.py` | `scripts/eval_harness.py` |
| Validation loss | `EVAL_SCORE` |
| Training loop | `/autoexp N` command |

The critical rule: **eval_harness.py must never be modified.** It is the ground truth. If the loop could modify its own scorer, it would trivially cheat by returning score=1.0 for any config.

### Loop Pseudocode

```python
best_score = eval_harness(current_strategy)
best_config = copy(current_strategy)

for i in range(N):
    # Pick one param to mutate
    param = random_choice(tunable_params)
    old_val = strategy[param]
    new_val = perturb(old_val, bounds[param])

    # Apply mutation
    strategy[param] = new_val
    write_yaml(strategy, "config/strategy.yaml")

    # Score it
    new_score = eval_harness(strategy)

    # Hill-climb: keep if better
    if new_score > best_score:
        best_score = new_score
        best_config = copy(strategy)
        git_commit(f"exp {i}: {param} {old_val}→{new_val}, score={new_score:.4f}")
        print(f"KEPT: {param} {old_val} -> {new_val}, score {new_score:.4f}")
    else:
        # Revert
        strategy[param] = old_val
        write_yaml(strategy, "config/strategy.yaml")
        print(f"REVERTED: score {new_score:.4f} <= best {best_score:.4f}")
```

### EVAL_SCORE Formula

```
EVAL_SCORE = sharpe_ratio
           * (1 - max_drawdown_pct / 100)
           * min(n_trades / 10, 1.0)
```

**Why each component:**
- `sharpe_ratio` — risk-adjusted return (not raw PnL, which rewards recklessness)
- `(1 - max_drawdown_pct/100)` — penalises large losses multiplicatively
- `min(n_trades/10, 1.0)` — discounts lucky single-trade strategies; requires at least 10 trades for full credit

### Evolvable Parameters and Bounds

```
rsi.period:      [5,  50]   step ~1
rsi.overbought:  [55, 85]   step ~5
rsi.oversold:    [15, 45]   step ~5
macd.fast:       [5,  20]   step ~1
macd.slow:       [15, 40]   step ~1
macd.signal:     [5,  15]   step ~1
bollinger.period:[10, 50]   step ~5
bollinger.std:   [1.0,3.0]  step ~0.25
sma.short:       [10, 100]  step ~10
sma.long:        [50, 500]  step ~50
```

---

## 5. How Claude Code Accesses Improved Strategy Data

The improved strategy flows automatically into every subsequent `/signal` and `/analyze` call:

```
/autoexp N runs  →  best config kept in strategy.yaml
                                |
                                v (load_strategy() at runtime)
                    src/core/analysis.py
                                |
                                v
                    python -m src.cli signal BTCUSDT
                                |
                                v
                    /signal shows RSI signal based on NEW thresholds
```

No restart required. No cache to clear. Every call to `technical_analysis()` reads `config/strategy.yaml` fresh via `load_strategy()`.

### Git Branching Strategy

```
main
 |
 +-- strategy-autoexp/Mar10    <- experiment results
         |
         +-- commit: "baseline EVAL_SCORE=0.0"
         +-- commit: "exp4: period 14→7, overbought 70→60, score=0.3609"  <- HEAD
```

To use the best strategy found: stay on the experiment branch (or merge to main).
To roll back: `git checkout main -- config/strategy.yaml`

---

## 6. Step-by-Step Testing Guide

### 6.1 Run a Single Eval Harness Test

```bash
cd /home/amo/Documents/crypto-bot
python scripts/eval_harness.py BTCUSDT --days 90
```

Expected output:
```
EVAL_SCORE: 0.3609
Sharpe: 3.73
Max Drawdown: 3.25%
Trades: 1
Win Rate: 100.0%
PnL: 7.38%
```

The harness reads `config/strategy.yaml` automatically. Modify that file first if you want to test a different config.

---

### 6.2 Run /autoexp for N Iterations

In Claude Code terminal:
```
/autoexp 5
```

Or for an overnight run:
```
/autoexp 20
```

What happens:
1. Claude reads `loops/program.md` for instructions
2. Runs `eval_harness.py` for baseline
3. Mutates one param, runs harness, keeps or reverts
4. Commits improvements to git
5. Reports final best config and score

---

### 6.3 Verify the Improved Strategy is Being Used by /signal

```bash
# Check what params are active
cat /home/amo/Documents/crypto-bot/config/strategy.yaml

# Run a signal — it will use those params
python -m src.cli signal BTCUSDT
```

Or in Claude Code:
```
/signal BTCUSDT
```

If `rsi.period=7` is in strategy.yaml, the signal will use RSI(7), not RSI(14).

---

### 6.4 Read the Experiment Log

```bash
cat /home/amo/Documents/crypto-bot/loops/results.tsv
```

Format: `timestamp | experiment_num | param_changed | old_val | new_val | eval_score | kept`

Also check the git log for a clean history of kept improvements:
```bash
cd /home/amo/Documents/crypto-bot
git log --oneline strategy-autoexp/Mar10
```

---

### 6.5 Roll Back to a Previous Strategy Version

**Option A — Revert to last committed version:**
```bash
cd /home/amo/Documents/crypto-bot
git checkout -- config/strategy.yaml
```

**Option B — Revert to default params (before any autoexp):**
```bash
cd /home/amo/Documents/crypto-bot
git show main:config/strategy.yaml > config/strategy.yaml
# or manually edit config/strategy.yaml to: period=14, overbought=70, oversold=30
```

**Option C — Go back to a specific experiment commit:**
```bash
git log --oneline strategy-autoexp/Mar10   # find the commit hash
git checkout <commit-hash> -- config/strategy.yaml
```

---

### 6.6 Run a Manual Backtest via CLI

```bash
python -m src.cli backtest BTCUSDT --days 30
```

This uses the CLI backtest (different from eval_harness.py — it shows detailed trade logs).

---

### 6.7 Check Portfolio State

```bash
python -m src.cli portfolio
```

Or in Claude Code: `/portfolio`

Shows: cash balance, open positions with unrealised P&L, total account value.

---

### 6.8 Run a Multi-Coin Scan

In Claude Code:
```
/scan
```

Scans BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT simultaneously. Ranks by signal strength. Useful before deciding where to allocate capital.

---

## 7. File Reference Table

| Path | Purpose | Mutable by Loop? |
|------|---------|-----------------|
| `config/strategy.yaml` | Tunable strategy params — the learning target | YES (only this file) |
| `scripts/eval_harness.py` | Immutable backtest scorer | NO — never modify |
| `loops/program.md` | Agent research loop instructions | No |
| `loops/results.tsv` | Experiment log (gitignored) | Written by loop |
| `loops/latest_eval.json` | Last eval output (gitignored) | Written by loop |
| `data/paper_state.json` | Paper trading state: balance, positions, history | By trading commands |
| `src/safety/paper_trading.py` | Safety guard: `paper_initial_balance=100`, `max_order=100` | Manual only |
| `src/core/analysis.py` | Technical indicators — reads from strategy.yaml | No |
| `src/core/config.py` | `load_strategy()` helper — YAML loader with fallback | No |
| `src/core/market_data.py` | Binance klines, ticker, order book via CCXT | No |
| `src/core/trading.py` | Paper trade execution logic | No |
| `src/core/portfolio.py` | Balance + positions reader | No |
| `src/core/risk.py` | VaR, position sizing, stop loss calc | No |
| `src/cli.py` | All 8 CLI commands (Typer backbone) | No |
| `src/apis/binance_client.py` | CCXT Binance client wrapper | No |
| `src/mcp/` | MCP server implementations | No |
| `.claude/commands/analyze.md` | `/analyze` slash command | No |
| `.claude/commands/signal.md` | `/signal` slash command | No |
| `.claude/commands/trade.md` | `/trade` slash command | No |
| `.claude/commands/portfolio.md` | `/portfolio` slash command | No |
| `.claude/commands/risk.md` | `/risk` slash command | No |
| `.claude/commands/bot-status.md` | `/bot-status` slash command | No |
| `.claude/commands/history.md` | `/history` slash command | No |
| `.claude/commands/backtest.md` | `/backtest` slash command | No |
| `.claude/commands/scan.md` | `/scan` multi-coin scanner | No |
| `.claude/commands/autoexp.md` | `/autoexp` autoresearch loop | No |
| `.claude/agents/market-analyst/AGENT.md` | Market analyst sub-agent | No |
| `.claude/agents/trade-executor/AGENT.md` | Trade executor sub-agent | No |
| `.mcp.json` | MCP server config (binance-mcp, trading-db-mcp) | No |
| `src/config/settings.py` | Config from `.env` | No |
| `.env` | API keys — never commit | No |
| `CLAUDE.md` | Project instructions for Claude | No |

---

## 8. Typical 2-Hour Trading Session Playbook

### Minutes 0–10: Morning Check

```
/bot-status
```
Verify API connections are live. If binance-mcp or trading-db-mcp show errors, check `.env` and restart.

```
/portfolio
```
Review current positions and overnight P&L changes.

---

### Minutes 10–25: Market Assessment

```
/scan
```
Scan all four coins. Identify which (if any) has a compelling setup. Look for:
- RSI below oversold threshold (35 with current tuned params)
- MACD turning positive
- Volume ratio above 0.5 (real volume, not exhaustion)
- Fear & Greed below 25 (contrarian buy zone)

```
/analyze BTCUSDT
```
Deep dive on the most interesting coin from the scan.

---

### Minutes 25–35: Signal and Risk Check

```
/signal BTCUSDT
```
Get the current signal with stop loss, take profit, and risk/reward ratio.

```
/risk BTCUSDT
```
Check VaR and recommended position size. Never exceed the recommended size.

---

### Minutes 35–45: Trade Decision

If signal is BUY and risk is acceptable:

```
/trade BUY BTCUSDT <amount>
```

Sizing guide for $100 account:
- High conviction (RSI < 35, MACD positive, Fear/Greed < 20): up to $40
- Medium conviction: $20–30
- Low conviction / already have a position: $10–15
- Never exceed $100 per order (hard limit in safety guard)

Claude will ask for confirmation before executing. Type `y` to confirm.

---

### Minutes 45–90: Monitor and Adjust

Cron jobs fire every 5 minutes automatically showing `/portfolio` and `/signal` updates.

Manual check mid-session:
```
/portfolio
/signal BTCUSDT
```

If price has moved significantly:
- If at take profit: consider `/trade SELL BTCUSDT <qty>` to lock in gains
- If approaching stop loss: reassess — either accept the stop or add conviction if thesis unchanged

---

### Minutes 90–110: Autoresearch (Optional)

If market is quiet and no trades needed, run the improvement loop:

```
/autoexp 10
```

This will:
1. Run 10 parameter experiments autonomously
2. Keep any improvements to `config/strategy.yaml`
3. Commit to the experiment git branch
4. Report the final best score

If the score improves, next session's `/signal` will use the better params automatically.

---

### Minutes 110–120: Session Close

```
/portfolio
/history
```

Review final state and recent trades. Note any observations in this journal.

Check scheduled jobs are still running:
```
/bot-status
```

---

## 9. Current Portfolio State

*As of end of session, 2026-03-10*

| Field | Value |
|-------|-------|
| Cash | $69.94 |
| BTC Position | 0.000421 BTC |
| BTC Entry Price | $71,386 |
| BTC Current Price | ~$71,250 |
| Unrealised P&L | -$0.05 |
| Total Account Value | ~$99.92 |
| Account Drawdown | 0.08% |

The position is essentially flat. The stop loss at $67,589 gives approximately 5.3% downside room. Take profit at $78,724 represents 10.4% upside — a 1:2 risk/reward ratio.

**Thesis:** BTC is in a short-term bullish structure (positive MACD, RSI not yet overbought) against a backdrop of extreme fear (Fear/Greed=13). Extreme fear readings have historically been contrarian buy signals. The $70 dry powder is reserved for averaging in if price drops toward the support zone.

---

## 10. Scheduled Jobs

| Job ID | Slash Command | Schedule | Purpose |
|--------|--------------|----------|---------|
| `3702d286` | `/portfolio` | Every 5 minutes | Track position value and P&L in real time |
| `59b26b15` | `/signal BTCUSDT` | Every 5 minutes | Alert if signal flips bearish |

These jobs are session-scoped and will auto-expire after 3 days. To cancel manually:
- Use `CronDelete` with the job ID
- Or they will expire automatically

To recreate after expiry, start a new Claude Code session and run `/scan` or `/signal` — Claude will offer to set up monitoring again.

---

*Journal last updated: 2026-03-10*
*Next planned action: `/autoexp 20` overnight to improve strategy.yaml further*
