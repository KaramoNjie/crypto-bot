"""
Data Validation Utilities for Crypto Trading Bot

Comprehensive data validation utilities to ensure data integrity
throughout the system and prevent display of invalid or stale data.
"""

import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Raised when data validation fails"""

    pass


class DataValidator:
    """Comprehensive data validation utilities"""

    @staticmethod
    def validate_price_data(data: Union[Dict, pd.DataFrame]) -> bool:
        """
        Validate price data for completeness and logical consistency

        Args:
            data: Price data (OHLCV format or ticker data)

        Returns:
            bool: True if data is valid

        Raises:
            ValidationError: If validation fails
        """
        try:
            if isinstance(data, dict):
                return DataValidator._validate_ticker_data(data)
            elif isinstance(data, pd.DataFrame):
                return DataValidator._validate_ohlcv_data(data)
            else:
                raise ValidationError(f"Unsupported data type: {type(data)}")

        except Exception as e:
            logger.error(f"Error validating price data: {e}")
            raise ValidationError(f"Price data validation failed: {e}")

    @staticmethod
    def _validate_ticker_data(data: Dict) -> bool:
        """Validate ticker data"""
        required_fields = ["price", "volume"]
        optional_fields = ["high", "low", "change_pct", "timestamp"]

        # Check required fields
        for field in required_fields:
            if field not in data:
                raise ValidationError(f"Missing required field: {field}")

            value = data[field]
            if not isinstance(value, (int, float)):
                raise ValidationError(f"Invalid data type for {field}: {type(value)}")

            if value < 0:
                raise ValidationError(f"Negative value for {field}: {value}")

        # Validate price is positive
        if data["price"] <= 0:
            raise ValidationError(f"Invalid price: {data['price']}")

        # Validate OHLC relationships if present
        if all(field in data for field in ["high", "low", "price"]):
            price = data["price"]
            high = data["high"]
            low = data["low"]

            if high < low:
                raise ValidationError(f"High ({high}) less than low ({low})")

            if price > high or price < low:
                raise ValidationError(
                    f"Price ({price}) outside high-low range ({low}-{high})"
                )

        return True

    @staticmethod
    def _validate_ohlcv_data(data: pd.DataFrame) -> bool:
        """Validate OHLCV DataFrame"""
        if data.empty:
            raise ValidationError("Empty OHLCV data")

        required_columns = ["open", "high", "low", "close", "volume"]

        # Check required columns
        missing_columns = [col for col in required_columns if col not in data.columns]
        if missing_columns:
            raise ValidationError(f"Missing columns: {missing_columns}")

        # Check for null values
        null_counts = data[required_columns].isnull().sum()
        if null_counts.any():
            raise ValidationError(
                f"Null values found: {null_counts[null_counts > 0].to_dict()}"
            )

        # Validate OHLC relationships
        invalid_high_low = data[data["high"] < data["low"]]
        if not invalid_high_low.empty:
            raise ValidationError(f"Found {len(invalid_high_low)} rows with high < low")

        invalid_open = data[
            (data["open"] > data["high"]) | (data["open"] < data["low"])
        ]
        if not invalid_open.empty:
            raise ValidationError(
                f"Found {len(invalid_open)} rows with invalid open prices"
            )

        invalid_close = data[
            (data["close"] > data["high"]) | (data["close"] < data["low"])
        ]
        if not invalid_close.empty:
            raise ValidationError(
                f"Found {len(invalid_close)} rows with invalid close prices"
            )

        # Check for negative volumes
        negative_volume = data[data["volume"] < 0]
        if not negative_volume.empty:
            raise ValidationError(
                f"Found {len(negative_volume)} rows with negative volume"
            )

        # Check for price outliers (prices that are 10x different from adjacent prices)
        if len(data) > 1:
            price_changes = data["close"].pct_change().abs()
            outliers = price_changes[price_changes > 5.0]  # 500% change
            if not outliers.empty:
                logger.warning(f"Found {len(outliers)} potential price outliers")

        return True

    @staticmethod
    def validate_portfolio_state(portfolio: Dict) -> bool:
        """
        Validate portfolio data consistency

        Args:
            portfolio: Portfolio data dictionary

        Returns:
            bool: True if portfolio state is valid
        """
        try:
            required_fields = ["total_balance", "available_balance"]

            # Check required fields
            for field in required_fields:
                if field not in portfolio:
                    raise ValidationError(f"Missing required portfolio field: {field}")

                value = portfolio[field]
                if not isinstance(value, (int, float)):
                    raise ValidationError(
                        f"Invalid data type for {field}: {type(value)}"
                    )

            # Validate balance relationships
            total_balance = portfolio["total_balance"]
            available_balance = portfolio["available_balance"]

            if total_balance < 0 or available_balance < 0:
                raise ValidationError("Negative balance values not allowed")

            if available_balance > total_balance:
                raise ValidationError(
                    f"Available balance ({available_balance}) cannot exceed total balance ({total_balance})"
                )

            # Validate unrealized P&L if present
            if "unrealized_pnl" in portfolio:
                unrealized_pnl = portfolio["unrealized_pnl"]
                if not isinstance(unrealized_pnl, (int, float)):
                    raise ValidationError(
                        f"Invalid unrealized P&L type: {type(unrealized_pnl)}"
                    )

            # Validate composition if present
            if "composition" in portfolio:
                composition = portfolio["composition"]
                if isinstance(composition, list):
                    total_allocation = sum(
                        item.get("allocation", 0) for item in composition
                    )
                    if total_allocation > 105:  # Allow 5% tolerance
                        logger.warning(
                            f"Portfolio allocation exceeds 100%: {total_allocation}%"
                        )

            return True

        except Exception as e:
            logger.error(f"Error validating portfolio state: {e}")
            raise ValidationError(f"Portfolio validation failed: {e}")

    @staticmethod
    def validate_trading_signal(signal: Dict) -> bool:
        """
        Validate trading signal parameters

        Args:
            signal: Trading signal dictionary

        Returns:
            bool: True if signal is valid
        """
        try:
            required_fields = ["symbol", "signal_type", "confidence"]

            # Check required fields
            for field in required_fields:
                if field not in signal:
                    raise ValidationError(f"Missing required signal field: {field}")

            # Validate signal type
            valid_signal_types = ["BUY", "SELL", "HOLD", "STRONG_BUY", "STRONG_SELL"]
            if signal["signal_type"] not in valid_signal_types:
                raise ValidationError(f"Invalid signal type: {signal['signal_type']}")

            # Validate confidence score
            confidence = signal["confidence"]
            if not isinstance(confidence, (int, float)):
                raise ValidationError(f"Invalid confidence type: {type(confidence)}")

            if not 0 <= confidence <= 1:
                raise ValidationError(
                    f"Confidence must be between 0 and 1: {confidence}"
                )

            # Validate symbol format
            symbol = signal["symbol"]
            if not isinstance(symbol, str) or "/" not in symbol:
                raise ValidationError(f"Invalid symbol format: {symbol}")

            # Validate timestamp if present
            if "timestamp" in signal:
                timestamp = signal["timestamp"]
                if not DataValidator.is_data_fresh(
                    timestamp, max_age_seconds=3600
                ):  # 1 hour
                    logger.warning(f"Trading signal is stale: {timestamp}")

            # Check for conflicting signals
            if "conflicting_signals" in signal:
                conflicts = signal["conflicting_signals"]
                if conflicts:
                    logger.warning(f"Signal has conflicts: {conflicts}")

            # Validate price levels if present
            price_fields = ["entry_price", "stop_loss", "take_profit"]
            prices = {}
            for field in price_fields:
                if field in signal:
                    price = signal[field]
                    if not isinstance(price, (int, float)) or price <= 0:
                        raise ValidationError(f"Invalid {field}: {price}")
                    prices[field] = price

            # Validate price relationships
            if "entry_price" in prices and "stop_loss" in prices:
                entry = prices["entry_price"]
                stop_loss = prices["stop_loss"]
                signal_type = signal["signal_type"]

                if signal_type in ["BUY", "STRONG_BUY"] and stop_loss >= entry:
                    raise ValidationError(
                        "Stop loss should be below entry price for buy signals"
                    )
                elif signal_type in ["SELL", "STRONG_SELL"] and stop_loss <= entry:
                    raise ValidationError(
                        "Stop loss should be above entry price for sell signals"
                    )

            return True

        except Exception as e:
            logger.error(f"Error validating trading signal: {e}")
            raise ValidationError(f"Trading signal validation failed: {e}")

    @staticmethod
    def validate_news_data(news_item: Dict) -> bool:
        """
        Validate news article data completeness

        Args:
            news_item: News article dictionary

        Returns:
            bool: True if news data is valid
        """
        try:
            required_fields = ["title", "content", "source", "published_at"]

            # Check required fields
            for field in required_fields:
                if field not in news_item:
                    raise ValidationError(f"Missing required news field: {field}")

                value = news_item[field]
                if not isinstance(value, str) or not value.strip():
                    raise ValidationError(f"Invalid or empty {field}")

            # Validate sentiment score if present
            if "sentiment_score" in news_item:
                sentiment = news_item["sentiment_score"]
                if not isinstance(sentiment, (int, float)):
                    raise ValidationError(
                        f"Invalid sentiment score type: {type(sentiment)}"
                    )

                if not -1 <= sentiment <= 1:
                    raise ValidationError(
                        f"Sentiment score must be between -1 and 1: {sentiment}"
                    )

            # Validate publication date
            published_at = news_item["published_at"]
            try:
                if isinstance(published_at, str):
                    pub_date = datetime.fromisoformat(
                        published_at.replace("Z", "+00:00")
                    )
                else:
                    pub_date = published_at

                # Check if date is reasonable (not in future, not too old)
                now = datetime.utcnow()
                if pub_date > now:
                    raise ValidationError("Publication date cannot be in the future")

                if pub_date < now - timedelta(days=365):
                    logger.warning("News item is very old (>1 year)")

            except ValueError as e:
                raise ValidationError(f"Invalid publication date format: {e}")

            # Validate source
            source = news_item["source"]
            if len(source) < 2:
                raise ValidationError("Source name too short")

            # Validate content length
            content = news_item["content"]
            if len(content) < 10:
                raise ValidationError("Content too short")

            return True

        except Exception as e:
            logger.error(f"Error validating news data: {e}")
            raise ValidationError(f"News data validation failed: {e}")

    @staticmethod
    def validate_configuration(config: Dict) -> bool:
        """
        Validate system configuration parameters

        Args:
            config: Configuration dictionary

        Returns:
            bool: True if configuration is valid
        """
        try:
            # Validate API keys
            api_keys = ["BINANCE_API_KEY", "BINANCE_SECRET_KEY"]
            for key in api_keys:
                if key in config:
                    api_key = config[key]
                    if not isinstance(api_key, str) or len(api_key) < 10:
                        raise ValidationError(f"Invalid API key format: {key}")

            # Validate trading parameters
            if "MAX_POSITION_SIZE" in config:
                max_size = config["MAX_POSITION_SIZE"]
                if not isinstance(max_size, (int, float)) or max_size <= 0:
                    raise ValidationError(f"Invalid max position size: {max_size}")

            if "MAX_DAILY_LOSS" in config:
                max_loss = config["MAX_DAILY_LOSS"]
                if not isinstance(max_loss, (int, float)) or max_loss <= 0:
                    raise ValidationError(f"Invalid max daily loss: {max_loss}")

            # Validate database configuration
            if "DATABASE_URL" in config:
                db_url = config["DATABASE_URL"]
                if not isinstance(db_url, str) or not db_url.startswith(
                    ("postgresql://", "sqlite://")
                ):
                    raise ValidationError("Invalid database URL format")

            # Validate rate limits
            if "API_RATE_LIMIT" in config:
                rate_limit = config["API_RATE_LIMIT"]
                if not isinstance(rate_limit, int) or rate_limit <= 0:
                    raise ValidationError(f"Invalid API rate limit: {rate_limit}")

            return True

        except Exception as e:
            logger.error(f"Error validating configuration: {e}")
            raise ValidationError(f"Configuration validation failed: {e}")

    @staticmethod
    def is_data_fresh(
        timestamp: Union[str, datetime], max_age_seconds: int = 300
    ) -> bool:
        """
        Check if data is fresh (within acceptable age limit)

        Args:
            timestamp: Data timestamp
            max_age_seconds: Maximum acceptable age in seconds

        Returns:
            bool: True if data is fresh
        """
        try:
            if timestamp is None:
                return False

            if isinstance(timestamp, str):
                # Try to parse various timestamp formats
                try:
                    # ISO format with timezone
                    dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                except ValueError:
                    try:
                        # Unix timestamp
                        dt = datetime.utcfromtimestamp(float(timestamp))
                    except ValueError:
                        # Standard datetime string
                        dt = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
            else:
                dt = timestamp

            age_seconds = (datetime.utcnow() - dt).total_seconds()
            return age_seconds <= max_age_seconds

        except Exception as e:
            logger.error(f"Error checking data freshness: {e}")
            return False

    @staticmethod
    def sanitize_user_input(input_data: Any) -> Any:
        """
        Sanitize user input to prevent injection attacks

        Args:
            input_data: Raw user input

        Returns:
            Sanitized input data
        """
        try:
            if isinstance(input_data, str):
                # Remove potentially dangerous characters
                sanitized = re.sub(r'[<>"\';\\]', "", input_data)

                # Limit length
                if len(sanitized) > 1000:
                    sanitized = sanitized[:1000]

                # Strip whitespace
                sanitized = sanitized.strip()

                return sanitized

            elif isinstance(input_data, dict):
                return {
                    key: DataValidator.sanitize_user_input(value)
                    for key, value in input_data.items()
                    if isinstance(key, str) and len(key) < 100
                }

            elif isinstance(input_data, list):
                return [
                    DataValidator.sanitize_user_input(item) for item in input_data[:100]
                ]

            elif isinstance(input_data, (int, float)):
                # Validate numeric ranges
                if abs(input_data) > 1e10:  # Very large numbers
                    raise ValidationError(f"Number too large: {input_data}")
                return input_data

            else:
                return str(input_data)[:100]  # Convert to string and limit length

        except Exception as e:
            logger.error(f"Error sanitizing user input: {e}")
            return ""

    @staticmethod
    def validate_symbol_format(symbol: str) -> bool:
        """
        Validate trading pair symbol format

        Args:
            symbol: Trading pair symbol (e.g., 'BTC/USDT')

        Returns:
            bool: True if symbol format is valid
        """
        try:
            if not isinstance(symbol, str):
                return False

            # Check basic format
            if "/" not in symbol:
                return False

            parts = symbol.split("/")
            if len(parts) != 2:
                return False

            base, quote = parts

            # Validate base and quote assets
            if not base or not quote:
                return False

            # Check for valid characters (alphanumeric only)
            if not re.match(r"^[A-Z0-9]+$", base) or not re.match(
                r"^[A-Z0-9]+$", quote
            ):
                return False

            # Check reasonable lengths
            if len(base) > 10 or len(quote) > 10:
                return False

            return True

        except Exception as e:
            logger.error(f"Error validating symbol format: {e}")
            return False

    @staticmethod
    def validate_order_data(order: Dict) -> bool:
        """
        Validate order data before processing

        Args:
            order: Order data dictionary

        Returns:
            bool: True if order data is valid
        """
        try:
            required_fields = ["symbol", "side", "type", "quantity"]

            # Check required fields
            for field in required_fields:
                if field not in order:
                    raise ValidationError(f"Missing required order field: {field}")

            # Validate symbol
            if not DataValidator.validate_symbol_format(order["symbol"]):
                raise ValidationError(f"Invalid symbol format: {order['symbol']}")

            # Validate side
            valid_sides = ["BUY", "SELL"]
            if order["side"] not in valid_sides:
                raise ValidationError(f"Invalid order side: {order['side']}")

            # Validate order type
            valid_types = ["MARKET", "LIMIT", "STOP_LIMIT", "STOP_MARKET"]
            if order["type"] not in valid_types:
                raise ValidationError(f"Invalid order type: {order['type']}")

            # Validate quantity
            quantity = order["quantity"]
            if not isinstance(quantity, (int, float)) or quantity <= 0:
                raise ValidationError(f"Invalid order quantity: {quantity}")

            # Validate price for limit orders
            if order["type"] in ["LIMIT", "STOP_LIMIT"]:
                if "price" not in order:
                    raise ValidationError("Price required for limit orders")

                price = order["price"]
                if not isinstance(price, (int, float)) or price <= 0:
                    raise ValidationError(f"Invalid order price: {price}")

            # Validate reasonable order sizes
            if quantity > 1000000:  # Arbitrary large number check
                logger.warning(f"Very large order quantity: {quantity}")

            return True

        except Exception as e:
            logger.error(f"Error validating order data: {e}")
            raise ValidationError(f"Order validation failed: {e}")

    @staticmethod
    def check_data_completeness(
        data: Union[Dict, pd.DataFrame], required_fields: List[str]
    ) -> Dict[str, Any]:
        """
        Check data completeness and return validation report

        Args:
            data: Data to validate
            required_fields: List of required fields

        Returns:
            Dict with validation results
        """
        try:
            report = {
                "is_complete": True,
                "missing_fields": [],
                "null_counts": {},
                "data_quality_score": 1.0,
                "recommendations": [],
            }

            if isinstance(data, dict):
                # Check dictionary fields
                for field in required_fields:
                    if field not in data:
                        report["missing_fields"].append(field)
                        report["is_complete"] = False
                    elif data[field] is None or (
                        isinstance(data[field], str) and not data[field].strip()
                    ):
                        report["null_counts"][field] = 1
                        report["data_quality_score"] -= 0.1

            elif isinstance(data, pd.DataFrame):
                # Check DataFrame columns
                for field in required_fields:
                    if field not in data.columns:
                        report["missing_fields"].append(field)
                        report["is_complete"] = False
                    else:
                        null_count = data[field].isnull().sum()
                        if null_count > 0:
                            report["null_counts"][field] = int(null_count)
                            report["data_quality_score"] -= (
                                null_count / len(data)
                            ) * 0.2

            # Generate recommendations
            if report["missing_fields"]:
                report["recommendations"].append(
                    f"Add missing fields: {report['missing_fields']}"
                )

            if report["null_counts"]:
                report["recommendations"].append("Address null/empty values in data")

            # Ensure score doesn't go negative
            report["data_quality_score"] = max(0.0, report["data_quality_score"])

            return report

        except Exception as e:
            logger.error(f"Error checking data completeness: {e}")
            return {
                "is_complete": False,
                "missing_fields": [],
                "null_counts": {},
                "data_quality_score": 0.0,
                "recommendations": ["Error occurred during validation"],
                "error": str(e),
            }
