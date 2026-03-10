"""
Comprehensive unit tests for database components.
Tests database connection, session management, and basic functionality.
"""
import pytest
import unittest.mock as mock
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError, OperationalError
from contextlib import contextmanager
import time
import threading
from decimal import Decimal

from src.database.connection import DatabaseManager, get_database_manager, initialize_database
from src.config.settings import Config


class TestDatabaseManager:
    """Test DatabaseManager class functionality."""

    @pytest.fixture
    def config(self):
        """Test configuration."""
        config = Config()
        config.DATABASE_URL = "sqlite:///:memory:"
        config.LOG_LEVEL = "INFO"
        return config

    def test_init_with_config(self, config):
        """Test initialization with config."""
        db_manager = DatabaseManager(config)
        assert db_manager.config == config
        assert db_manager._engine is None
        assert db_manager._session_factory is None
        assert db_manager._is_connected is False

    def test_initialize_success(self, config):
        """Test successful initialization."""
        db_manager = DatabaseManager(config)
        db_manager.initialize()

        assert db_manager._engine is not None
        assert db_manager._session_factory is not None
        assert db_manager._is_connected is True
        assert db_manager._connection_errors == 0

    def test_initialize_with_invalid_url(self):
        """Test initialization with invalid database URL."""
        config = Config()
        config.DATABASE_URL = "invalid://database/url"
        db_manager = DatabaseManager(config)

        with pytest.raises((SQLAlchemyError, Exception)):
            db_manager.initialize()

    def test_get_session_context_manager(self, config):
        """Test get_session as context manager."""
        db_manager = DatabaseManager(config)
        db_manager.initialize()

        with db_manager.get_session() as session:
            assert isinstance(session, Session)
            assert session.is_active
            # Test basic query
            result = session.execute(text("SELECT 1")).scalar()
            assert result == 1

    def test_get_session_exception_handling(self, config):
        """Test session exception handling and rollback."""
        db_manager = DatabaseManager(config)
        db_manager.initialize()

        with pytest.raises(ValueError):
            with db_manager.get_session() as session:
                # Simulate an error
                raise ValueError("Test error")

        # Session should be properly closed despite error

    def test_get_session_when_not_initialized(self, config):
        """Test get_session when not initialized."""
        db_manager = DatabaseManager(config)

        with pytest.raises(RuntimeError):
            with db_manager.get_session() as session:
                pass

    def test_close_connection(self, config):
        """Test connection closing."""
        db_manager = DatabaseManager(config)
        db_manager.initialize()

        db_manager.close()

        # Manager should be marked as disconnected
        assert db_manager._is_connected is False

    def test_connection_pool_settings(self, config):
        """Test connection pool configuration."""
        db_manager = DatabaseManager(config)
        db_manager.initialize()

        # Verify pool settings
        assert db_manager._engine.pool.size() <= 10
        assert hasattr(db_manager._engine.pool, '_max_overflow')

    def test_health_status_healthy(self, config):
        """Test health status when healthy."""
        db_manager = DatabaseManager(config)
        db_manager.initialize()

        status = db_manager.get_health_status()
        assert status["status"] == "healthy"
        assert status["error_count"] == 0

    def test_health_status_disconnected(self, config):
        """Test health status when disconnected."""
        db_manager = DatabaseManager(config)

        status = db_manager.get_health_status()
        assert status["status"] == "disconnected"
        assert "error_count" in status

    def test_concurrent_sessions(self, config):
        """Test concurrent session access."""
        db_manager = DatabaseManager(config)
        db_manager.initialize()
        results = []

        def create_session(index):
            with db_manager.get_session() as session:
                results.append(f"session_{index}")
                time.sleep(0.1)  # Simulate work

        threads = []
        for i in range(5):
            thread = threading.Thread(target=create_session, args=(i,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        assert len(results) == 5
        assert all(result.startswith("session_") for result in results)


class TestDatabaseGlobalFunctions:
    """Test global database functions."""

    @pytest.fixture
    def config(self):
        """Test configuration."""
        config = Config()
        config.DATABASE_URL = "sqlite:///:memory:"
        return config

    def test_initialize_database(self, config):
        """Test global database initialization."""
        db_manager = initialize_database(config)
        assert isinstance(db_manager, DatabaseManager)
        assert db_manager._is_connected is True

        # Test getting the manager
        retrieved_manager = get_database_manager()
        assert retrieved_manager is db_manager

    def test_get_database_manager_not_initialized(self):
        """Test getting database manager when not initialized."""
        # Reset global state
        import src.database.connection as db_module
        db_module._db_manager = None

        with pytest.raises(RuntimeError, match="Database not initialized"):
            get_database_manager()


class TestDatabaseBasicOperations:
    """Test basic database operations."""

    @pytest.fixture
    def db_manager(self):
        """Create test database manager."""
        config = Config()
        config.DATABASE_URL = "sqlite:///:memory:"
        db_manager = DatabaseManager(config)
        db_manager.initialize()
        return db_manager

    def test_basic_crud_operations(self, db_manager):
        """Test basic CRUD operations."""
        with db_manager.get_session() as session:
            # Create a simple table for testing
            session.execute(text("""
                CREATE TABLE IF NOT EXISTS test_table (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    value REAL
                )
            """))
            session.commit()

            # Insert
            session.execute(text("INSERT INTO test_table (name, value) VALUES ('test', 123.45)"))
            session.commit()

            # Read
            result = session.execute(text("SELECT name, value FROM test_table WHERE name = 'test'")).fetchone()
            assert result[0] == "test"
            assert result[1] == 123.45

            # Update
            session.execute(text("UPDATE test_table SET value = 456.78 WHERE name = 'test'"))
            session.commit()

            # Verify update
            result = session.execute(text("SELECT value FROM test_table WHERE name = 'test'")).scalar()
            assert result == 456.78

            # Delete
            session.execute(text("DELETE FROM test_table WHERE name = 'test'"))
            session.commit()

            # Verify deletion
            result = session.execute(text("SELECT COUNT(*) FROM test_table")).scalar()
            assert result == 0

    def test_transaction_rollback(self, db_manager):
        """Test transaction rollback functionality."""
        with db_manager.get_session() as session:
            # Create table
            session.execute(text("""
                CREATE TABLE IF NOT EXISTS test_rollback (
                    id INTEGER PRIMARY KEY,
                    name TEXT UNIQUE
                )
            """))
            session.commit()

        # Test rollback on error
        try:
            with db_manager.get_session() as session:
                session.execute(text("INSERT INTO test_rollback (name) VALUES ('test1')"))
                session.flush()  # Flush to get any immediate errors

                # Simulate error
                raise Exception("Test error")
        except Exception:
            pass

        # Verify rollback - no records should exist
        with db_manager.get_session() as session:
            count = session.execute(text("SELECT COUNT(*) FROM test_rollback")).scalar()
            assert count == 0


class TestDatabasePerformance:
    """Test database performance and optimization."""

    @pytest.fixture
    def db_manager(self):
        """Create test database manager."""
        config = Config()
        config.DATABASE_URL = "sqlite:///:memory:"
        db_manager = DatabaseManager(config)
        db_manager.initialize()
        return db_manager

    def test_bulk_operations_performance(self, db_manager):
        """Test bulk operations performance."""
        with db_manager.get_session() as session:
            # Create test table
            session.execute(text("""
                CREATE TABLE IF NOT EXISTS perf_test (
                    id INTEGER PRIMARY KEY,
                    name TEXT,
                    value REAL,
                    timestamp INTEGER
                )
            """))
            session.commit()

        start_time = time.time()

        # Bulk insert
        with db_manager.get_session() as session:
            for i in range(1000):
                session.execute(text(
                    "INSERT INTO perf_test (name, value, timestamp) VALUES (:name, :value, :timestamp)"
                ), {
                    "name": f"test_{i}",
                    "value": i * 1.5,
                    "timestamp": int(time.time() * 1000) + i
                })
            session.commit()

        duration = time.time() - start_time

        # Should insert 1000 records in reasonable time (< 2 seconds)
        assert duration < 2.0

        # Verify all records inserted
        with db_manager.get_session() as session:
            count = session.execute(text("SELECT COUNT(*) FROM perf_test")).scalar()
            assert count == 1000

    def test_query_performance(self, db_manager):
        """Test query performance."""
        # Insert test data
        with db_manager.get_session() as session:
            session.execute(text("""
                CREATE TABLE IF NOT EXISTS query_test (
                    id INTEGER PRIMARY KEY,
                    category TEXT,
                    value REAL,
                    created_at INTEGER
                )
            """))

            categories = ["A", "B", "C", "D"]
            for i in range(5000):
                session.execute(text(
                    "INSERT INTO query_test (category, value, created_at) VALUES (:cat, :val, :time)"
                ), {
                    "cat": categories[i % len(categories)],
                    "val": i * 0.1,
                    "time": int(time.time() * 1000) + i
                })
            session.commit()

        # Test query performance
        start_time = time.time()

        with db_manager.get_session() as session:
            # Should be reasonably fast
            category_a = session.execute(text(
                "SELECT COUNT(*) FROM query_test WHERE category = 'A'"
            )).scalar()

            recent_records = session.execute(text(
                "SELECT COUNT(*) FROM query_test WHERE created_at > :time"
            ), {"time": int(time.time() * 1000) + 2500}).scalar()

        duration = time.time() - start_time

        # Queries should be fast (< 0.5 seconds)
        assert duration < 0.5
        assert category_a == 1250  # 5000 / 4 categories
        assert recent_records == 2500

    def test_connection_pool_efficiency(self, db_manager):
        """Test connection pool efficiency under load."""
        results = []

        def perform_operations(thread_id):
            with db_manager.get_session() as session:
                # Simple operation
                result = session.execute(text("SELECT :id"), {"id": thread_id}).scalar()
                results.append(result)

        # Run concurrent operations
        threads = []
        for i in range(10):
            thread = threading.Thread(target=perform_operations, args=(i,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        assert len(results) == 10
        assert sorted(results) == list(range(10))


class TestDatabaseErrorHandling:
    """Test database error handling scenarios."""

    @pytest.fixture
    def config(self):
        """Test configuration."""
        config = Config()
        config.DATABASE_URL = "sqlite:///:memory:"
        return config

    def test_connection_error_handling(self):
        """Test handling of connection errors."""
        config = Config()
        config.DATABASE_URL = "invalid://database/url"
        db_manager = DatabaseManager(config)

        with pytest.raises((SQLAlchemyError, Exception)):
            db_manager.initialize()

    def test_session_error_handling(self, config):
        """Test session error handling."""
        db_manager = DatabaseManager(config)
        db_manager.initialize()

        with pytest.raises(Exception):
            with db_manager.get_session() as session:
                # Create invalid operation
                session.execute(text("INVALID SQL QUERY"))

    def test_session_cleanup_on_error(self, config):
        """Test proper session cleanup after errors."""
        db_manager = DatabaseManager(config)
        db_manager.initialize()

        initial_connections = db_manager._engine.pool.checkedout()

        try:
            with db_manager.get_session() as session:
                raise Exception("Test error")
        except Exception:
            pass

        final_connections = db_manager._engine.pool.checkedout()

        # Connection should be properly returned to pool
        assert final_connections <= initial_connections

    def test_database_reconnection(self, config):
        """Test database reconnection after failure."""
        db_manager = DatabaseManager(config)
        db_manager.initialize()

        # Simulate disconnection
        db_manager._is_connected = False

        # Should reconnect automatically when getting session
        with db_manager.get_session() as session:
            result = session.execute(text("SELECT 1")).scalar()
            assert result == 1

        assert db_manager._is_connected is True


class TestDatabaseDecorators:
    """Test database utility decorators."""

    def test_retry_decorator_import(self):
        """Test that retry decorator can be imported."""
        from src.database.connection import retry_db_operation
        assert retry_db_operation is not None

    def test_cache_decorator_import(self):
        """Test that cache decorator can be imported."""
        from src.database.connection import cache_result
        assert cache_result is not None

    @patch('time.sleep')  # Mock sleep to speed up test
    def test_retry_decorator_functionality(self, mock_sleep):
        """Test retry decorator functionality."""
        from src.database.connection import retry_db_operation

        call_count = 0

        @retry_db_operation(max_retries=3, delay=0.1)
        def failing_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Test error")
            return "success"

        result = failing_function()
        assert result == "success"
        assert call_count == 3
        assert mock_sleep.call_count == 2  # Should sleep between retries


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
