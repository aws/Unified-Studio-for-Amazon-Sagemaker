# Makefile for SMUS CI/CD Pipeline CLI

.PHONY: test test-unit test-integration test-all test-coverage clean install dev-install

# Default test target - runs unit tests
test: test-unit

# Install package in development mode
dev-install:
	pip install -e .

# Install package normally
install:
	pip install .

# Run unit tests only
test-unit:
	python run_tests.py --type unit

# Run integration tests only (requires AWS credentials)
test-integration:
	@echo "Running integration tests (requires AWS credentials in current session)..."
	python run_tests.py --type integration

# Run all tests (unit + integration)
test-all: test-unit test-integration

# Run tests with coverage
test-coverage:
	python run_tests.py --html-report

# Clean build artifacts
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
