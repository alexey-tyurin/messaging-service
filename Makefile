# Makefile for Messaging Service

.PHONY: help setup install run run-bg stop restart-app app-status app-logs test clean docker-up docker-down docker-build migrate lint format

# Variables
PYTHON := python3
PIP := pip3
DOCKER_COMPOSE := docker compose
APP_NAME := messaging-service

# Default target
help:
	@echo "Available commands:"
	@echo ""
	@echo "Local Development:"
	@echo "  run          - Run the application (foreground - blocks terminal)"
	@echo "  run-bg       - Run the application in background (recommended)"
	@echo "  stop         - Stop all running services"
	@echo "  restart-app  - Restart the application in background"
	@echo "  app-status   - Check if application is running"
	@echo "  app-logs     - View application logs (for background mode)"
	@echo "  worker       - Run the background worker"
	@echo ""
	@echo "Setup & Testing:"
	@echo "  setup        - Set up the development environment"
	@echo "  install      - Install Python dependencies"
	@echo "  test         - Run tests"
	@echo "  test-flow    - Run message flow tests (Redis queue integration)"
	@echo "  lint         - Run linting"
	@echo "  format       - Format code with black"
	@echo "  migrate      - Run database migrations"
	@echo "  migration    - Create a new migration"
	@echo ""
	@echo "Docker:"
	@echo "  docker-up    - Start Docker containers"
	@echo "  docker-down  - Stop Docker containers"
	@echo "  docker-build - Build Docker images"
	@echo "  logs         - View Docker logs"
	@echo ""
	@echo "Other:"
	@echo "  clean        - Clean up generated files"

# Setup development environment
setup: install docker-up migrate
	@echo "Development environment set up successfully!"

# Install dependencies
install:
	$(PIP) install -r requirements.txt
	$(PIP) install -r requirements-dev.txt 2>/dev/null || true

# Run the application (foreground - blocks terminal)
run:
	./bin/start.sh

# Run the application in background (frees up terminal)
run-bg:
	@echo "Starting application in background..."
	@mkdir -p logs
	@nohup ./bin/start.sh > logs/app.log 2>&1 & echo $$! > .app.pid
	@sleep 3
	@if [ -f .app.pid ]; then \
		PID=$$(cat .app.pid); \
		if ps -p $$PID > /dev/null 2>&1; then \
			echo "✓ Application started successfully in background (PID: $$PID)"; \
			echo "  View logs: make app-logs"; \
			echo "  Check status: make app-status"; \
			echo "  Stop: make stop"; \
		else \
			echo "✗ Application failed to start. Check: tail logs/app.log"; \
			cat logs/app.log 2>/dev/null || echo "No log file found"; \
		fi \
	fi

# Stop all services
stop:
	./bin/stop.sh
	@rm -f .app.pid 2>/dev/null || true

# Restart the application
restart-app: stop
	@echo "Waiting 2 seconds before restart..."
	@sleep 2
	$(MAKE) run-bg

# View application logs
app-logs:
	@if [ -f logs/app.log ]; then \
		tail -f logs/app.log; \
	else \
		echo "No log file found. Start the app with: make run-bg"; \
	fi

# Check application status
app-status:
	@if [ -f .app.pid ]; then \
		PID=$$(cat .app.pid); \
		if ps -p $$PID > /dev/null 2>&1; then \
			echo "✓ Application is running (PID: $$PID)"; \
			lsof -i:8080 | grep LISTEN || true; \
		else \
			echo "✗ Application is not running"; \
			rm -f .app.pid; \
		fi \
	else \
		echo "✗ Application is not running"; \
	fi

# Run the background worker
worker:
	$(PYTHON) -m app.workers.message_processor

# Run tests
test:
	./bin/test.sh

# Run message flow tests (tests complete flow through Redis queues)
test-flow:
	./bin/test_flow.sh

# Run unit tests
test-unit:
	pytest tests/unit -v --cov=app --cov-report=html

# Run integration tests
test-integration:
	pytest tests/integration -v

# Run linting
lint:
	flake8 app tests
	mypy app

# Format code
format:
	black app tests
	isort app tests

# Run database migrations
migrate:
	alembic upgrade head

# Create a new migration
migration:
	@read -p "Enter migration message: " msg; \
	alembic revision --autogenerate -m "$$msg"

# Docker commands
docker-up:
	$(DOCKER_COMPOSE) up -d

docker-down:
	$(DOCKER_COMPOSE) down

docker-build:
	$(DOCKER_COMPOSE) build

docker-logs:
	$(DOCKER_COMPOSE) logs -f

docker-restart:
	$(DOCKER_COMPOSE) restart

# Database commands
db-shell:
	$(DOCKER_COMPOSE) exec postgres psql -U messaging_user -d messaging_service

db-reset:
	$(DOCKER_COMPOSE) exec postgres psql -U messaging_user -d messaging_service -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
	$(MAKE) migrate

# Redis commands
redis-cli:
	$(DOCKER_COMPOSE) exec redis redis-cli

# Clean up
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name ".coverage" -delete

# Development shortcuts
dev: docker-up
	$(DOCKER_COMPOSE) logs -f app

logs:
	$(DOCKER_COMPOSE) logs -f

ps:
	$(DOCKER_COMPOSE) ps

restart: docker-down docker-up

# Production commands
build-prod:
	docker build -t $(APP_NAME):latest .

run-prod:
	docker run -d \
		--name $(APP_NAME) \
		-p 8080:8080 \
		--env-file .env \
		$(APP_NAME):latest

# CI/CD commands
ci-test:
	pytest --cov=app --cov-report=xml --cov-report=term

ci-lint:
	flake8 app tests --format=junit-xml --output-file=lint-results.xml
	mypy app --junit-xml mypy-results.xml

# Performance testing
load-test:
	locust -f tests/load/locustfile.py --host=http://localhost:8080

# Documentation
docs:
	@echo "API documentation available at http://localhost:8080/docs"
	@echo "Architecture documentation in ARCHITECTURE.md"

# Health checks
health:
	curl -f http://localhost:8080/health || exit 1

ready:
	curl -f http://localhost:8080/ready || exit 1

# Monitoring
metrics:
	curl http://localhost:8080/metrics

# Quick start for development
quickstart: setup
	@echo "========================================="
	@echo "Messaging Service is ready!"
	@echo "========================================="
	@echo "API: http://localhost:8080"
	@echo "Docs: http://localhost:8080/docs"
	@echo "Prometheus: http://localhost:9090"
	@echo "Grafana: http://localhost:3000 (admin/admin)"
	@echo "========================================="
