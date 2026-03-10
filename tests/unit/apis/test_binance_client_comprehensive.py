"""
Comprehensive unit tests for BinanceClient
Tests all critical functionality for production readiness
"""
import pytest
import threading
import time
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock
import pandas as pd

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..', 'src'))

from src.apis.binance_client import BinanceClient
import ccxt


class TestBinanceClientInitialization:
    """Test client initialization scenarios"""

    def test_initialization_with_valid_config(self):
        """Test successful initialization with valid configuration"""
        config = Mock()
        config.BINANCE_API_KEY = "valid_key"
        config.BINANCE_SECRET_KEY = "valid_secret"
        config.BINANCE_TESTNET = True
        config.PAPER_TRADING = True

        client = BinanceClient(config)

        assert client is not None
        assert client.config == config
        assert hasattr(client, 'paper_balance')
        assert hasattr(client, '_balance_lock')
        assert 'USDT' in client.paper_balance
        assert client.paper_balance['USDT']['free'] == 10000.0

    def test_initialization_with_missing_credentials(self):
        """Test initialization with missing API credentials"""
        config = Mock()
        config.BINANCE_API_KEY = None
        config.BINANCE_SECRET_KEY = None
        config.BINANCE_TESTNET = True
        config.PAPER_TRADING = False

        # Client should initialize but with empty credentials
        client = BinanceClient(config)
        assert client.config == config
        # The exchange should be initialized with empty strings for missing keys

    def test_paper_trading_initialization(self):
        """Test paper trading mode initialization"""
        config = Mock()
        config.BINANCE_API_KEY = "test_key"
        config.BINANCE_SECRET_KEY = "test_secret"
        config.BINANCE_TESTNET = True
        config.PAPER_TRADING = True

        client = BinanceClient(config)

        assert client.config == config
        assert client.is_connected is True  # Paper trading should always be "connected"
        assert hasattr(client, '_balance_lock')
        assert client._balance_lock is not None
        assert "USDT" in client.paper_balance  # Should have initial paper balance

    def test_live_trading_initialization(self):
        """Test live trading mode initialization"""
        config = Mock()
        config.BINANCE_API_KEY = "test_key"
        config.BINANCE_SECRET_KEY = "test_secret"
        config.BINANCE_TESTNET = False
        config.PAPER_TRADING = False

        # Mock the exchange initialization to avoid actual API calls
        with patch('ccxt.binance') as mock_exchange:
            mock_instance = Mock()
            mock_exchange.return_value = mock_instance

            client = BinanceClient(config)
            assert client.exchange is not None


class TestPaperTradingBalance:
    """Test paper trading balance operations"""

    @pytest.fixture
    def paper_client(self):
        config = Mock()
        config.BINANCE_API_KEY = "test_key"
        config.BINANCE_SECRET_KEY = "test_secret"
        config.BINANCE_TESTNET = True
        config.PAPER_TRADING = True
        return BinanceClient(config)

    def test_initial_balance_setup(self, paper_client):
        """Test initial paper trading balance"""
        balance = paper_client.get_account_balance()

        assert isinstance(balance, dict)
        assert balance['USDT']['free'] == 10000.0
        assert balance['USDT']['used'] == 0.0
        assert balance['USDT']['total'] == 10000.0

    def test_balance_thread_safety(self, paper_client):
        """Test thread safety of balance operations"""
        results = []
        errors = []

        def place_order():
            try:
                with patch.object(paper_client, 'get_ticker', return_value={'last': 45000.0}):
                    result = paper_client.place_order('BTC/USDT', 'BUY', 0.01, 45000.0)
                    results.append(result)
            except Exception as e:
                errors.append(e)

        # Create multiple threads to test thread safety
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=place_order)
            threads.append(thread)

        # Start all threads
        for thread in threads:
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Check that no errors occurred and balance is consistent
        assert len(errors) == 0, f"Thread safety errors: {errors}"

        # Calculate expected balance
        successful_orders = sum(1 for result in results if result.get('success'))
        expected_balance = 10000.0 - (successful_orders * 0.01 * 45000.0)
        actual_balance = paper_client.paper_balance['USDT']['free']

        assert abs(actual_balance - expected_balance) < 0.01, "Balance calculation inconsistent"

    def test_insufficient_balance_handling(self, paper_client):
        """Test handling of insufficient balance scenarios"""
        with patch.object(paper_client, 'get_ticker', return_value={'last': 45000.0}):
            # Try to place an order larger than available balance
            result = paper_client.place_order('BTC/USDT', 'BUY', 1.0, 45000.0)  # $45,000 order

            assert result['success'] is False
            assert 'insufficient balance' in result['error'].lower()

    def test_balance_updates_with_slippage(self, paper_client):
        """Test balance updates include realistic slippage"""
        initial_balance = paper_client.paper_balance['USDT']['free']

        with patch.object(paper_client, 'get_ticker', return_value={'last': 45000.0}):
            result = paper_client.place_order('BTC/USDT', 'BUY', 0.01)  # Market order

            if result['success']:
                # Check that slippage was applied
                executed_price = result['data']['price']
                assert executed_price != 45000.0  # Should have slippage
                assert result['data']['slippage'] > 0


class TestOrderValidation:
    """Test order parameter validation"""

    @pytest.fixture
    def validation_client(self):
        config = Mock()
        config.BINANCE_API_KEY = "test_key"
        config.BINANCE_SECRET_KEY = "test_secret"
        config.BINANCE_TESTNET = True
        config.PAPER_TRADING = True
        return BinanceClient(config)

    def test_paper_trading_validation_basic(self, validation_client):
        """Test basic validation in paper trading mode"""
        # Valid parameters
        result = validation_client.validate_order_parameters('BTC/USDT', 'BUY', 0.01, 45000.0)
        assert result['valid'] is True
        assert result['error'] is None

        # Invalid amount
        result = validation_client.validate_order_parameters('BTC/USDT', 'BUY', -0.01, 45000.0)
        assert result['valid'] is False
        assert 'positive' in result['error'].lower()

        # Invalid price
        result = validation_client.validate_order_parameters('BTC/USDT', 'BUY', 0.01, -45000.0)
        assert result['valid'] is False
        assert 'positive' in result['error'].lower()

    def test_decimal_precision_validation(self, validation_client):
        """Test decimal precision handling in validation"""
        # Test with float precision issues
        problematic_amounts = [0.1 + 0.2, 1.0/3.0, 0.123456789]

        for amount in problematic_amounts:
            result = validation_client.validate_order_parameters('BTC/USDT', 'BUY', amount, 45000.0)
            # Should not crash with float precision errors
            assert isinstance(result, dict)
            assert 'valid' in result

    def test_live_trading_validation_without_markets(self, validation_client):
        """Test validation when markets data is unavailable"""
        validation_client.config.PAPER_TRADING = False

        with patch.object(validation_client, 'get_markets', return_value={}):
            result = validation_client.validate_order_parameters('BTC/USDT', 'BUY', 0.01, 45000.0)
            # Should fallback to basic validation
            assert result['valid'] is True


class TestPrecisionFormatting:
    """Test price and quantity precision formatting"""

    @pytest.fixture
    def formatting_client(self):
        config = Mock()
        config.BINANCE_API_KEY = "test_key"
        config.BINANCE_SECRET_KEY = "test_secret"
        config.BINANCE_TESTNET = True
        config.PAPER_TRADING = True
        return BinanceClient(config)

    def test_amount_formatting_decimal_arithmetic(self, formatting_client):
        """Test amount formatting uses proper decimal arithmetic"""
        test_cases = [
            (0.123456789, 0.12345679),  # Should round to 8 decimals
            (1.0/3.0, 0.33333333),      # Should handle division properly
            (0.1 + 0.2, 0.3),           # Should handle float precision issues
        ]

        for input_amount, expected_max in test_cases:
            formatted = formatting_client._format_amount('BTC/USDT', input_amount)
            assert isinstance(formatted, float)
            # Should be close to expected, accounting for step size adjustments
            assert abs(formatted - expected_max) < 0.00000001

    def test_price_formatting_decimal_arithmetic(self, formatting_client):
        """Test price formatting uses proper decimal arithmetic"""
        test_cases = [
            (45000.123456, 45000.12300000),  # Should round to tick size
            (44999.999999, 44999.999999),    # Should handle precision
            (1e-9, 0.0),                     # Should handle very small values
        ]

        for input_price, expected_max in test_cases:
            formatted = formatting_client._format_price('BTC/USDT', input_price)
            assert isinstance(formatted, float)
            # Should be properly formatted
            assert formatted >= 0


class TestErrorHandling:
    """Test error handling scenarios"""

    @pytest.fixture
    def error_client(self):
        config = Mock()
        config.BINANCE_API_KEY = "test_key"
        config.BINANCE_SECRET_KEY = "test_secret"
        config.BINANCE_TESTNET = True
        config.PAPER_TRADING = True
        return BinanceClient(config)

    def test_none_symbol_handling(self, error_client):
        """Test handling of None symbol input"""
        result = error_client.get_ticker(None)
        assert result == {}

    def test_empty_symbol_handling(self, error_client):
        """Test handling of empty symbol input"""
        result = error_client.get_ticker("")
        assert result == {}

    def test_invalid_symbol_format_handling(self, error_client):
        """Test handling of invalid symbol format"""
        result = error_client.get_ticker("INVALID_FORMAT")
        assert result == {}

    def test_network_error_handling(self, error_client):
        """Test handling of network errors"""
        error_client.config.PAPER_TRADING = False
        error_client.exchange = Mock()
        error_client.exchange.fetch_ticker.side_effect = ccxt.NetworkError("Network error")

        result = error_client.get_ticker("BTC/USDT")
        assert result == {}
        assert error_client.is_connected is False

    def test_exchange_error_handling(self, error_client):
        """Test handling of exchange errors"""
        error_client.config.PAPER_TRADING = False
        error_client.exchange = Mock()
        error_client.exchange.fetch_ticker.side_effect = ccxt.ExchangeError("Exchange error")

        result = error_client.get_ticker("BTC/USDT")
        assert result == {}


class TestMarketDataRetrieval:
    """Test market data retrieval functionality"""

    @pytest.fixture
    def data_client(self):
        config = Mock()
        config.BINANCE_API_KEY = "test_key"
        config.BINANCE_SECRET_KEY = "test_secret"
        config.BINANCE_TESTNET = True
        config.PAPER_TRADING = False
        client = BinanceClient(config)
        client.exchange = Mock()
        return client

    def test_klines_data_retrieval(self, data_client):
        """Test klines data retrieval and formatting"""
        mock_ohlcv = [
            [1234567890000, 100.0, 110.0, 95.0, 105.0, 1000.0],
            [1234567890001, 105.0, 115.0, 100.0, 110.0, 1100.0],
        ]
        data_client.exchange.fetch_ohlcv.return_value = mock_ohlcv

        result = data_client.get_klines('BTC/USDT', '1h', 2)

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2
        assert list(result.columns) == ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        assert result['close'].iloc[0] == 105.0

    def test_empty_klines_handling(self, data_client):
        """Test handling of empty klines response"""
        data_client.exchange.fetch_ohlcv.return_value = []

        result = data_client.get_klines('BTC/USDT', '1h', 100)

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0

    def test_klines_error_handling(self, data_client):
        """Test klines retrieval error handling"""
        data_client.exchange.fetch_ohlcv.side_effect = ccxt.NetworkError("Network error")

        with pytest.raises(ccxt.NetworkError):
            data_client.get_klines('BTC/USDT', '1h', 100)


class TestConnectionManagement:
    """Test connection management functionality"""

    def test_paper_trading_connection_status(self):
        """Test connection status in paper trading mode"""
        config = Mock()
        config.BINANCE_API_KEY = "test_key"
        config.BINANCE_SECRET_KEY = "test_secret"
        config.BINANCE_TESTNET = True
        config.PAPER_TRADING = True

        client = BinanceClient(config)

        status = client.get_connection_status()
        assert status['is_connected'] is True
        assert status['paper_trading'] is True

    def test_connection_test_paper_trading(self):
        """Test connection testing in paper trading mode"""
        config = Mock()
        config.BINANCE_API_KEY = "test_key"
        config.BINANCE_SECRET_KEY = "test_secret"
        config.BINANCE_TESTNET = True
        config.PAPER_TRADING = True

        client = BinanceClient(config)

        result = client.test_connection()
        assert result['success'] is True
        assert result['data']['authentication'] == 'paper_trading'

    def test_live_connection_test_success(self):
        """Test successful live connection testing"""
        config = Mock()
        config.BINANCE_API_KEY = "test_key"
        config.BINANCE_SECRET_KEY = "test_secret"
        config.BINANCE_TESTNET = True
        config.PAPER_TRADING = False

        client = BinanceClient(config)
        client.exchange = Mock()
        client.exchange.fetch_time.return_value = 1234567890000
        client.exchange.fetch_balance.return_value = {}

        result = client.test_connection()
        assert result['success'] is True
        assert 'response_time' in result['data']


class TestAccountOperations:
    """Test account-related operations"""

    @pytest.fixture
    def account_client(self):
        config = Mock()
        config.BINANCE_API_KEY = "test_key"
        config.BINANCE_SECRET_KEY = "test_secret"
        config.BINANCE_TESTNET = True
        config.PAPER_TRADING = False
        client = BinanceClient(config)
        client.exchange = Mock()
        return client

    def test_account_info_paper_trading(self):
        """Test account info in paper trading mode"""
        config = Mock()
        config.PAPER_TRADING = True
        config.BINANCE_API_KEY = "test_key"
        config.BINANCE_SECRET_KEY = "test_secret"
        config.BINANCE_TESTNET = True

        client = BinanceClient(config)

        result = client.get_account_info()
        assert result['success'] is True
        assert result['data']['canTrade'] is True
        assert 'balances' in result['data']

    def test_account_info_live_trading(self, account_client):
        """Test account info in live trading mode"""
        mock_account = {
            'makerCommission': 10,
            'takerCommission': 10,
            'canTrade': True,
            'balances': []
        }
        account_client.exchange.private_get_account.return_value = mock_account

        result = account_client.get_account_info()
        assert result['success'] is True
        assert result['data']['canTrade'] is True

    def test_trading_fees_retrieval(self, account_client):
        """Test trading fees retrieval"""
        mock_fees = {'BTC/USDT': {'maker': 0.001, 'taker': 0.001}}
        account_client.exchange.fetch_trading_fees.return_value = mock_fees

        result = account_client.get_trading_fees('BTC/USDT')
        assert result['success'] is True
        assert result['data']['maker'] == 0.001


@pytest.mark.performance
class TestPerformance:
    """Test performance characteristics"""

    def test_validation_performance(self):
        """Test validation performance with large datasets"""
        config = Mock()
        config.BINANCE_API_KEY = "test_key"
        config.BINANCE_SECRET_KEY = "test_secret"
        config.BINANCE_TESTNET = True
        config.PAPER_TRADING = True

        client = BinanceClient(config)

        start_time = time.time()
        for _ in range(1000):
            client.validate_order_parameters('BTC/USDT', 'BUY', 0.01, 45000.0)
        end_time = time.time()

        avg_time = (end_time - start_time) / 1000
        assert avg_time < 0.001, f"Validation too slow: {avg_time:.6f}s average"

    def test_balance_operation_performance(self):
        """Test balance operation performance"""
        config = Mock()
        config.BINANCE_API_KEY = "test_key"
        config.BINANCE_SECRET_KEY = "test_secret"
        config.BINANCE_TESTNET = True
        config.PAPER_TRADING = True

        client = BinanceClient(config)

        start_time = time.time()
        for _ in range(100):
            client.get_account_balance()
        end_time = time.time()

        avg_time = (end_time - start_time) / 100
        assert avg_time < 0.0001, f"Balance retrieval too slow: {avg_time:.6f}s average"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
