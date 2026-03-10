#!/usr/bin/env python3
"""
Setup Validation Script for Crypto Trading Bot

Comprehensive validation script to ensure the system is properly configured
for production use with live data and no mock data dependencies.

Usage:
    python scripts/validate_setup.py --full
    python scripts/validate_setup.py --quick
    python scripts/validate_setup.py --component database
    python scripts/validate_setup.py --component binance
    python scripts/validate_setup.py --production-check
"""

import argparse
import asyncio
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from src.config.settings import Config
    from src.utils.data_validation import DataValidator
    from src.utils.error_handling import error_handler
    from src.database.connection import get_database_manager, initialize_database
    from src.apis.binance_client import BinanceClient
except ImportError as e:
    print(f"Error importing required modules: {e}")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('validation.log')
    ]
)
logger = logging.getLogger(__name__)


class ValidationResult:
    """Represents the result of a validation check"""

    def __init__(self, name: str, passed: bool, message: str = "", details: Dict = None):
        self.name = name
        self.passed = passed
        self.message = message
        self.details = details or {}
        self.timestamp = datetime.utcnow()

    def __str__(self):
        status = "✅ PASS" if self.passed else "❌ FAIL"
        return f"{status} {self.name}: {self.message}"


class SetupValidator:
    """Comprehensive setup validation utilities"""

    def __init__(self):
        self.results: List[ValidationResult] = []
        self.config: Optional[Config] = None
        self.start_time = datetime.utcnow()

    def add_result(self, result: ValidationResult):
        """Add validation result"""
        self.results.append(result)
        logger.info(str(result))

    def validate_configuration(self) -> bool:
        """Validate all required configuration is present and valid"""
        logger.info("🔧 Validating configuration...")

        try:
            # Load configuration
            self.config = Config()
            self.add_result(ValidationResult(
                "Configuration Loading", True, "Configuration loaded successfully"
            ))

            # Check required environment variables
            required_vars = [
                'BINANCE_API_KEY',
                'BINANCE_SECRET_KEY',
                'DATABASE_URL'
            ]

            missing_vars = []
            for var in required_vars:
                if not os.getenv(var):
                    missing_vars.append(var)

            if missing_vars:
                self.add_result(ValidationResult(
                    "Required Environment Variables", False,
                    f"Missing: {', '.join(missing_vars)}"
                ))
                return False
            else:
                self.add_result(ValidationResult(
                    "Required Environment Variables", True,
                    "All required variables present"
                ))

            # Validate API key format
            api_key = os.getenv('BINANCE_API_KEY', '')
            if len(api_key) < 20 or not api_key.isalnum():
                self.add_result(ValidationResult(
                    "Binance API Key Format", False,
                    "API key appears to be invalid format"
                ))
            else:
                self.add_result(ValidationResult(
                    "Binance API Key Format", True,
                    "API key format looks valid"
                ))

            # Check production settings
            if self.config.ENVIRONMENT == 'production':
                if self.config.ALLOW_MOCK_DATA:
                    self.add_result(ValidationResult(
                        "Production Mock Data Check", False,
                        "Mock data is enabled in production - this must be disabled"
                    ))
                    return False
                else:
                    self.add_result(ValidationResult(
                        "Production Mock Data Check", True,
                        "Mock data is properly disabled for production"
                    ))

            return True

        except Exception as e:
            self.add_result(ValidationResult(
                "Configuration Loading", False, f"Failed to load configuration: {e}"
            ))
            return False

    def validate_database(self) -> bool:
        """Validate database connection and schema"""
        logger.info("🗄️  Validating database...")

        try:
            # Initialize database
            initialize_database(self.config)
            db_manager = get_database_manager()

            if not db_manager:
                self.add_result(ValidationResult(
                    "Database Manager", False, "Failed to create database manager"
                ))
                return False

            self.add_result(ValidationResult(
                "Database Manager", True, "Database manager created successfully"
            ))

            # Test connection
            with db_manager.get_session() as session:
                from sqlalchemy import text
                session.execute(text("SELECT 1"))

            self.add_result(ValidationResult(
                "Database Connection", True, "Database connection successful"
            ))

            # Check required tables
            expected_tables = [
                'portfolios', 'positions', 'orders', 'trading_pairs',
                'market_data', 'strategies', 'news', 'technical_indicators'
            ]

            with db_manager.get_session() as session:
                # Get existing tables (PostgreSQL specific)
                try:
                    result = session.execute(
                        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
                    )
                    existing_tables = [row[0] for row in result]
                except:
                    # Fallback for SQLite
                    result = session.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )
                    existing_tables = [row[0] for row in result]

                missing_tables = [t for t in expected_tables if t not in existing_tables]

                if missing_tables:
                    self.add_result(ValidationResult(
                        "Database Schema", False,
                        f"Missing tables: {', '.join(missing_tables)}"
                    ))
                    return False
                else:
                    self.add_result(ValidationResult(
                        "Database Schema", True,
                        f"All {len(expected_tables)} required tables present"
                    ))

            return True

        except Exception as e:
            self.add_result(ValidationResult(
                "Database Validation", False, f"Database validation failed: {e}"
            ))
            return False

    def validate_binance_api(self) -> bool:
        """Validate Binance API connectivity and permissions"""
        logger.info("🔗 Validating Binance API...")

        try:
            if not self.config:
                self.add_result(ValidationResult(
                    "Binance API Configuration", False, "Configuration not loaded"
                ))
                return False

            # Initialize Binance client
            binance_client = BinanceClient(self.config)

            # Test basic connectivity
            connection_test = binance_client.test_connection()

            if connection_test.get('status') != 'healthy':
                self.add_result(ValidationResult(
                    "Binance Connection", False,
                    f"Connection failed: {connection_test.get('message', 'Unknown error')}"
                ))
                return False
            else:
                response_time = connection_test.get('response_time', 0)
                self.add_result(ValidationResult(
                    "Binance Connection", True,
                    f"Connection successful (response time: {response_time:.3f}s)"
                ))

            # Test market data access
            try:
                markets = binance_client.get_markets()
                if markets:
                    market_count = len(markets)
                    self.add_result(ValidationResult(
                        "Market Data Access", True,
                        f"Successfully retrieved {market_count} trading pairs"
                    ))
                else:
                    self.add_result(ValidationResult(
                        "Market Data Access", False, "No market data retrieved"
                    ))
                    return False
            except Exception as e:
                self.add_result(ValidationResult(
                    "Market Data Access", False, f"Market data access failed: {e}"
                ))
                return False

            # Test account access if not paper trading
            if not self.config.PAPER_TRADING:
                try:
                    account_info = binance_client.get_account_info()
                    if account_info.get('success'):
                        self.add_result(ValidationResult(
                            "Account Access", True, "Account information retrieved successfully"
                        ))
                    else:
                        self.add_result(ValidationResult(
                            "Account Access", False,
                            f"Account access failed: {account_info.get('error', 'Unknown error')}"
                        ))
                        return False
                except Exception as e:
                    self.add_result(ValidationResult(
                        "Account Access", False, f"Account access test failed: {e}"
                    ))
                    return False
            else:
                self.add_result(ValidationResult(
                    "Account Access", True, "Paper trading mode - account access not required"
                ))

            return True

        except Exception as e:
            self.add_result(ValidationResult(
                "Binance API Validation", False, f"Binance API validation failed: {e}"
            ))
            return False

    def validate_news_apis(self) -> bool:
        """Validate news API sources accessibility"""
        logger.info("📰 Validating news APIs...")

        try:
            if not self.config:
                return False

            # Check news API configuration
            news_keys = self.config.NEWS_API_KEYS
            configured_sources = [k for k, v in news_keys.items() if v]

            if not configured_sources:
                self.add_result(ValidationResult(
                    "News API Configuration", False,
                    "No news API keys configured - news analysis will be unavailable"
                ))
                return False
            else:
                self.add_result(ValidationResult(
                    "News API Configuration", True,
                    f"Configured sources: {', '.join(configured_sources)}"
                ))

            # Test each configured news source
            working_sources = []
            failed_sources = []

            for source, api_key in news_keys.items():
                if not api_key:
                    continue

                try:
                    # Basic validation - would need actual news client implementation
                    if len(api_key) > 10:  # Basic key format check
                        working_sources.append(source)
                        self.add_result(ValidationResult(
                            f"News API - {source}", True, "API key format valid"
                        ))
                    else:
                        failed_sources.append(source)
                        self.add_result(ValidationResult(
                            f"News API - {source}", False, "Invalid API key format"
                        ))
                except Exception as e:
                    failed_sources.append(source)
                    self.add_result(ValidationResult(
                        f"News API - {source}", False, f"Validation failed: {e}"
                    ))

            return len(working_sources) > 0

        except Exception as e:
            self.add_result(ValidationResult(
                "News API Validation", False, f"News API validation failed: {e}"
            ))
            return False

    def validate_components(self) -> bool:
        """Validate all trading components initialization"""
        logger.info("🔧 Validating component initialization...")

        try:
            # Test agent imports
            agent_modules = [
                ('Market Analyzer', 'src.agents.market_analyzer', 'MarketAnalyzerAgent'),
                ('Risk Manager', 'src.agents.risk_manager', 'RiskManagerAgent'),
                ('Trading Executor', 'src.agents.trading_executor', 'TradingExecutorAgent'),
            ]

            for name, module_path, class_name in agent_modules:
                try:
                    module = __import__(module_path, fromlist=[class_name])
                    agent_class = getattr(module, class_name)
                    self.add_result(ValidationResult(
                        f"Agent Import - {name}", True, f"{class_name} imported successfully"
                    ))
                except ImportError as e:
                    self.add_result(ValidationResult(
                        f"Agent Import - {name}", False, f"Import failed: {e}"
                    ))
                    return False
                except AttributeError as e:
                    self.add_result(ValidationResult(
                        f"Agent Import - {name}", False, f"Class not found: {e}"
                    ))
                    return False

            # Test state manager
            try:
                from src.graph.state_manager import initialize_state_manager, get_state_manager
                initialize_state_manager()
                state_manager = get_state_manager()

                if state_manager:
                    self.add_result(ValidationResult(
                        "State Manager", True, "State manager initialized successfully"
                    ))
                else:
                    self.add_result(ValidationResult(
                        "State Manager", False, "State manager initialization returned None"
                    ))
                    return False
            except Exception as e:
                self.add_result(ValidationResult(
                    "State Manager", False, f"State manager initialization failed: {e}"
                ))
                return False

            return True

        except Exception as e:
            self.add_result(ValidationResult(
                "Component Validation", False, f"Component validation failed: {e}"
            ))
            return False

    def validate_security(self) -> bool:
        """Validate security configurations"""
        logger.info("🔒 Validating security configuration...")

        try:
            if not self.config:
                return False

            # Check API key storage (should not be in code)
            api_key_file_check = self.check_for_hardcoded_keys()
            if api_key_file_check:
                self.add_result(ValidationResult(
                    "Hardcoded API Keys", False,
                    f"Found potential hardcoded keys in: {', '.join(api_key_file_check)}"
                ))
            else:
                self.add_result(ValidationResult(
                    "Hardcoded API Keys", True, "No hardcoded API keys detected"
                ))

            # Check rate limiting configuration
            if self.config.API_RATE_LIMIT_BINANCE < 100:
                self.add_result(ValidationResult(
                    "Rate Limiting", False, "Binance rate limit seems too low"
                ))
            else:
                self.add_result(ValidationResult(
                    "Rate Limiting", True, "Rate limiting configured appropriately"
                ))

            # Check data validation strictness
            if self.config.DATA_VALIDATION_STRICTNESS == 'low' and self.config.ENVIRONMENT == 'production':
                self.add_result(ValidationResult(
                    "Data Validation Strictness", False,
                    "Low validation strictness not recommended for production"
                ))
            else:
                self.add_result(ValidationResult(
                    "Data Validation Strictness", True,
                    f"Validation strictness: {self.config.DATA_VALIDATION_STRICTNESS}"
                ))

            return True

        except Exception as e:
            self.add_result(ValidationResult(
                "Security Validation", False, f"Security validation failed: {e}"
            ))
            return False

    def check_for_hardcoded_keys(self) -> List[str]:
        """Check for hardcoded API keys in source files"""
        suspicious_files = []

        # Patterns that might indicate hardcoded keys
        key_patterns = [
            r'api[_-]?key\s*=\s*["\'][a-zA-Z0-9]{20,}["\']',
            r'secret[_-]?key\s*=\s*["\'][a-zA-Z0-9]{20,}["\']',
            r'BINANCE[_-]API[_-]KEY\s*=\s*["\'][^"\']+["\']'
        ]

        try:
            import re

            for pattern in key_patterns:
                regex = re.compile(pattern, re.IGNORECASE)

                # Check Python files
                for py_file in project_root.rglob("*.py"):
                    if py_file.name == __file__.split('/')[-1]:  # Skip this file
                        continue

                    try:
                        with open(py_file, 'r', encoding='utf-8') as f:
                            content = f.read()
                            if regex.search(content):
                                suspicious_files.append(str(py_file.relative_to(project_root)))
                    except:
                        continue
        except:
            pass

        return suspicious_files

    def validate_performance(self) -> bool:
        """Validate system performance configuration"""
        logger.info("⚡ Validating performance configuration...")

        try:
            if not self.config:
                return False

            # Check cache TTL settings
            if self.config.DATA_CACHE_TTL < 10:
                self.add_result(ValidationResult(
                    "Cache TTL", False, "Cache TTL too low - may cause excessive API calls"
                ))
            elif self.config.DATA_CACHE_TTL > 300:
                self.add_result(ValidationResult(
                    "Cache TTL", False, "Cache TTL very high - data may be stale"
                ))
            else:
                self.add_result(ValidationResult(
                    "Cache TTL", True, f"Cache TTL appropriately set: {self.config.DATA_CACHE_TTL}s"
                ))

            # Check timeout settings
            timeout_checks = [
                ('API_TIMEOUT_BINANCE', self.config.API_TIMEOUT_BINANCE, 5, 30),
                ('API_TIMEOUT_NEWS', self.config.API_TIMEOUT_NEWS, 5, 60),
                ('API_TIMEOUT_DATABASE', self.config.API_TIMEOUT_DATABASE, 1, 10)
            ]

            for name, value, min_val, max_val in timeout_checks:
                if value < min_val:
                    self.add_result(ValidationResult(
                        f"Timeout - {name}", False, f"Timeout too low: {value}s (min: {min_val}s)"
                    ))
                elif value > max_val:
                    self.add_result(ValidationResult(
                        f"Timeout - {name}", False, f"Timeout too high: {value}s (max: {max_val}s)"
                    ))
                else:
                    self.add_result(ValidationResult(
                        f"Timeout - {name}", True, f"Timeout appropriately set: {value}s"
                    ))

            # Check batch sizes
            if self.config.BATCH_SIZE_ORDERS > 500:
                self.add_result(ValidationResult(
                    "Batch Size Orders", False, "Order batch size may be too large"
                ))
            else:
                self.add_result(ValidationResult(
                    "Batch Size Orders", True, f"Order batch size: {self.config.BATCH_SIZE_ORDERS}"
                ))

            return True

        except Exception as e:
            self.add_result(ValidationResult(
                "Performance Validation", False, f"Performance validation failed: {e}"
            ))
            return False

    def validate_production_readiness(self) -> bool:
        """Validate system is ready for production deployment"""
        logger.info("🚀 Validating production readiness...")

        try:
            if not self.config:
                return False

            production_issues = []

            # Environment check
            if self.config.ENVIRONMENT != 'production':
                production_issues.append("ENVIRONMENT is not set to 'production'")

            # Debug mode check
            if self.config.DEBUG_MODE:
                production_issues.append("DEBUG_MODE is enabled")

            # Mock data check
            if self.config.ALLOW_MOCK_DATA:
                production_issues.append("ALLOW_MOCK_DATA is enabled")

            # Security headers check
            if not self.config.SECURITY_HEADERS_ENABLED:
                production_issues.append("SECURITY_HEADERS_ENABLED is disabled")

            # Maintenance mode check
            if self.config.MAINTENANCE_MODE:
                production_issues.append("MAINTENANCE_MODE is enabled")

            if production_issues:
                self.add_result(ValidationResult(
                    "Production Readiness", False,
                    f"Issues found: {'; '.join(production_issues)}"
                ))
                return False
            else:
                self.add_result(ValidationResult(
                    "Production Readiness", True,
                    "System appears ready for production deployment"
                ))
                return True

        except Exception as e:
            self.add_result(ValidationResult(
                "Production Readiness", False, f"Production readiness check failed: {e}"
            ))
            return False

    def run_full_validation(self) -> bool:
        """Run complete validation suite"""
        logger.info("🔍 Starting full system validation...")

        validation_steps = [
            ("Configuration", self.validate_configuration),
            ("Database", self.validate_database),
            ("Binance API", self.validate_binance_api),
            ("News APIs", self.validate_news_apis),
            ("Components", self.validate_components),
            ("Security", self.validate_security),
            ("Performance", self.validate_performance),
            ("Production Readiness", self.validate_production_readiness)
        ]

        all_passed = True

        for step_name, validation_func in validation_steps:
            logger.info(f"\n--- {step_name} Validation ---")
            try:
                step_result = validation_func()
                if not step_result:
                    all_passed = False
                    logger.error(f"{step_name} validation failed")
                else:
                    logger.info(f"{step_name} validation passed")
            except Exception as e:
                logger.error(f"{step_name} validation error: {e}")
                all_passed = False

        return all_passed

    def run_quick_validation(self) -> bool:
        """Run essential validation checks only"""
        logger.info("⚡ Running quick validation...")

        essential_steps = [
            ("Configuration", self.validate_configuration),
            ("Database", self.validate_database),
            ("Binance API", self.validate_binance_api)
        ]

        all_passed = True

        for step_name, validation_func in essential_steps:
            try:
                if not validation_func():
                    all_passed = False
            except Exception as e:
                logger.error(f"{step_name} validation error: {e}")
                all_passed = False

        return all_passed

    def run_component_validation(self, component: str) -> bool:
        """Run validation for specific component"""
        logger.info(f"🔧 Validating component: {component}")

        component_validators = {
            'database': self.validate_database,
            'binance': self.validate_binance_api,
            'news': self.validate_news_apis,
            'components': self.validate_components,
            'security': self.validate_security,
            'performance': self.validate_performance,
            'production': self.validate_production_readiness
        }

        if component not in component_validators:
            logger.error(f"Unknown component: {component}")
            return False

        try:
            return component_validators[component]()
        except Exception as e:
            logger.error(f"Component validation error: {e}")
            return False

    def generate_report(self) -> str:
        """Generate validation report"""
        duration = datetime.utcnow() - self.start_time

        passed_count = sum(1 for r in self.results if r.passed)
        total_count = len(self.results)

        report = f"""
=== CRYPTO TRADING BOT VALIDATION REPORT ===

Validation Date: {self.start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}
Duration: {duration.total_seconds():.2f} seconds
Total Checks: {total_count}
Passed: {passed_count}
Failed: {total_count - passed_count}
Success Rate: {(passed_count / total_count * 100):.1f}%

=== DETAILED RESULTS ===
"""

        for result in self.results:
            status = "✅" if result.passed else "❌"
            report += f"\n{status} {result.name}: {result.message}"

        if total_count - passed_count > 0:
            report += f"\n\n=== FAILED CHECKS ({total_count - passed_count}) ==="
            for result in self.results:
                if not result.passed:
                    report += f"\n❌ {result.name}: {result.message}"

        report += "\n\n=== RECOMMENDATIONS ==="
        if total_count == passed_count:
            report += "\n🎉 All validations passed! System is ready for deployment."
        else:
            report += "\n⚠️  Please address the failed checks before deployment."
            report += "\n📋 Review the failed checks above and fix the identified issues."
            report += "\n🔄 Re-run validation after making changes."

        return report


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Validate crypto trading bot setup",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/validate_setup.py --full
  python scripts/validate_setup.py --quick
  python scripts/validate_setup.py --component database
  python scripts/validate_setup.py --production-check
        """
    )

    parser.add_argument('--full', action='store_true',
                       help='Run complete validation suite')
    parser.add_argument('--quick', action='store_true',
                       help='Run essential validation checks only')
    parser.add_argument('--component', type=str,
                       choices=['database', 'binance', 'news', 'components', 'security', 'performance', 'production'],
                       help='Validate specific component')
    parser.add_argument('--production-check', action='store_true',
                       help='Run production readiness check only')
    parser.add_argument('--report-file', type=str,
                       help='Save report to file')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose output')

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Default to quick validation if no specific option provided
    if not any([args.full, args.quick, args.component, args.production_check]):
        args.quick = True

    validator = SetupValidator()

    try:
        print("🚀 Crypto Trading Bot - Setup Validation")
        print("=" * 50)

        success = False

        if args.full:
            success = validator.run_full_validation()
        elif args.quick:
            success = validator.run_quick_validation()
        elif args.component:
            success = validator.run_component_validation(args.component)
        elif args.production_check:
            validator.validate_configuration()  # Load config first
            success = validator.validate_production_readiness()

        # Generate and display report
        report = validator.generate_report()
        print(report)

        # Save report to file if requested
        if args.report_file:
            with open(args.report_file, 'w') as f:
                f.write(report)
            print(f"\n📄 Report saved to: {args.report_file}")

        # Exit with appropriate code
        if success:
            print("\n✅ Validation completed successfully!")
            sys.exit(0)
        else:
            print("\n❌ Validation failed - please address the issues above")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\n⚠️ Validation interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Validation failed with error: {e}")
        print(f"\n💥 Validation failed with error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
