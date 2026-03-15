# Trading Strategy Autoresearch — program.md
# Human edits this file. The agent reads it and follows it exactly.

## Your role
You are an autonomous trading strategy researcher running inside Claude Code.
Your job is to improve the EVAL_SCORE of this paper-trading crypto bot by modifying
`config/strategy.yaml` one experiment at a time.

EVAL_SCORE = mean(per-coin scores) * coverage_factor * feedback_factor
  per-coin = sharpe * (1 - drawdown/100) * min(n_trades/10, 1.0)
  coverage = fraction of coins with ≥1 trade (penalises BTC-only strategies)
  feedback = 1 + (live_win_rate - 0.5) * 0.2  (±10%, needs ≥3 live trades)
Higher is better. Rewards Sharpe, penalises drawdown, discounts low trade counts.

## Setup (first iteration only)
1. Create branch: `git checkout -b strategy-autoexp/$(date +%b%d)` (init git first if needed: `git init && git add -A && git commit -m "baseline"`)
2. Read: CLAUDE.md, loops/program.md (this file), config/strategy.yaml, scripts/eval_harness.py (do not modify)
3. Establish baseline: run the eval command below, record in loops/results.tsv
4. Begin experimenting.

## Eval command (always the same)
```bash
python scripts/eval_harness.py --days 90 --timeframe 1h --output-json loops/latest_eval.json > loops/run.log 2>&1
grep "^EVAL_SCORE:" loops/run.log
```

The harness reads `strategy_mode` from strategy.yaml to decide which strategy to backtest.
You can also override via `--strategy <mode>` CLI flag.

Available strategies: rsi, ensemble, multi_confirm, momentum, squeeze, vwap, vwap_rsi, squeeze_vwap

To compare all strategies at once:
```bash
python scripts/eval_harness.py --days 90 --timeframe 1h --compare-all
```

Tests all 4 coins: BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT on 1h candles.

## Experiment loop (repeat)
For each iteration:
1. **Hypothesis** — one small, coherent change to `config/strategy.yaml`.
   Examples: change strategy_mode, tune VWAP deviation, adjust RSI thresholds,
   change ensemble weights, try different momentum breakout period.
   Document reasoning in the commit message.
2. **Apply** — edit `config/strategy.yaml` ONLY.
3. **Commit**:
   ```bash
   git add config/strategy.yaml
   git commit -m "exp: <what you changed and why>"
   ```
4. **Eval** — run eval command above (always with `--timeframe 1h`).
5. **Parse** — `grep "^EVAL_SCORE:" loops/run.log`
   - If empty → run crashed. Check `tail -20 loops/run.log`. Max 2 fix attempts, then revert.
6. **Keep or revert**:
   - New EVAL_SCORE strictly > previous best → keep
   - Otherwise → `git reset --hard HEAD~1`
7. **Log** (append to loops/results.tsv — do NOT git-add):
   ```
   <commit_hash>\t<eval_score>\t<keep|revert>\t<description>
   ```
8. Repeat.

## Allowed files (agent may ONLY edit)
- `config/strategy.yaml`

## Forbidden files (never touch)
- `scripts/eval_harness.py`
- `src/safety/paper_trading.py`
- `src/apis/binance_client.py`
- `.env`
- Any file not listed under Allowed

## Parameter bounds (hard limits)
See bounds comments in `config/strategy.yaml`. Never go outside them.

| Parameter | Min | Max |
|-----------|-----|-----|
| rsi.period | 7 | 30 |
| rsi.overbought | 60 | 85 |
| rsi.oversold | 15 | 40 |
| macd.fast | 5 | 21 |
| macd.slow | 15 | 50 |
| bollinger.period | 10 | 30 |
| bollinger.std | 1.5 | 3.0 |
| volume_multiplier | 1.0 | 3.0 |
| risk_per_trade_pct | 0.5 | 5.0 |
| stop_loss_vol_mult | 0.5 | 4.0 |
| take_profit_vol_mult | 1.0 | 8.0 |
| vwap.deviation_pct | 0.5 | 5.0 |
| vwap.window | 12 | 96 |
| vwap.rsi_oversold | 20 | 45 |
| vwap.rsi_overbought | 55 | 80 |
| momentum.breakout_period | 5 | 50 |
| momentum.volume_confirm | 1.0 | 3.0 |
| momentum.trailing_stop_pct | 1.0 | 10.0 |
| squeeze.width_threshold | 0.01 | 0.06 |
| squeeze.squeeze_candles | 3 | 15 |
| multi_confirm.require_agree | 2 | 5 |
| vwap_rsi.entry_deviation | 0.5 | 5.0 |
| vwap_rsi.entry_rsi | 20 | 45 |
| vwap_rsi.exit_rsi | 55 | 85 |

## Strategy hints
- Change one parameter at a time (easier to attribute causality)
- VWAP reversion is currently the best strategy (EVAL_SCORE ~3.8)
- Try switching strategy_mode to test different trading philosophies
- If parameter tuning stalls, try a different strategy_mode entirely
- Strategies with n_trades < 5 over 90 days are likely overfitting
- Note negative results in commit messages so future iterations skip them
- A good session = 10–20 experiments (~6–12/hour)

## Safety invariants (always true)
- PAPER_TRADING=true enforced at safety module level — do not change
- Max order $100, max 10 positions, max 20% drawdown — in safety module, not configurable here

## Stopping condition
Stop when: human stops you, OR 50 experiments logged with no improvement in last 20.
Then summarise the best config and 5 most impactful changes found.
