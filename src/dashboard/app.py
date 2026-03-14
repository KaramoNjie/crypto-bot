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
    """Return current signals for all coins."""
    try:
        from src.core.signals import scan_all
        results = scan_all()
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/signals/<symbol>")
def api_signal_detail(symbol):
    """Detailed signal for one symbol."""
    try:
        from src.core.signals import generate_signal
        return jsonify(generate_signal(symbol.upper()))
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
