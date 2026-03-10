"""
Comprehensive unit tests for TradeValidator class.
Tests all validation functionality including quantity, price, order formatting, and precision handling.
"""
import pytest
import unittest.mock as mock
from decimal import Decimal, ROUND_HALF_UP
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any
import time

from src.execution.trade_validator import TradeValidator


class TestTradeValidatorInitialization:
    """Test TradeValidator initialization scenarios."""

    def test_init_with_binance_client(self):
        """Test initialization with Binance client."""
        mock_client = Mock()
        validator = TradeValidator(mock_client)
        assert validator.binance_client == mock_client
        assert hasattr(validator, '_exchange_info_cache')
        assert isinstance(validator._exchange_info_cache, dict)

    def test_init_without_client(self):
        """Test initialization without client raises TypeError."""
        with pytest.raises(TypeError):
            TradeValidator()


class TestTradeValidatorSymbolInfo:
    """Test symbol information retrieval and caching."""

    @pytest.fixture
    def mock_client(self):
        """Create mock Binance client."""
        client = Mock()
        client.get_symbol_info.return_value = {
            "symbol": "BTCUSDT",
            "status": "TRADING",
            "baseAsset": "BTC",
            "quoteAsset": "USDT",
            "baseAssetPrecision": 8,
            "quotePrecision": 8,
            "filters": [
                {
                    "filterType": "LOT_SIZE",
                    "minQty": "0.00001000",
                    "maxQty": "9000.00000000",
                    "stepSize": "0.00001000"
                },
                {
                    "filterType": "PRICE_FILTER",
                    "minPrice": "0.01000000",
                    "maxPrice": "1000000.00000000",
                    "tickSize": "0.01000000"
                },
                {
                    "filterType": "MIN_NOTIONAL",
                    "minNotional": "10.00000000"
                }
            ]
        }
        return client

    @pytest.fixture
    def validator(self, mock_client):
        """Create validator instance."""
        return TradeValidator(mock_client)

    def test_get_symbol_info_success(self, validator, mock_client):
        """Test successful symbol info retrieval."""
        info = validator.get_symbol_info("BTCUSDT")

        assert info["symbol"] == "BTCUSDT"
        assert info["baseAsset"] == "BTC"
        assert info["quoteAsset"] == "USDT"
        mock_client.get_symbol_info.assert_called_once_with("BTCUSDT")

    def test_get_symbol_info_caching(self, validator, mock_client):
        """Test symbol info caching functionality."""
        # First call
        info1 = validator.get_symbol_info("BTCUSDT")
        # Second call
        info2 = validator.get_symbol_info("BTCUSDT")

        assert info1 == info2
        # Should only call API once due to caching
        mock_client.get_symbol_info.assert_called_once_with("BTCUSDT")

    def test_get_symbol_info_api_error(self, validator, mock_client):
        """Test handling of API errors."""
        mock_client.get_symbol_info.side_effect = Exception("API Error")

        info = validator.get_symbol_info("BTCUSDT")

        assert info is None

    def test_get_symbol_info_none_response(self, validator, mock_client):
        """Test handling of None response from API."""
        mock_client.get_symbol_info.return_value = None

        info = validator.get_symbol_info("BTCUSDT")

        assert info is None


class TestTradeValidatorQuantityValidation:
    """Test quantity validation functionality."""

    @pytest.fixture
    def mock_client(self):
        """Create mock Binance client."""
        client = Mock()
        client.get_symbol_info.return_value = {
            "symbol": "BTCUSDT",
            "filters": [
                {
                    "filterType": "LOT_SIZE",
                    "minQty": "0.00001000",
                    "maxQty": "9000.00000000",
                    "stepSize": "0.00001000"
                }
            ]
        }
        return client

    @pytest.fixture
    def validator(self, mock_client):
        """Create validator instance."""
        return TradeValidator(mock_client)

    def test_validate_quantity_valid_cases(self, validator):
        """Test quantity validation for valid cases."""
        valid_cases = [
            ("BTCUSDT", 0.00001, True),  # Minimum quantity
            ("BTCUSDT", 0.001, True),    # Regular quantity
            ("BTCUSDT", 1.0, True),      # Whole number
            ("BTCUSDT", 100.0, True),    # Large quantity
        ]

        for symbol, quantity, expected in valid_cases:
            result = validator.validate_quantity(symbol, quantity)
            assert result["valid"] == expected, f"Failed for quantity {quantity}"
            if expected:
                assert "error" not in result

    def test_validate_quantity_invalid_cases(self, validator):
        """Test quantity validation for invalid cases."""
        invalid_cases = [
            ("BTCUSDT", 0.000005, "below minimum"),  # Below minimum
            ("BTCUSDT", 10000.0, "above maximum"),   # Above maximum
            ("BTCUSDT", 0.000015, "step size"),      # Invalid step size
            ("BTCUSDT", 0.0, "below minimum"),       # Zero quantity
            ("BTCUSDT", -1.0, "below minimum"),      # Negative quantity
        ]

        for symbol, quantity, error_type in invalid_cases:
            result = validator.validate_quantity(symbol, quantity)
            assert not result["valid"], f"Should be invalid for quantity {quantity}"
            assert "error" in result
            assert error_type.lower() in result["error"].lower()

    def test_validate_quantity_decimal_precision(self, validator):
        """Test decimal precision handling in quantity validation."""
        # Test with Decimal input
        result = validator.validate_quantity("BTCUSDT", Decimal("0.00001"))
        assert result["valid"]

        # Test precise calculations
        result = validator.validate_quantity("BTCUSDT", 0.00002)  # 2 * stepSize
        assert result["valid"]

        result = validator.validate_quantity("BTCUSDT", 0.000025)  # 2.5 * stepSize
        assert not result["valid"]

    def test_validate_quantity_no_symbol_info(self, validator, mock_client):
        """Test quantity validation when symbol info is unavailable."""
        mock_client.get_symbol_info.return_value = None

        result = validator.validate_quantity("INVALID", 1.0)

        assert not result["valid"]
        assert "symbol information" in result["error"].lower()


class TestTradeValidatorPriceValidation:
    """Test price validation functionality."""

    @pytest.fixture
    def mock_client(self):
        """Create mock Binance client."""
        client = Mock()
        client.get_symbol_info.return_value = {
            "symbol": "BTCUSDT",
            "filters": [
                {
                    "filterType": "PRICE_FILTER",
                    "minPrice": "0.01000000",
                    "maxPrice": "1000000.00000000",
                    "tickSize": "0.01000000"
                }
            ]
        }
        return client

    @pytest.fixture
    def validator(self, mock_client):
        """Create validator instance."""
        return TradeValidator(mock_client)

    def test_validate_price_valid_cases(self, validator):
        """Test price validation for valid cases."""
        valid_cases = [
            ("BTCUSDT", 0.01, True),     # Minimum price
            ("BTCUSDT", 50000.0, True),  # Regular price
            ("BTCUSDT", 100000.0, True), # High price
            ("BTCUSDT", 1.23, True),     # Decimal price with valid tick
        ]

        for symbol, price, expected in valid_cases:
            result = validator.validate_price(symbol, price)
            assert result["valid"] == expected, f"Failed for price {price}"
            if expected:
                assert "error" not in result

    def test_validate_price_invalid_cases(self, validator):
        """Test price validation for invalid cases."""
        invalid_cases = [
            ("BTCUSDT", 0.005, "below minimum"),    # Below minimum
            ("BTCUSDT", 2000000.0, "above maximum"), # Above maximum
            ("BTCUSDT", 1.235, "tick size"),        # Invalid tick size
            ("BTCUSDT", 0.0, "below minimum"),      # Zero price
            ("BTCUSDT", -100.0, "below minimum"),   # Negative price
        ]

        for symbol, price, error_type in invalid_cases:
            result = validator.validate_price(symbol, price)
            assert not result["valid"], f"Should be invalid for price {price}"
            assert "error" in result
            assert error_type.lower() in result["error"].lower()


class TestTradeValidatorOrderValidation:
    """Test complete order validation functionality."""

    @pytest.fixture
    def mock_client(self):
        """Create mock Binance client with comprehensive symbol info."""
        client = Mock()
        client.get_symbol_info.return_value = {
            "symbol": "BTCUSDT",
            "status": "TRADING",
            "filters": [
                {
                    "filterType": "LOT_SIZE",
                    "minQty": "0.00001000",
                    "maxQty": "9000.00000000",
                    "stepSize": "0.00001000"
                },
                {
                    "filterType": "PRICE_FILTER",
                    "minPrice": "0.01000000",
                    "maxPrice": "1000000.00000000",
                    "tickSize": "0.01000000"
                },
                {
                    "filterType": "MIN_NOTIONAL",
                    "minNotional": "10.00000000"
                }
            ]
        }
        return client

    @pytest.fixture
    def validator(self, mock_client):
        """Create validator instance."""
        return TradeValidator(mock_client)

    def test_validate_order_valid_order(self, validator):
        """Test validation of valid order."""
        order = {
            "symbol": "BTCUSDT",
            "side": "BUY",
            "type": "LIMIT",
            "quantity": 0.001,
            "price": 50000.0
        }

        result = validator.validate_order(order)

        assert result["valid"]
        assert "error" not in result

    def test_validate_order_missing_fields(self, validator):
        """Test validation with missing required fields."""
        incomplete_orders = [
            {"side": "BUY", "type": "LIMIT", "quantity": 0.001, "price": 50000.0},  # Missing symbol
            {"symbol": "BTCUSDT", "type": "LIMIT", "quantity": 0.001, "price": 50000.0},  # Missing side
            {"symbol": "BTCUSDT", "side": "BUY", "quantity": 0.001, "price": 50000.0},  # Missing type
            {"symbol": "BTCUSDT", "side": "BUY", "type": "LIMIT", "price": 50000.0},  # Missing quantity
        ]

        for order in incomplete_orders:
            result = validator.validate_order(order)
            assert not result["valid"]
            assert "missing" in result["error"].lower() or "required" in result["error"].lower()

    def test_validate_order_invalid_values(self, validator):
        """Test validation with invalid field values."""
        invalid_orders = [
            {  # Invalid side
                "symbol": "BTCUSDT", "side": "INVALID", "type": "LIMIT",
                "quantity": 0.001, "price": 50000.0
            },
            {  # Invalid type
                "symbol": "BTCUSDT", "side": "BUY", "type": "INVALID",
                "quantity": 0.001, "price": 50000.0
            },
            {  # Invalid quantity
                "symbol": "BTCUSDT", "side": "BUY", "type": "LIMIT",
                "quantity": -0.001, "price": 50000.0
            },
            {  # Invalid price
                "symbol": "BTCUSDT", "side": "BUY", "type": "LIMIT",
                "quantity": 0.001, "price": -100.0
            }
        ]

        for order in invalid_orders:
            result = validator.validate_order(order)
            assert not result["valid"]
            assert "error" in result

    def test_validate_order_min_notional(self, validator):
        """Test minimum notional value validation."""
        # Valid order above min notional
        valid_order = {
            "symbol": "BTCUSDT", "side": "BUY", "type": "LIMIT",
            "quantity": 0.001, "price": 50000.0  # Notional = 50
        }
        result = validator.validate_order(valid_order)
        assert result["valid"]

        # Invalid order below min notional
        invalid_order = {
            "symbol": "BTCUSDT", "side": "BUY", "type": "LIMIT",
            "quantity": 0.0001, "price": 50.0  # Notional = 0.005
        }
        result = validator.validate_order(invalid_order)
        assert not result["valid"]
        assert "notional" in result["error"].lower()

    def test_validate_order_market_type(self, validator):
        """Test validation of market orders (no price required)."""
        market_order = {
            "symbol": "BTCUSDT",
            "side": "BUY",
            "type": "MARKET",
            "quantity": 0.001
        }

        result = validator.validate_order(market_order)
        assert result["valid"]


class TestTradeValidatorFormatting:
    """Test quantity and price formatting functionality."""

    @pytest.fixture
    def mock_client(self):
        """Create mock Binance client."""
        client = Mock()
        client.get_symbol_info.return_value = {
            "symbol": "BTCUSDT",
            "baseAssetPrecision": 5,
            "quotePrecision": 2,
            "filters": [
                {
                    "filterType": "LOT_SIZE",
                    "stepSize": "0.00001000"
                },
                {
                    "filterType": "PRICE_FILTER",
                    "tickSize": "0.01000000"
                }
            ]
        }
        return client

    @pytest.fixture
    def validator(self, mock_client):
        """Create validator instance."""
        return TradeValidator(mock_client)

    def test_format_quantity_precision(self, validator):
        """Test quantity formatting with proper precision."""
        test_cases = [
            (0.123456789, "0.12346"),  # Rounds to 5 decimal places
            (1.0, "1"),                # Removes trailing zeros
            (0.00001, "0.00001"),      # Minimum step size
            (0.000015, "0.00002"),     # Rounds to nearest step
            (10.5, "10.5"),            # Simple decimal
        ]

        for input_qty, expected in test_cases:
            result = validator.format_quantity("BTCUSDT", input_qty)
            assert result == expected, f"Failed for input {input_qty}: got {result}, expected {expected}"

    def test_format_price_precision(self, validator):
        """Test price formatting with proper precision."""
        test_cases = [
            (50000.123456, "50000.12"),  # Rounds to 2 decimal places
            (100.0, "100"),              # Removes trailing zeros
            (99.99, "99.99"),            # Preserves valid decimals
            (0.01, "0.01"),              # Minimum tick size
            (0.015, "0.02"),             # Rounds to nearest tick
        ]

        for input_price, expected in test_cases:
            result = validator.format_price("BTCUSDT", input_price)
            assert result == expected, f"Failed for input {input_price}: got {result}, expected {expected}"

    def test_format_with_decimal_input(self, validator):
        """Test formatting with Decimal input values."""
        qty_decimal = Decimal("0.123456789")
        price_decimal = Decimal("50000.123456")

        qty_result = validator.format_quantity("BTCUSDT", qty_decimal)
        price_result = validator.format_price("BTCUSDT", price_decimal)

        assert qty_result == "0.12346"
        assert price_result == "50000.12"

    def test_format_edge_cases(self, validator):
        """Test formatting edge cases."""
        # Zero values
        assert validator.format_quantity("BTCUSDT", 0.0) == "0"
        assert validator.format_price("BTCUSDT", 0.0) == "0"

        # Very small values
        assert validator.format_quantity("BTCUSDT", 0.000001) == "0.00000"
        assert validator.format_price("BTCUSDT", 0.001) == "0.00"

        # Very large values
        large_qty = validator.format_quantity("BTCUSDT", 9999.99999)
        assert len(large_qty.split('.')[0]) <= 10  # Reasonable length

        large_price = validator.format_price("BTCUSDT", 999999.99)
        assert len(large_price.split('.')[0]) <= 10  # Reasonable length


class TestTradeValidatorPerformance:
    """Test TradeValidator performance and caching."""

    @pytest.fixture
    def validator(self):
        """Create validator with mock client."""
        mock_client = Mock()
        mock_client.get_symbol_info.return_value = {
            "symbol": "BTCUSDT",
            "filters": [
                {"filterType": "LOT_SIZE", "minQty": "0.00001", "maxQty": "9000", "stepSize": "0.00001"},
                {"filterType": "PRICE_FILTER", "minPrice": "0.01", "maxPrice": "1000000", "tickSize": "0.01"}
            ]
        }
        return TradeValidator(mock_client)

    def test_caching_performance(self, validator):
        """Test that caching improves performance."""
        # First call - should hit API
        start_time = time.time()
        for _ in range(10):
            validator.get_symbol_info("BTCUSDT")
        first_duration = time.time() - start_time

        # Subsequent calls - should use cache
        start_time = time.time()
        for _ in range(10):
            validator.get_symbol_info("BTCUSDT")
        second_duration = time.time() - start_time

        # Cached calls should be much faster
        assert second_duration < first_duration * 0.1
        # API should only be called once
        validator.binance_client.get_symbol_info.assert_called_once()

    def test_validation_performance(self, validator):
        """Test validation performance for bulk operations."""
        orders = []
        for i in range(100):
            orders.append({
                "symbol": "BTCUSDT",
                "side": "BUY",
                "type": "LIMIT",
                "quantity": 0.001 + (i * 0.0001),
                "price": 50000.0 + (i * 10)
            })

        start_time = time.time()
        results = [validator.validate_order(order) for order in orders]
        duration = time.time() - start_time

        # Should validate 100 orders in reasonable time (< 0.5 seconds)
        assert duration < 0.5
        assert len(results) == 100
        assert all(result["valid"] for result in results)


class TestTradeValidatorErrorHandling:
    """Test error handling and edge cases."""

    @pytest.fixture
    def validator(self):
        """Create validator with mock client."""
        mock_client = Mock()
        return TradeValidator(mock_client)

    def test_invalid_symbol_handling(self, validator):
        """Test handling of invalid symbols."""
        validator.binance_client.get_symbol_info.return_value = None

        qty_result = validator.validate_quantity("INVALID", 1.0)
        price_result = validator.validate_price("INVALID", 100.0)
        order_result = validator.validate_order({
            "symbol": "INVALID", "side": "BUY", "type": "LIMIT",
            "quantity": 1.0, "price": 100.0
        })

        assert not qty_result["valid"]
        assert not price_result["valid"]
        assert not order_result["valid"]

    def test_none_input_handling(self, validator):
        """Test handling of None inputs."""
        validator.binance_client.get_symbol_info.return_value = {
            "symbol": "BTCUSDT",
            "filters": []
        }

        # Test None quantity
        result = validator.validate_quantity("BTCUSDT", None)
        assert not result["valid"]

        # Test None price
        result = validator.validate_price("BTCUSDT", None)
        assert not result["valid"]

        # Test None order
        result = validator.validate_order(None)
        assert not result["valid"]

    def test_missing_filters_handling(self, validator):
        """Test handling when symbol info is missing required filters."""
        validator.binance_client.get_symbol_info.return_value = {
            "symbol": "BTCUSDT",
            "filters": []  # Missing required filters
        }

        qty_result = validator.validate_quantity("BTCUSDT", 1.0)
        price_result = validator.validate_price("BTCUSDT", 100.0)

        # Should handle gracefully with appropriate error messages
        assert not qty_result["valid"]
        assert not price_result["valid"]
        assert "filter" in qty_result["error"].lower()
        assert "filter" in price_result["error"].lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
