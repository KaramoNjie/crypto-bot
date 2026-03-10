import os
from dataclasses import dataclass, field
from typing import List, Optional
from dotenv import load_dotenv
import logging

load_dotenv()
logger = logging.getLogger(__name__)


@dataclass
class Config:
    """Application configuration with validation"""

    # API Keys
    BINANCE_API_KEY: Optional[str] = field(
        default_factory=lambda: os.getenv("BINANCE_API_KEY")
    )
    BINANCE_SECRET_KEY: Optional[str] = field(
        default_factory=lambda: os.getenv("BINANCE_SECRET_KEY")
    )
    COINMARKETCAP_API_KEY: Optional[str] = field(
        default_factory=lambda: os.getenv("COINMARKETCAP_API_KEY")
    )
    OPENAI_API_KEY: Optional[str] = field(
        default_factory=lambda: os.getenv("OPENAI_API_KEY")
    )
    NEWSAPI_KEY: Optional[str] = field(default_factory=lambda: os.getenv("NEWSAPI_KEY"))
    CRYPTOPANIC_API_KEY: Optional[str] = field(
        default_factory=lambda: os.getenv("CRYPTOPANIC_API_KEY")
    )

    # Trading Settings
    PAPER_TRADING: bool = field(
        default_factory=lambda: os.getenv("PAPER_TRADING", "true").lower() == "true"
    )
    DEFAULT_RISK_PERCENTAGE: float = field(
        default_factory=lambda: float(os.getenv("DEFAULT_RISK_PERCENTAGE", "2.0"))
    )
    MAX_POSITIONS: int = field(
        default_factory=lambda: int(os.getenv("MAX_POSITIONS", "5"))
    )
    MIN_CONFIDENCE_SCORE: float = field(
        default_factory=lambda: float(os.getenv("MIN_CONFIDENCE_SCORE", "0.7"))
    )

    # Binance Settings
    BINANCE_TESTNET: bool = field(init=False)
    BINANCE_BASE_URL: str = field(init=False)

    # Analysis Settings
    TECHNICAL_INDICATORS: List[str] = field(
        default_factory=lambda: ["RSI", "MACD", "BOLLINGER", "EMA", "SMA"]
    )
    NEWS_SENTIMENT_THRESHOLD: float = 0.1

    # LangChain Settings
    LANGCHAIN_MODEL: str = field(
        default_factory=lambda: os.getenv("LANGCHAIN_MODEL", "gpt-4-turbo-preview")
    )
    LANGCHAIN_TEMPERATURE: float = field(
        default_factory=lambda: float(os.getenv("LANGCHAIN_TEMPERATURE", "0.1"))
    )
    LANGCHAIN_MAX_TOKENS: int = field(
        default_factory=lambda: int(os.getenv("LANGCHAIN_MAX_TOKENS", "2000"))
    )
    LANGCHAIN_CACHE_ENABLED: bool = field(
        default_factory=lambda: os.getenv("LANGCHAIN_CACHE_ENABLED", "true").lower()
        == "true"
    )
    LANGCHAIN_RATE_LIMIT_REQUESTS: int = field(
        default_factory=lambda: int(os.getenv("LANGCHAIN_RATE_LIMIT_REQUESTS", "60"))
    )
    LANGCHAIN_RATE_LIMIT_WINDOW: int = field(
        default_factory=lambda: int(os.getenv("LANGCHAIN_RATE_LIMIT_WINDOW", "60"))
    )

    # Database
    DATABASE_URL: str = field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL", "sqlite:///./trading_bot.db"
        )
    )
    REDIS_URL: str = field(
        default_factory=lambda: os.getenv("REDIS_URL", "redis://localhost:6379")
    )

    # Logging
    LOG_LEVEL: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))

    # Data Source Configuration
    USE_REAL_DATA: bool = field(
        default_factory=lambda: os.getenv("USE_REAL_DATA", "false").lower() == "true"
    )
    ALLOW_MOCK_DATA: bool = field(
        default_factory=lambda: os.getenv("ALLOW_MOCK_DATA", "false").lower() == "true"
    )
    ALLOW_MOCK_FALLBACK: bool = field(
        default_factory=lambda: os.getenv("ALLOW_MOCK_FALLBACK", "false").lower()
        == "true"
    )
    DATA_FRESHNESS_THRESHOLD: int = field(
        default_factory=lambda: int(os.getenv("DATA_FRESHNESS_THRESHOLD", "300"))
    )  # seconds
    FALLBACK_DATA_SOURCES: List[str] = field(
        default_factory=lambda: (
            os.getenv("FALLBACK_DATA_SOURCES", "").split(",")
            if os.getenv("FALLBACK_DATA_SOURCES")
            else []
        )
    )

    # Error Handling Configuration
    ERROR_RETRY_ATTEMPTS: int = field(
        default_factory=lambda: int(os.getenv("ERROR_RETRY_ATTEMPTS", "3"))
    )
    ERROR_RETRY_DELAY: float = field(
        default_factory=lambda: float(os.getenv("ERROR_RETRY_DELAY", "1.0"))
    )
    CIRCUIT_BREAKER_THRESHOLD: int = field(
        default_factory=lambda: int(os.getenv("CIRCUIT_BREAKER_THRESHOLD", "5"))
    )
    GRACEFUL_DEGRADATION_MODE: bool = field(
        default_factory=lambda: os.getenv("GRACEFUL_DEGRADATION_MODE", "true").lower()
        == "true"
    )

    # Performance Configuration
    DATA_CACHE_TTL: int = field(
        default_factory=lambda: int(os.getenv("DATA_CACHE_TTL", "30"))
    )  # seconds
    API_TIMEOUT_BINANCE: int = field(
        default_factory=lambda: int(os.getenv("API_TIMEOUT_BINANCE", "10"))
    )  # seconds
    API_TIMEOUT_NEWS: int = field(
        default_factory=lambda: int(os.getenv("API_TIMEOUT_NEWS", "15"))
    )  # seconds
    API_TIMEOUT_DATABASE: int = field(
        default_factory=lambda: int(os.getenv("API_TIMEOUT_DATABASE", "5"))
    )  # seconds
    BATCH_SIZE_ORDERS: int = field(
        default_factory=lambda: int(os.getenv("BATCH_SIZE_ORDERS", "50"))
    )
    BATCH_SIZE_MARKET_DATA: int = field(
        default_factory=lambda: int(os.getenv("BATCH_SIZE_MARKET_DATA", "100"))
    )

    # Monitoring Configuration
    HEALTH_CHECK_INTERVAL_API: int = field(
        default_factory=lambda: int(os.getenv("HEALTH_CHECK_INTERVAL_API", "60"))
    )  # seconds
    HEALTH_CHECK_INTERVAL_DATABASE: int = field(
        default_factory=lambda: int(os.getenv("HEALTH_CHECK_INTERVAL_DATABASE", "30"))
    )  # seconds
    ALERT_THRESHOLD_API_ERRORS: int = field(
        default_factory=lambda: int(os.getenv("ALERT_THRESHOLD_API_ERRORS", "10"))
    )
    ALERT_THRESHOLD_RESPONSE_TIME: float = field(
        default_factory=lambda: float(os.getenv("ALERT_THRESHOLD_RESPONSE_TIME", "2.0"))
    )  # seconds
    LOG_LEVEL_OVERRIDES: dict = field(
        default_factory=lambda: {
            "binance": os.getenv("LOG_LEVEL_BINANCE", "INFO"),
            "database": os.getenv("LOG_LEVEL_DATABASE", "INFO"),
            "agents": os.getenv("LOG_LEVEL_AGENTS", "INFO"),
            "news": os.getenv("LOG_LEVEL_NEWS", "WARNING"),
        }
    )

    # Security Configuration
    API_RATE_LIMIT_BINANCE: int = field(
        default_factory=lambda: int(os.getenv("API_RATE_LIMIT_BINANCE", "1200"))
    )  # requests per minute
    API_RATE_LIMIT_NEWS: int = field(
        default_factory=lambda: int(os.getenv("API_RATE_LIMIT_NEWS", "100"))
    )  # requests per minute
    DATA_VALIDATION_STRICTNESS: str = field(
        default_factory=lambda: os.getenv("DATA_VALIDATION_STRICTNESS", "medium")
    )  # low, medium, high
    SECURITY_HEADERS_ENABLED: bool = field(
        default_factory=lambda: os.getenv("SECURITY_HEADERS_ENABLED", "true").lower()
        == "true"
    )

    # News API Configuration
    NEWS_API_KEYS: dict = field(
        default_factory=lambda: {
            "newsapi": os.getenv("NEWSAPI_KEY"),
            "cryptopanic": os.getenv("CRYPTOPANIC_API_KEY"),
            "coindesk": os.getenv("COINDESK_API_KEY", ""),
        }
    )
    NEWS_SOURCES: List[str] = field(
        default_factory=lambda: os.getenv("NEWS_SOURCES", "newsapi,cryptopanic").split(
            ","
        )
    )

    # Production Settings
    ENVIRONMENT: str = field(
        default_factory=lambda: os.getenv("ENVIRONMENT", "development")
    )
    DEBUG_MODE: bool = field(
        default_factory=lambda: os.getenv("DEBUG_MODE", "true").lower() == "true"
    )
    MAINTENANCE_MODE: bool = field(
        default_factory=lambda: os.getenv("MAINTENANCE_MODE", "false").lower() == "true"
    )

    def __post_init__(self):
        """Initialize derived fields and validate configuration"""
        self.BINANCE_TESTNET = self.PAPER_TRADING
        self.BINANCE_BASE_URL = (
            "https://testnet.binance.vision"
            if self.BINANCE_TESTNET
            else "https://api.binance.com"
        )
        self._validate()

    def _validate(self):
        """Validate required configuration values"""
        # Basic trading validation
        if not self.PAPER_TRADING:
            required = ["BINANCE_API_KEY", "BINANCE_SECRET_KEY"]
            missing = [k for k in required if not getattr(self, k)]
            if missing:
                raise ValueError(
                    f"Missing required configuration for live trading: {missing}"
                )

        if not 0 <= self.DEFAULT_RISK_PERCENTAGE <= 10:
            raise ValueError(
                "DEFAULT_RISK_PERCENTAGE must be between 0 and 10 (inclusive)"
            )

        if self.MAX_POSITIONS < 1:
            raise ValueError("MAX_POSITIONS must be at least 1")

        if not 0 <= self.MIN_CONFIDENCE_SCORE <= 1:
            raise ValueError("MIN_CONFIDENCE_SCORE must be between 0 and 1")

        # Validate LangChain settings
        if not 0 <= self.LANGCHAIN_TEMPERATURE <= 2:
            raise ValueError("LANGCHAIN_TEMPERATURE must be between 0 and 2")

        if self.LANGCHAIN_MAX_TOKENS < 1:
            raise ValueError("LANGCHAIN_MAX_TOKENS must be at least 1")

        if self.LANGCHAIN_RATE_LIMIT_REQUESTS < 1:
            raise ValueError("LANGCHAIN_RATE_LIMIT_REQUESTS must be at least 1")

        if self.LANGCHAIN_RATE_LIMIT_WINDOW < 1:
            raise ValueError("LANGCHAIN_RATE_LIMIT_WINDOW must be at least 1")

        # Validate data source configuration
        if self.DATA_FRESHNESS_THRESHOLD < 30:
            raise ValueError("DATA_FRESHNESS_THRESHOLD must be at least 30 seconds")

        # Validate error handling configuration
        if self.ERROR_RETRY_ATTEMPTS < 1 or self.ERROR_RETRY_ATTEMPTS > 10:
            raise ValueError("ERROR_RETRY_ATTEMPTS must be between 1 and 10")

        if self.ERROR_RETRY_DELAY < 0.1 or self.ERROR_RETRY_DELAY > 60:
            raise ValueError("ERROR_RETRY_DELAY must be between 0.1 and 60 seconds")

        if self.CIRCUIT_BREAKER_THRESHOLD < 1:
            raise ValueError("CIRCUIT_BREAKER_THRESHOLD must be at least 1")

        # Validate performance configuration
        if self.DATA_CACHE_TTL < 5 or self.DATA_CACHE_TTL > 3600:
            raise ValueError("DATA_CACHE_TTL must be between 5 and 3600 seconds")

        for timeout_name, timeout_value in [
            ("API_TIMEOUT_BINANCE", self.API_TIMEOUT_BINANCE),
            ("API_TIMEOUT_NEWS", self.API_TIMEOUT_NEWS),
            ("API_TIMEOUT_DATABASE", self.API_TIMEOUT_DATABASE),
        ]:
            if timeout_value < 1 or timeout_value > 60:
                raise ValueError(f"{timeout_name} must be between 1 and 60 seconds")

        if self.BATCH_SIZE_ORDERS < 1 or self.BATCH_SIZE_ORDERS > 1000:
            raise ValueError("BATCH_SIZE_ORDERS must be between 1 and 1000")

        if self.BATCH_SIZE_MARKET_DATA < 1 or self.BATCH_SIZE_MARKET_DATA > 1000:
            raise ValueError("BATCH_SIZE_MARKET_DATA must be between 1 and 1000")

        # Validate monitoring configuration
        if self.HEALTH_CHECK_INTERVAL_API < 10 or self.HEALTH_CHECK_INTERVAL_API > 3600:
            raise ValueError(
                "HEALTH_CHECK_INTERVAL_API must be between 10 and 3600 seconds"
            )

        if (
            self.HEALTH_CHECK_INTERVAL_DATABASE < 10
            or self.HEALTH_CHECK_INTERVAL_DATABASE > 3600
        ):
            raise ValueError(
                "HEALTH_CHECK_INTERVAL_DATABASE must be between 10 and 3600 seconds"
            )

        if self.ALERT_THRESHOLD_API_ERRORS < 1:
            raise ValueError("ALERT_THRESHOLD_API_ERRORS must be at least 1")

        if self.ALERT_THRESHOLD_RESPONSE_TIME < 0.1:
            raise ValueError(
                "ALERT_THRESHOLD_RESPONSE_TIME must be at least 0.1 seconds"
            )

        # Validate security configuration
        if self.API_RATE_LIMIT_BINANCE < 1 or self.API_RATE_LIMIT_BINANCE > 6000:
            raise ValueError(
                "API_RATE_LIMIT_BINANCE must be between 1 and 6000 requests per minute"
            )

        if self.API_RATE_LIMIT_NEWS < 1 or self.API_RATE_LIMIT_NEWS > 1000:
            raise ValueError(
                "API_RATE_LIMIT_NEWS must be between 1 and 1000 requests per minute"
            )

        if self.DATA_VALIDATION_STRICTNESS not in ["low", "medium", "high"]:
            raise ValueError(
                "DATA_VALIDATION_STRICTNESS must be 'low', 'medium', or 'high'"
            )

        # Validate environment settings
        if self.ENVIRONMENT not in ["development", "staging", "production"]:
            raise ValueError(
                "ENVIRONMENT must be 'development', 'staging', or 'production'"
            )

        # Production-specific validation
        if self.ENVIRONMENT == "production":
            self._validate_production_config()

        # News API validation
        if not self.NEWS_SOURCES:
            logger.warning(
                "No news sources configured - news analysis will be disabled"
            )

        # Log configuration completion
        logger.info(
            f"Configuration loaded: PAPER_TRADING={self.PAPER_TRADING}, ENV={self.ENVIRONMENT}"
        )

    def _validate_production_config(self):
        """Additional validation for production environment"""
        # Ensure mock data is disabled in production
        if self.ALLOW_MOCK_DATA:
            raise ValueError("ALLOW_MOCK_DATA must be False in production environment")

        # Ensure debug mode is disabled
        if self.DEBUG_MODE:
            logger.warning("DEBUG_MODE should be disabled in production")

        # Ensure secure API timeouts
        if self.API_TIMEOUT_BINANCE < 5:
            raise ValueError(
                "API_TIMEOUT_BINANCE should be at least 5 seconds in production"
            )

        # Ensure reasonable cache TTL
        if self.DATA_CACHE_TTL > 300:
            logger.warning(
                "DATA_CACHE_TTL is quite high for production - consider reducing for fresher data"
            )

        # Validate critical API keys
        if not self.PAPER_TRADING:
            if not self.BINANCE_API_KEY or len(self.BINANCE_API_KEY) < 20:
                raise ValueError("Invalid BINANCE_API_KEY for production")

            if not self.BINANCE_SECRET_KEY or len(self.BINANCE_SECRET_KEY) < 20:
                raise ValueError("Invalid BINANCE_SECRET_KEY for production")

        # Ensure security headers are enabled
        if not self.SECURITY_HEADERS_ENABLED:
            logger.warning("SECURITY_HEADERS should be enabled in production")

        logger.info("Production configuration validation completed")
