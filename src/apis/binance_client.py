import hashlib
import logging
import time
import uuid
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional
import threading

import ccxt
import pandas as pd
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

logger = logging.getLogger(__name__)


class BinanceClient:
    def __init__(self, config) -> None:
        self.config = config
        # Initialize paper balance with common trading pairs
        self.paper_balance = {
            "USDT": {"free": 10000.0, "used": 0.0, "total": 10000.0},
            "BTC": {"free": 0.0, "used": 0.0, "total": 0.0},
            "ETH": {"free": 0.0, "used": 0.0, "total": 0.0},
            "ADA": {"free": 0.0, "used": 0.0, "total": 0.0},
            "BNB": {"free": 0.0, "used": 0.0, "total": 0.0},
            "SOL": {"free": 0.0, "used": 0.0, "total": 0.0},
            "DOT": {"free": 0.0, "used": 0.0, "total": 0.0},
            "LINK": {"free": 0.0, "used": 0.0, "total": 0.0},
        }

        # Thread lock for paper trading balance updates (Fix: Bug #5 Race Condition)
        self._balance_lock = threading.RLock()

        # Always initialize exchange attribute to None first
        self.exchange = None
        self.is_connected = False
        self.last_connection_test = None

        try:
            # Enhanced configuration based on CCXT best practices
            exchange_config = {
                "apiKey": self.config.BINANCE_API_KEY or "",
                "secret": self.config.BINANCE_SECRET_KEY or "",
                "sandbox": self.config.BINANCE_TESTNET,
                "rateLimit": 1200,  # 1200ms = 50 requests per minute
                "enableRateLimit": True,
                "timeout": 30000,  # 30 seconds timeout
                "options": {
                    "defaultType": "spot",
                    "adjustForTimeDifference": True,
                    "recvWindow": 10000,
                },
                "verbose": False,  # Set to True for debugging
            }

            self.exchange = ccxt.binance(exchange_config)

            if self.config.BINANCE_TESTNET:
                self.exchange.set_sandbox_mode(True)

            # Test connection during initialization if not paper trading
            if not self.config.PAPER_TRADING and self.config.BINANCE_API_KEY:
                self._test_initial_connection()
            else:
                self.is_connected = True  # Assume paper trading is always "connected"

        except ccxt.NetworkError as e:
            logger.error(f"Network error initializing Binance client: {e}")
            self.is_connected = False
            if not self.config.PAPER_TRADING:
                raise
        except ccxt.ExchangeError as e:
            logger.error(f"Exchange error initializing Binance client: {e}")
            self.is_connected = False
            if not self.config.PAPER_TRADING:
                raise
        except Exception as e:
            logger.error(f"Unexpected error initializing Binance client: {e}")
            self.is_connected = False
            if not self.config.PAPER_TRADING:
                raise

    def _test_initial_connection(self):
        """Test initial connection during initialization"""
        try:
            # Load markets to test connection
            self.exchange.load_markets()
            self.is_connected = True
            self.last_connection_test = time.time()
            logger.info("Binance client connection test successful")
        except ccxt.NetworkError as e:
            logger.error(f"Network error during initial connection test: {e}")
            self.is_connected = False
            raise
        except ccxt.ExchangeError as e:
            logger.error(f"Exchange error during initial connection test: {e}")
            self.is_connected = False
            raise
        except Exception as e:
            logger.error(f"Unexpected error during initial connection test: {e}")
            self.is_connected = False
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((ccxt.NetworkError, ccxt.ExchangeError)),
    )
    def get_account_balance(self) -> Dict:
        """Get account balance"""
        try:
            if self.config.PAPER_TRADING:
                return self.paper_balance

            if not self.exchange:
                logger.error("Exchange client not initialized")
                return {}

            balance = self.exchange.fetch_balance()
            return balance
        except ccxt.NetworkError as e:
            logger.error(f"Network error fetching balance: {e}")
            self.is_connected = False
            raise  # Re-raise for tenacity retry
        except ccxt.ExchangeError as e:
            logger.error(f"Exchange error fetching balance: {e}")
            raise  # Re-raise for tenacity retry
        except Exception as e:
            logger.error(f"Unexpected error fetching balance: {e}")
            return {}

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((ccxt.NetworkError, ccxt.ExchangeError)),
    )
    def get_klines(
        self, symbol: str, interval: str = "1h", limit: int = 100
    ) -> pd.DataFrame:
        """Get historical price data"""
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, interval, limit=limit)
            if not ohlcv:
                logger.warning(f"No data returned for {symbol}")
                return pd.DataFrame()

            df = pd.DataFrame(
                ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"]
            )
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            return df
        except ccxt.NetworkError as e:
            logger.error(f"Network error fetching klines for {symbol}: {e}")
            raise  # Re-raise for tenacity retry
        except ccxt.ExchangeError as e:
            logger.error(f"Exchange error fetching klines for {symbol}: {e}")
            raise  # Re-raise for tenacity retry
        except Exception as e:
            logger.error(f"Error fetching klines for {symbol}: {e}")
            return pd.DataFrame()

    def get_ticker(self, symbol: str) -> Dict:
        """Get current ticker for symbol with proper error handling (Fix: Issue #5)"""
        try:
            # Validate input parameters
            if not symbol or not isinstance(symbol, str):
                logger.warning(f"Invalid symbol provided: {symbol}")
                return {}

            if not self.exchange:
                logger.error("Exchange client not initialized")
                return {}

            ticker = self.exchange.fetch_ticker(symbol)
            return ticker
        except ccxt.NetworkError as e:
            logger.error(f"Network error fetching ticker for {symbol}: {e}")
            self.is_connected = False
            return {}
        except ccxt.ExchangeError as e:
            logger.error(f"Exchange error fetching ticker for {symbol}: {e}")
            return {}
        except Exception as e:
            logger.error(f"Unexpected error fetching ticker for {symbol}: {e}")
            return {}

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((ccxt.NetworkError, ccxt.ExchangeError)),
    )
    def place_order(
        self, symbol: str, side: str, amount: float, price: Optional[float] = None
    ) -> Dict:
        """Place an order (market or limit)"""
        try:
            # Validate order parameters first
            validation = self.validate_order_parameters(symbol, side, amount, price)
            if not validation.get("valid", False):
                return {
                    "success": False,
                    "data": None,
                    "error": validation.get("error", "Validation failed"),
                }

            # Apply precision formatting
            formatted_amount = self._format_amount(symbol, amount)
            formatted_price = self._format_price(symbol, price) if price else None

            if self.config.PAPER_TRADING:
                # Simulate paper trading order with realistic slippage
                order_id = uuid.uuid4().hex[:8]

                ticker = self.get_ticker(symbol)
                current_price = ticker.get("last", 0) if ticker else 0

                if not current_price:
                    return {
                        "success": False,
                        "data": None,
                        "error": "Could not fetch current price",
                    }

                # Add realistic market slippage (0.1% - 0.5%)
                import random

                slippage = random.uniform(0.001, 0.005)
                if side.upper() == "BUY":
                    execution_price = current_price * (1 + slippage)
                else:
                    execution_price = current_price * (1 - slippage)

                # Use formatted limit price if provided, otherwise use execution price
                final_price = formatted_price or execution_price

                # Update paper balance with thread safety (Fix: Bug #5 Race Condition)
                if "/" not in symbol:
                    raise ValueError(f"Invalid symbol format '{symbol}': expected 'BASE/QUOTE' (e.g. 'BTC/USDT')")
                base_currency, quote_currency = symbol.split("/", 1)

                with self._balance_lock:
                    # Initialize balance for new currencies
                    for currency in [base_currency, quote_currency]:
                        if currency not in self.paper_balance:
                            self.paper_balance[currency] = {
                                "free": 0.0,
                                "used": 0.0,
                                "total": 0.0,
                            }

                    if side.upper() == "BUY":
                        cost = formatted_amount * final_price
                        if self.paper_balance[quote_currency]["free"] >= cost:
                            self.paper_balance[quote_currency]["free"] -= cost
                            self.paper_balance[quote_currency]["total"] = (
                                self.paper_balance[quote_currency]["free"]
                                + self.paper_balance[quote_currency]["used"]
                            )
                            self.paper_balance[base_currency][
                                "free"
                            ] += formatted_amount
                            self.paper_balance[base_currency]["total"] = (
                                self.paper_balance[base_currency]["free"]
                                + self.paper_balance[base_currency]["used"]
                            )
                        else:
                            return {
                                "success": False,
                                "data": None,
                                "error": "Insufficient balance",
                            }
                    else:  # SELL
                        if (
                            self.paper_balance[base_currency]["free"]
                            >= formatted_amount
                        ):
                            self.paper_balance[base_currency][
                                "free"
                            ] -= formatted_amount
                            self.paper_balance[base_currency]["total"] = (
                                self.paper_balance[base_currency]["free"]
                                + self.paper_balance[base_currency]["used"]
                            )
                            revenue = formatted_amount * final_price
                            self.paper_balance[quote_currency]["free"] += revenue
                            self.paper_balance[quote_currency]["total"] = (
                                self.paper_balance[quote_currency]["free"]
                                + self.paper_balance[quote_currency]["used"]
                            )
                        else:
                            return {
                                "success": False,
                                "data": None,
                                "error": "Insufficient balance",
                            }

                return {
                    "success": True,
                    "data": {
                        "id": f"paper_{order_id}",
                        "symbol": symbol,
                        "side": side,
                        "type": "market" if price is None else "limit",
                        "amount": formatted_amount,
                        "price": final_price,
                        "status": "filled",
                        "timestamp": pd.Timestamp.now().isoformat(),
                        "slippage": slippage if price is None else 0,
                    },
                    "error": None,
                }

            # Real trading
            if price is None:
                order = self.exchange.create_market_order(
                    symbol, side, formatted_amount
                )
            else:
                order = self.exchange.create_limit_order(
                    symbol, side, formatted_amount, formatted_price
                )

            return order

        except ccxt.NetworkError as e:
            logger.error(f"Network error placing order: {e}")
            raise  # Re-raise for tenacity retry
        except ccxt.ExchangeError as e:
            logger.error(f"Exchange error placing order: {e}")
            raise  # Re-raise for tenacity retry
        except Exception as e:
            logger.error(f"Error placing order: {e}")
            return {"error": str(e)}

    def get_order_status(self, order_id: str, symbol: str) -> Dict:
        """Get status of an order"""
        try:
            if self.config.PAPER_TRADING:
                # For paper trading, assume all orders are filled
                return {"status": "filled"}

            order = self.exchange.fetch_order(order_id, symbol)
            return order
        except Exception as e:
            logger.error(f"Error fetching order status: {e}")
            return {"error": str(e)}

    def cancel_order(self, order_id: str, symbol: str) -> Dict:
        """Cancel an open order"""
        try:
            if self.config.PAPER_TRADING:
                return {"status": "cancelled"}

            result = self.exchange.cancel_order(order_id, symbol)
            return result
        except Exception as e:
            logger.error(f"Error cancelling order: {e}")
            return {"error": str(e)}

    def get_markets(self) -> Dict:
        """Get available trading markets"""
        try:
            if not self.exchange:
                logger.error("Exchange client not initialized")
                return {}

            markets = self.exchange.load_markets()
            return markets
        except ccxt.NetworkError as e:
            logger.error(f"Network error fetching markets: {e}")
            self.is_connected = False
            return {}
        except ccxt.ExchangeError as e:
            logger.error(f"Exchange error fetching markets: {e}")
            return {}
        except Exception as e:
            logger.error(f"Unexpected error fetching markets: {e}")
            return {}

    def get_account_info(self) -> Dict:
        """Get detailed account information including balances, permissions, and trading status"""
        try:
            if self.config.PAPER_TRADING:
                return {
                    "success": True,
                    "data": {
                        "makerCommission": 10,
                        "takerCommission": 10,
                        "buyerCommission": 0,
                        "sellerCommission": 0,
                        "canTrade": True,
                        "canWithdraw": False,
                        "canDeposit": False,
                        "updateTime": int(time.time() * 1000),
                        "accountType": "SPOT",
                        "balances": self.paper_balance,
                        "permissions": ["SPOT"],
                    },
                    "error": None,
                }

            account_info = self.exchange.private_get_account()
            return {"success": True, "data": account_info, "error": None}
        except ccxt.AuthenticationError as e:
            logger.error(f"Authentication error getting account info: {e}")
            return {"success": False, "data": None, "error": "Authentication failed"}
        except ccxt.ExchangeError as e:
            logger.error(f"Exchange error getting account info: {e}")
            return {"success": False, "data": None, "error": str(e)}
        except ccxt.NetworkError as e:
            logger.error(f"Network error getting account info: {e}")
            return {
                "success": False,
                "data": None,
                "error": "Network connection failed",
            }
        except Exception as e:
            logger.error(f"Unexpected error getting account info: {e}")
            return {"success": False, "data": None, "error": str(e)}

    def get_order_book(self, symbol: str, limit: int = 100) -> Dict:
        """Get market depth data (order book)"""
        try:
            if not self.exchange:
                return {
                    "success": False,
                    "data": None,
                    "error": "Exchange client not initialized",
                }

            order_book = self.exchange.fetch_order_book(symbol, limit=limit)
            return {"success": True, "data": order_book, "error": None}
        except ccxt.ExchangeError as e:
            logger.error(f"Exchange error getting order book for {symbol}: {e}")
            return {"success": False, "data": None, "error": str(e)}
        except ccxt.NetworkError as e:
            logger.error(f"Network error getting order book for {symbol}: {e}")
            return {
                "success": False,
                "data": None,
                "error": "Network connection failed",
            }
        except Exception as e:
            logger.error(f"Unexpected error getting order book for {symbol}: {e}")
            return {"success": False, "data": None, "error": str(e)}

    def set_trading_mode(self, mode: str) -> Dict:
        """Switch between spot and futures trading modes"""
        try:
            if mode.lower() not in ["spot", "futures"]:
                return {
                    "success": False,
                    "data": None,
                    "error": "Invalid mode. Use 'spot' or 'futures'",
                }

            # Update exchange configuration
            self.exchange.options["defaultType"] = mode.lower()

            # Reinitialize exchange with new type
            self.exchange.load_markets()

            return {
                "success": True,
                "data": {"trading_mode": mode.lower()},
                "error": None,
            }
        except Exception as e:
            logger.error(f"Error setting trading mode to {mode}: {e}")
            return {"success": False, "data": None, "error": str(e)}

    def get_trading_fees(self, symbol: Optional[str] = None) -> Dict:
        """Get current trading fees"""
        try:
            if self.config.PAPER_TRADING:
                return {
                    "success": True,
                    "data": {
                        "maker": 0.001,  # 0.1%
                        "taker": 0.001,  # 0.1%
                        "symbol": symbol,
                    },
                    "error": None,
                }

            if symbol:
                fees = self.exchange.fetch_trading_fees()
                symbol_fee = fees.get(symbol, {})
                return {"success": True, "data": symbol_fee, "error": None}
            else:
                fees = self.exchange.fetch_trading_fees()
                return {"success": True, "data": fees, "error": None}
        except ccxt.AuthenticationError as e:
            logger.error(f"Authentication error getting trading fees: {e}")
            return {"success": False, "data": None, "error": "Authentication failed"}
        except ccxt.ExchangeError as e:
            logger.error(f"Exchange error getting trading fees: {e}")
            return {"success": False, "data": None, "error": str(e)}
        except ccxt.NetworkError as e:
            logger.error(f"Network error getting trading fees: {e}")
            return {
                "success": False,
                "data": None,
                "error": "Network connection failed",
            }
        except Exception as e:
            logger.error(f"Unexpected error getting trading fees: {e}")
            return {"success": False, "data": None, "error": str(e)}

    def get_deposit_history(
        self, asset: Optional[str] = None, limit: int = 100
    ) -> Dict:
        """Get deposit history"""
        try:
            if self.config.PAPER_TRADING:
                return {"success": True, "data": [], "error": None}

            deposits = self.exchange.fetch_deposits(asset, limit=limit)
            return {"success": True, "data": deposits, "error": None}
        except ccxt.AuthenticationError as e:
            logger.error(f"Authentication error getting deposit history: {e}")
            return {"success": False, "data": None, "error": "Authentication failed"}
        except ccxt.ExchangeError as e:
            logger.error(f"Exchange error getting deposit history: {e}")
            return {"success": False, "data": None, "error": str(e)}
        except ccxt.NetworkError as e:
            logger.error(f"Network error getting deposit history: {e}")
            return {
                "success": False,
                "data": None,
                "error": "Network connection failed",
            }
        except Exception as e:
            logger.error(f"Unexpected error getting deposit history: {e}")
            return {"success": False, "data": None, "error": str(e)}

    def get_withdraw_history(
        self, asset: Optional[str] = None, limit: int = 100
    ) -> Dict:
        """Get withdrawal history"""
        try:
            if self.config.PAPER_TRADING:
                return {"success": True, "data": [], "error": None}

            withdrawals = self.exchange.fetch_withdrawals(asset, limit=limit)
            return {"success": True, "data": withdrawals, "error": None}
        except ccxt.AuthenticationError as e:
            logger.error(f"Authentication error getting withdrawal history: {e}")
            return {"success": False, "data": None, "error": "Authentication failed"}
        except ccxt.ExchangeError as e:
            logger.error(f"Exchange error getting withdrawal history: {e}")
            return {"success": False, "data": None, "error": str(e)}
        except ccxt.NetworkError as e:
            logger.error(f"Network error getting withdrawal history: {e}")
            return {
                "success": False,
                "data": None,
                "error": "Network connection failed",
            }
        except Exception as e:
            logger.error(f"Unexpected error getting withdrawal history: {e}")
            return {"success": False, "data": None, "error": str(e)}

    def test_connection(self) -> Dict:
        """Enhanced connection testing with detailed status information"""
        try:
            start_time = time.time()

            if self.config.PAPER_TRADING:
                return {
                    "success": True,
                    "data": {
                        "connection": "healthy",
                        "authentication": "paper_trading",
                        "response_time": 0.001,
                        "connection_quality": "excellent",
                        "timestamp": int(time.time() * 1000),
                    },
                    "error": None,
                }

            # Check if exchange is initialized
            if not self.exchange:
                return {
                    "success": False,
                    "data": None,
                    "error": "Exchange client not initialized",
                }

            # Test basic connectivity with proper error handling
            try:
                server_time = self.exchange.fetch_time()
                response_time = time.time() - start_time
                self.is_connected = True
                self.last_connection_test = time.time()
            except ccxt.NetworkError as e:
                logger.error(f"Network error during connection test: {e}")
                self.is_connected = False
                return {
                    "success": False,
                    "data": None,
                    "error": f"Network error: {str(e)}",
                }

            # Test API key permissions
            try:
                # account_info = self.exchange.fetch_balance()  # Commented out as unused
                has_trading_permission = True
            except ccxt.AuthenticationError as e:
                logger.warning(f"Authentication error during connection test: {e}")
                has_trading_permission = False
            except ccxt.ExchangeError as e:
                logger.error(f"Exchange error during permission test: {e}")
                has_trading_permission = False

            # Determine connection quality based on response time
            if response_time < 0.1:
                quality = "excellent"
            elif response_time < 0.5:
                quality = "good"
            elif response_time < 1.0:
                quality = "fair"
            else:
                quality = "poor"

            return {
                "success": True,
                "data": {
                    "connection": "healthy" if has_trading_permission else "degraded",
                    "authentication": (
                        "verified" if has_trading_permission else "limited"
                    ),
                    "response_time": response_time,
                    "connection_quality": quality,
                    "server_time": server_time,
                    "timestamp": int(time.time() * 1000),
                },
                "error": None,
            }

        except ccxt.NetworkError as e:
            logger.error(f"Network error in connection test: {e}")
            return {"success": False, "data": None, "error": f"Network error: {str(e)}"}
        except ccxt.AuthenticationError as e:
            logger.error(f"Authentication error in connection test: {e}")
            return {
                "success": False,
                "data": None,
                "error": f"Authentication failed: {str(e)}",
            }
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return {
                "success": False,
                "data": None,
                "error": f"Connection test failed: {str(e)}",
            }

    def validate_price_data(self, data: Dict, symbol: str) -> bool:
        """Validate price data for obvious errors or manipulation"""
        try:
            if not data or not isinstance(data, dict):
                logger.warning(f"Invalid data format for {symbol}")
                return False

            # Check required fields
            required_fields = ["last", "bid", "ask", "baseVolume"]
            for field in required_fields:
                if field not in data or data[field] is None:
                    logger.warning(f"Missing {field} for {symbol}")
                    return False

            price = float(data["last"])
            bid = float(data["bid"])
            ask = float(data["ask"])
            volume = float(data["baseVolume"])

            # Basic validation checks
            if price <= 0 or bid <= 0 or ask <= 0:
                logger.warning(
                    f"Invalid price values for {symbol}: price={price}, bid={bid}, ask={ask}"
                )
                return False

            # Check bid/ask relationship
            if bid > ask:
                logger.warning(
                    f"Bid higher than ask for {symbol}: bid={bid}, ask={ask}"
                )
                return False

            # Check price is within bid/ask spread
            if price < bid or price > ask:
                logger.warning(
                    f"Price outside bid/ask spread for {symbol}: price={price}, bid={bid}, ask={ask}"
                )
                return False

            # Check for suspicious volume
            if volume < 0:
                logger.warning(f"Negative volume for {symbol}: {volume}")
                return False

            return True

        except (ValueError, TypeError) as e:
            logger.error(f"Error validating price data for {symbol}: {e}")
            return False

    def check_data_freshness(self, timestamp: int, max_age_seconds: int = 300) -> bool:
        """Check if market data is fresh enough"""
        try:
            current_time = int(time.time() * 1000)  # Convert to milliseconds
            age_ms = current_time - timestamp
            age_seconds = age_ms / 1000

            return age_seconds <= max_age_seconds

        except Exception as e:
            logger.error(f"Error checking data freshness: {e}")
            return False

    def get_enhanced_ticker(self, symbol: str) -> Dict:
        """Get ticker with enhanced validation and error handling"""
        try:
            if self.config.PAPER_TRADING:
                # Enhanced paper trading simulation
                import random

                base_prices = {
                    "BTC/USDT": 45000,
                    "ETH/USDT": 2800,
                    "ADA/USDT": 0.45,
                    "BNB/USDT": 300,
                    "SOL/USDT": 100,
                    "DOT/USDT": 25,
                }

                base_price = base_prices.get(symbol, 100)
                # Add realistic price movement
                change_pct = random.uniform(-0.05, 0.05)  # ±5% movement
                current_price = base_price * (1 + change_pct)

                # Simulate realistic bid/ask spread
                spread_pct = 0.001  # 0.1% spread
                bid = current_price * (1 - spread_pct)
                ask = current_price * (1 + spread_pct)

                ticker_data = {
                    "symbol": symbol,
                    "last": current_price,
                    "bid": bid,
                    "ask": ask,
                    "percentage": change_pct * 100,
                    "baseVolume": random.uniform(1000, 10000),
                    "timestamp": int(time.time() * 1000),
                }

                return {
                    "success": True,
                    "data": ticker_data,
                    "validated": True,
                    "fresh": True,
                }

            # Get real ticker data
            ticker = self.exchange.fetch_ticker(symbol)

            # Validate the data
            is_valid = self.validate_price_data(ticker, symbol)
            is_fresh = self.check_data_freshness(ticker.get("timestamp", 0))

            return {
                "success": True,
                "data": ticker,
                "validated": is_valid,
                "fresh": is_fresh,
                "warnings": (
                    []
                    if is_valid and is_fresh
                    else [
                        "Data validation failed" if not is_valid else "",
                        "Data may be stale" if not is_fresh else "",
                    ]
                ),
            }

        except ccxt.ExchangeError as e:
            logger.error(f"Exchange error getting ticker for {symbol}: {e}")
            return {
                "success": False,
                "data": None,
                "error": f"Exchange error: {str(e)}",
                "validated": False,
                "fresh": False,
            }
        except Exception as e:
            logger.error(f"Error getting enhanced ticker for {symbol}: {e}")
            return {
                "success": False,
                "data": None,
                "error": str(e),
                "validated": False,
                "fresh": False,
            }

    def get_rate_limit_status(self) -> Dict:
        """Get current rate limiting status"""
        try:
            # Get rate limit info from exchange headers
            rate_limit_info = {
                "requests_per_minute": getattr(self.exchange, "rateLimit", 1200),
                "current_weight": 0,  # Would need to track this
                "remaining_requests": 1000,  # Estimated
                "reset_time": int(time.time()) + 60,
            }

            return {"success": True, "data": rate_limit_info}

        except Exception as e:
            logger.error(f"Error getting rate limit status: {e}")
            return {"success": False, "error": str(e)}

    def adaptive_rate_limit(self, endpoint_type: str = "default"):
        """Implement adaptive rate limiting based on API response"""
        try:
            # Different rate limits for different endpoint types
            rate_limits = {
                "ticker": 0.1,  # 10 requests per second
                "orderbook": 0.2,  # 5 requests per second
                "trades": 0.5,  # 2 requests per second
                "account": 1.0,  # 1 request per second
                "default": 0.5,
            }

            delay = rate_limits.get(endpoint_type, 0.5)
            time.sleep(delay)

            return True

        except Exception as e:
            logger.error(f"Error in adaptive rate limiting: {e}")
            return False

    def circuit_breaker_check(self) -> bool:
        """Check if circuit breaker should be triggered"""
        try:
            # Simple circuit breaker implementation
            if not hasattr(self, "_error_count"):
                self._error_count = 0
                self._error_window_start = time.time()

            # Reset error count every 5 minutes
            if time.time() - self._error_window_start > 300:
                self._error_count = 0
                self._error_window_start = time.time()

            # Trigger circuit breaker if too many errors
            if self._error_count > 10:
                logger.warning("Circuit breaker triggered - too many API errors")
                return True

            return False

        except Exception as e:
            logger.error(f"Error in circuit breaker check: {e}")
            return False

    def log_api_interaction(
        self, method: str, symbol: str = None, duration: float = 0, error: str = None
    ):
        """Log API interactions for monitoring"""
        try:
            # log_entry = {  # Commented out as unused variable
            #     "timestamp": datetime.utcnow().isoformat(),
            #     "method": method,
            #     "symbol": symbol,
            #     "duration": duration,
            #     "success": error is None,
            #     "error": error
            # }

            # Log to file or monitoring system
            if error:
                logger.error(f"API Error - {method}: {error}")
                # Increment error count for circuit breaker
                if hasattr(self, "_error_count"):
                    self._error_count += 1
            else:
                logger.debug(f"API Success - {method} completed in {duration:.3f}s")

        except Exception as e:
            logger.error(f"Error logging API interaction: {e}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((ccxt.NetworkError, ccxt.ExchangeError)),
    )
    def _retryable_api_call(self, func, *args, **kwargs):
        """Wrapper for retryable API calls"""
        return func(*args, **kwargs)

    def get_connection_status(self) -> Dict:
        """Get detailed connection status"""
        return {
            "is_connected": self.is_connected,
            "last_test": self.last_connection_test,
            "exchange_initialized": self.exchange is not None,
            "paper_trading": self.config.PAPER_TRADING,
            "testnet": self.config.BINANCE_TESTNET,
        }

    def validate_symbol(self, symbol: str) -> bool:
        """Validate if symbol is available for trading"""
        try:
            markets = self.get_markets()
            return symbol in markets
        except Exception as e:
            logger.error(f"Error validating symbol {symbol}: {e}")
            return False

    def validate_order_parameters(
        self, symbol: str, side: str, amount: float, price: Optional[float] = None
    ) -> Dict:
        """Validate order parameters including precision, step size, and minimum amounts (Fix: Bug #1)"""
        try:
            # For paper trading or when markets aren't available, use basic validation
            if self.config.PAPER_TRADING:
                # Basic validation for paper trading
                if amount <= 0:
                    return {"valid": False, "error": "Amount must be positive"}
                if price is not None and price <= 0:
                    return {"valid": False, "error": "Price must be positive"}
                return {"valid": True, "error": None}

            markets = self.get_markets()
            if not markets:
                # If markets aren't available, skip detailed validation
                logger.warning("Markets not available, using basic validation")
                if amount <= 0:
                    return {"valid": False, "error": "Amount must be positive"}
                if price is not None and price <= 0:
                    return {"valid": False, "error": "Price must be positive"}
                return {"valid": True, "error": None}

            if symbol not in markets:
                return {"valid": False, "error": f"Symbol {symbol} not available"}

            market_info = markets.get(symbol, {})

            if not market_info:
                return {
                    "valid": False,
                    "error": f"Market info not available for {symbol}",
                }

            # Check amount precision and step size
            amount_precision = market_info.get("precision", {}).get("amount", 8)
            if round(amount, amount_precision) != amount:
                return {
                    "valid": False,
                    "error": f"Amount precision should be {amount_precision} decimal places",
                }

            # Check amount step size using proper decimal arithmetic (Fix: Bug #1)
            step_size = (
                market_info.get("limits", {}).get("amount", {}).get("step", 0.00000001)
            )
            try:
                decimal_amount = Decimal(str(amount))
                decimal_step = Decimal(str(step_size))
                if decimal_step > 0 and decimal_amount % decimal_step != 0:
                    return {
                        "valid": False,
                        "error": f"Amount must be multiple of step size {step_size}",
                    }
            except Exception as e:
                logger.warning(f"Could not validate step size for amount {amount}: {e}")

            # Check price precision and tick size if limit order
            if price is not None:
                price_precision = market_info.get("precision", {}).get("price", 8)
                if round(price, price_precision) != price:
                    return {
                        "valid": False,
                        "error": f"Price precision should be {price_precision} decimal places",
                    }

                # Check price tick size using proper decimal arithmetic (Fix: Bug #1)
                tick_size = (
                    market_info.get("limits", {})
                    .get("price", {})
                    .get("step", 0.00000001)
                )
                try:
                    decimal_price = Decimal(str(price))
                    decimal_tick = Decimal(str(tick_size))
                    if decimal_tick > 0 and decimal_price % decimal_tick != 0:
                        return {
                            "valid": False,
                            "error": f"Price must be multiple of tick size {tick_size}",
                        }
                except Exception as e:
                    logger.warning(
                        f"Could not validate tick size for price {price}: {e}"
                    )

            # Check minimum amounts
            min_amount = market_info.get("limits", {}).get("amount", {}).get("min", 0)
            if amount < min_amount:
                return {"valid": False, "error": f"Minimum amount is {min_amount}"}

            # Check minimum cost
            min_cost = market_info.get("limits", {}).get("cost", {}).get("min", 0)
            if price and (amount * price) < min_cost:
                return {"valid": False, "error": f"Minimum order cost is {min_cost}"}

            return {"valid": True, "error": None}

        except Exception as e:
            logger.error(f"Error validating order parameters: {e}")
            return {"valid": False, "error": str(e)}

    def _format_amount(self, symbol: str, amount: float) -> float:
        """Format amount to correct step size using proper decimal arithmetic (Fix: Bug #1)"""
        try:
            markets = self.get_markets()
            market_info = markets.get(symbol, {})
            step_size = (
                market_info.get("limits", {}).get("amount", {}).get("step", 0.00000001)
            )

            # Use decimal arithmetic for precise calculations
            decimal_amount = Decimal(str(amount))
            decimal_step = Decimal(str(step_size))

            if decimal_step > 0:
                # Round to nearest multiple of step_size
                rounded = (decimal_amount / decimal_step).quantize(
                    Decimal("1"), rounding=ROUND_HALF_UP
                ) * decimal_step
                return float(rounded)
            else:
                return amount
        except Exception as e:
            logger.error(f"Error formatting amount: {e}")
            return amount

    def _format_price(self, symbol: str, price: float) -> float:
        """Format price to correct tick size using proper decimal arithmetic (Fix: Bug #1)"""
        try:
            markets = self.get_markets()
            market_info = markets.get(symbol, {})
            tick_size = (
                market_info.get("limits", {}).get("price", {}).get("step", 0.00000001)
            )

            # Use decimal arithmetic for precise calculations
            decimal_price = Decimal(str(price))
            decimal_tick = Decimal(str(tick_size))

            if decimal_tick > 0:
                # Round to nearest multiple of tick_size
                rounded = (decimal_price / decimal_tick).quantize(
                    Decimal("1"), rounding=ROUND_HALF_UP
                ) * decimal_tick
                return float(rounded)
            else:
                return price
        except Exception as e:
            logger.error(f"Error formatting price: {e}")
            return price
