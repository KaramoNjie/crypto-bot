---
description: Show what agents have learned, strategies tested, and bugs found
---

Show the agent knowledge base — what has been learned from trading, strategy experiments, and bugs found.

1. Run: `python -m src.cli learnings --limit 30`
2. Also show the trade outcomes: `python -c "import json; d=json.load(open('data/trade_outcomes.json')); print(json.dumps(d, indent=2))"` (if the file exists)
3. Check if `data/knowledge.json` exists and summarize: how many entries, what categories, most recent learnings

Interpret the results:
- **strategy** entries: what parameter changes worked/failed in autoexp
- **trade** entries: what trades were executed and why
- **bug** entries: what bugs were found and fixed
- **market** entries: market insights and patterns observed
- **config** entries: configuration changes and their effects

Highlight actionable insights: what should be tried next, what to avoid, what's working.
