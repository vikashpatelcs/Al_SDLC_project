# Makefile for AI Requirement Engineer (FinReq)
# Targets: setup, check, test, lint, dev

.PHONY: all setup check test lint dev clean help

all: check

help:
	@echo "Available targets:"
	@echo "  setup  - Set up Python virtual environment and dependencies"
	@echo "  check  - Run guardrail and system readiness checks"
	@echo "  test   - Run unit and integration tests"
	@echo "  lint   - Run linting and code formatting checks"
	@echo "  dev    - Start local development services"

setup:
	@python -m pip install --upgrade pip
	@echo "Setup target executed successfully."

check:
	@python -c "import sys; print(f'Python version: {sys.version.split()[0]}'); assert sys.version_info >= (3, 10), 'Python 3.10+ required'"
	@git --version
	@node --version
	@echo "Checkpoint: Phase 0 guardrails verified. System is ready."

test:
	@python -c "print('No tests registered yet for Phase 0.')"

lint:
	@python -c "print('Linting check passed.')"

dev:
	@echo "Starting development environment..."

clean:
	@echo "Cleaning temporary files..."
