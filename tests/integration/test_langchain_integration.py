#!/usr/bin/env python3
"""
Integration tests for LangChain agent wrappers

This script tests:
1. LangChain wrapper initialization with actual agents
2. Conversational interfaces for market analysis
3. Conversational interfaces for news analysis
4. Conversational interfaces for trading execution
5. LangGraph workflow orchestration
6. Error handling in conversational contexts
"""

import asyncio
import logging
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Configure test logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@pytest.fixture
def mock_openai_key():
    """Mock OpenAI API key for testing"""
    return "sk-test-key-for-testing-purposes"


@pytest.fixture
def mock_agents():
    """Create mock agents for testing"""
    from src.agents.market_analyzer import MarketAnalyzerAgent
    from src.agents.news_analyzer import NewsAnalyzerAgent
    from src.agents.trading_executor import TradingExecutorAgent
    from src.database.connection import DatabaseManager
    from src.graph.state_manager import StateManager

    # Create mock dependencies
    state_manager = StateManager()
    db_manager = MagicMock(spec=DatabaseManager)

    # Mock database session
    mock_session = MagicMock()
    db_manager.get_session.return_value = mock_session

    # Create agent configs
    market_config = {
        "trading_pairs": ["BTC/USDT"],
        "timeframes": ["1h"],
        "analysis_interval_seconds": 30,
        "min_confidence_threshold": 0.6,
    }

    news_config = {
        "news_sources": ["crypto_news", "financial_news"],
        "sentiment_threshold": 0.1,
        "analysis_interval_seconds": 60,
    }

    trading_config = {
        "trading_pairs": ["BTC/USDT"],
        "max_position_size": 0.1,
        "risk_per_trade": 0.02,
    }

    # Create agents
    market_agent = MarketAnalyzerAgent(market_config, state_manager, db_manager)
    news_agent = NewsAnalyzerAgent(news_config, state_manager, db_manager)
    trading_agent = TradingExecutorAgent(trading_config, state_manager, db_manager)

    return {
        "market": market_agent,
        "news": news_agent,
        "trading": trading_agent,
        "state_manager": state_manager,
        "db_manager": db_manager,
    }


class TestLangChainIntegration:
    """Test LangChain integration with trading agents"""

    @pytest.mark.asyncio
    async def test_market_analyzer_wrapper_initialization(self, mock_agents, mock_openai_key):
        """Test MarketAnalyzerWrapper initialization"""
        print("\n" + "=" * 60)
        print("TESTING MARKET ANALYZER WRAPPER INITIALIZATION")
        print("=" * 60)

        try:
            from src.langchain_agents.market_analyzer_wrapper import MarketAnalyzerWrapper

            # Mock OpenAI key
            with patch.dict(os.environ, {"OPENAI_API_KEY": mock_openai_key}):
                config = {"OPENAI_API_KEY": mock_openai_key, "model": "gpt-3.5-turbo", "temperature": 0.1}
                wrapper = MarketAnalyzerWrapper(
                    mock_agents["market"],
                    mock_agents["state_manager"],
                    mock_agents["db_manager"],
                    config
                )

                assert wrapper.agent == mock_agents["market"]
                assert hasattr(wrapper, 'tools')
                assert hasattr(wrapper, 'logger')
                assert wrapper.logger is not None

                print("✅ MarketAnalyzerWrapper initialized successfully")
                print(f"   Tools available: {len(wrapper.tools)}")
                if wrapper.tools:
                    print(f"   Tool names: {[tool.name for tool in wrapper.tools]}")
                else:
                    print("   No tools created (expected in test environment)")

        except Exception as e:
            print(f"❌ MarketAnalyzerWrapper initialization failed: {e}")
            import traceback
            traceback.print_exc()
            raise

    @pytest.mark.asyncio
    async def test_news_analyzer_wrapper_initialization(self, mock_agents, mock_openai_key):
        """Test NewsAnalyzerWrapper initialization"""
        print("\n" + "=" * 60)
        print("TESTING NEWS ANALYZER WRAPPER INITIALIZATION")
        print("=" * 60)

        try:
            from src.langchain_agents.news_analyzer_wrapper import NewsAnalyzerWrapper

            with patch.dict(os.environ, {"OPENAI_API_KEY": mock_openai_key}):
                config = {"OPENAI_API_KEY": mock_openai_key, "model": "gpt-3.5-turbo", "temperature": 0.1}
                wrapper = NewsAnalyzerWrapper(
                    mock_agents["news"],
                    mock_agents["state_manager"],
                    mock_agents["db_manager"],
                    config
                )

                assert wrapper.agent == mock_agents["news"]
                assert hasattr(wrapper, 'tools')
                assert hasattr(wrapper, 'logger')

                print("✅ NewsAnalyzerWrapper initialized successfully")
                print(f"   Tools available: {len(wrapper.tools)}")

        except Exception as e:
            print(f"❌ NewsAnalyzerWrapper initialization failed: {e}")
            import traceback
            traceback.print_exc()
            raise

    @pytest.mark.asyncio
    async def test_trading_executor_wrapper_initialization(self, mock_agents, mock_openai_key):
        """Test TradingExecutorWrapper initialization"""
        print("\n" + "=" * 60)
        print("TESTING TRADING EXECUTOR WRAPPER INITIALIZATION")
        print("=" * 60)

        try:
            from src.langchain_agents.trading_executor_wrapper import TradingExecutorWrapper

            with patch.dict(os.environ, {"OPENAI_API_KEY": mock_openai_key}):
                config = {"OPENAI_API_KEY": mock_openai_key, "model": "gpt-3.5-turbo", "temperature": 0.1}
                wrapper = TradingExecutorWrapper(
                    mock_agents["trading"],
                    mock_agents["state_manager"],
                    mock_agents["db_manager"],
                    config
                )

                assert wrapper.agent == mock_agents["trading"]
                assert hasattr(wrapper, 'tools')
                assert hasattr(wrapper, 'logger')

                print("✅ TradingExecutorWrapper initialized successfully")
                print(f"   Tools available: {len(wrapper.tools)}")

        except Exception as e:
            print(f"❌ TradingExecutorWrapper initialization failed: {e}")
            import traceback
            traceback.print_exc()
            raise

    @pytest.mark.asyncio
    async def test_market_analysis_conversation(self, mock_agents, mock_openai_key):
        """Test conversational market analysis"""
        print("\n" + "=" * 60)
        print("TESTING MARKET ANALYSIS CONVERSATION")
        print("=" * 60)

        try:
            from src.langchain_agents.market_analyzer_wrapper import MarketAnalyzerWrapper

            with patch.dict(os.environ, {"OPENAI_API_KEY": mock_openai_key}):
                config = {"OPENAI_API_KEY": mock_openai_key, "model": "gpt-3.5-turbo", "temperature": 0.1}
                wrapper = MarketAnalyzerWrapper(
                    mock_agents["market"],
                    mock_agents["state_manager"],
                    mock_agents["db_manager"],
                    config
                )

                # Mock the LLM to return a simple response
                with patch('langchain_openai.ChatOpenAI') as mock_llm:
                    mock_instance = MagicMock()
                    mock_instance.ainvoke.return_value = MagicMock(
                        content="Based on the current market data, BTC/USDT shows bullish signals with RSI at 65 and MACD crossing above the signal line."
                    )
                    mock_llm.return_value = mock_instance

                    # Test conversational query
                    query = "What's the current market analysis for BTC/USDT?"
                    response = await wrapper.chat(query)

                    assert isinstance(response, dict)
                    assert "response" in response
                    assert len(response["response"]) > 0
                    print("✅ Market analysis conversation successful")
                    print(f"   Response length: {len(response['response'])} characters")

        except Exception as e:
            print(f"❌ Market analysis conversation failed: {e}")
            import traceback
            traceback.print_exc()
            raise

    @pytest.mark.asyncio
    async def test_news_sentiment_conversation(self, mock_agents, mock_openai_key):
        """Test conversational news sentiment analysis"""
        print("\n" + "=" * 60)
        print("TESTING NEWS SENTIMENT CONVERSATION")
        print("=" * 60)

        try:
            from src.langchain_agents.news_analyzer_wrapper import NewsAnalyzerWrapper

            with patch.dict(os.environ, {"OPENAI_API_KEY": mock_openai_key}):
                wrapper = NewsAnalyzerWrapper(
                    mock_agents["news"],
                    mock_agents["state_manager"],
                    mock_agents["db_manager"],
                    {"OPENAI_API_KEY": mock_openai_key, "LANGCHAIN_MODEL": "gpt-3.5-turbo", "LANGCHAIN_TEMPERATURE": 0.1}
                )

                # Mock the LLM
                with patch('langchain_openai.ChatOpenAI') as mock_llm:
                    mock_instance = MagicMock()
                    mock_instance.ainvoke.return_value = MagicMock(
                        content="Current sentiment analysis shows positive news coverage for Bitcoin with a sentiment score of 0.75."
                    )
                    mock_llm.return_value = mock_instance

                    query = "What's the current news sentiment for Bitcoin?"
                    response = await wrapper.query(query)

                    assert isinstance(response, str)
                    assert len(response) > 0
                    print("✅ News sentiment conversation successful")

        except Exception as e:
            print(f"❌ News sentiment conversation failed: {e}")
            import traceback
            traceback.print_exc()
            raise

    @pytest.mark.asyncio
    async def test_trading_execution_conversation(self, mock_agents, mock_openai_key):
        """Test conversational trading execution"""
        print("\n" + "=" * 60)
        print("TESTING TRADING EXECUTION CONVERSATION")
        print("=" * 60)

        try:
            from src.langchain_agents.trading_executor_wrapper import TradingExecutorWrapper

            with patch.dict(os.environ, {"OPENAI_API_KEY": mock_openai_key}):
                wrapper = TradingExecutorWrapper(
                    mock_agents["trading"],
                    mock_agents["state_manager"],
                    mock_agents["db_manager"],
                    {"OPENAI_API_KEY": mock_openai_key, "LANGCHAIN_MODEL": "gpt-3.5-turbo", "LANGCHAIN_TEMPERATURE": 0.05}
                )

                # Mock the LLM
                with patch('langchain_openai.ChatOpenAI') as mock_llm:
                    mock_instance = MagicMock()
                    mock_instance.ainvoke.return_value = MagicMock(
                        content="I'll help you execute a buy order for 0.01 BTC at the current market price."
                    )
                    mock_llm.return_value = mock_instance

                    query = "Buy 0.01 BTC at market price"
                    response = await wrapper.query(query)

                    assert isinstance(response, str)
                    assert len(response) > 0
                    print("✅ Trading execution conversation successful")

        except Exception as e:
            print(f"❌ Trading execution conversation failed: {e}")
            import traceback
            traceback.print_exc()
            raise

    @pytest.mark.asyncio
    async def test_langgraph_workflow_orchestration(self, mock_agents, mock_openai_key):
        """Test LangGraph workflow orchestration"""
        print("\n" + "=" * 60)
        print("TESTING LANGGRAPH WORKFLOW ORCHESTRATION")
        print("=" * 60)

        try:
            from src.langchain_agents.trading_workflow import TradingWorkflow

            with patch.dict(os.environ, {"OPENAI_API_KEY": mock_openai_key}):
                workflow = TradingWorkflow(mock_agents["market"], mock_agents["news"], mock_agents["trading"])

                # Mock the LLM for workflow
                with patch('langchain_openai.ChatOpenAI') as mock_llm:
                    mock_instance = MagicMock()
                    mock_instance.ainvoke.return_value = MagicMock(
                        content="Based on market analysis and news sentiment, I recommend a BUY signal for BTC/USDT."
                    )
                    mock_llm.return_value = mock_instance

                    # Test workflow execution
                    query = "Should I buy BTC right now?"
                    response = await workflow.run(query)

                    assert isinstance(response, str)
                    assert len(response) > 0
                    print("✅ LangGraph workflow orchestration successful")
                    print(f"   Response: {response[:100]}...")

        except Exception as e:
            print(f"❌ LangGraph workflow orchestration failed: {e}")
            import traceback
            traceback.print_exc()
            raise

    @pytest.mark.asyncio
    async def test_error_handling_in_conversations(self, mock_agents, mock_openai_key):
        """Test error handling in conversational interfaces"""
        print("\n" + "=" * 60)
        print("TESTING ERROR HANDLING IN CONVERSATIONS")
        print("=" * 60)

        try:
            from src.langchain_agents.market_analyzer_wrapper import MarketAnalyzerWrapper

            with patch.dict(os.environ, {"OPENAI_API_KEY": mock_openai_key}):
                wrapper = MarketAnalyzerWrapper(mock_agents["market"])

                # Mock LLM to raise an exception
                with patch('langchain_openai.ChatOpenAI') as mock_llm:
                    mock_instance = MagicMock()
                    mock_instance.ainvoke.side_effect = Exception("API Error")
                    mock_llm.return_value = mock_instance

                    query = "What's the market analysis?"
                    response = await wrapper.query(query)

                    # Should handle error gracefully
                    assert isinstance(response, str)
                    assert "error" in response.lower() or "failed" in response.lower()
                    print("✅ Error handling in conversations successful")

        except Exception as e:
            print(f"❌ Error handling test failed: {e}")
            import traceback
            traceback.print_exc()
            raise


@pytest.mark.asyncio
async def test_full_integration_flow(mock_agents, mock_openai_key):
    """Test full integration flow from conversation to execution"""
    print("\n" + "=" * 60)
    print("TESTING FULL INTEGRATION FLOW")
    print("=" * 60)

    try:
        from src.langchain_agents.trading_workflow import TradingWorkflow

        with patch.dict(os.environ, {"OPENAI_API_KEY": mock_openai_key}):
            workflow = TradingWorkflow(mock_agents["market"], mock_agents["news"], mock_agents["trading"])

            # Mock all LLMs
            with patch('langchain_openai.ChatOpenAI') as mock_llm:
                mock_instance = MagicMock()
                mock_instance.ainvoke.return_value = MagicMock(
                    content="After analyzing market data and news sentiment, I recommend executing a small buy order for BTC/USDT."
                )
                mock_llm.return_value = mock_instance

                # Test complete flow
                query = "Analyze BTC and execute a small buy order if conditions are good"
                response = await workflow.run(query)

                assert isinstance(response, str)
                assert len(response) > 0
                print("✅ Full integration flow successful")
                print(f"   Final response length: {len(response)} characters")

    except Exception as e:
        print(f"❌ Full integration flow failed: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    # Run tests manually if executed directly
    async def run_manual_tests():
        print("LANGCHAIN INTEGRATION TESTS")
        print("=" * 80)

        # Create mock fixtures
        mock_key = "sk-test-key"
        mock_agents_fixture = await asyncio.coroutine(lambda: None)()  # This will be replaced by pytest

        # For manual testing, we'd need to implement the mock_agents fixture here
        # But since this is meant to be run with pytest, we'll just run pytest
        import subprocess
        result = subprocess.run([
            sys.executable, "-m", "pytest",
            "tests/integration/test_langchain_integration.py",
            "-v", "--tb=short"
        ], cwd=project_root)

        sys.exit(result.returncode)

    asyncio.run(run_manual_tests())