"""
Simple Configuration for Development and Testing
"""

import os
from dataclasses import dataclass, field
from typing import List, Optional
from dotenv import load_dotenv

load_dotenv()


@dataclass
class SimpleConfig:
    """Simplified configuration for development"""

    # Environment
    ENVIRONMENT: str = field(
        default_factory=lambda: os.getenv("ENVIRONMENT", "development")
    )
    DEBUG: bool = field(
        default_factory=lambda: os.getenv("DEBUG", "true").lower() == "true"
    )
    PAPER_TRADING: bool = field(
        default_factory=lambda: os.getenv("PAPER_TRADING", "true").lower() == "true"
    )

    # Database
    DATABASE_URL: str = field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL", "sqlite:///trading_db_test.db"
        )
    )

    # API Keys (Optional)
    BINANCE_API_KEY: Optional[str] = field(
        default_factory=lambda: os.getenv("BINANCE_API_KEY")
    )
    BINANCE_SECRET_KEY: Optional[str] = field(
        default_factory=lambda: os.getenv("BINANCE_SECRET_KEY")
    )
    BINANCE_TESTNET: bool = field(
        default_factory=lambda: os.getenv("BINANCE_TESTNET", "true").lower() == "true"
    )

    # OpenAI
    OPENAI_API_KEY: Optional[str] = field(
        default_factory=lambda: os.getenv("OPENAI_API_KEY")
    )
    OPENAI_MODEL: str = field(
        default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4-turbo-preview")
    )

    # News APIs
    NEWSAPI_KEY: Optional[str] = field(default_factory=lambda: os.getenv("NEWSAPI_KEY"))
    CRYPTOPANIC_API_KEY: Optional[str] = field(
        default_factory=lambda: os.getenv("CRYPTOPANIC_API_KEY")
    )

    # Trading
    MAX_POSITION_SIZE: float = field(
        default_factory=lambda: float(os.getenv("MAX_POSITION_SIZE", "0.1"))
    )
    RISK_PER_TRADE: float = field(
        default_factory=lambda: float(os.getenv("RISK_PER_TRADE", "0.02"))
    )
    MIN_CONFIDENCE_SCORE: float = field(
        default_factory=lambda: float(os.getenv("MIN_CONFIDENCE_SCORE", "0.7"))
    )
    MAX_POSITIONS: int = field(
        default_factory=lambda: int(os.getenv("MAX_POSITIONS", "5"))
    )

    # Logging
    LOG_LEVEL: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))

    def __post_init__(self):
        """Post-initialization validation"""
        # Basic validation
        if not 0 <= self.MAX_POSITION_SIZE <= 1:
            raise ValueError("MAX_POSITION_SIZE must be between 0 and 1")
        if not 0 <= self.RISK_PER_TRADE <= 0.1:
            raise ValueError("RISK_PER_TRADE must be between 0 and 0.1")
        if not 0 <= self.MIN_CONFIDENCE_SCORE <= 1:
            raise ValueError("MIN_CONFIDENCE_SCORE must be between 0 and 1")
