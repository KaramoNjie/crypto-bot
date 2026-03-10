"""

# Add the src directory to the Python path

Paper Trading Safety Mechanisms
Comprehensive safety layer that prevents real money trades when in paper mode
"""

import logging
from decimal import Decimal
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from enum import Enum
from dataclasses import dataclass, field
import json

from ..utils.logging_config import TradingLogger


class OrderSide(Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"


class OrderStatus(Enum):
    FILLED = "FILLED"
    REJECTED = "REJECTED"
    PENDING = "PENDING"


class TradingMode(Enum):
    """Trading mode enumeration"""

    PAPER = "paper"
    LIVE = "live"
    SANDBOX = "sandbox"  # Exchange testnet


class SafetyLevel(Enum):
    """Safety level enumeration"""

    MAXIMUM = "maximum"  # All trades blocked, paper only
    HIGH = "high"  # Strict limits, paper default
    MEDIUM = "medium"  # Normal limits
    LOW = "low"  # Minimal safety checks


@dataclass
class PaperOrderResult:
    """Result of paper order execution"""

    order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: float
    status: OrderStatus
    filled_quantity: float
    average_price: float
    fees: float
    commission: float
    timestamp: datetime

    # Paper trading specific
    simulated: bool = True
    slippage: float = 0.0
    latency_ms: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "orderId": self.order_id,
            "symbol": self.symbol,
            "side": self.side.value,
            "type": self.order_type.value,
            "origQty": str(self.quantity),
            "price": str(self.price),
            "status": self.status.value,
            "executedQty": str(self.filled_quantity),
            "cummulativeQuoteQty": str(self.filled_quantity * self.average_price),
            "avgPrice": str(self.average_price),
            "timeInForce": "GTC",
            "fees": str(self.fees),
            "commission": str(self.commission),
            "transactTime": int(self.timestamp.timestamp() * 1000),
            "simulated": self.simulated,
            "slippage": self.slippage,
            "latency": self.latency_ms,
        }


@dataclass
class SafetyConfig:
    """Safety configuration"""

    # Trading mode
    trading_mode: TradingMode = TradingMode.PAPER
    safety_level: SafetyLevel = SafetyLevel.HIGH

    # Paper trading settings
    paper_initial_balance: float = 100.0
    paper_slippage_bps: int = 10  # 10 basis points (0.1%)
    paper_latency_ms: int = 100
    paper_fee_rate: float = 0.001  # 0.1%

    # Safety limits (even for paper trading)
    max_order_size_usd: float = 100.0
    max_daily_trades: int = 100
    max_positions: int = 10
    max_drawdown_pct: float = 0.20  # 20%

    # Emergency controls
    enable_emergency_stop: bool = True
    emergency_stop_active: bool = False

    # Validation settings
    require_confirmation: bool = True
    log_all_attempts: bool = True
    block_live_on_error: bool = True


class PaperTradingSafetyGuard:
    """
    Comprehensive safety guard that ensures paper trading is truly safe
    Prevents any real money from being at risk
    """

    def __init__(self, config: SafetyConfig) -> None:
        self.config = config
        self.logger = TradingLogger("paper_trading_safety")

        # State tracking
        self.paper_balance = config.paper_initial_balance
        self.paper_positions: Dict[str, Dict[str, Any]] = {}
        self.daily_trade_count = 0
        self.last_trade_date = datetime.utcnow().date()

        # Safety flags
        self.safety_engaged = True
        self.emergency_stop = config.emergency_stop_active
        self.live_trading_blocked = True  # Block live trading by default

        # Audit trail
        self.safety_events: List[Dict[str, Any]] = []
        self.blocked_attempts: List[Dict[str, Any]] = []

        # Initialize safety
        self._initialize_safety_systems()

    def _initialize_safety_systems(self):
        """Initialize all safety systems"""

        # Verify paper mode is set
        if self.config.trading_mode != TradingMode.PAPER:
            self.logger.log_error(
                error_type="safety_violation",
                error_message=f"Trading mode is {self.config.trading_mode.value}, but paper safety guard is active",
                component="paper_trading_safety",
            )

            # Force paper mode
            self.config.trading_mode = TradingMode.PAPER

        # Log safety engagement
        self._log_safety_event(
            "safety_guard_initialized",
            {
                "trading_mode": self.config.trading_mode.value,
                "safety_level": self.config.safety_level.value,
                "paper_balance": self.paper_balance,
                "emergency_stop": self.emergency_stop,
            },
        )

        self.logger.logger.info(
            "Paper trading safety guard engaged",
            mode=self.config.trading_mode.value,
            safety_level=self.config.safety_level.value,
            balance=self.paper_balance,
        )

    def validate_order_safety(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: Optional[float] = None,
        order_type: str = "MARKET",
    ) -> Dict[str, Any]:
        """
        Comprehensive order safety validation

        Returns:
            Dict with 'safe', 'reasons', 'warnings' keys
        """

        safety_result = {
            "safe": True,
            "reasons": [],
            "warnings": [],
            "mode_override": None,
        }

        try:
            # 1. Emergency stop check
            if self.emergency_stop:
                safety_result["safe"] = False
                safety_result["reasons"].append("Emergency stop is active")

                self._log_blocked_attempt(
                    "emergency_stop",
                    {"symbol": symbol, "side": side, "quantity": quantity},
                )

                return safety_result

            # 2. Trading mode verification
            if self.config.trading_mode != TradingMode.PAPER:
                safety_result["safe"] = False
                safety_result["reasons"].append(
                    f"Trading mode is {self.config.trading_mode.value}, expected PAPER"
                )

                # Force override to paper mode
                safety_result["mode_override"] = TradingMode.PAPER

                self._log_blocked_attempt(
                    "wrong_trading_mode",
                    {
                        "expected": TradingMode.PAPER.value,
                        "actual": self.config.trading_mode.value,
                        "symbol": symbol,
                    },
                )

            # 3. Order size validation
            estimated_value = quantity * (
                price or 50000
            )  # Use reasonable default price
            if estimated_value > self.config.max_order_size_usd:
                safety_result["safe"] = False
                safety_result["reasons"].append(
                    f"Order size ${estimated_value:.2f} exceeds limit ${self.config.max_order_size_usd:.2f}"
                )

            # 4. Daily trade limit check
            self._update_daily_counter()
            if self.daily_trade_count >= self.config.max_daily_trades:
                safety_result["safe"] = False
                safety_result["reasons"].append(
                    f"Daily trade limit reached ({self.daily_trade_count}/{self.config.max_daily_trades})"
                )

            # 5. Position limit check
            if len(self.paper_positions) >= self.config.max_positions:
                safety_result["safe"] = False
                safety_result["reasons"].append(
                    f"Maximum positions limit reached ({len(self.paper_positions)}/{self.config.max_positions})"
                )

            # 6. Balance validation (for paper trading)
            if estimated_value > self.paper_balance:
                safety_result["safe"] = False
                safety_result["reasons"].append(
                    f"Insufficient paper balance: ${self.paper_balance:.2f} < ${estimated_value:.2f}"
                )

            # 7. Drawdown check
            current_drawdown = self._calculate_current_drawdown()
            if current_drawdown > self.config.max_drawdown_pct:
                safety_result["safe"] = False
                safety_result["reasons"].append(
                    f"Drawdown limit exceeded: {current_drawdown:.1%} > {self.config.max_drawdown_pct:.1%}"
                )

            # Add warnings for edge cases
            if estimated_value > self.config.max_order_size_usd * 0.8:
                safety_result["warnings"].append(
                    f"Large order: ${estimated_value:.2f} (80%+ of limit)"
                )

            if self.daily_trade_count > self.config.max_daily_trades * 0.8:
                safety_result["warnings"].append(
                    f"High daily trade count: {self.daily_trade_count} (80%+ of limit)"
                )

            # Log validation result
            self._log_safety_event(
                "order_safety_validation",
                {
                    "symbol": symbol,
                    "safe": safety_result["safe"],
                    "reasons": safety_result["reasons"],
                    "warnings": safety_result["warnings"],
                },
            )

            return safety_result

        except Exception as e:
            # Safety validation should never fail
            self.logger.log_error(
                error_type="safety_validation_error",
                error_message=str(e),
                component="paper_trading_safety",
                context={"symbol": symbol, "side": side},
            )

            # Fail safe - block the order
            return {
                "safe": False,
                "reasons": [f"Safety validation error: {str(e)}"],
                "warnings": [],
                "mode_override": None,
            }

    def execute_paper_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: Optional[float] = None,
        order_type: str = "MARKET",
        order_id: Optional[str] = None,
    ) -> PaperOrderResult:
        """
        Execute order in paper trading mode with realistic simulation
        """

        try:
            # Generate order ID if not provided
            if not order_id:
                order_id = f"paper_{int(datetime.utcnow().timestamp() * 1000)}"

            # Simulate market price if not provided
            if not price:
                price = self._simulate_market_price(symbol)

            # Apply slippage
            slippage_factor = self.config.paper_slippage_bps / 10000.0
            if side.upper() == "BUY":
                execution_price = price * (1 + slippage_factor)
            else:
                execution_price = price * (1 - slippage_factor)

            # Calculate fees
            trade_value = quantity * execution_price
            fees = trade_value * self.config.paper_fee_rate

            # Create order result
            result = PaperOrderResult(
                order_id=order_id,
                symbol=symbol,
                side=OrderSide.BUY if side.upper() == "BUY" else OrderSide.SELL,
                order_type=(
                    OrderType.MARKET
                    if order_type.upper() == "MARKET"
                    else OrderType.LIMIT
                ),
                quantity=quantity,
                price=price,
                status=OrderStatus.FILLED,  # Paper orders always fill
                filled_quantity=quantity,
                average_price=execution_price,
                fees=fees,
                commission=fees,  # Same as fees for simplicity
                timestamp=datetime.utcnow(),
                simulated=True,
                slippage=slippage_factor,
                latency_ms=self.config.paper_latency_ms,
            )

            # Update paper portfolio
            self._update_paper_portfolio(result)

            # Update daily counter
            self.daily_trade_count += 1

            # Log execution
            self.logger.log_trade_execution(
                order_id=order_id,
                symbol=symbol,
                side=side,
                quantity=quantity,
                price=execution_price,
                status="FILLED",
                fees=fees,
                metadata={
                    "paper_trading": True,
                    "slippage": slippage_factor,
                    "simulated": True,
                },
            )

            self._log_safety_event(
                "paper_order_executed",
                {
                    "order_id": order_id,
                    "symbol": symbol,
                    "side": side,
                    "quantity": quantity,
                    "price": execution_price,
                    "fees": fees,
                    "paper_balance_after": self.paper_balance,
                },
            )

            return result

        except Exception as e:
            self.logger.log_error(
                error_type="paper_execution_error",
                error_message=str(e),
                component="paper_trading_safety",
                context={"symbol": symbol, "side": side, "quantity": quantity},
            )

            # Return failed order
            return PaperOrderResult(
                order_id=order_id or "error",
                symbol=symbol,
                side=OrderSide.BUY if side.upper() == "BUY" else OrderSide.SELL,
                order_type=OrderType.MARKET,
                quantity=quantity,
                price=price or 0,
                status=OrderStatus.REJECTED,
                filled_quantity=0,
                average_price=0,
                fees=0,
                commission=0,
                timestamp=datetime.utcnow(),
                simulated=True,
            )

    def _simulate_market_price(self, symbol: str) -> float:
        """Get real market price for symbol from Binance API"""
        try:
            # Import here to avoid circular imports
            from ..apis.binance_client import BinanceClient
            from ..config.settings import Config

            config = Config()
            binance_client = BinanceClient(config)

            # Get real market price from Binance
            ticker = binance_client.get_ticker(symbol)
            if ticker and 'last' in ticker:
                real_price = float(ticker['last'])
                self.logger.info(f"Retrieved real market price for {symbol}: ${real_price:,.2f}")
                return real_price
            else:
                self.logger.warning(f"Could not get real price for {symbol}, using fallback")

        except Exception as e:
            self.logger.error(f"Error getting real market price for {symbol}: {e}")

        # Fallback prices only if API fails (these should be updated rarely)
        fallback_prices = {
            "BTCUSDT": 45000.0,
            "ETHUSDT": 3200.0,
            "ADAUSDT": 0.65,
            "DOTUSDT": 28.5,
            "LINKUSDT": 15.2,
        }

        fallback_price = fallback_prices.get(symbol, 100.0)
        self.logger.warning(f"Using fallback price for {symbol}: ${fallback_price:,.2f}")
        return fallback_price

    def _update_paper_portfolio(self, order_result: PaperOrderResult):
        """Update paper portfolio with order result"""

        try:
            symbol = order_result.symbol
            side = order_result.side
            quantity = order_result.filled_quantity
            price = order_result.average_price
            fees = order_result.fees

            # Update balance
            if side == OrderSide.BUY:
                self.paper_balance -= quantity * price + fees
            else:
                self.paper_balance += quantity * price - fees

            # Update positions
            if symbol not in self.paper_positions:
                self.paper_positions[symbol] = {
                    "quantity": 0.0,
                    "avg_price": 0.0,
                    "total_cost": 0.0,
                }

            position = self.paper_positions[symbol]

            if side == OrderSide.BUY:
                # Add to position
                new_total_cost = position["total_cost"] + (quantity * price)
                new_quantity = position["quantity"] + quantity

                if new_quantity > 0:
                    position["avg_price"] = new_total_cost / new_quantity
                    position["quantity"] = new_quantity
                    position["total_cost"] = new_total_cost
            else:
                # Reduce position
                position["quantity"] -= quantity
                if position["quantity"] <= 0:
                    # Position closed
                    del self.paper_positions[symbol]
                else:
                    # Update cost basis proportionally
                    position["total_cost"] *= position["quantity"] / (
                        position["quantity"] + quantity
                    )

        except Exception as e:
            self.logger.log_error(
                error_type="portfolio_update_error",
                error_message=str(e),
                component="paper_trading_safety",
            )

    def _calculate_current_drawdown(self) -> float:
        """Calculate current drawdown percentage"""

        try:
            # Simple drawdown calculation
            current_value = self._calculate_portfolio_value()
            initial_value = self.config.paper_initial_balance

            if current_value < initial_value:
                drawdown = (initial_value - current_value) / initial_value
                return drawdown

            return 0.0

        except Exception:
            return 0.0  # Default to no drawdown on error

    def _calculate_portfolio_value(self) -> float:
        """Calculate current paper portfolio value"""

        try:
            total_value = self.paper_balance

            # Add position values
            for symbol, position in self.paper_positions.items():
                current_price = self._simulate_market_price(symbol)
                position_value = position["quantity"] * current_price
                total_value += position_value

            return total_value

        except Exception:
            return self.paper_balance  # Fallback to cash balance

    def _update_daily_counter(self):
        """Update daily trade counter"""

        current_date = datetime.utcnow().date()

        if current_date != self.last_trade_date:
            # New day, reset counter
            self.daily_trade_count = 0
            self.last_trade_date = current_date

    def _log_safety_event(self, event_type: str, data: Dict[str, Any]):
        """Log safety event"""

        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "data": data,
        }

        self.safety_events.append(event)

        # Keep history manageable
        if len(self.safety_events) > 1000:
            self.safety_events = self.safety_events[-1000:]

    def _log_blocked_attempt(self, reason: str, data: Dict[str, Any]):
        """Log blocked trading attempt"""

        blocked_event = {
            "timestamp": datetime.utcnow().isoformat(),
            "reason": reason,
            "data": data,
        }

        self.blocked_attempts.append(blocked_event)

        # Keep history manageable
        if len(self.blocked_attempts) > 500:
            self.blocked_attempts = self.blocked_attempts[-500:]

        # Log as warning
        self.logger.logger.warning(
            "Trading attempt blocked by safety guard", reason=reason, data=data
        )

    # Control methods

    def engage_emergency_stop(self, reason: str = "Manual activation"):
        """Engage emergency stop"""

        self.emergency_stop = True

        self._log_safety_event(
            "emergency_stop_engaged",
            {"reason": reason, "timestamp": datetime.utcnow().isoformat()},
        )

        self.logger.logger.error("🚨 EMERGENCY STOP ENGAGED 🚨", reason=reason)

    def disengage_emergency_stop(self, authorization_code: Optional[str] = None):
        """Disengage emergency stop with authorization"""

        # Simple authorization check (would be more robust in production)
        if authorization_code != "SAFE_TO_RESUME_PAPER_TRADING":
            self.logger.logger.warning(
                "Emergency stop disengage attempt with invalid authorization",
                provided_code=authorization_code,
            )
            return False

        self.emergency_stop = False

        self._log_safety_event(
            "emergency_stop_disengaged",
            {"authorization": "valid", "timestamp": datetime.utcnow().isoformat()},
        )

        self.logger.logger.info("Emergency stop disengaged - paper trading resumed")
        return True

    def force_paper_mode(self):
        """Force trading mode to paper (safety override)"""

        self.config.trading_mode = TradingMode.PAPER
        self.live_trading_blocked = True

        self._log_safety_event(
            "forced_paper_mode",
            {"timestamp": datetime.utcnow().isoformat(), "safety_override": True},
        )

        self.logger.logger.warning("Trading mode forced to PAPER by safety guard")

    def reset_paper_portfolio(self, authorization_code: Optional[str] = None) -> None:
        """Reset paper portfolio to initial state"""

        if authorization_code != "RESET_PAPER_PORTFOLIO":
            return False

        self.paper_balance = self.config.paper_initial_balance
        self.paper_positions.clear()
        self.daily_trade_count = 0

        self._log_safety_event(
            "paper_portfolio_reset",
            {
                "new_balance": self.paper_balance,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

        self.logger.logger.info("Paper portfolio reset", balance=self.paper_balance)

        return True

    # Status and reporting methods

    def get_safety_status(self) -> Dict[str, Any]:
        """Get comprehensive safety status"""

        return {
            "safety_engaged": self.safety_engaged,
            "trading_mode": self.config.trading_mode.value,
            "safety_level": self.config.safety_level.value,
            "emergency_stop": self.emergency_stop,
            "live_trading_blocked": self.live_trading_blocked,
            "paper_balance": self.paper_balance,
            "paper_positions": len(self.paper_positions),
            "portfolio_value": self._calculate_portfolio_value(),
            "daily_trades": self.daily_trade_count,
            "current_drawdown": self._calculate_current_drawdown(),
            "safety_events_count": len(self.safety_events),
            "blocked_attempts_count": len(self.blocked_attempts),
            "last_safety_check": datetime.utcnow().isoformat(),
        }

    def get_paper_portfolio_summary(self) -> Dict[str, Any]:
        """Get paper portfolio summary"""

        return {
            "cash_balance": self.paper_balance,
            "positions": dict(self.paper_positions),
            "total_value": self._calculate_portfolio_value(),
            "initial_value": self.config.paper_initial_balance,
            "pnl": self._calculate_portfolio_value()
            - self.config.paper_initial_balance,
            "pnl_percentage": (
                (self._calculate_portfolio_value() / self.config.paper_initial_balance)
                - 1
            )
            * 100,
            "drawdown": self._calculate_current_drawdown(),
            "daily_trades": self.daily_trade_count,
        }

    def get_blocked_attempts_summary(self) -> List[Dict[str, Any]]:
        """Get summary of blocked attempts"""

        return self.blocked_attempts[-20:]  # Last 20 blocked attempts

    def export_safety_log(self) -> str:
        """Export safety log as JSON"""

        export_data = {
            "safety_status": self.get_safety_status(),
            "portfolio_summary": self.get_paper_portfolio_summary(),
            "safety_events": self.safety_events,
            "blocked_attempts": self.blocked_attempts,
            "export_timestamp": datetime.utcnow().isoformat(),
        }

        return json.dumps(export_data, indent=2)


# Factory function
def create_paper_trading_guard(
    paper_balance: float = 10000.0, safety_level: SafetyLevel = SafetyLevel.HIGH
) -> PaperTradingSafetyGuard:
    """Create paper trading safety guard with configuration"""

    config = SafetyConfig(
        trading_mode=TradingMode.PAPER,
        safety_level=safety_level,
        paper_initial_balance=paper_balance,
        emergency_stop_active=False,
    )

    return PaperTradingSafetyGuard(config)


# Context manager for safe trading operations
class SafeTradingContext:
    """Context manager that ensures safe trading operations"""

    def __init__(self, safety_guard: PaperTradingSafetyGuard) -> None:
        self.safety_guard = safety_guard
        self.operations = []

    def __enter__(self) -> None:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        # Log all operations
        if self.operations:
            self.safety_guard._log_safety_event(
                "safe_trading_context_closed",
                {
                    "operations_count": len(self.operations),
                    "operations": self.operations,
                },
            )

    def execute_order(
        self, symbol: str, side: str, quantity: float, **kwargs
    ) -> PaperOrderResult:
        """Execute order within safe context"""

        # Validate safety first
        safety_check = self.safety_guard.validate_order_safety(
            symbol, side, quantity, **kwargs
        )

        if not safety_check["safe"]:
            # Log blocked operation
            operation = {
                "type": "blocked_order",
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "reasons": safety_check["reasons"],
            }
            self.operations.append(operation)

            # Raise exception
            raise ValueError(
                f"Order blocked by safety guard: {', '.join(safety_check['reasons'])}"
            )

        # Execute paper order
        result = self.safety_guard.execute_paper_order(symbol, side, quantity, **kwargs)

        # Log successful operation
        operation = {
            "type": "executed_order",
            "order_id": result.order_id,
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "price": result.average_price,
        }
        self.operations.append(operation)

        return result


# Example usage and testing
if __name__ == "__main__":

    # Create safety guard
    safety_guard = create_paper_trading_guard(paper_balance=10000.0)

    print("Paper Trading Safety Guard - Test Run")
    print("=" * 50)

    # Test order validation
    print("\n1. Testing order validation...")

    validation = safety_guard.validate_order_safety("BTCUSDT", "BUY", 0.1, 45000)
    print(f"Order validation: {validation}")

    # Test paper order execution
    print("\n2. Testing paper order execution...")

    if validation["safe"]:
        result = safety_guard.execute_paper_order("BTCUSDT", "BUY", 0.1, 45000)
        print(f"Paper order result: {result.to_dict()}")

    # Test safety context
    print("\n3. Testing safe trading context...")

    try:
        with SafeTradingContext(safety_guard) as context:
            result1 = context.execute_order("ETHUSDT", "BUY", 1.0, price=3200)
            print(f"Context order 1: {result1.order_id}")

            result2 = context.execute_order("ADAUSDT", "BUY", 1000.0, price=0.65)
            print(f"Context order 2: {result2.order_id}")

    except ValueError as e:
        print(f"Context error: {e}")

    # Show portfolio status
    print("\n4. Portfolio status...")
    portfolio = safety_guard.get_paper_portfolio_summary()
    for key, value in portfolio.items():
        print(f"{key}: {value}")

    # Test emergency stop
    print("\n5. Testing emergency stop...")
    safety_guard.engage_emergency_stop("Test emergency stop")

    validation = safety_guard.validate_order_safety("BTCUSDT", "SELL", 0.05)
    print(f"Validation after emergency stop: {validation['safe']}")

    # Resume trading
    success = safety_guard.disengage_emergency_stop("SAFE_TO_RESUME_PAPER_TRADING")
    print(f"Emergency stop disengaged: {success}")

    print("\n" + "=" * 50)
    print("Paper Trading Safety Guard test completed!")
