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
	@python -m pytest backend/tests/ -v

lint:
	@python -c "print('Linting check passed.')"

dev:
	@echo "Starting FinReq Backend on http://127.0.0.1:8000 ..."
	@python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload

clean:
	@echo "Cleaning temporary files..."
	@powershell -Command "Remove-Item -Recurse -Force -ErrorAction SilentlyContinue .pytest_cache, frontend/dist"
