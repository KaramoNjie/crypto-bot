"""
Test runner script for the crypto trading bot.
Provides different test execution modes and configurations.
"""

import asyncio
import sys
import subprocess
from pathlib import Path
from typing import List, Optional

import click
import pytest


@click.group()
def cli():
    """Crypto Trading Bot Test Runner"""
    pass


@cli.command()
@click.option('--coverage', is_flag=True, help='Run with coverage reporting')
@click.option('--verbose', '-v', is_flag=True, help='Verbose output')
@click.option('--parallel', '-p', is_flag=True, help='Run tests in parallel')
@click.option('--markers', '-m', help='Only run tests with specific markers')
@click.option('--exclude-slow', is_flag=True, help='Exclude slow tests')
def unit(coverage: bool, verbose: bool, parallel: bool, markers: Optional[str], exclude_slow: bool):
    """Run unit tests only."""
    args = _build_pytest_args(
        test_path="tests/unit/",
        coverage=coverage,
        verbose=verbose,
        parallel=parallel,
        markers=markers,
        exclude_slow=exclude_slow
    )

    click.echo("🧪 Running unit tests...")
    result = subprocess.run(["python", "-m", "pytest"] + args)
    sys.exit(result.returncode)


@cli.command()
@click.option('--coverage', is_flag=True, help='Run with coverage reporting')
@click.option('--verbose', '-v', is_flag=True, help='Verbose output')
@click.option('--markers', '-m', help='Only run tests with specific markers')
def integration(coverage: bool, verbose: bool, markers: Optional[str]):
    """Run integration tests only."""
    args = _build_pytest_args(
        test_path="tests/integration/",
        coverage=coverage,
        verbose=verbose,
        parallel=False,  # Integration tests shouldn't run in parallel
        markers=markers,
        exclude_slow=False
    )

    click.echo("🔗 Running integration tests...")
    result = subprocess.run(["python", "-m", "pytest"] + args)
    sys.exit(result.returncode)


@cli.command()
@click.option('--coverage', is_flag=True, help='Run with coverage reporting')
@click.option('--verbose', '-v', is_flag=True, help='Verbose output')
@click.option('--parallel', '-p', is_flag=True, help='Run tests in parallel')
@click.option('--markers', '-m', help='Only run tests with specific markers')
@click.option('--exclude-slow', is_flag=True, help='Exclude slow tests')
@click.option('--fail-fast', '-x', is_flag=True, help='Stop on first failure')
def all(coverage: bool, verbose: bool, parallel: bool, markers: Optional[str],
        exclude_slow: bool, fail_fast: bool):
    """Run all tests."""
    args = _build_pytest_args(
        test_path="tests/",
        coverage=coverage,
        verbose=verbose,
        parallel=parallel,
        markers=markers,
        exclude_slow=exclude_slow,
        fail_fast=fail_fast
    )

    click.echo("🚀 Running all tests...")
    result = subprocess.run(["python", "-m", "pytest"] + args)
    sys.exit(result.returncode)


@cli.command()
@click.option('--min-coverage', default=80, help='Minimum coverage percentage required')
def coverage(min_coverage: int):
    """Run tests with coverage analysis."""
    args = [
        "tests/",
        "--cov=src/",
        "--cov-report=html:htmlcov",
        "--cov-report=term-missing",
        "--cov-report=xml",
        f"--cov-fail-under={min_coverage}",
        "--cov-branch"
    ]

    click.echo(f"📊 Running tests with coverage analysis (min {min_coverage}%)...")
    result = subprocess.run(["python", "-m", "pytest"] + args)

    if result.returncode == 0:
        click.echo(f"✅ Coverage requirements met (>={min_coverage}%)")
        click.echo("📈 Coverage report: htmlcov/index.html")
    else:
        click.echo(f"❌ Coverage below {min_coverage}%")

    sys.exit(result.returncode)


@cli.command()
@click.argument('test_file')
@click.option('--verbose', '-v', is_flag=True, help='Verbose output')
@click.option('--debug', is_flag=True, help='Enable debug mode')
def single(test_file: str, verbose: bool, debug: bool):
    """Run a single test file."""
    args = [test_file]

    if verbose:
        args.extend(["-v", "-s"])

    if debug:
        args.extend(["--pdb", "--capture=no"])

    click.echo(f"🎯 Running single test: {test_file}")
    result = subprocess.run(["python", "-m", "pytest"] + args)
    sys.exit(result.returncode)


@cli.command()
@click.option('--output', '-o', default='benchmark_results.json', help='Output file for results')
def benchmark(output: str):
    """Run performance benchmarks."""
    args = [
        "tests/",
        "-m", "benchmark",
        "--benchmark-json", output,
        "--benchmark-only"
    ]

    click.echo("⚡ Running performance benchmarks...")
    result = subprocess.run(["python", "-m", "pytest"] + args)

    if result.returncode == 0:
        click.echo(f"📊 Benchmark results saved to: {output}")

    sys.exit(result.returncode)


@cli.command()
def lint():
    """Run code quality checks."""
    click.echo("🔍 Running code quality checks...")

    # Run flake8
    click.echo("Running flake8...")
    flake8_result = subprocess.run([
        "flake8", "src/", "tests/",
        "--max-line-length=88",
        "--ignore=E203,W503,E501",
        "--statistics"
    ])

    # Run mypy
    click.echo("Running mypy...")
    mypy_result = subprocess.run([
        "mypy", "src/",
        "--ignore-missing-imports",
        "--strict-optional"
    ])

    # Run black check
    click.echo("Running black check...")
    black_result = subprocess.run([
        "black", "--check", "--diff", "src/", "tests/"
    ])

    # Run isort check
    click.echo("Running isort check...")
    isort_result = subprocess.run([
        "isort", "--check-only", "--diff", "src/", "tests/"
    ])

    # Overall result
    if all(r.returncode == 0 for r in [flake8_result, mypy_result, black_result, isort_result]):
        click.echo("✅ All code quality checks passed!")
        sys.exit(0)
    else:
        click.echo("❌ Some code quality checks failed!")
        sys.exit(1)


@cli.command()
def format():
    """Format code using black and isort."""
    click.echo("🎨 Formatting code...")

    # Run black
    click.echo("Running black...")
    subprocess.run(["black", "src/", "tests/"])

    # Run isort
    click.echo("Running isort...")
    subprocess.run(["isort", "src/", "tests/"])

    click.echo("✅ Code formatting completed!")


@cli.command()
def clean():
    """Clean up test artifacts."""
    click.echo("🧹 Cleaning up test artifacts...")

    # Remove common test artifacts
    artifacts = [
        ".pytest_cache",
        "__pycache__",
        "*.pyc",
        ".coverage",
        "htmlcov",
        "coverage.xml",
        ".tox",
        "*.egg-info"
    ]

    for pattern in artifacts:
        subprocess.run(["find", ".", "-name", pattern, "-exec", "rm", "-rf", "{}", "+"])

    click.echo("✅ Cleanup completed!")


def _build_pytest_args(
    test_path: str,
    coverage: bool = False,
    verbose: bool = False,
    parallel: bool = False,
    markers: Optional[str] = None,
    exclude_slow: bool = False,
    fail_fast: bool = False
) -> List[str]:
    """Build pytest arguments based on options."""
    args = [test_path]

    if coverage:
        args.extend([
            "--cov=src/",
            "--cov-report=term-missing",
            "--cov-report=html:htmlcov"
        ])

    if verbose:
        args.extend(["-v", "-s"])

    if parallel:
        args.extend(["-n", "auto"])

    if markers:
        args.extend(["-m", markers])

    if exclude_slow:
        args.extend(["-m", "not slow"])

    if fail_fast:
        args.append("-x")

    # Always use asyncio mode for async tests
    args.append("--asyncio-mode=auto")

    # Show local variables on failure
    args.append("-l")

    return args


if __name__ == "__main__":
    cli()
