"""Agent knowledge tracker — documents what strategies work, why, and how.

Stores structured learning in data/knowledge.json.
Each entry records: what was tried, what happened, what was learned.
The dashboard and agents can query this to avoid repeating mistakes.
"""

import json
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
KNOWLEDGE_FILE = DATA_DIR / "knowledge.json"


def _load() -> list:
    if not KNOWLEDGE_FILE.exists():
        return []
    try:
        return json.loads(KNOWLEDGE_FILE.read_text())
    except Exception:
        return []


def _save(entries: list) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    data = json.dumps(entries, indent=2, default=str)
    fd, tmp_path = tempfile.mkstemp(dir=DATA_DIR, suffix=".tmp")
    try:
        os.write(fd, data.encode())
        os.fsync(fd)
        os.close(fd)
        os.replace(tmp_path, str(KNOWLEDGE_FILE))
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def log_learning(category: str, title: str, detail: str,
                 source: str = "agent", tags: Optional[list] = None,
                 data: Optional[dict] = None) -> None:
    """Record a learning event.

    Args:
        category: One of: strategy, trade, risk, market, bug, config
        title: Short summary (< 80 chars)
        detail: Full explanation of what was learned
        source: Who recorded it (agent, autoexp, user, system)
        tags: Optional tags for filtering
        data: Optional structured data (metrics, params, etc.)
    """
    entries = _load()
    entry = {
        "id": len(entries) + 1,
        "timestamp": datetime.now().isoformat(),
        "category": category,
        "title": title,
        "detail": detail,
        "source": source,
        "tags": tags or [],
        "data": data or {},
    }
    entries.append(entry)
    _save(entries)
    logger.debug(f"Knowledge logged: [{category}] {title}")


def log_trade_learning(symbol: str, action: str, outcome: str,
                       pnl_pct: Optional[float] = None,
                       signals_used: Optional[dict] = None,
                       lesson: str = "") -> None:
    """Convenience wrapper for trade-specific learnings."""
    log_learning(
        category="trade",
        title=f"{action} {symbol}: {outcome}",
        detail=lesson or f"{action} {symbol} resulted in {outcome}",
        source="trade-executor",
        tags=[symbol, action.lower(), outcome.lower()],
        data={
            "symbol": symbol,
            "action": action,
            "outcome": outcome,
            "pnl_pct": pnl_pct,
            "signals": signals_used,
        },
    )


def log_strategy_experiment(params: dict, eval_score: float,
                            kept: bool, hypothesis: str) -> None:
    """Record autoexp experiment results."""
    log_learning(
        category="strategy",
        title=f"{'KEPT' if kept else 'REVERTED'} (score={eval_score:.4f}): {hypothesis[:60]}",
        detail=hypothesis,
        source="autoexp",
        tags=["experiment", "kept" if kept else "reverted"],
        data={"params": params, "eval_score": eval_score, "kept": kept},
    )


def get_learnings(category: Optional[str] = None, limit: int = 50,
                  tags: Optional[list] = None) -> list:
    """Query knowledge base.

    Args:
        category: Filter by category (None = all)
        limit: Max entries to return
        tags: Filter by any matching tag
    """
    entries = _load()

    if category:
        entries = [e for e in entries if e.get("category") == category]

    if tags:
        tag_set = set(t.lower() for t in tags)
        entries = [e for e in entries
                   if tag_set & set(t.lower() for t in e.get("tags", []))]

    return entries[-limit:]


def get_summary() -> dict:
    """Summary stats of the knowledge base."""
    entries = _load()
    categories = {}
    for e in entries:
        cat = e.get("category", "other")
        categories[cat] = categories.get(cat, 0) + 1

    return {
        "total_entries": len(entries),
        "by_category": categories,
        "latest": entries[-1] if entries else None,
    }
