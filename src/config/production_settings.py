"""
Production-Ready Configuration Management

This module provides comprehensive configuration management with:
- Environment-based configuration
- Validation and security checks
- Type safety with Pydantic
- Production-specific validations
"""

import os
import logging
from pathlib import Path
from typing import Dict, List, Optional, Union, Any
from decimal import Decimal
from datetime import timedelta

from pydantic import Field, field_validator, model_validator, SecretStr
from pydantic_settings import BaseSettings
from pydantic.types import PositiveFloat, PositiveInt


logger = logging.getLogger(__name__)


class DatabaseConfig(BaseSettings):
    """Database configuration settings"""

    url: str = Field(default="sqlite:///trading_db_test.db", env="DATABASE_URL")
    pool_size: PositiveInt = Field(default=20, env="DB_POOL_SIZE")
    max_overflow: PositiveInt = Field(default=30, env="DB_MAX_OVERFLOW")
    pool_pre_ping: bool = Field(default=True, env="DB_POOL_PRE_PING")
    pool_recycle: PositiveInt = Field(default=3600, env="DB_POOL_RECYCLE")
    echo: bool = Field(default=False, env="DB_ECHO")

    # Connection timeouts
    connect_timeout: PositiveInt = Field(default=10, env="DB_CONNECT_TIMEOUT")
    command_timeout: PositiveInt = Field(default=30, env="DB_COMMAND_TIMEOUT")

    # Production-specific settings
    ssl_mode: str = Field(default="require", env="DB_SSL_MODE")
    application_name: str = Field(
        default="crypto-trading-bot", env="DB_APPLICATION_NAME"
    )

    @field_validator("url")
    def validate_database_url(cls, v):
        """Validate database URL format"""
        if not v.startswith(("postgresql://", "postgresql+asyncpg://", "sqlite:///")):
            raise ValueError(
                "DATABASE_URL must be a PostgreSQL or SQLite connection string"
            )
        return v


class APIConfig(BaseSettings):
    """API configuration settings"""

    # Binance API
    binance_api_key: Optional[SecretStr] = Field(None, env="BINANCE_API_KEY")
    binance_secret_key: Optional[SecretStr] = Field(None, env="BINANCE_SECRET_KEY")
    binance_testnet: bool = Field(default=True, env="BINANCE_TESTNET")
    binance_rate_limit: PositiveInt = Field(default=1200, env="BINANCE_RATE_LIMIT")

    # OpenAI API
    openai_api_key: Optional[SecretStr] = Field(None, env="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4-turbo", env="OPENAI_MODEL")
    openai_temperature: float = Field(
        default=0.1, ge=0.0, le=2.0, env="OPENAI_TEMPERATURE"
    )
    openai_max_tokens: PositiveInt = Field(default=2000, env="OPENAI_MAX_TOKENS")

    # News APIs
    newsapi_key: Optional[SecretStr] = Field(None, env="NEWSAPI_KEY")
    cryptopanic_api_key: Optional[SecretStr] = Field(None, env="CRYPTOPANIC_API_KEY")
    coinmarketcap_api_key: Optional[SecretStr] = Field(
        None, env="COINMARKETCAP_API_KEY"
    )

    # API Timeouts and retries
    api_timeout: PositiveInt = Field(default=30, env="API_TIMEOUT")
    api_retries: PositiveInt = Field(default=3, env="API_RETRIES")
    api_retry_delay: PositiveFloat = Field(default=1.0, env="API_RETRY_DELAY")

    @field_validator("openai_temperature")
    def validate_temperature(cls, v):
        """Validate OpenAI temperature is within valid range"""
        if not 0.0 <= v <= 2.0:
            raise ValueError("OpenAI temperature must be between 0.0 and 2.0")
        return v


class TradingConfig(BaseSettings):
    """Trading configuration settings"""

    # Paper trading settings
    paper_trading: bool = Field(default=True, env="PAPER_TRADING")
    initial_balance: PositiveFloat = Field(default=10000.0, env="INITIAL_BALANCE")

    # Risk management
    max_position_size: float = Field(
        default=0.1, ge=0.01, le=1.0, env="MAX_POSITION_SIZE"
    )
    risk_per_trade: float = Field(default=0.02, ge=0.001, le=0.1, env="RISK_PER_TRADE")
    stop_loss_percentage: float = Field(
        default=0.05, ge=0.01, le=0.5, env="STOP_LOSS_PCT"
    )
    take_profit_ratio: float = Field(
        default=2.0, ge=1.0, le=10.0, env="TAKE_PROFIT_RATIO"
    )

    # Position limits
    max_positions: PositiveInt = Field(default=5, env="MAX_POSITIONS")
    max_daily_trades: PositiveInt = Field(default=20, env="MAX_DAILY_TRADES")
    max_daily_loss: PositiveFloat = Field(default=500.0, env="MAX_DAILY_LOSS")

    # Strategy settings
    min_confidence_score: float = Field(
        default=0.7, ge=0.1, le=1.0, env="MIN_CONFIDENCE_SCORE"
    )
    default_timeframe: str = Field(default="1h", env="DEFAULT_TIMEFRAME")
    supported_pairs: List[str] = Field(
        default=["BTCUSDT", "ETHUSDT", "BNBUSDT", "ADAUSDT", "DOTUSDT"],
        env="SUPPORTED_PAIRS",
    )

    @field_validator("default_timeframe")
    def validate_timeframe(cls, v):
        """Validate timeframe format"""
        valid_timeframes = [
            "1m",
            "3m",
            "5m",
            "15m",
            "30m",
            "1h",
            "2h",
            "4h",
            "6h",
            "8h",
            "12h",
            "1d",
            "3d",
            "1w",
            "1M",
        ]
        if v not in valid_timeframes:
            raise ValueError(
                f"Invalid timeframe: {v}. Must be one of {valid_timeframes}"
            )
        return v

    @field_validator("supported_pairs")
    def validate_trading_pairs(cls, v):
        """Validate trading pair format"""
        for pair in v:
            if not isinstance(pair, str) or len(pair) < 6:
                raise ValueError(f"Invalid trading pair format: {pair}")
        return v


class SecurityConfig(BaseSettings):
    """Security configuration settings"""

    # Encryption
    encryption_key: Optional[SecretStr] = Field(None, env="ENCRYPTION_KEY")
    jwt_secret_key: SecretStr = Field(
        default="dev-secret-key-change-in-production", env="JWT_SECRET_KEY"
    )

    # CORS settings
    allowed_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8501"],
        env="ALLOWED_ORIGINS",
    )

    # Rate limiting
    rate_limit_requests: PositiveInt = Field(default=100, env="RATE_LIMIT_REQUESTS")
    rate_limit_window: PositiveInt = Field(default=60, env="RATE_LIMIT_WINDOW")

    # Security headers
    enable_security_headers: bool = Field(default=True, env="ENABLE_SECURITY_HEADERS")

    # API key validation
    require_api_authentication: bool = Field(default=False, env="REQUIRE_API_AUTH")


class MonitoringConfig(BaseSettings):
    """Monitoring and observability configuration"""

    # Logging
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_format: str = Field(default="json", env="LOG_FORMAT")
    log_file: Optional[str] = Field(None, env="LOG_FILE")

    # Metrics collection
    enable_metrics: bool = Field(default=True, env="ENABLE_METRICS")
    metrics_port: PositiveInt = Field(default=8000, env="METRICS_PORT")

    # Health checks
    health_check_interval: PositiveInt = Field(default=30, env="HEALTH_CHECK_INTERVAL")

    # Alerting thresholds
    error_rate_threshold: float = Field(
        default=0.05, ge=0.0, le=1.0, env="ERROR_RATE_THRESHOLD"
    )
    response_time_threshold: PositiveFloat = Field(
        default=2.0, env="RESPONSE_TIME_THRESHOLD"
    )

    # LangSmith integration
    langsmith_api_key: Optional[SecretStr] = Field(None, env="LANGSMITH_API_KEY")
    langsmith_project: str = Field(
        default="crypto-trading-bot", env="LANGSMITH_PROJECT"
    )
    langsmith_tracing: bool = Field(default=True, env="LANGSMITH_TRACING")

    @field_validator("log_level")
    def validate_log_level(cls, v):
        """Validate log level"""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Invalid log level: {v}. Must be one of {valid_levels}")
        return v.upper()

    @field_validator("log_format")
    def validate_log_format(cls, v):
        """Validate log format"""
        valid_formats = ["json", "text"]
        if v not in valid_formats:
            raise ValueError(f"Invalid log format: {v}. Must be one of {valid_formats}")
        return v


class PerformanceConfig(BaseSettings):
    """Performance and caching configuration"""

    # Redis configuration
    redis_url: str = Field(default="redis://localhost:6379", env="REDIS_URL")
    redis_max_connections: PositiveInt = Field(default=20, env="REDIS_MAX_CONNECTIONS")

    # Cache settings
    cache_ttl_market_data: PositiveInt = Field(default=30, env="CACHE_TTL_MARKET_DATA")
    cache_ttl_news: PositiveInt = Field(default=300, env="CACHE_TTL_NEWS")
    cache_ttl_indicators: PositiveInt = Field(default=60, env="CACHE_TTL_INDICATORS")

    # Batch processing
    batch_size_orders: PositiveInt = Field(default=50, env="BATCH_SIZE_ORDERS")
    batch_size_market_data: PositiveInt = Field(
        default=100, env="BATCH_SIZE_MARKET_DATA"
    )

    # WebSocket settings
    websocket_max_connections: PositiveInt = Field(default=10, env="WS_MAX_CONNECTIONS")
    websocket_heartbeat_interval: PositiveInt = Field(
        default=30, env="WS_HEARTBEAT_INTERVAL"
    )


class ProductionConfig(BaseSettings):
    """Main production configuration class"""

    # Environment settings
    environment: str = Field(default="development", env="ENVIRONMENT")
    debug: bool = Field(default=False, env="DEBUG")
    testing: bool = Field(default=False, env="TESTING")

    # Application metadata
    app_name: str = Field(default="Crypto Trading Bot", env="APP_NAME")
    app_version: str = Field(default="2.0.0", env="APP_VERSION")

    # Sub-configurations
    database: DatabaseConfig = DatabaseConfig()
    api: APIConfig = APIConfig()
    trading: TradingConfig = TradingConfig()
    security: SecurityConfig = SecurityConfig()
    monitoring: MonitoringConfig = MonitoringConfig()
    performance: PerformanceConfig = PerformanceConfig()

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        populate_by_name = True
        validate_assignment = True
        extra = "allow"

    @field_validator("environment")
    def validate_environment(cls, v):
        """Validate environment setting"""
        valid_envs = ["development", "staging", "production"]
        if v not in valid_envs:
            raise ValueError(f"Invalid environment: {v}. Must be one of {valid_envs}")
        return v

    @model_validator(mode="after")
    def validate_production_settings(self):
        """Validate production-specific requirements"""
        if self.environment == "production":
            # Ensure critical settings for production
            if self.debug:
                logger.warning("DEBUG mode should be disabled in production")

            # Validate API keys for live trading
            if not self.trading.paper_trading:
                if not self.api.binance_api_key or not self.api.binance_secret_key:
                    raise ValueError(
                        "Binance API credentials required for live trading in production"
                    )

            # Ensure security settings
            if not self.security.enable_security_headers:
                logger.warning("Security headers should be enabled in production")

            if not self.security.jwt_secret_key:
                raise ValueError("JWT secret key is required in production")

        return self

    @property
    def is_production(self) -> bool:
        """Check if running in production environment"""
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development environment"""
        return self.environment == "development"

    def get_database_url(self, async_driver: bool = False) -> str:
        """Get appropriate database URL"""
        url = self.database.url
        if async_driver and not url.startswith("postgresql+asyncpg://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://")
        return url

    def get_binance_base_url(self) -> str:
        """Get Binance API base URL based on configuration"""
        if self.api.binance_testnet:
            return "https://testnet.binance.vision"
        return "https://api.binance.com"

    def validate_required_keys(self) -> None:
        """Validate that required API keys are present"""
        missing_keys = []

        # Check required keys based on configuration
        if not self.trading.paper_trading:
            if not self.api.binance_api_key:
                missing_keys.append("BINANCE_API_KEY")
            if not self.api.binance_secret_key:
                missing_keys.append("BINANCE_SECRET_KEY")

        if self.monitoring.langsmith_tracing and not self.monitoring.langsmith_api_key:
            logger.warning("LangSmith tracing enabled but API key not provided")

        if missing_keys:
            raise ValueError(f'Missing required API keys: {", ".join(missing_keys)}')

    def setup_logging(self) -> None:
        """Setup logging configuration"""
        level = getattr(logging, self.monitoring.log_level)

        # Configure root logger
        logging.basicConfig(
            level=level,
            format=(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                if self.monitoring.log_format == "text"
                else None
            ),
        )

        # Set specific logger levels
        if self.is_production:
            logging.getLogger("urllib3").setLevel(logging.WARNING)
            logging.getLogger("requests").setLevel(logging.WARNING)
            logging.getLogger("asyncio").setLevel(logging.WARNING)

        logger.info(
            f"Logging configured: level={self.monitoring.log_level}, format={self.monitoring.log_format}"
        )


def load_config() -> ProductionConfig:
    """Load and validate configuration"""
    try:
        config = ProductionConfig()
        config.validate_required_keys()
        config.setup_logging()

        logger.info(
            f"Configuration loaded successfully: environment={config.environment}"
        )
        return config

    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        raise


# Global configuration instance
config = load_config()


def get_settings() -> ProductionConfig:
    """Get the global configuration instance"""
    return config
