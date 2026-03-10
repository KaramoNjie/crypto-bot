"""
API Health Monitoring Utility

This module provides comprehensive health monitoring for all external APIs
and services used by the crypto trading bot, including connection testing,
status tracking, and automatic recovery strategies.
"""

import logging
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health status enumeration"""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """Result of a health check"""

    service: str
    status: HealthStatus
    response_time: float
    message: str
    timestamp: datetime
    details: Dict[str, Any]


class APIHealthChecker:
    """
    Comprehensive API health monitoring and management

    Monitors the health of all external services and provides recovery strategies.
    """

    def __init__(self, config) -> None:
        self.config = config
        self.health_history: Dict[str, List[HealthCheckResult]] = {}
        self.last_check: Dict[str, datetime] = {}
        self.cache_ttl = 30  # seconds
        self.max_history_size = 100

        # Recovery strategies
        self.recovery_attempts: Dict[str, int] = {}
        self.max_recovery_attempts = 3
        self.recovery_backoff_seconds = 60

    def check_binance_health(self) -> HealthCheckResult:
        """Check Binance API health"""
        start_time = time.time()

        try:
            from src.apis.binance_client import BinanceClient

            client = BinanceClient(self.config)
            result = client.test_connection()

            response_time = time.time() - start_time

            if result.get("success"):
                status = HealthStatus.HEALTHY
                message = f"Binance API healthy - {result['data'].get('authentication', 'unknown')}"
            else:
                status = HealthStatus.UNHEALTHY
                message = f"Binance API error: {result.get('error', 'Unknown error')}"

            details = {
                "connection": result.get("data", {}).get("connection", "unknown"),
                "authentication": result.get("data", {}).get(
                    "authentication", "unknown"
                ),
            }

        except Exception as e:
            response_time = time.time() - start_time
            status = HealthStatus.UNHEALTHY
            message = f"Binance health check failed: {str(e)}"
            details = {"error": str(e)}

        result = HealthCheckResult(
            service="binance",
            status=status,
            response_time=response_time,
            message=message,
            timestamp=datetime.utcnow(),
            details=details,
        )

        self._store_result(result)
        return result

    def check_news_api_health(self) -> HealthCheckResult:
        """Check News API health"""
        start_time = time.time()

        try:
            from src.apis.news_api_client import NewsAPIClient

            client = NewsAPIClient(self.config)
            result = client.test_connection()

            response_time = time.time() - start_time

            overall_status = result.get("overall_status", "unknown")

            if overall_status == "healthy":
                status = HealthStatus.HEALTHY
                message = "News APIs healthy"
            elif overall_status == "degraded":
                status = HealthStatus.DEGRADED
                message = "News APIs degraded - some services unavailable"
            else:
                status = HealthStatus.UNHEALTHY
                message = "News APIs unhealthy"

            details = {
                "newsapi": result.get("newsapi", "unknown"),
                "cryptopanic": result.get("cryptopanic", "unknown"),
                "cache_size": result.get("cache_size", 0),
                "rate_limit_remaining": result.get("rate_limit_remaining", 0),
            }

        except Exception as e:
            response_time = time.time() - start_time
            status = HealthStatus.UNHEALTHY
            message = f"News API health check failed: {str(e)}"
            details = {"error": str(e)}

        result = HealthCheckResult(
            service="news_api",
            status=status,
            response_time=response_time,
            message=message,
            timestamp=datetime.utcnow(),
            details=details,
        )

        self._store_result(result)
        return result

    def check_database_health(self) -> HealthCheckResult:
        """Check database health"""
        start_time = time.time()

        try:
            from src.database.connection import get_database_manager

            db_manager = get_database_manager(self.config)
            response_time = time.time() - start_time

            if db_manager:
                # Test basic connectivity
                with db_manager.get_session() as session:
                    from sqlalchemy import text

                    session.execute(text("SELECT 1"))

                status = HealthStatus.HEALTHY
                message = "Database connection healthy"
                details = {"connection": "established"}
            else:
                status = HealthStatus.UNHEALTHY
                message = "Database manager not available"
                details = {"connection": "failed"}

        except Exception as e:
            response_time = time.time() - start_time
            status = HealthStatus.UNHEALTHY
            message = f"Database health check failed: {str(e)}"
            details = {"error": str(e)}

        result = HealthCheckResult(
            service="database",
            status=status,
            response_time=response_time,
            message=message,
            timestamp=datetime.utcnow(),
            details=details,
        )

        self._store_result(result)
        return result

    def check_overall_system_health(self) -> Dict[str, Any]:
        """Check health of all systems"""
        results = {
            "binance": self.check_binance_health(),
            "news_api": self.check_news_api_health(),
            "database": self.check_database_health(),
        }

        # Determine overall status
        statuses = [result.status for result in results.values()]

        if all(status == HealthStatus.HEALTHY for status in statuses):
            overall_status = HealthStatus.HEALTHY
            overall_message = "All systems healthy"
        elif any(status == HealthStatus.UNHEALTHY for status in statuses):
            overall_status = HealthStatus.UNHEALTHY
            overall_message = "Critical system failure detected"
        elif any(status == HealthStatus.DEGRADED for status in statuses):
            overall_status = HealthStatus.DEGRADED
            overall_message = "Some systems degraded"
        else:
            overall_status = HealthStatus.UNKNOWN
            overall_message = "System status unknown"

        return {
            "overall_status": overall_status.value,
            "overall_message": overall_message,
            "services": {
                service: {
                    "status": result.status.value,
                    "message": result.message,
                    "response_time": result.response_time,
                    "timestamp": result.timestamp.isoformat(),
                    "details": result.details,
                }
                for service, result in results.items()
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

    def get_service_health_history(
        self, service: str, hours: int = 24
    ) -> List[HealthCheckResult]:
        """Get health history for a specific service"""
        if service not in self.health_history:
            return []

        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        return [
            result
            for result in self.health_history[service]
            if result.timestamp >= cutoff_time
        ]

    def get_service_uptime_percentage(self, service: str, hours: int = 24) -> float:
        """Calculate uptime percentage for a service"""
        history = self.get_service_health_history(service, hours)

        if not history:
            return 0.0

        healthy_checks = sum(
            1 for result in history if result.status == HealthStatus.HEALTHY
        )
        return (healthy_checks / len(history)) * 100

    def attempt_recovery(self, service: str) -> bool:
        """Attempt to recover a failed service"""
        if service not in self.recovery_attempts:
            self.recovery_attempts[service] = 0

        if self.recovery_attempts[service] >= self.max_recovery_attempts:
            logger.warning(f"Max recovery attempts reached for {service}")
            return False

        self.recovery_attempts[service] += 1
        logger.info(
            f"Attempting recovery for {service} (attempt {self.recovery_attempts[service]})"
        )

        try:
            if service == "binance":
                # For Binance, we might try reconnecting or refreshing credentials
                result = self.check_binance_health()
                if result.status == HealthStatus.HEALTHY:
                    self.recovery_attempts[service] = 0  # Reset on success
                    return True

            elif service == "database":
                # For database, we might try reconnecting
                result = self.check_database_health()
                if result.status == HealthStatus.HEALTHY:
                    self.recovery_attempts[service] = 0  # Reset on success
                    return True

            elif service == "news_api":
                # For news API, we might clear cache or reset rate limits
                result = self.check_news_api_health()
                if result.status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED]:
                    self.recovery_attempts[service] = 0  # Reset on success
                    return True

        except Exception as e:
            logger.error(f"Recovery attempt failed for {service}: {e}")

        return False

    def _store_result(self, result: HealthCheckResult) -> None:
        """Store health check result in history"""
        if result.service not in self.health_history:
            self.health_history[result.service] = []

        self.health_history[result.service].append(result)
        self.last_check[result.service] = result.timestamp

        # Maintain max history size
        if len(self.health_history[result.service]) > self.max_history_size:
            self.health_history[result.service] = self.health_history[result.service][
                -self.max_history_size :
            ]

    def get_cached_health_status(self, service: str) -> Optional[HealthCheckResult]:
        """Get cached health status if still valid"""
        if service not in self.last_check:
            return None

        time_since_check = (
            datetime.utcnow() - self.last_check[service]
        ).total_seconds()
        if time_since_check > self.cache_ttl:
            return None

        if service in self.health_history and self.health_history[service]:
            return self.health_history[service][-1]

        return None


def test_binance_connection(config) -> Dict[str, Any]:
    """Standalone function to test Binance connection"""
    checker = APIHealthChecker(config)
    result = checker.check_binance_health()
    return {
        "service": result.service,
        "status": result.status.value,
        "message": result.message,
        "response_time": result.response_time,
        "details": result.details,
    }


def test_news_apis(config) -> Dict[str, Any]:
    """Standalone function to test News APIs"""
    checker = APIHealthChecker(config)
    result = checker.check_news_api_health()
    return {
        "service": result.service,
        "status": result.status.value,
        "message": result.message,
        "response_time": result.response_time,
        "details": result.details,
    }


def test_database_connection(config) -> Dict[str, Any]:
    """Standalone function to test database connection"""
    checker = APIHealthChecker(config)
    result = checker.check_database_health()
    return {
        "service": result.service,
        "status": result.status.value,
        "message": result.message,
        "response_time": result.response_time,
        "details": result.details,
    }


def get_overall_system_health(config) -> Dict[str, Any]:
    """Get overall system health status"""
    checker = APIHealthChecker(config)
    return checker.check_overall_system_health()


def get_api_rate_limit_status(config) -> Dict[str, Any]:
    """Get current API rate limit status"""
    checker = APIHealthChecker(config)

    # Check news API for rate limit info
    news_result = checker.check_news_api_health()

    return {
        "news_api": {
            "remaining": news_result.details.get("rate_limit_remaining", 0),
            "status": news_result.status.value,
        },
        "timestamp": datetime.utcnow().isoformat(),
    }


def format_health_report(health_data: Dict[str, Any]) -> str:
    """Format health data into a human-readable report"""
    report_lines = [
        "=== System Health Report ===",
        f"Overall Status: {health_data['overall_status'].upper()}",
        f"Message: {health_data['overall_message']}",
        f"Timestamp: {health_data['timestamp']}",
        "",
        "Service Details:",
    ]

    for service, data in health_data["services"].items():
        report_lines.extend(
            [
                f"  {service.upper()}:",
                f"    Status: {data['status'].upper()}",
                f"    Message: {data['message']}",
                f"    Response Time: {data['response_time']:.2f}s",
                f"    Last Check: {data['timestamp']}",
                "",
            ]
        )

    return "\n".join(report_lines)
