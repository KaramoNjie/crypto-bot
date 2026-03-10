# Makefile for Crypto Trading Bot

.PHONY: help install test lint format clean run docker-build docker-run

help:
	@echo "Available commands:"
	@echo "  make install       - Install dependencies"
	@echo "  make test         - Run tests"
	@echo "  make lint         - Run linting"
	@echo "  make format       - Format code"
	@echo "  make clean        - Clean up generated files"
	@echo "  make run          - Run the application"
	@echo "  make docker-build - Build Docker image"
	@echo "  make docker-run   - Run Docker container"

install:
	pip install -r requirements.txt
	pip install -r requirements-dev.txt
	pre-commit install

test:
	pytest tests/ -v --cov=src --cov-report=term-missing

test-unit:
	pytest tests/unit/ -v

test-integration:
	pytest tests/integration/ -v

test-performance:
	pytest tests/performance/ -v --benchmark-only

lint:
	flake8 src tests
	mypy src
	bandit -r src/
	safety check

format:
	black src tests
	isort src tests

clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf build dist .coverage htmlcov .pytest_cache
	rm -rf logs/*.log

run:
	PYTHONPATH=. .venv/bin/python -m streamlit run src/ui/main_app.py

run-debug:
	PYTHONPATH=. LOG_LEVEL=DEBUG .venv/bin/python -m streamlit run src/ui/main_app.py

docker-build:
	docker-compose -f infrastructure/docker/docker-compose.yml build

docker-run:
	docker-compose -f infrastructure/docker/docker-compose.yml up

docker-down:
	docker-compose -f infrastructure/docker/docker-compose.yml down

db-init:
	python scripts/setup_database.py

db-migrate:
	alembic upgrade head

db-rollback:
	alembic downgrade -1

backtest:
	python scripts/backtest.py

monitor:
	docker-compose -f infrastructure/docker/docker-compose.yml up prometheus grafana
