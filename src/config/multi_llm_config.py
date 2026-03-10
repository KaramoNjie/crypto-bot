"""
Multi-LLM Provider Configuration for LangChain

This module provides configuration and utilities for using multiple LLM providers
with LangChain's init_chat_model function.
"""

import os
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from langchain.chat_models import init_chat_model
import logging

logger = logging.getLogger(__name__)


@dataclass
class LLMProviderConfig:
    """Configuration for an LLM provider"""
    name: str
    model_identifier: str
    api_key_env: str
    required_packages: List[str]
    description: str
    pricing_tier: str  # 'free', 'paid', 'freemium'


class MultiLLMManager:
    """Manager for multiple LLM providers using LangChain"""

    def __init__(self):
        self.providers = {
            # OpenAI
            "openai_gpt4": LLMProviderConfig(
                name="OpenAI GPT-4",
                model_identifier="openai:gpt-4",
                api_key_env="OPENAI_API_KEY",
                required_packages=["langchain-openai"],
                description="Most capable model, excellent reasoning",
                pricing_tier="paid"
            ),
            "openai_gpt4_turbo": LLMProviderConfig(
                name="OpenAI GPT-4 Turbo",
                model_identifier="openai:gpt-4-turbo-preview",
                api_key_env="OPENAI_API_KEY",
                required_packages=["langchain-openai"],
                description="Faster GPT-4 with larger context",
                pricing_tier="paid"
            ),
            "openai_gpt35": LLMProviderConfig(
                name="OpenAI GPT-3.5 Turbo",
                model_identifier="openai:gpt-3.5-turbo",
                api_key_env="OPENAI_API_KEY",
                required_packages=["langchain-openai"],
                description="Fast and cost-effective",
                pricing_tier="paid"
            ),

            # Anthropic Claude
            "anthropic_claude3_opus": LLMProviderConfig(
                name="Claude 3 Opus",
                model_identifier="anthropic:claude-3-opus-20240229",
                api_key_env="ANTHROPIC_API_KEY",
                required_packages=["langchain-anthropic"],
                description="Most capable Claude model",
                pricing_tier="paid"
            ),
            "anthropic_claude3_sonnet": LLMProviderConfig(
                name="Claude 3 Sonnet",
                model_identifier="anthropic:claude-3-sonnet-20240229",
                api_key_env="ANTHROPIC_API_KEY",
                required_packages=["langchain-anthropic"],
                description="Balanced performance and speed",
                pricing_tier="freemium"
            ),
            "anthropic_claude3_haiku": LLMProviderConfig(
                name="Claude 3 Haiku",
                model_identifier="anthropic:claude-3-haiku-20240307",
                api_key_env="ANTHROPIC_API_KEY",
                required_packages=["langchain-anthropic"],
                description="Fastest Claude model",
                pricing_tier="freemium"
            ),

            # Groq (Fast inference)
            "groq_llama3_70b": LLMProviderConfig(
                name="Groq Llama 3 70B",
                model_identifier="groq:llama3-70b-8192",
                api_key_env="GROQ_API_KEY",
                required_packages=["langchain-groq"],
                description="Very fast inference, good performance",
                pricing_tier="freemium"
            ),
            "groq_mixtral": LLMProviderConfig(
                name="Groq Mixtral 8x7B",
                model_identifier="groq:mixtral-8x7b-32768",
                api_key_env="GROQ_API_KEY",
                required_packages=["langchain-groq"],
                description="Fast mixture of experts model",
                pricing_tier="freemium"
            ),

            # Together AI
            "together_llama3_70b": LLMProviderConfig(
                name="Together Llama 3 70B",
                model_identifier="together:meta-llama/Llama-3-70b-chat-hf",
                api_key_env="TOGETHER_API_KEY",
                required_packages=["langchain-together"],
                description="Open source model via Together",
                pricing_tier="freemium"
            ),

            # Mistral AI
            "mistral_large": LLMProviderConfig(
                name="Mistral Large",
                model_identifier="mistral:mistral-large-latest",
                api_key_env="MISTRAL_API_KEY",
                required_packages=["langchain-mistralai"],
                description="Mistral's most capable model",
                pricing_tier="paid"
            ),
            "mistral_medium": LLMProviderConfig(
                name="Mistral Medium",
                model_identifier="mistral:mistral-medium-latest",
                api_key_env="MISTRAL_API_KEY",
                required_packages=["langchain-mistralai"],
                description="Balanced Mistral model",
                pricing_tier="freemium"
            ),

            # Cohere
            "cohere_command_r": LLMProviderConfig(
                name="Cohere Command R",
                model_identifier="cohere:command-r",
                api_key_env="COHERE_API_KEY",
                required_packages=["langchain-cohere"],
                description="Cohere's command model",
                pricing_tier="freemium"
            ),

            # Ollama (Local)
            "ollama_llama3": LLMProviderConfig(
                name="Ollama Llama 3",
                model_identifier="ollama:llama3",
                api_key_env="",  # No API key needed for local
                required_packages=["langchain-ollama"],
                description="Local Llama 3 model",
                pricing_tier="free"
            ),
            "ollama_mistral": LLMProviderConfig(
                name="Ollama Mistral",
                model_identifier="ollama:mistral",
                api_key_env="",
                required_packages=["langchain-ollama"],
                description="Local Mistral model",
                pricing_tier="free"
            ),

            # Google AI (Gemini)
            "google_gemini_pro": LLMProviderConfig(
                name="Google Gemini Pro",
                model_identifier="google-genai:gemini-pro",
                api_key_env="GOOGLE_API_KEY",
                required_packages=["langchain-google-genai"],
                description="Google's flagship multimodal model",
                pricing_tier="freemium"
            ),
            "google_gemini_pro_vision": LLMProviderConfig(
                name="Google Gemini Pro Vision",
                model_identifier="google-genai:gemini-pro-vision",
                api_key_env="GOOGLE_API_KEY",
                required_packages=["langchain-google-genai"],
                description="Gemini with vision capabilities",
                pricing_tier="freemium"
            ),
            "google_gemini_15_pro": LLMProviderConfig(
                name="Google Gemini 1.5 Pro",
                model_identifier="google-genai:gemini-1.5-pro-latest",
                api_key_env="GOOGLE_API_KEY",
                required_packages=["langchain-google-genai"],
                description="Latest Gemini 1.5 with large context",
                pricing_tier="paid"
            ),
            "google_gemini_15_flash": LLMProviderConfig(
                name="Google Gemini 1.5 Flash",
                model_identifier="google-genai:gemini-1.5-flash-latest",
                api_key_env="GOOGLE_API_KEY",
                required_packages=["langchain-google-genai"],
                description="Faster Gemini 1.5 optimized for speed",
                pricing_tier="freemium"
            ),

            # Google Vertex AI (Enterprise)
            "vertex_gemini_pro": LLMProviderConfig(
                name="Vertex AI Gemini Pro",
                model_identifier="google-vertexai:gemini-pro",
                api_key_env="GOOGLE_APPLICATION_CREDENTIALS",
                required_packages=["langchain-google-vertexai"],
                description="Enterprise Gemini via Vertex AI",
                pricing_tier="paid"
            ),
        }

        # Priority order: Free -> Freemium -> Paid
        self.priority_order = [
            # Free options first
            "ollama_llama3", "ollama_mistral",
            # Freemium options (fast and affordable)
            "groq_llama3_70b", "groq_mixtral",
            "google_gemini_15_flash", "google_gemini_pro",
            "anthropic_claude3_haiku", "anthropic_claude3_sonnet",
            "together_llama3_70b", "mistral_medium", "cohere_command_r",
            "google_gemini_pro_vision",
            # Paid options last
            "google_gemini_15_pro", "mistral_large", "anthropic_claude3_opus",
            "vertex_gemini_pro", "openai_gpt35", "openai_gpt4_turbo", "openai_gpt4"
        ]

    def get_available_providers(self) -> List[Tuple[str, LLMProviderConfig]]:
        """Get list of available providers (those with API keys configured)"""
        available = []

        for provider_id in self.priority_order:
            config = self.providers[provider_id]

            # For local models (Ollama), no API key needed
            if not config.api_key_env:
                available.append((provider_id, config))
            # For API providers, check if key exists
            elif os.getenv(config.api_key_env):
                available.append((provider_id, config))

        return available

    def get_best_available_provider(self) -> Optional[Tuple[str, LLMProviderConfig]]:
        """Get the best available provider based on priority order"""
        available = self.get_available_providers()
        return available[0] if available else None

    def test_provider(self, provider_id: str, temperature: float = 0) -> Tuple[bool, str]:
        """Test if a specific provider is working"""
        if provider_id not in self.providers:
            return False, f"Unknown provider: {provider_id}"

        config = self.providers[provider_id]

        # Check API key if required
        if config.api_key_env and not os.getenv(config.api_key_env):
            return False, f"Missing API key: {config.api_key_env}"

        try:
            # Try to initialize the model
            llm = init_chat_model(
                config.model_identifier,
                temperature=temperature
            )
            return True, "Provider working"

        except Exception as e:
            return False, str(e)

    def create_llm(self, provider_id: Optional[str] = None, temperature: float = 0, **kwargs):
        """Create an LLM instance using specified or best available provider"""
        if provider_id is None:
            # Get best available provider
            best = self.get_best_available_provider()
            if not best:
                raise ValueError("No LLM providers available")
            provider_id, config = best
        else:
            if provider_id not in self.providers:
                raise ValueError(f"Unknown provider: {provider_id}")
            config = self.providers[provider_id]

        # Check API key if required
        if config.api_key_env and not os.getenv(config.api_key_env):
            raise ValueError(f"Missing API key for {config.name}: {config.api_key_env}")

        try:
            llm = init_chat_model(
                config.model_identifier,
                temperature=temperature,
                **kwargs
            )
            logger.info(f"Created LLM: {config.name}")
            return llm, config

        except Exception as e:
            logger.error(f"Failed to create LLM {config.name}: {e}")
            raise

    def get_provider_status(self) -> Dict[str, Dict]:
        """Get status of all providers"""
        status = {}

        for provider_id, config in self.providers.items():
            # Check API key
            has_key = True
            if config.api_key_env:
                has_key = bool(os.getenv(config.api_key_env))

            # Test provider
            is_working, message = self.test_provider(provider_id)

            status[provider_id] = {
                "name": config.name,
                "has_api_key": has_key,
                "is_working": is_working,
                "message": message,
                "pricing_tier": config.pricing_tier,
                "description": config.description
            }

        return status


# Global instance
_multi_llm_manager = None

def get_multi_llm_manager() -> MultiLLMManager:
    """Get the global MultiLLMManager instance"""
    global _multi_llm_manager
    if _multi_llm_manager is None:
        _multi_llm_manager = MultiLLMManager()
    return _multi_llm_manager


def create_best_available_llm(temperature: float = 0, **kwargs):
    """Create the best available LLM"""
    manager = get_multi_llm_manager()
    return manager.create_llm(temperature=temperature, **kwargs)


def list_available_providers() -> List[str]:
    """List available provider names"""
    manager = get_multi_llm_manager()
    available = manager.get_available_providers()
    return [config.name for _, config in available]
