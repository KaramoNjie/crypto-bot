"""
Main Application Entry Point for Crypto Trading Bot

This is the primary entry point that initializes all systems including:
- Agent Manager and all trading agents
- Database connections
- WebSocket connections
- Streamlit UI

Run with: python src/main.py
"""

import asyncio
import logging
import signal
import sys
import os
from typing import Optional

from .config.settings import Config
from .utils.logging_config import setup_trading_bot_logging, TradingLogger
from .orchestration.agent_manager import (
    initialize_agent_manager,
    shutdown_agent_manager,
    get_agent_manager,
)
from .ui.agent_state_api import initialize_agent_state_api
from .data.data_provider import RealDataProvider
from .database.connection import DatabaseManager

# Add the src directory and parent directory to the Python path
src_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(src_dir)


class TradingBotApplication:
    """Main application coordinator"""

    def __init__(self) -> None:
        self.config = Config()
        self.logger = TradingLogger("main_app").logger
        self.agent_manager = None
        self.data_provider = None
        self.database_manager = None
        self.shutdown_event = asyncio.Event()

    async def initialize(self) -> bool:
        """Initialize all systems"""
        try:
            self.logger.info("🚀 Starting Crypto Trading Bot...")

            # Initialize database
            self.logger.info("📊 Initializing database...")
            self.database_manager = DatabaseManager(self.config)
            await self.database_manager.initialize()

            # Initialize data provider
            self.logger.info("📈 Initializing data provider...")
            self.data_provider = RealDataProvider(self.config)
            data_success = await self.data_provider.initialize()

            if not data_success:
                self.logger.warning(
                    "⚠️ Data provider initialization failed, continuing with limited functionality"
                )

            # Initialize agent manager
            self.logger.info("🤖 Initializing agent manager...")
            self.agent_manager = await initialize_agent_manager(self.config)

            if not self.agent_manager:
                self.logger.error("❌ Failed to initialize agent manager")
                return False

            # Initialize agent state API
            self.logger.info("🔗 Initializing agent state API...")
            await initialize_agent_state_api()

            # Start all agents
            self.logger.info("▶️ Starting all agents...")
            success = await self.agent_manager.start_all_agents()

            if not success:
                self.logger.error("❌ Failed to start all agents")
                return False

            self.logger.info("✅ All systems initialized successfully!")
            return True

        except Exception as e:
            self.logger.error(f"❌ Failed to initialize application: {e}")
            return False

    async def run(self):
        """Run the application"""
        try:
            # Initialize systems
            success = await self.initialize()
            if not success:
                self.logger.error("Failed to initialize, exiting...")
                return False

            self.logger.info("🎯 Trading bot is now running!")
            self.logger.info("🌐 Access the UI at: http://localhost:8501")
            self.logger.info("💬 Chat with agents through the UI")
            self.logger.info("📊 Monitor performance on the dashboard")

            # Setup signal handlers for graceful shutdown
            loop = asyncio.get_event_loop()
            for signame in {"SIGINT", "SIGTERM"}:
                if hasattr(signal, signame):
                    loop.add_signal_handler(
                        getattr(signal, signame), self._signal_handler, signame
                    )

            # Keep running until shutdown
            await self.shutdown_event.wait()

            self.logger.info("🛑 Shutting down...")
            await self.shutdown()

            return True

        except Exception as e:
            self.logger.error(f"❌ Application error: {e}")
            await self.shutdown()
            return False

    def _signal_handler(self, signame):
        """Handle shutdown signals"""
        self.logger.info(f"📡 Received {signame}, initiating shutdown...")
        self.shutdown_event.set()

    async def shutdown(self):
        """Graceful shutdown of all systems"""
        try:
            self.logger.info("🔄 Shutting down systems...")

            # Stop agent manager
            if self.agent_manager:
                await shutdown_agent_manager()

            # Close data provider
            if self.data_provider:
                await self.data_provider.cleanup()

            # Close database
            if self.database_manager:
                await self.database_manager.close()

            self.logger.info("✅ Shutdown complete")

        except Exception as e:
            self.logger.error(f"❌ Error during shutdown: {e}")


def run_streamlit_ui():
    """Launch the Streamlit UI"""
    import subprocess
    import time

    logger = TradingLogger("streamlit_launcher").logger

    try:
        logger.info("🌐 Launching Streamlit UI...")

        # Launch Streamlit
        streamlit_cmd = [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            "src/ui/main_app.py",
            "--server.port=8501",
            "--server.address=localhost",
            "--server.headless=true",
        ]

        process = subprocess.Popen(
            streamlit_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )

        # Give Streamlit a moment to start
        time.sleep(3)

        if process.poll() is None:
            logger.info("✅ Streamlit UI launched successfully")
            logger.info("🌐 Access at: http://localhost:8501")
            return process
        else:
            stdout, stderr = process.communicate()
            logger.error("❌ Streamlit failed to start:")
            logger.error(f"STDOUT: {stdout.decode()}")
            logger.error(f"STDERR: {stderr.decode()}")
            return None

    except Exception as e:
        logger.error(f"❌ Error launching Streamlit: {e}")
        return None


async def main():
    """Main application entry point"""

    # Setup logging first
    setup_trading_bot_logging()
    logger = TradingLogger("main").logger

    try:
        logger.info("🎯 Crypto Trading Bot Starting...")

        # Check if we should run in UI mode (default) or headless mode
        ui_mode = "--no-ui" not in sys.argv

        if ui_mode:
            # Launch Streamlit UI in background
            streamlit_process = run_streamlit_ui()

            if not streamlit_process:
                logger.error("❌ Failed to launch UI, exiting...")
                return False

        # Create and run the main application
        app = TradingBotApplication()

        try:
            success = await app.run()
            return success

        finally:
            # Clean up Streamlit process if it was started
            if ui_mode and streamlit_process:
                try:
                    streamlit_process.terminate()
                    streamlit_process.wait(timeout=5)
                    logger.info("✅ Streamlit UI stopped")
                except Exception as e:
                    logger.warning(f"⚠️ Error stopping Streamlit: {e}")

    except KeyboardInterrupt:
        logger.info("👋 Received keyboard interrupt, exiting...")
        return True

    except Exception as e:
        logger.error(f"❌ Unexpected error in main: {e}")
        return False


if __name__ == "__main__":
    # Print startup banner
    print(
        """
    ╔══════════════════════════════════════════════════════════════╗
    ║                   🚀 CRYPTO TRADING BOT 🚀                   ║
    ║                                                              ║
    ║  🤖 AI-Powered Trading with Multi-Agent Architecture        ║
    ║  📊 Real-time Market Analysis & Risk Management             ║
    ║  💬 Interactive Agent Chat Interface                        ║
    ║  📈 Live Dashboard & Portfolio Monitoring                   ║
    ║                                                              ║
    ║  Access UI: http://localhost:8501                           ║
    ║  Press Ctrl+C to stop                                       ║
    ╚══════════════════════════════════════════════════════════════╝
    """
    )

    # Run the application
    try:
        result = asyncio.run(main())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        sys.exit(1)
