# /autoexp — Autonomous Strategy Experiment Loop

Run the autoresearch loop: Claude autonomously tunes `config/strategy.yaml`
via backtests and keeps only improvements.

## Steps

1. Ask how many iterations (default: 20).

2. Safety check:
   ```bash
   cd /home/amo/Documents/crypto-bot && python -c "import yaml; print(yaml.safe_load(open('config/strategy.yaml')))" 2>&1
   ```
   If it fails, stop and report the error.

3. Establish baseline with honest eval (fees + walk-forward):
   ```bash
   cd /home/amo/Documents/crypto-bot && python scripts/eval_harness.py --days 90 --fees --output-json loops/latest_eval.json
   ```
   Tests BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT.
   EVAL_SCORE = mean(per-coin scores) * coverage_factor * feedback_factor.
   Parse and display the baseline EVAL_SCORE and per-coin breakdown.

4. Initialise git if needed and create experiment branch:
   ```bash
   cd /home/amo/Documents/crypto-bot && git rev-parse --git-dir 2>/dev/null || (git init && git add -A && git commit -m "baseline before autoexp")
   git checkout -b strategy-autoexp/$(date +%b%d) 2>/dev/null || git checkout strategy-autoexp/$(date +%b%d)
   ```
   Initialise `loops/results.tsv` if it doesn't exist:
   ```bash
   [ -f loops/results.tsv ] || echo -e "commit\teval_score\tstatus\tdescription" > loops/results.tsv
   ```

5. Run the experiment loop following `loops/program.md` exactly:
   - Read program.md before starting
   - For each iteration: hypothesis → edit strategy.yaml → commit → eval → keep/revert → log
   - 8 strategies available: rsi, ensemble, multi_confirm, momentum, squeeze, vwap, vwap_rsi, squeeze_vwap
   - Eval harness supports: --fees (0.15% transaction costs), --walk-forward (out-of-sample), --compare-all
   - Stop after requested iterations or stopping condition in program.md

6. At the end, summarise:
   - Best EVAL_SCORE achieved vs baseline
   - Top 3 most impactful parameter changes
   - Current best `config/strategy.yaml` values
   - Contents of `loops/results.tsv`
