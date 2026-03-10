#!/usr/bin/env python3
"""
Safe Test Run Script for Crypto Trading Bot

This script provides a safe way to test the trading bot application
with comprehensive checks and error handling.

Usage:
    python scripts/test_run.py                  # Full test run
    python scripts/test_run.py --quick          # Quick test
    python scripts/test_run.py --check-only     # Check only, don't start app
    python scripts/test_run.py --safe-mode      # Start in safe mode
    python scripts/test_run.py --port 8502      # Custom port
"""

import argparse
import asyncio
import logging
import os
import sys
import time
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('test_run.log')
    ]
)
logger = logging.getLogger(__name__)


class TestRunner:
    """Comprehensive test runner for the crypto trading bot"""

    def __init__(self):
        self.test_results = []
        self.start_time = datetime.now()
        self.config = None
        self.port = 8501

    def log_test_result(self, test_name: str, passed: bool, message: str = ""):
        """Log test result"""
        result = {
            'test': test_name,
            'passed': passed,
            'message': message,
            'timestamp': datetime.now()
        }
        self.test_results.append(result)

        status = "✅ PASS" if passed else "❌ FAIL"
        logger.info(f"{status} {test_name}: {message}")
        print(f"{status} {test_name}: {message}")

    def check_python_version(self) -> bool:
        """Check Python version compatibility"""
        try:
            version = sys.version_info
            if version.major == 3 and version.minor >= 8:
                self.log_test_result(
                    "Python Version", True,
                    f"Python {version.major}.{version.minor}.{version.micro} (compatible)"
                )
                return True
            else:
                self.log_test_result(
                    "Python Version", False,
                    f"Python {version.major}.{version.minor}.{version.micro} (requires 3.8+)"
                )
                return False
        except Exception as e:
            self.log_test_result("Python Version", False, f"Error checking version: {e}")
            return False

    def check_dependencies(self) -> bool:
        """Check required dependencies"""
        required_packages = [
            ('streamlit', 'Streamlit'),
            ('pandas', 'Pandas'),
            ('numpy', 'NumPy'),
            ('plotly', 'Plotly'),
            ('sqlalchemy', 'SQLAlchemy'),
            ('ccxt', 'CCXT'),
            ('requests', 'Requests')
        ]

        all_present = True
        missing_packages = []

        for package, name in required_packages:
            try:
                __import__(package)
                self.log_test_result(f"Package {name}", True, "Available")
            except ImportError:
                self.log_test_result(f"Package {name}", False, "Missing")
                missing_packages.append(package)
                all_present = False

        if missing_packages:
            print(f"\n📦 Missing packages: {', '.join(missing_packages)}")
            print("Install with: pip install " + " ".join(missing_packages))

        return all_present

    def check_configuration(self) -> bool:
        """Check configuration loading"""
        try:
            from src.config.settings import Config
            self.config = Config()
            self.log_test_result("Configuration Loading", True, "Configuration loaded successfully")

            # Check critical settings
            issues = []

            if not self.config.DATABASE_URL:
                issues.append("DATABASE_URL not set")

            if not self.config.PAPER_TRADING and not self.config.BINANCE_API_KEY:
                issues.append("BINANCE_API_KEY required for live trading")

            if self.config.ALLOW_MOCK_DATA and self.config.ENVIRONMENT == 'production':
                issues.append("Mock data enabled in production")

            if issues:
                self.log_test_result("Configuration Validation", False, f"Issues: {'; '.join(issues)}")
                return False
            else:
                self.log_test_result(
                    "Configuration Validation", True,
                    f"Environment: {self.config.ENVIRONMENT}, Paper Trading: {self.config.PAPER_TRADING}"
                )
                return True

        except Exception as e:
            self.log_test_result("Configuration Loading", False, f"Error: {e}")
            return False

    def test_database_connection(self) -> bool:
        """Test database connection"""
        try:
            from src.database.connection import initialize_database, get_database_manager

            db_manager = initialize_database(self.config)
            self.log_test_result("Database Initialization", True, "Database manager created")

            # Test connection
            with db_manager.get_session() as session:
                from sqlalchemy import text
                session.execute(text("SELECT 1"))

            # Get health status
            health = db_manager.get_health_status()
            if health['status'] == 'healthy':
                self.log_test_result(
                    "Database Connection", True,
                    f"Connected (pool size: {health.get('pool_size', 'unknown')})"
                )
                return True
            else:
                self.log_test_result(
                    "Database Connection", False,
                    f"Status: {health['status']}, errors: {health.get('error_count', 0)}"
                )
                return False

        except Exception as e:
            self.log_test_result("Database Connection", False, f"Error: {e}")
            return False

    def test_binance_connection(self) -> bool:
        """Test Binance API connection"""
        try:
            from src.apis.binance_client import BinanceClient

            client = BinanceClient(self.config)
            self.log_test_result("Binance Client Creation", True, "Client initialized")

            # Test connection
            connection_test = client.test_connection()
            if connection_test.get('success'):
                response_time = connection_test.get('data', {}).get('response_time', 'unknown')
                self.log_test_result(
                    "Binance Connection", True,
                    f"Connected (response time: {response_time:.3f}s)" if isinstance(response_time, (int, float)) else "Connected"
                )
                return True
            else:
                error = connection_test.get('error', 'Unknown error')
                self.log_test_result("Binance Connection", False, f"Error: {error}")
                return False

        except Exception as e:
            self.log_test_result("Binance Connection", False, f"Error: {e}")
            return False

    def test_streamlit_import(self) -> bool:
        """Test Streamlit application import"""
        try:
            from src.ui.streamlit_app import TradingDashboard
            self.log_test_result("Streamlit App Import", True, "TradingDashboard class imported")

            # Test component imports
            try:
                from src.ui.components.dashboard import DashboardComponents
                self.log_test_result("Dashboard Components", True, "Components imported")
            except Exception as e:
                self.log_test_result("Dashboard Components", False, f"Error: {e}")
                return False

            return True

        except Exception as e:
            self.log_test_result("Streamlit App Import", False, f"Error: {e}")
            return False

    def check_port_availability(self, port: int) -> bool:
        """Check if port is available"""
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('localhost', port))
            sock.close()

            if result == 0:
                self.log_test_result(f"Port {port}", False, "Port already in use")
                return False
            else:
                self.log_test_result(f"Port {port}", True, "Port available")
                return True
        except Exception as e:
            self.log_test_result(f"Port {port}", False, f"Error checking port: {e}")
            return False

    def run_comprehensive_check(self) -> bool:
        """Run all checks"""
        print("🚀 Starting Crypto Trading Bot Test Run")
        print("=" * 50)

        checks = [
            ("Python Version", self.check_python_version),
            ("Dependencies", self.check_dependencies),
            ("Configuration", self.check_configuration),
            ("Database", self.test_database_connection),
            ("Binance API", self.test_binance_connection),
            ("Streamlit Import", self.test_streamlit_import),
            ("Port Availability", lambda: self.check_port_availability(self.port))
        ]

        passed_checks = 0
        total_checks = len(checks)

        for check_name, check_func in checks:
            print(f"\n--- {check_name} Check ---")
            try:
                if check_func():
                    passed_checks += 1
            except Exception as e:
                logger.error(f"{check_name} check failed with exception: {e}")
                self.log_test_result(check_name, False, f"Exception: {e}")

        success_rate = (passed_checks / total_checks) * 100
        print(f"\n📊 Test Results: {passed_checks}/{total_checks} checks passed ({success_rate:.1f}%)")

        return passed_checks == total_checks

    def start_streamlit_app(self, safe_mode: bool = False):
        """Start Streamlit application"""
        try:
            print(f"\n🌐 Starting Streamlit application on port {self.port}")

            # Build streamlit command
            cmd = [
                sys.executable, "-m", "streamlit", "run",
                "src/ui/streamlit_app.py",
                f"--server.port={self.port}",
                "--server.address=0.0.0.0",
                "--server.headless=false"
            ]

            if safe_mode:
                # Set safe mode environment variable
                os.environ['SAFE_MODE'] = 'true'
                print("🛡️  Running in safe mode")

            print(f"Command: {' '.join(cmd)}")
            print(f"🔗 Access the app at: http://localhost:{self.port}")
            print("Press Ctrl+C to stop the application")

            # Start the application
            process = subprocess.run(cmd, cwd=project_root)
            return process.returncode == 0

        except KeyboardInterrupt:
            print("\n⚠️  Application stopped by user")
            return True
        except Exception as e:
            print(f"❌ Failed to start application: {e}")
            logger.error(f"Failed to start Streamlit app: {e}")
            return False

    def generate_report(self) -> str:
        """Generate test report"""
        duration = datetime.now() - self.start_time
        passed_count = sum(1 for r in self.test_results if r['passed'])
        total_count = len(self.test_results)

        report = f"""
🔍 CRYPTO TRADING BOT - TEST REPORT
{'=' * 50}

Test Date: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}
Duration: {duration.total_seconds():.2f} seconds
Total Tests: {total_count}
Passed: {passed_count}
Failed: {total_count - passed_count}
Success Rate: {(passed_count / total_count * 100):.1f}%

📋 DETAILED RESULTS
{'-' * 30}
"""

        for result in self.test_results:
            status = "✅" if result['passed'] else "❌"
            report += f"{status} {result['test']}: {result['message']}\n"

        if total_count - passed_count > 0:
            report += f"\n⚠️  FAILED TESTS ({total_count - passed_count})\n{'-' * 20}\n"
            for result in self.test_results:
                if not result['passed']:
                    report += f"❌ {result['test']}: {result['message']}\n"

        report += f"\n💡 RECOMMENDATIONS\n{'-' * 20}\n"
        if passed_count == total_count:
            report += "🎉 All tests passed! System is ready for operation.\n"
        else:
            report += "⚠️  Please address the failed tests before running the application.\n"
            report += "🔧 Check the detailed results above and fix the identified issues.\n"

        return report


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Safe test runner for crypto trading bot",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('--quick', action='store_true',
                       help='Run quick checks only (skip comprehensive tests)')
    parser.add_argument('--check-only', action='store_true',
                       help='Run checks only, do not start the application')
    parser.add_argument('--safe-mode', action='store_true',
                       help='Start application in safe mode')
    parser.add_argument('--port', type=int, default=8501,
                       help='Port to run Streamlit on (default: 8501)')
    parser.add_argument('--report-file', type=str,
                       help='Save test report to file')

    args = parser.parse_args()

    # Create test runner
    runner = TestRunner()
    runner.port = args.port

    try:
        # Run checks
        if args.quick:
            print("⚡ Running quick checks...")
            success = (
                runner.check_python_version() and
                runner.check_dependencies() and
                runner.check_configuration()
            )
        else:
            success = runner.run_comprehensive_check()

        # Generate report
        report = runner.generate_report()
        print(report)

        # Save report if requested
        if args.report_file:
            with open(args.report_file, 'w') as f:
                f.write(report)
            print(f"📄 Report saved to: {args.report_file}")

        # Start application if checks passed and not check-only
        if success and not args.check_only:
            print("\n" + "=" * 50)
            if input("Start the application now? [y/N]: ").lower().strip() == 'y':
                app_success = runner.start_streamlit_app(safe_mode=args.safe_mode)
                sys.exit(0 if app_success else 1)
            else:
                print("Application start cancelled by user")
                sys.exit(0)
        elif not success:
            print("\n❌ Tests failed - please fix issues before running the application")
            sys.exit(1)
        else:
            print("\n✅ All checks passed!")
            sys.exit(0)

    except KeyboardInterrupt:
        print("\n\n⚠️  Test run interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Test run failed: {e}")
        print(f"\n💥 Test run failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
