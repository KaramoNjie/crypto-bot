"""CLI backbone for crypto trading bot.

Usage:
    python -m src.cli analyze BTCUSDT
    python -m src.cli signal BTCUSDT
    python -m src.cli trade BUY BTCUSDT 100
    python -m src.cli portfolio
    python -m src.cli risk BTCUSDT
    python -m src.cli status
    python -m src.cli history
    python -m src.cli backtest BTCUSDT --days 30
    python -m src.cli signals                  # Multi-coin signal scan
    python -m src.cli auto-trade               # Autonomous trading loop
    python -m src.cli dashboard                # Start web dashboard
    python -m src.cli reset-portfolio          # Reset to fresh $100
    python -m src.cli learnings                # Show agent knowledge
"""

import json
import sys
import logging
from datetime import datetime

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

app = typer.Typer(
    name="crypto-bot",
    help="Crypto Trading Bot — Claude Code Native Interface",
    no_args_is_help=True,
)
console = Console()

# Suppress noisy logs for CLI output
logging.basicConfig(level=logging.WARNING)


def _json_out(data: dict):
    """Print dict as formatted JSON."""
    console.print_json(json.dumps(data, indent=2, default=str))


@app.command()
def analyze(
    symbol: str = typer.Argument("BTCUSDT", help="Trading pair e.g. BTCUSDT"),
    interval: str = typer.Option("1h", help="Candle interval: 1m,5m,15m,1h,4h,1d"),
):
    """Run full market analysis: technicals + news + fear/greed."""
    from .core.analysis import full_analysis

    console.print(f"[bold]Analyzing {symbol}...[/bold]")
    result = full_analysis(symbol)

    # Pretty print key metrics
    tech = result.get("technicals", {})
    market = result.get("market", {})
    fg = result.get("fear_greed", {})

    table = Table(title=f"Market Analysis: {symbol}")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Price", f"${market.get('price', 'N/A'):,.2f}" if isinstance(market.get('price'), (int, float)) else str(market.get('price', 'N/A')))
    table.add_row("24h Change", f"{market.get('change_24h_pct', 'N/A')}%")
    table.add_row("24h Volume", f"${market.get('volume_24h', 0):,.0f}" if isinstance(market.get('volume_24h'), (int, float)) else "N/A")
    table.add_row("RSI", str(tech.get("rsi", "N/A")))

    macd = tech.get("macd", {})
    table.add_row("MACD Line", str(macd.get("line", "N/A")))
    table.add_row("MACD Signal", str(macd.get("signal", "N/A")))
    table.add_row("MACD Histogram", str(macd.get("histogram", "N/A")))

    bb = tech.get("bollinger", {})
    table.add_row("BB Upper", str(bb.get("upper", "N/A")))
    table.add_row("BB Middle", str(bb.get("middle", "N/A")))
    table.add_row("BB Lower", str(bb.get("lower", "N/A")))
    table.add_row("BB Position", str(tech.get("bb_position", "N/A")))

    table.add_row("SMA 20", str(tech.get("sma_20", "N/A")))
    table.add_row("SMA 50", str(tech.get("sma_50", "N/A")))
    table.add_row("Volume Ratio", str(tech.get("volume_ratio", "N/A")))

    table.add_row("Fear & Greed", f"{fg.get('value', 'N/A')} ({fg.get('classification', '')})")

    console.print(table)

    # News summary
    news = result.get("news", {})
    articles = news.get("articles", [])
    if articles:
        console.print(f"\n[bold]Recent News ({len(articles)} articles):[/bold]")
        for art in articles[:5]:
            sentiment_color = {"positive": "green", "negative": "red"}.get(art.get("sentiment", ""), "yellow")
            console.print(f"  [{sentiment_color}]{art.get('sentiment', '?').upper()}[/{sentiment_color}] {art.get('title', 'N/A')}")

    # Full JSON for programmatic use
    console.print("\n[dim]Full JSON data:[/dim]")
    _json_out(result)


@app.command()
def signal(
    symbol: str = typer.Argument("BTCUSDT", help="Trading pair"),
):
    """Generate trading signal with analysis + risk data."""
    from .core.analysis import full_analysis
    from .core.risk import assess_risk

    console.print(f"[bold]Generating signal for {symbol}...[/bold]")

    analysis = full_analysis(symbol)
    risk = assess_risk(symbol)

    signal_data = {
        "symbol": symbol,
        "analysis": analysis,
        "risk": risk,
        "generated_at": datetime.now().isoformat(),
    }

    # Summary panel
    tech = analysis.get("technicals", {})
    rsi = tech.get("rsi")
    macd_hist = tech.get("macd", {}).get("histogram")
    fg = analysis.get("fear_greed", {}).get("value")
    risk_level = risk.get("risk_level", "UNKNOWN")
    rec_size = risk.get("position_sizing", {}).get("recommended_usd", 0)

    summary = f"""Price: ${analysis.get('market', {}).get('price', 0):,.2f}
RSI: {rsi}  |  MACD Hist: {macd_hist}  |  Fear/Greed: {fg}
Risk Level: {risk_level}  |  Suggested Position: ${rec_size:,.0f}
Stop Loss: ${risk.get('position_sizing', {}).get('stop_loss', 0):,.2f}
Take Profit: ${risk.get('position_sizing', {}).get('take_profit', 0):,.2f}"""

    console.print(Panel(summary, title=f"Signal: {symbol}", border_style="blue"))
    _json_out(signal_data)


@app.command()
def trade(
    side: str = typer.Argument(..., help="BUY or SELL"),
    symbol: str = typer.Argument(..., help="Trading pair e.g. BTCUSDT"),
    amount: float = typer.Argument(..., help="Amount in USDT"),
):
    """Execute a paper trade."""
    from .core.trading import execute_paper_trade

    console.print(f"[bold]Executing paper {side.upper()} {symbol} ${amount:,.2f}...[/bold]")
    result = execute_paper_trade(symbol, side, amount)

    if result.get("status") == "FILLED":
        console.print(Panel(
            f"[green]FILLED[/green]\n"
            f"Symbol: {result['symbol']}\n"
            f"Side: {result['side']}\n"
            f"Quantity: {result['quantity']}\n"
            f"Price: ${result['price']:,.2f}\n"
            f"Amount: ${result['amount_usdt']:,.2f}\n"
            f"Fees: {result['fees']}\n"
            f"Balance After: ${result['balance_after']:,.2f}",
            title="Paper Trade Executed",
            border_style="green",
        ))
    else:
        console.print(Panel(
            f"[red]{result.get('status', 'ERROR')}[/red]\n"
            f"{json.dumps(result, indent=2, default=str)}",
            title="Trade Rejected",
            border_style="red",
        ))


@app.command()
def portfolio():
    """View paper portfolio summary."""
    from .core.portfolio import get_portfolio_summary

    console.print("[bold]Loading portfolio...[/bold]")
    data = get_portfolio_summary()

    # Summary
    pnl_color = "green" if data["total_pnl"] >= 0 else "red"
    console.print(Panel(
        f"Cash: ${data['cash_balance']:,.2f}\n"
        f"Positions: ${data['total_position_value']:,.2f}\n"
        f"Total Value: ${data['total_value']:,.2f}\n"
        f"P&L: [{pnl_color}]${data['total_pnl']:+,.2f} ({data['total_pnl_pct']:+.2f}%)[/{pnl_color}]\n"
        f"Open Positions: {data['position_count']}",
        title="Paper Portfolio",
        border_style="blue",
    ))

    # Positions table
    if data["positions"]:
        table = Table(title="Open Positions")
        table.add_column("Symbol", style="cyan")
        table.add_column("Qty", justify="right")
        table.add_column("Entry", justify="right")
        table.add_column("Current", justify="right")
        table.add_column("Value", justify="right")
        table.add_column("P&L", justify="right")
        table.add_column("P&L %", justify="right")

        for pos in data["positions"]:
            pnl_style = "green" if pos["unrealized_pnl"] >= 0 else "red"
            table.add_row(
                pos["symbol"],
                f"{pos['quantity']:.6f}",
                f"${pos['entry_price']:,.2f}",
                f"${pos['current_price']:,.2f}",
                f"${pos['market_value']:,.2f}",
                f"[{pnl_style}]${pos['unrealized_pnl']:+,.2f}[/{pnl_style}]",
                f"[{pnl_style}]{pos['pnl_pct']:+.2f}%[/{pnl_style}]",
            )
        console.print(table)
    else:
        console.print("[dim]No open positions[/dim]")


@app.command()
def risk(
    symbol: str = typer.Argument("BTCUSDT", help="Trading pair"),
):
    """Run risk assessment for a symbol."""
    from .core.risk import assess_risk

    console.print(f"[bold]Assessing risk for {symbol}...[/bold]")
    result = assess_risk(symbol)

    if "error" in result:
        console.print(f"[red]Error: {result['error']}[/red]")
        return

    vol = result.get("volatility", {})
    ps = result.get("position_sizing", {})

    risk_color = {
        "VERY_HIGH": "red", "HIGH": "red",
        "MODERATE": "yellow", "LOW": "green", "VERY_LOW": "green",
    }.get(result.get("risk_level", ""), "white")

    console.print(Panel(
        f"Risk Level: [{risk_color}]{result['risk_level']}[/{risk_color}]\n"
        f"Daily Volatility: {vol.get('daily', 'N/A')}%\n"
        f"Annualized Volatility: {vol.get('annualized', 'N/A')}%\n"
        f"VaR (95%, 1-day): ${result.get('var_95_1day', 'N/A')}\n"
        f"\nPosition Sizing:\n"
        f"  Recommended: ${ps.get('recommended_usd', 0):,.2f} ({ps.get('recommended_pct', 0)}%)\n"
        f"  Stop Loss: ${ps.get('stop_loss', 0):,.2f}\n"
        f"  Take Profit: ${ps.get('take_profit', 0):,.2f}\n"
        f"  Risk/Reward: {ps.get('risk_reward_ratio', 'N/A')}\n"
        f"\nFear & Greed: {result.get('fear_greed', 'N/A')} ({result.get('fear_greed_label', '')})\n"
        f"RSI: {result.get('rsi', 'N/A')}",
        title=f"Risk Assessment: {symbol}",
        border_style=risk_color,
    ))


@app.command()
def status():
    """System health check: API connections, config."""
    from .core.config import get_config, get_binance_client
    from .core.market_data import get_fear_greed

    console.print("[bold]Checking system status...[/bold]")

    config = get_config()
    results = {}

    # Binance API
    try:
        client = get_binance_client()
        ticker = client.get_ticker("BTCUSDT")
        results["binance_api"] = "connected" if ticker else "error"
        results["btc_price"] = f"${float(ticker.get('last', ticker.get('close', 0))):,.2f}"
    except Exception as e:
        results["binance_api"] = f"error: {e}"

    # Fear & Greed API
    fg = get_fear_greed()
    results["fear_greed_api"] = "connected" if fg.get("value") else "error"

    # Config
    results["paper_trading"] = config.PAPER_TRADING
    results["environment"] = config.ENVIRONMENT
    results["binance_key_set"] = bool(config.BINANCE_API_KEY)
    results["newsapi_key_set"] = bool(config.NEWSAPI_KEY)

    table = Table(title="System Status")
    table.add_column("Component", style="cyan")
    table.add_column("Status", style="green")

    for k, v in results.items():
        style = "green" if v in (True, "connected") else "red" if "error" in str(v) else "yellow"
        table.add_row(k, f"[{style}]{v}[/{style}]")

    console.print(table)


@app.command()
def history(
    limit: int = typer.Option(20, help="Number of trades to show"),
):
    """Show recent paper trades."""
    from .core.portfolio import get_trade_history

    trades = get_trade_history(limit)

    if not trades:
        console.print("[dim]No trade history yet.[/dim]")
        return

    table = Table(title=f"Recent Trades (last {limit})")
    table.add_column("Time", style="dim")
    table.add_column("Symbol", style="cyan")
    table.add_column("Side")
    table.add_column("Amount", justify="right")
    table.add_column("Price", justify="right")

    for t in trades:
        side_style = "green" if t.get("side") == "BUY" else "red"
        table.add_row(
            t.get("timestamp", "")[:19],
            t.get("symbol", ""),
            f"[{side_style}]{t.get('side', '')}[/{side_style}]",
            f"${t.get('amount_usdt', 0):,.2f}",
            f"${t.get('price', 0):,.2f}",
        )

    console.print(table)


@app.command()
def backtest(
    symbol: str = typer.Argument("BTCUSDT", help="Trading pair"),
    days: int = typer.Option(30, help="Number of days to backtest"),
):
    """Simple backtest using RSI strategy over historical data."""
    from .core.market_data import get_klines
    from .core.analysis import _rsi
    import numpy as np

    console.print(f"[bold]Backtesting RSI strategy on {symbol} ({days} days)...[/bold]")

    # Get daily candles
    klines = get_klines(symbol, "1d", min(days, 365))
    if not klines or len(klines) < 20:
        console.print("[red]Not enough data for backtest.[/red]")
        return

    closes = np.array([float(k[4]) for k in klines])

    # Simple RSI strategy: buy when RSI < 30, sell when RSI > 70
    balance = 10000.0
    position = 0.0
    entry_price = 0.0
    trades = []

    for i in range(20, len(closes)):
        price = closes[i]
        rsi = _rsi(closes[:i + 1])
        if rsi is None:
            continue

        if rsi < 30 and position == 0:
            # Buy
            position = balance / price
            entry_price = price
            balance = 0
            trades.append({"type": "BUY", "price": price, "rsi": rsi})
        elif rsi > 70 and position > 0:
            # Sell
            balance = position * price
            pnl = ((price / entry_price) - 1) * 100
            trades.append({"type": "SELL", "price": price, "rsi": rsi, "pnl_pct": round(pnl, 2)})
            position = 0

    # Close any open position at last price
    final_value = balance + (position * closes[-1])
    total_return = ((final_value / 10000) - 1) * 100

    # Calculate max drawdown
    values = [10000.0]
    temp_balance = 10000.0
    temp_position = 0.0
    for i in range(20, len(closes)):
        price = closes[i]
        rsi = _rsi(closes[:i + 1])
        if rsi is not None and rsi < 30 and temp_position == 0:
            temp_position = temp_balance / price
            temp_balance = 0
        elif rsi is not None and rsi > 70 and temp_position > 0:
            temp_balance = temp_position * price
            temp_position = 0
        values.append(temp_balance + temp_position * price)

    values = np.array(values)
    peak = np.maximum.accumulate(values)
    drawdown = ((values - peak) / peak) * 100
    max_dd = float(np.min(drawdown))

    wins = sum(1 for t in trades if t.get("pnl_pct", 0) > 0)
    total_sells = sum(1 for t in trades if t["type"] == "SELL")
    win_rate = (wins / total_sells * 100) if total_sells > 0 else 0

    console.print(Panel(
        f"Period: {days} days ({len(klines)} candles)\n"
        f"Strategy: RSI Mean Reversion (Buy < 30, Sell > 70)\n"
        f"\nTotal Return: {'[green]' if total_return >= 0 else '[red]'}{total_return:+.2f}%{'[/green]' if total_return >= 0 else '[/red]'}\n"
        f"Final Value: ${final_value:,.2f}\n"
        f"Max Drawdown: [red]{max_dd:.2f}%[/red]\n"
        f"Total Trades: {len(trades)}\n"
        f"Win Rate: {win_rate:.0f}%\n"
        f"Buy & Hold Return: {((closes[-1] / closes[0]) - 1) * 100:+.2f}%",
        title=f"Backtest Results: {symbol}",
        border_style="blue",
    ))


@app.command()
def signals(
    timeframe: str = typer.Option("1h", help="Candle timeframe"),
    discover: bool = typer.Option(False, "--discover", "-d",
                                  help="Auto-discover top pairs by volume/momentum"),
    max_pairs: int = typer.Option(8, help="Max pairs when using --discover"),
):
    """Scan coins and show ensemble trading signals. Use --discover for auto pair selection."""
    from .core.signals import scan_all, discover_top_pairs

    if discover:
        console.print("[bold]Discovering top pairs by volume & momentum...[/bold]")
        top = discover_top_pairs(max_pairs=max_pairs)
        disc_table = Table(title="Top Pairs Discovered")
        disc_table.add_column("Symbol", style="cyan")
        disc_table.add_column("Price", justify="right")
        disc_table.add_column("24h Vol", justify="right")
        disc_table.add_column("24h Change", justify="right")
        disc_table.add_column("Momentum", justify="right")
        for p in top:
            chg_color = "green" if p["change_pct"] >= 0 else "red"
            disc_table.add_row(
                p["symbol"],
                f"${p['price']:,.4f}",
                f"${p['volume_24h']:,.0f}",
                f"[{chg_color}]{p['change_pct']:+.2f}%[/{chg_color}]",
                f"{p['momentum_score']:.1f}",
            )
        console.print(disc_table)
        console.print()

    console.print("[bold]Scanning markets for signals...[/bold]")
    results = scan_all(timeframe=timeframe, auto_discover=discover, max_pairs=max_pairs)

    table = Table(title="Multi-Coin Signal Scanner")
    table.add_column("Symbol", style="cyan")
    table.add_column("Price", justify="right")
    table.add_column("Action")
    table.add_column("Score", justify="right")
    table.add_column("Confidence", justify="right")
    table.add_column("RSI")
    table.add_column("MACD")
    table.add_column("BB")
    table.add_column("EMA")
    table.add_column("Vol")

    for sig in results:
        if sig.get("error"):
            table.add_row(sig["symbol"], "--", "[yellow]ERROR[/yellow]", "--", "--",
                          "--", "--", "--", "--", "--")
            continue

        action_color = {"BUY": "green", "SELL": "red", "HOLD": "dim"}.get(sig["action"], "white")
        strats = sig.get("strategies", {})

        def _chip(s):
            v = s.get("score", 0) if s else 0
            c = "green" if v > 0.1 else "red" if v < -0.1 else "dim"
            return f"[{c}]{v:+.2f}[/{c}]"

        table.add_row(
            sig["symbol"],
            f"${sig['price']:,.2f}",
            f"[{action_color}]{sig['action']}[/{action_color}]",
            f"{sig['ensemble_score']:+.3f}",
            f"{sig['confidence']:.0%}",
            _chip(strats.get("rsi")),
            _chip(strats.get("macd")),
            _chip(strats.get("bollinger")),
            _chip(strats.get("ema_cross")),
            _chip(strats.get("volume")),
        )

    console.print(table)

    # Show top recommendation
    buys = [s for s in results if s.get("action") == "BUY"]
    sells = [s for s in results if s.get("action") == "SELL"]
    if buys:
        best = buys[0]
        console.print(f"\n[green bold]Top BUY:[/green bold] {best['symbol']} "
                      f"(score={best['ensemble_score']:+.3f}, conf={best['confidence']:.0%})")
    if sells:
        best = sells[0]
        console.print(f"[red bold]Top SELL:[/red bold] {best['symbol']} "
                      f"(score={best['ensemble_score']:+.3f}, conf={best['confidence']:.0%})")
    if not buys and not sells:
        console.print("\n[dim]No strong signals — HOLD all positions[/dim]")


@app.command("auto-trade")
def auto_trade(
    interval: int = typer.Option(300, help="Seconds between scans"),
    min_confidence: float = typer.Option(0.5, help="Min confidence to trade (0-1)"),
    iterations: int = typer.Option(0, help="Max iterations (0=infinite)"),
    dry_run: bool = typer.Option(False, help="Show signals without trading"),
    discover: bool = typer.Option(False, "--discover", "-d",
                                  help="Auto-discover top pairs each scan"),
):
    """Start autonomous multi-currency trading loop. Use --discover for dynamic pair selection."""
    from .core.auto_trader import run_loop

    if dry_run:
        console.print("[yellow]DRY RUN — signals only, no trades[/yellow]")
    if discover:
        console.print("[cyan]AUTO-DISCOVER MODE — scanning all Binance for top pairs[/cyan]")

    console.print(f"[bold]Starting auto-trader[/bold] "
                  f"(interval={interval}s, min_conf={min_confidence:.0%})")
    run_loop(interval_seconds=interval, min_confidence=min_confidence,
             max_iterations=iterations, auto_discover=discover)


@app.command()
def dashboard():
    """Start the real-time web dashboard."""
    from .dashboard.app import main as run_dashboard
    run_dashboard()


@app.command("reset-portfolio")
def reset_portfolio():
    """Reset paper portfolio to fresh $100."""
    from .core.state import reset_state, save_state

    console.print("[yellow]Resetting paper portfolio to $100.00...[/yellow]")
    guard = reset_state()
    save_state(guard)
    console.print("[green]Portfolio reset. Balance: $100.00, 0 positions.[/green]")


@app.command()
def learnings(
    category: str = typer.Option(None, help="Filter by category"),
    limit: int = typer.Option(20, help="Number of entries to show"),
):
    """Show agent knowledge base entries."""
    from .core.knowledge import get_learnings, get_summary

    summary = get_summary()
    console.print(Panel(
        f"Total entries: {summary['total_entries']}\n"
        f"By category: {json.dumps(summary.get('by_category', {}), indent=2)}",
        title="Knowledge Base Summary",
        border_style="purple",
    ))

    entries = get_learnings(category=category, limit=limit)
    if not entries:
        console.print("[dim]No learnings recorded yet.[/dim]")
        return

    for e in entries[-limit:]:
        tags = " ".join(f"[purple]{t}[/purple]" for t in e.get("tags", []))
        console.print(f"\n[bold]{e.get('title', 'untitled')}[/bold]")
        console.print(f"  [dim]{e.get('detail', '')}[/dim]")
        console.print(f"  {tags} [dim]{e.get('source', '')} @ {e.get('timestamp', '')[:16]}[/dim]")


if __name__ == "__main__":
    app()
