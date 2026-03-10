"""
Default Configuration for Crypto Trading Bot
Based on TradingAgents DEFAULT_CONFIG but adapted for cryptocurrency trading
"""

import os

# Default configuration following TradingAgents pattern
DEFAULT_CONFIG = {
    # Project structure
    "project_dir": os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")),
    "results_dir": os.getenv("CRYPTO_BOT_RESULTS_DIR", "./results"),
    "data_dir": os.path.join(
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")),
        "data"
    ),
    "data_cache_dir": os.path.join(
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")),
        "data/cache"
    ),

    # LLM settings (following TradingAgents pattern)
    "llm_provider": "openai",  # openai, anthropic, google, groq
    "deep_think_llm": "gpt-4o",  # For complex analysis and debates
    "quick_think_llm": "gpt-4o-mini",  # For quick responses and tools
    "backend_url": "https://api.openai.com/v1",

    # Alternative LLM configurations
    "llm_configs": {
        "openai": {
            "backend_url": "https://api.openai.com/v1",
            "deep_think_llm": "gpt-4o",
            "quick_think_llm": "gpt-4o-mini",
            "api_key_env": "OPENAI_API_KEY"
        },
        "anthropic": {
            "backend_url": "https://api.anthropic.com",
            "deep_think_llm": "claude-3-opus-20240229",
            "quick_think_llm": "claude-3-haiku-20240307",
            "api_key_env": "ANTHROPIC_API_KEY"
        },
        "google": {
            "backend_url": "https://generativelanguage.googleapis.com/v1",
            "deep_think_llm": "gemini-1.5-pro",
            "quick_think_llm": "gemini-1.5-flash",
            "api_key_env": "GOOGLE_API_KEY"
        },
        "groq": {
            "backend_url": "https://api.groq.com/openai/v1",
            "deep_think_llm": "llama-3.1-70b-versatile",
            "quick_think_llm": "llama-3.1-8b-instant",
            "api_key_env": "GROQ_API_KEY"
        },
        "ollama": {
            "backend_url": "http://localhost:11434/v1",
            "deep_think_llm": "llama3:70b",
            "quick_think_llm": "llama3:8b",
            "api_key_env": None  # Ollama doesn't need API key
        }
    },

    # Debate and discussion settings (key TradingAgents features)
    "max_debate_rounds": 3,  # Bull vs Bear researcher debate rounds
    "max_risk_discuss_rounds": 2,  # Risk management discussion rounds
    "max_recur_limit": 100,  # Maximum recursion limit for graph execution

    # Tool settings
    "online_tools": True,  # Use real-time data vs cached data
    "tool_timeout": 30,  # Timeout for tool calls in seconds

    # Trading settings
    "paper_trading": True,  # Start with paper trading
    "binance_testnet": True,  # Use Binance testnet for paper trading
    "max_position_size": 0.1,  # Maximum 10% of portfolio per position
    "risk_per_trade": 0.02,  # Maximum 2% risk per trade
    "min_confidence": 0.6,  # Minimum confidence for trade execution
    "default_stop_loss": 0.05,  # Default 5% stop loss
    "default_take_profit": 0.15,  # Default 15% take profit

    # API configuration
    "api_configs": {
        "binance": {
            "api_key_env": "BINANCE_API_KEY",
            "secret_key_env": "BINANCE_SECRET_KEY",
            "testnet": True,
            "base_url": "https://testnet.binance.vision"  # Testnet URL
        },
        "coinmarketcap": {
            "api_key_env": "COINMARKETCAP_API_KEY",
            "base_url": "https://pro-api.coinmarketcap.com"
        },
        "news_api": {
            "api_key_env": "NEWS_API_KEY",
            "base_url": "https://newsapi.org/v2"
        },
        "cryptopanic": {
            "api_key_env": "CRYPTOPANIC_API_KEY",
            "base_url": "https://cryptopanic.com/api/v1"
        },
        "twitter": {
            "bearer_token_env": "TWITTER_BEARER_TOKEN",
            "base_url": "https://api.twitter.com/2"
        },
        "reddit": {
            "client_id_env": "REDDIT_CLIENT_ID",
            "client_secret_env": "REDDIT_CLIENT_SECRET",
            "base_url": "https://www.reddit.com"
        }
    },

    # Database settings
    "database": {
        "url": os.getenv("DATABASE_URL", "postgresql://crypto_user:crypto_pass@localhost:5432/crypto_trading_db"),
        "pool_size": 10,
        "max_overflow": 20,
        "echo": False  # Set to True for SQL debugging
    },

    # Memory system settings (following TradingAgents pattern)
    "memory": {
        "enabled": True,
        "collection_name": "crypto_trading_memory",
        "max_memories": 1000,
        "cleanup_days": 90,  # Clean up memories older than 90 days
        "embedding_model": "text-embedding-3-small"  # For OpenAI
    },

    # Agent settings
    "agents": {
        "enable_all": True,
        "analyst_team": ["market_analyzer", "news_analyzer", "sentiment_analyzer", "fundamentals_analyzer"],
        "researcher_team": ["bull_researcher", "bear_researcher", "research_manager"],
        "risk_team": ["conservative_risk", "aggressive_risk", "neutral_risk", "risk_manager"],
        "execution_team": ["trader", "portfolio_manager"],
        "chat_enabled": True,
        "agent_timeout": 60  # Timeout for agent execution in seconds
    },

    # Portfolio settings
    "portfolio": {
        "initial_balance": 10000.0,  # Starting balance in USDT
        "max_positions": 5,  # Maximum number of concurrent positions
        "rebalance_threshold": 0.05,  # Rebalance when allocation drifts 5%
        "emergency_stop_loss": 0.20,  # Emergency stop at 20% portfolio loss
        "profit_taking_threshold": 0.50  # Take profits at 50% gains
    },

    # Risk management
    "risk_management": {
        "max_daily_loss": 0.05,  # Maximum 5% daily loss
        "max_weekly_loss": 0.10,  # Maximum 10% weekly loss
        "max_monthly_loss": 0.20,  # Maximum 20% monthly loss
        "volatility_adjustment": True,  # Adjust position size based on volatility
        "correlation_limit": 0.7,  # Maximum correlation between positions
        "kelly_criterion": False,  # Use Kelly criterion for position sizing
        "var_confidence": 0.95  # VaR confidence level
    },

    # Monitoring and alerts
    "monitoring": {
        "health_check_interval": 300,  # Health check every 5 minutes
        "performance_tracking": True,
        "alert_on_errors": True,
        "alert_on_large_moves": True,
        "large_move_threshold": 0.10,  # Alert on 10% price moves
        "webhook_url": os.getenv("WEBHOOK_URL"),  # For alerts
    },

    # Logging configuration
    "logging": {
        "level": "INFO",
        "format": "json",  # json or text
        "file_enabled": True,
        "file_path": "logs/crypto_trading_bot.log",
        "max_file_size": "10MB",
        "backup_count": 5
    },

    # UI settings
    "ui": {
        "port": 8501,
        "host": "0.0.0.0",
        "debug": False,
        "auto_refresh_interval": 30,  # Auto refresh every 30 seconds
        "chart_height": 500,
        "chart_width": 900,
        "theme": "dark"
    },

    # Backtesting settings
    "backtesting": {
        "start_date": "2023-01-01",
        "end_date": "2024-12-31",
        "initial_capital": 10000,
        "commission": 0.001,  # 0.1% commission
        "slippage": 0.0005,  # 0.05% slippage
        "benchmark": "BTCUSDT"
    },

    # Default symbols for analysis
    "default_symbols": [
        "BTCUSDT",  # Bitcoin
        "ETHUSDT",  # Ethereum
        "BNBUSDT",  # Binance Coin
        "ADAUSDT",  # Cardano
        "SOLUSDT",  # Solana
        "DOTUSDT",  # Polkadot
        "MATICUSDT",  # Polygon
        "LINKUSDT",  # Chainlink
        "UNIUSDT",  # Uniswap
        "AVAXUSDT"  # Avalanche
    ],

    # Symbol categories
    "symbol_categories": {
        "large_cap": ["BTCUSDT", "ETHUSDT", "BNBUSDT"],
        "mid_cap": ["ADAUSDT", "SOLUSDT", "DOTUSDT", "MATICUSDT"],
        "defi": ["UNIUSDT", "LINKUSDT", "AAVEUSDT", "COMPUSDT"],
        "layer1": ["BTCUSDT", "ETHUSDT", "SOLUSDT", "AVAXUSDT", "DOTUSDT"],
        "layer2": ["MATICUSDT", "ARBUSDT", "OPUSDT"]
    },

    # Feature flags
    "features": {
        "multi_agent_system": True,
        "agent_debates": True,
        "memory_system": True,
        "real_time_data": True,
        "paper_trading": True,
        "live_trading": False,  # Disabled by default for safety
        "advanced_risk_management": True,
        "portfolio_optimization": True,
        "social_sentiment": True,
        "news_analysis": True,
        "technical_analysis": True,
        "fundamental_analysis": True
    },

    # Performance optimization
    "performance": {
        "cache_enabled": True,
        "cache_ttl": 300,  # Cache TTL in seconds
        "parallel_analysis": True,
        "max_workers": 4,  # Maximum worker threads
        "batch_size": 10,  # Batch size for bulk operations
        "memory_limit_mb": 512  # Memory limit in MB
    },

    # Environment settings
    "environment": {
        "name": os.getenv("ENVIRONMENT", "development"),  # development, staging, production
        "debug": os.getenv("DEBUG", "false").lower() == "true",
        "testing": os.getenv("TESTING", "false").lower() == "true",
        "version": "1.0.0"
    }
}


def get_config_for_environment(env: str = None) -> dict:
    """
    Get configuration adjusted for specific environment

    Args:
        env: Environment name (development, staging, production)

    Returns:
        Configuration dictionary
    """
    config = DEFAULT_CONFIG.copy()

    if env is None:
        env = config["environment"]["name"]

    if env == "production":
        # Production-specific settings
        config.update({
            "logging": {
                **config["logging"],
                "level": "WARNING",
                "debug": False
            },
            "ui": {
                **config["ui"],
                "debug": False
            },
            "database": {
                **config["database"],
                "echo": False
            },
            "features": {
                **config["features"],
                "live_trading": True,  # Enable for production
                "paper_trading": False
            }
        })
    elif env == "staging":
        # Staging-specific settings
        config.update({
            "logging": {
                **config["logging"],
                "level": "INFO"
            },
            "features": {
                **config["features"],
                "live_trading": False,
                "paper_trading": True
            }
        })
    elif env == "development":
        # Development-specific settings
        config.update({
            "logging": {
                **config["logging"],
                "level": "DEBUG",
                "debug": True
            },
            "ui": {
                **config["ui"],
                "debug": True
            },
            "database": {
                **config["database"],
                "echo": True  # Enable SQL logging in development
            }
        })

    return config


def get_llm_config(provider: str) -> dict:
    """
    Get LLM configuration for specific provider

    Args:
        provider: LLM provider name

    Returns:
        LLM configuration dictionary
    """
    llm_configs = DEFAULT_CONFIG["llm_configs"]

    if provider not in llm_configs:
        raise ValueError(f"Unknown LLM provider: {provider}")

    return llm_configs[provider]


def validate_config(config: dict) -> bool:
    """
    Validate configuration settings

    Args:
        config: Configuration dictionary

    Returns:
        True if valid, raises exception if invalid
    """
    required_keys = [
        "llm_provider",
        "deep_think_llm",
        "quick_think_llm",
        "max_debate_rounds",
        "online_tools"
    ]

    for key in required_keys:
        if key not in config:
            raise ValueError(f"Missing required configuration key: {key}")

    # Validate LLM provider
    if config["llm_provider"] not in DEFAULT_CONFIG["llm_configs"]:
        raise ValueError(f"Invalid LLM provider: {config['llm_provider']}")

    # Validate numeric ranges
    if not 1 <= config["max_debate_rounds"] <= 10:
        raise ValueError("max_debate_rounds must be between 1 and 10")

    if not 0.0 <= config["min_confidence"] <= 1.0:
        raise ValueError("min_confidence must be between 0.0 and 1.0")

    return True


# Export the default configuration
__all__ = ["DEFAULT_CONFIG", "get_config_for_environment", "get_llm_config", "validate_config"]
