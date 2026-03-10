"""
LangChain Configuration Module

This module provides configuration utilities for LangChain components
used in the conversational trading interfaces.
"""

import os
from typing import Dict, Any
from .settings import Config


def get_langchain_config() -> Dict[str, Any]:
    """
    Get LangChain configuration from environment and settings

    Returns:
        Dictionary containing LangChain configuration
    """
    config = Config()

    return {
        "OPENAI_API_KEY": config.OPENAI_API_KEY,
        "LANGCHAIN_MODEL": config.LANGCHAIN_MODEL,
        "LANGCHAIN_TEMPERATURE": config.LANGCHAIN_TEMPERATURE,
        "LANGCHAIN_MAX_TOKENS": config.LANGCHAIN_MAX_TOKENS,
        "LANGCHAIN_CACHE_ENABLED": config.LANGCHAIN_CACHE_ENABLED,
        "LANGCHAIN_RATE_LIMIT_REQUESTS": config.LANGCHAIN_RATE_LIMIT_REQUESTS,
        "LANGCHAIN_RATE_LIMIT_WINDOW": config.LANGCHAIN_RATE_LIMIT_WINDOW,
        # Additional LangChain settings
        "LANGCHAIN_TRACING_V2": os.getenv("LANGCHAIN_TRACING_V2", "false").lower()
        == "true",
        "LANGCHAIN_API_KEY": os.getenv("LANGCHAIN_API_KEY"),
        "LANGCHAIN_PROJECT": os.getenv("LANGCHAIN_PROJECT", "crypto-trading-bot"),
    }


def get_agent_config(agent_type: str) -> Dict[str, Any]:
    """
    Get agent-specific configuration

    Args:
        agent_type: Type of agent ('market_analyzer', 'news_analyzer', 'trading_executor')

    Returns:
        Agent-specific configuration dictionary
    """
    base_config = get_langchain_config()

    # Agent-specific overrides
    agent_configs = {
        "market_analyzer": {
            "model": "openai:gpt-4-turbo-preview",  # Use most capable model for analysis
            "temperature": 0,  # Deterministic behavior as per langchain.rules
            "max_tokens": 1500,
        },
        "news_analyzer": {
            "model": "openai:gpt-4-turbo-preview",  # Good at understanding context
            "temperature": 0,  # Deterministic behavior as per langchain.rules
            "max_tokens": 1200,
        },
        "risk_manager": {
            "model": "openai:gpt-4-turbo-preview",  # Precise risk calculations
            "temperature": 0,  # Deterministic behavior as per langchain.rules
            "max_tokens": 1000,
        },
        "trading_executor": {
            "model": "openai:gpt-4-turbo-preview",  # Precise execution instructions
            "temperature": 0,  # Deterministic behavior as per langchain.rules
            "max_tokens": 800,
        },
    }

    # Merge base config with agent-specific config
    agent_config = base_config.copy()
    if agent_type in agent_configs:
        agent_config.update(agent_configs[agent_type])

    return agent_config


def validate_langchain_config(config: Dict[str, Any]) -> bool:
    """
    Validate LangChain configuration

    Args:
        config: Configuration dictionary to validate

    Returns:
        True if valid, raises ValueError if invalid
    """
    required_keys = ["OPENAI_API_KEY"]
    missing_keys = [key for key in required_keys if not config.get(key)]

    if missing_keys:
        raise ValueError(f"Missing required LangChain configuration: {missing_keys}")

    # Validate temperature
    temperature = config.get("LANGCHAIN_TEMPERATURE", 0.1)
    if not 0 <= temperature <= 2:
        raise ValueError(f"Invalid temperature {temperature}, must be between 0 and 2")

    # Validate max tokens
    max_tokens = config.get("LANGCHAIN_MAX_TOKENS", 2000)
    if max_tokens < 1:
        raise ValueError(f"Invalid max_tokens {max_tokens}, must be at least 1")

    return True
