"""MCP server exposing Binance market data and analysis tools to Claude Code.

Run with: python -m src.mcp.binance_server
"""

import asyncio
import json
import logging
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

logging.basicConfig(level=logging.WARNING)

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

server = Server("binance-mcp")


@server.list_tools()
async def list_tools():
    return [
        Tool(
            name="get_ticker",
            description="Get current price, 24h change, and volume for a crypto trading pair",
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Trading pair e.g. BTCUSDT"}
                },
                "required": ["symbol"],
            },
        ),
        Tool(
            name="get_technical_indicators",
            description="Compute RSI, MACD, Bollinger Bands, SMAs for a crypto pair",
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Trading pair e.g. BTCUSDT"},
                    "interval": {"type": "string", "description": "Candle interval: 1m,5m,15m,1h,4h,1d", "default": "1h"},
                },
                "required": ["symbol"],
            },
        ),
        Tool(
            name="get_orderbook",
            description="Get order book snapshot with bid/ask spread for a crypto pair",
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Trading pair e.g. BTCUSDT"},
                    "limit": {"type": "integer", "description": "Number of levels", "default": 20},
                },
                "required": ["symbol"],
            },
        ),
        Tool(
            name="get_fear_greed",
            description="Get the Crypto Fear & Greed Index (0-100 scale)",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="get_news",
            description="Get recent cryptocurrency news with sentiment",
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Crypto symbol e.g. BTC, ETH"},
                },
                "required": ["symbol"],
            },
        ),
        Tool(
            name="full_analysis",
            description="Run complete market analysis: ticker + technicals + news + fear/greed combined",
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Trading pair e.g. BTCUSDT"},
                },
                "required": ["symbol"],
            },
        ),
        Tool(
            name="assess_risk",
            description="Risk assessment with volatility, VaR, position sizing, stop/take levels",
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Trading pair e.g. BTCUSDT"},
                },
                "required": ["symbol"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    try:
        from src.core.market_data import get_ticker, get_orderbook, get_fear_greed
        from src.core.analysis import technical_analysis, news_analysis, full_analysis
        from src.core.risk import assess_risk

        if name == "get_ticker":
            result = get_ticker(arguments["symbol"])
        elif name == "get_technical_indicators":
            result = technical_analysis(arguments["symbol"], arguments.get("interval", "1h"))
        elif name == "get_orderbook":
            result = get_orderbook(arguments["symbol"], arguments.get("limit", 20))
        elif name == "get_fear_greed":
            result = get_fear_greed()
        elif name == "get_news":
            result = news_analysis(arguments["symbol"])
        elif name == "full_analysis":
            result = full_analysis(arguments["symbol"])
        elif name == "assess_risk":
            result = assess_risk(arguments["symbol"])
        else:
            result = {"error": f"Unknown tool: {name}"}

        return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]

    except Exception as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]


async def main():
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
