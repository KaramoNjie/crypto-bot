"""MCP server exposing portfolio and trade data to Claude Code.

Run with: python -m src.mcp.db_server
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

server = Server("trading-db-mcp")


@server.list_tools()
async def list_tools():
    return [
        Tool(
            name="get_portfolio",
            description="Get paper trading portfolio: cash, positions, total value, P&L",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="get_trade_history",
            description="Get recent paper trade history",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Number of trades", "default": 20},
                },
            },
        ),
        Tool(
            name="execute_paper_trade",
            description="Execute a paper trade (BUY or SELL) with safety checks",
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Trading pair e.g. BTCUSDT"},
                    "side": {"type": "string", "description": "BUY or SELL"},
                    "amount_usdt": {"type": "number", "description": "Dollar amount to trade"},
                },
                "required": ["symbol", "side", "amount_usdt"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    try:
        from src.core.portfolio import get_portfolio_summary, get_trade_history
        from src.core.trading import execute_paper_trade

        if name == "get_portfolio":
            result = get_portfolio_summary()
        elif name == "get_trade_history":
            result = get_trade_history(arguments.get("limit", 20))
        elif name == "execute_paper_trade":
            result = execute_paper_trade(
                arguments["symbol"],
                arguments["side"],
                arguments["amount_usdt"],
            )
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
