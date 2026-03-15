"""Real-time trading dashboard — Flask web app.

Run: python -m src.dashboard.app
Opens at: http://localhost:5050
"""

import json
import logging
from datetime import datetime
from pathlib import Path

from flask import Flask, render_template, jsonify

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"

app = Flask(__name__, template_folder=str(TEMPLATE_DIR))


def _read_json(path: Path, default=None):
    if not path.exists():
        return default if default is not None else {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return default if default is not None else {}


def _sanitize(obj):
    """Convert numpy types to native Python for JSON serialization."""
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    if hasattr(obj, 'item'):  # numpy scalar
        return obj.item()
    return obj


@app.route("/")
def index():
    return render_template("dashboard.html")


@app.route("/api/portfolio")
def api_portfolio():
    """Return current portfolio state."""
    try:
        from src.core.portfolio import get_portfolio_summary
        return jsonify(get_portfolio_summary())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/signals")
def api_signals():
    """Return current signals for default coins."""
    try:
        from src.core.signals import scan_all
        results = scan_all()
        return jsonify(_sanitize(results))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/signals/discover")
def api_signals_discover():
    """Auto-discover top pairs and return signals."""
    try:
        from src.core.signals import scan_all
        results = scan_all(auto_discover=True, max_pairs=8)
        return jsonify(_sanitize(results))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/discover")
def api_discover():
    """Return top discovered pairs by volume/momentum."""
    try:
        from src.core.signals import discover_top_pairs
        return jsonify(discover_top_pairs(max_pairs=10))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/signals/<symbol>")
def api_signal_detail(symbol):
    """Detailed signal for one symbol."""
    try:
        from src.core.signals import generate_signal
        return jsonify(_sanitize(generate_signal(symbol.upper())))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/trades")
def api_trades():
    """Return trade history."""
    try:
        from src.core.portfolio import get_trade_history
        return jsonify(get_trade_history(limit=50))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/outcomes")
def api_outcomes():
    """Return trade outcomes with P&L."""
    data = _read_json(DATA_DIR / "trade_outcomes.json", [])
    return jsonify(data)


@app.route("/api/knowledge")
def api_knowledge():
    """Return agent knowledge base."""
    try:
        from src.core.knowledge import get_learnings
        return jsonify(get_learnings(limit=100))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/knowledge/summary")
def api_knowledge_summary():
    try:
        from src.core.knowledge import get_summary
        return jsonify(get_summary())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/strategy")
def api_strategy():
    """Return current strategy config."""
    try:
        from src.core.config import load_strategy
        return jsonify(load_strategy())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/eval")
def api_eval():
    """Return latest eval results."""
    data = _read_json(DATA_DIR.parent / "loops" / "latest_eval.json")
    return jsonify(data)


@app.route("/api/experiments")
def api_experiments():
    """Return experiment history from results.tsv."""
    tsv_path = DATA_DIR.parent / "loops" / "results.tsv"
    if not tsv_path.exists():
        return jsonify([])
    try:
        rows = []
        for line in tsv_path.read_text().strip().split("\n")[1:]:  # skip header
            parts = line.split("\t")
            if len(parts) >= 4:
                rows.append({
                    "commit": parts[0],
                    "eval_score": float(parts[1]) if parts[1] else 0,
                    "status": parts[2],
                    "description": parts[3],
                })
        return jsonify(rows)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/compare")
def api_compare():
    """Return strategy comparison data from --compare-all."""
    data = _read_json(DATA_DIR.parent / "loops" / "latest_eval_v2.json")
    if not data:
        # Fall back: build minimal comparison from latest_eval.json
        latest = _read_json(DATA_DIR.parent / "loops" / "latest_eval.json")
        if latest and latest.get("aggregate"):
            mode = latest.get("strategy_mode", "unknown")
            data = {mode: {
                "eval_score": latest["aggregate"].get("eval_score", 0),
                "avg_sharpe": latest["aggregate"].get("avg_sharpe", 0),
                "total_trades": latest["aggregate"].get("total_trades", 0),
                "avg_pnl_pct": latest["aggregate"].get("avg_pnl_pct", 0),
                "avg_drawdown_pct": latest["aggregate"].get("avg_drawdown_pct", 0),
                "coverage": latest["aggregate"].get("coverage_factor", 0),
            }}
    return jsonify(data)


@app.route("/api/feedback")
def api_feedback():
    """Return live trading feedback stats."""
    try:
        from src.core.feedback import get_live_stats
        outcomes = _read_json(DATA_DIR / "trade_outcomes.json", [])
        stats = get_live_stats()
        stats["total_outcomes"] = len(outcomes)
        stats["open_trades"] = sum(1 for t in outcomes if t.get("status") == "open")
        return jsonify(stats)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/daily-pnl")
def api_daily_pnl():
    """Return daily P&L tracking data."""
    data = _read_json(DATA_DIR / "daily_pnl.json", [])
    return jsonify(data)


@app.route("/api/status")
def api_status():
    """System health check."""
    status = {"timestamp": datetime.now().isoformat(), "components": {}}
    try:
        from src.core.market_data import get_ticker
        t = get_ticker("BTCUSDT")
        status["components"]["binance"] = "ok" if "price" in t else "error"
        status["btc_price"] = t.get("price")
    except Exception as e:
        status["components"]["binance"] = f"error: {e}"
    try:
        from src.core.market_data import get_fear_greed
        fg = get_fear_greed()
        status["components"]["fear_greed"] = "ok" if "value" in fg else "error"
        status["fear_greed"] = fg.get("value")
    except Exception as e:
        status["components"]["fear_greed"] = f"error: {e}"

    status["components"]["paper_state"] = "ok" if (DATA_DIR / "paper_state.json").exists() else "missing"
    return jsonify(status)


def main():
    print("=" * 60)
    print("  Crypto Trading Dashboard")
    print("  http://localhost:5050")
    print("=" * 60)
    app.run(host="0.0.0.0", port=5050, debug=False)


if __name__ == "__main__":
    main()
