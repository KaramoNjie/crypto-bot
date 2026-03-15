---
description: Show what agents have learned, strategies tested, and bugs found
---

Show the agent knowledge base — what has been learned from trading, strategy experiments, and bugs found.

1. Run: `cd /home/amo/Documents/crypto-bot && python -m src.cli learnings --limit 30`
2. Also show trade outcomes: `cd /home/amo/Documents/crypto-bot && python -c "import json, pathlib; f=pathlib.Path('data/trade_outcomes.json'); print(json.dumps(json.loads(f.read_text()), indent=2) if f.exists() else 'No trade outcomes yet')"`
3. Show daily P&L tracking: `cd /home/amo/Documents/crypto-bot && python -c "import json, pathlib; f=pathlib.Path('data/daily_pnl.json'); print(json.dumps(json.loads(f.read_text()), indent=2) if f.exists() else 'No daily P&L data yet')"`
4. Check knowledge base: `cd /home/amo/Documents/crypto-bot && python -c "import json, pathlib; f=pathlib.Path('data/knowledge.json'); d=json.loads(f.read_text()) if f.exists() else []; print(f'{len(d)} entries')"`

Interpret the results:
- **strategy** entries: what parameter changes worked/failed in autoexp
- **trade** entries: what trades were executed and why (including stop-loss/take-profit triggers)
- **bug** entries: what bugs were found and fixed
- **market** entries: market insights and patterns observed
- **config** entries: configuration changes and their effects
- **daily P&L**: consistency of returns over time

Highlight actionable insights: what should be tried next, what to avoid, what's working.
