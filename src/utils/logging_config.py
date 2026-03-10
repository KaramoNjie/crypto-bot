"""
Structured logging configuration with structlog
"""

import logging
import logging.config
import sys
from datetime import datetime
from typing import Any, Dict, Optional
import structlog
import json
from pathlib import Path


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging"""

    def format(self, record):
        """Format log record as JSON"""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in (
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
                "getMessage",
                "exc_info",
                "exc_text",
                "stack_info",
            ):
                log_entry[key] = value

        return json.dumps(log_entry, default=str)


def configure_structlog():
    """Configure structlog for structured logging"""

    def add_timestamp(logger, method_name, event_dict):
        """Add timestamp to log entry"""
        event_dict["timestamp"] = datetime.utcnow().isoformat()
        return event_dict

    def add_log_level(logger, method_name, event_dict):
        """Add log level to entry"""
        event_dict["level"] = method_name.upper()
        return event_dict

    def add_logger_name(logger, method_name, event_dict):
        """Add logger name to entry"""
        event_dict["logger"] = logger.name
        return event_dict

    # Configure structlog
    structlog.configure(
        processors=[
            add_timestamp,
            add_log_level,
            add_logger_name,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.stdlib.LoggerFactory(),
        context_class=dict,
        cache_logger_on_first_use=True,
    )


def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    enable_console: bool = True,
    enable_structured: bool = True,
):
    """
    Setup comprehensive logging configuration

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional log file path
        enable_console: Whether to enable console logging
        enable_structured: Whether to use structured JSON logging
    """

    # Create logs directory if it doesn't exist
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

    # Configure structlog if enabled
    if enable_structured:
        configure_structlog()

    # Base logging configuration
    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {"format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s"},
            "detailed": {
                "format": "%(asctime)s [%(levelname)s] %(name)s.%(funcName)s:%(lineno)d: %(message)s"
            },
            "json": {
                "()": JSONFormatter,
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": log_level,
                "formatter": "json" if enable_structured else "standard",
                "stream": sys.stdout,
            }
        },
        "loggers": {
            "": {"level": log_level, "handlers": [], "propagate": False},  # Root logger
            "src": {  # Application logger
                "level": log_level,
                "handlers": [],
                "propagate": False,
            },
            "trading_bot": {  # Bot logger
                "level": log_level,
                "handlers": [],
                "propagate": False,
            },
        },
    }

    # Add console handler if enabled
    if enable_console:
        for logger_name in config["loggers"]:
            config["loggers"][logger_name]["handlers"].append("console")

    # Add file handler if log file specified
    if log_file:
        config["handlers"]["file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "level": log_level,
            "formatter": "json" if enable_structured else "detailed",
            "filename": log_file,
            "maxBytes": 10 * 1024 * 1024,  # 10MB
            "backupCount": 5,
            "encoding": "utf8",
        }

        # Add file handler to all loggers
        for logger_name in config["loggers"]:
            config["loggers"][logger_name]["handlers"].append("file")

    # Apply configuration
    logging.config.dictConfig(config)

    # Set specific library log levels
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    logging.getLogger("websockets").setLevel(logging.WARNING)
    logging.getLogger("ccxt").setLevel(logging.INFO)
    logging.getLogger("binance").setLevel(logging.INFO)

    # Test logging
    logger = (
        structlog.get_logger("logging_config")
        if enable_structured
        else logging.getLogger("logging_config")
    )
    logger.info(
        "Logging system configured",
        log_level=log_level,
        structured=enable_structured,
        file_logging=bool(log_file),
    )


class TradingLogger:
    """Enhanced logger for trading operations"""

    def __init__(self, name: str) -> None:
        self.logger = structlog.get_logger(name)
        self.name = name

    def log_trade_signal(
        self,
        signal_id: str,
        symbol: str,
        direction: str,
        confidence: float,
        price: float,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Log trading signal"""
        self.logger.info(
            "Trading signal generated",
            event_type="signal",
            signal_id=signal_id,
            symbol=symbol,
            direction=direction,
            confidence=confidence,
            price=price,
            metadata=metadata or {},
        )

    def log_trade_execution(
        self,
        order_id: str,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        status: str,
        fees: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Log trade execution"""
        self.logger.info(
            "Trade executed",
            event_type="execution",
            order_id=order_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            status=status,
            fees=fees,
            metadata=metadata or {},
        )

    def log_risk_assessment(
        self,
        signal_id: str,
        symbol: str,
        approved: bool,
        risk_level: str,
        position_size: float,
        reasons: list,
        warnings: list,
    ):
        """Log risk assessment"""
        self.logger.info(
            "Risk assessment completed",
            event_type="risk_assessment",
            signal_id=signal_id,
            symbol=symbol,
            approved=approved,
            risk_level=risk_level,
            position_size=position_size,
            reasons=reasons,
            warnings=warnings,
        )

    def log_portfolio_update(
        self,
        total_balance: float,
        available_balance: float,
        unrealized_pnl: float,
        open_positions: int,
        daily_pnl: float,
    ):
        """Log portfolio update"""
        self.logger.info(
            "Portfolio updated",
            event_type="portfolio",
            total_balance=total_balance,
            available_balance=available_balance,
            unrealized_pnl=unrealized_pnl,
            open_positions=open_positions,
            daily_pnl=daily_pnl,
        )

    def log_news_analysis(
        self,
        article_count: int,
        sentiment_signals: int,
        avg_sentiment: float,
        top_coins: list,
    ):
        """Log news analysis results"""
        self.logger.info(
            "News analysis completed",
            event_type="news_analysis",
            article_count=article_count,
            sentiment_signals=sentiment_signals,
            avg_sentiment=avg_sentiment,
            top_coins=top_coins,
        )

    def log_market_data(
        self,
        symbol: str,
        price: float,
        volume: float,
        price_change: float,
        indicators: Optional[Dict[str, Any]] = None,
    ):
        """Log market data"""
        self.logger.info(
            "Market data updated",
            event_type="market_data",
            symbol=symbol,
            price=price,
            volume=volume,
            price_change=price_change,
            indicators=indicators or {},
        )

    def log_error(
        self,
        error_type: str,
        error_message: str,
        component: str,
        context: Optional[Dict[str, Any]] = None,
    ):
        """Log error with context"""
        self.logger.error(
            "Error occurred",
            event_type="error",
            error_type=error_type,
            error_message=error_message,
            component=component,
            context=context or {},
        )

    def log_performance_metric(
        self,
        metric_name: str,
        metric_value: Any,
        component: str,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Log performance metric"""
        self.logger.info(
            "Performance metric",
            event_type="metric",
            metric_name=metric_name,
            metric_value=metric_value,
            component=component,
            metadata=metadata or {},
        )


class LogAnalyzer:
    """Analyzer for log data and system health"""

    def __init__(self, log_file: str) -> None:
        self.log_file = Path(log_file)
        self.logger = structlog.get_logger("log_analyzer")

    def analyze_trading_activity(self, hours: int = 24) -> Dict[str, Any]:
        """Analyze trading activity from logs"""
        try:
            if not self.log_file.exists():
                return {"error": "Log file not found"}

            cutoff_time = datetime.utcnow().timestamp() - (hours * 3600)

            signals = 0
            executions = 0
            errors = 0
            symbols = set()

            with open(self.log_file, "r") as f:
                for line in f:
                    try:
                        log_entry = json.loads(line.strip())

                        # Skip old entries
                        if "timestamp" in log_entry:
                            log_time = datetime.fromisoformat(
                                log_entry["timestamp"].replace("Z", "+00:00")
                            ).timestamp()
                            if log_time < cutoff_time:
                                continue

                        event_type = log_entry.get("event_type", "")

                        if event_type == "signal":
                            signals += 1
                            if "symbol" in log_entry:
                                symbols.add(log_entry["symbol"])
                        elif event_type == "execution":
                            executions += 1
                        elif event_type == "error":
                            errors += 1

                    except (json.JSONDecodeError, ValueError):
                        continue

            return {
                "period_hours": hours,
                "trading_signals": signals,
                "trade_executions": executions,
                "errors": errors,
                "unique_symbols": len(symbols),
                "symbols_traded": list(symbols),
            }

        except Exception as e:
            self.logger.error("Error analyzing trading activity", error=str(e))
            return {"error": str(e)}

    def get_error_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get error summary from logs"""
        try:
            if not self.log_file.exists():
                return {"error": "Log file not found"}

            cutoff_time = datetime.utcnow().timestamp() - (hours * 3600)

            error_types = {}
            components = {}
            total_errors = 0

            with open(self.log_file, "r") as f:
                for line in f:
                    try:
                        log_entry = json.loads(line.strip())

                        # Skip old entries
                        if "timestamp" in log_entry:
                            log_time = datetime.fromisoformat(
                                log_entry["timestamp"].replace("Z", "+00:00")
                            ).timestamp()
                            if log_time < cutoff_time:
                                continue

                        if log_entry.get("event_type") == "error":
                            total_errors += 1

                            error_type = log_entry.get("error_type", "unknown")
                            error_types[error_type] = error_types.get(error_type, 0) + 1

                            component = log_entry.get("component", "unknown")
                            components[component] = components.get(component, 0) + 1

                    except (json.JSONDecodeError, ValueError):
                        continue

            return {
                "period_hours": hours,
                "total_errors": total_errors,
                "error_types": error_types,
                "components_with_errors": components,
            }

        except Exception as e:
            self.logger.error("Error analyzing errors", error=str(e))
            return {"error": str(e)}


# Global logger instances
def get_trading_logger(name: str) -> TradingLogger:
    """Get a trading logger instance"""
    return TradingLogger(name)


def setup_trading_bot_logging():
    """Setup logging specifically for the trading bot"""
    from ..config.settings import Config

    config = Config()

    log_level = getattr(config, "LOG_LEVEL", "INFO")
    log_file = Path("logs") / "trading_bot.log"

    setup_logging(
        log_level=log_level,
        log_file=str(log_file),
        enable_console=True,
        enable_structured=True,
    )

    return get_trading_logger("trading_bot")


# Example usage
if __name__ == "__main__":
    # Setup logging
    setup_trading_bot_logging()

    # Get logger
    logger = get_trading_logger("test")

    # Test different log types
    logger.log_trade_signal(
        signal_id="test_001",
        symbol="BTCUSDT",
        direction="buy",
        confidence=0.85,
        price=45000.0,
        metadata={"strategy": "sentiment", "news_count": 5},
    )

    logger.log_trade_execution(
        order_id="order_001",
        symbol="BTCUSDT",
        side="BUY",
        quantity=0.001,
        price=45000.0,
        status="FILLED",
        fees=0.45,
    )

    logger.log_error(
        error_type="api_error",
        error_message="Connection timeout",
        component="binance_client",
        context={"retry_count": 3, "endpoint": "/api/v3/order"},
    )
