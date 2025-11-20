# Makefile for Messaging Service

.PHONY: help setup install run stop restart test clean docker-up docker-down docker-build migrate lint format

# Variables
PYTHON := python3
PIP := pip3
DOCKER_COMPOSE := docker compose
APP_NAME := messaging-service

# Default target
help:
	@echo "Available commands:"
	@echo "  setup        - Set up the development environment"
	@echo "  install      - Install Python dependencies"
	@echo "  run          - Run the application locally"
	@echo "  stop         - Stop all running services"
	@echo "  restart      - Restart the application"
	@echo "  worker       - Run the background worker"
	@echo "  test         - Run tests"
	@echo "  lint         - Run linting"
	@echo "  format       - Format code with black"
	@echo "  migrate      - Run database migrations"
	@echo "  migration    - Create a new migration"
	@echo "  docker-up    - Start Docker containers"
	@echo "  docker-down  - Stop Docker containers"
	@echo "  docker-build - Build Docker images"
	@echo "  docker-logs  - View Docker logs"
	@echo "  clean        - Clean up generated files"

# Setup development environment
setup: install docker-up migrate
	@echo "Development environment set up successfully!"

# Install dependencies
install:
	$(PIP) install -r requirements.txt
	$(PIP) install -r requirements-dev.txt 2>/dev/null || true

# Run the application
run:
	./bin/start.sh

# Stop all services
stop:
	./bin/stop.sh

# Restart the application
restart: stop
	@echo "Waiting 2 seconds before restart..."
	@sleep 2
	$(MAKE) run

# Run the background worker
worker:
	$(PYTHON) -m app.workers.message_processor

# Run tests
test:
	./bin/test.sh

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
		-p 8000:8000 \
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
	locust -f tests/load/locustfile.py --host=http://localhost:8000

# Documentation
docs:
	@echo "API documentation available at http://localhost:8000/docs"
	@echo "Architecture documentation in ARCHITECTURE.md"

# Health checks
health:
	curl -f http://localhost:8000/health || exit 1

ready:
	curl -f http://localhost:8000/ready || exit 1

# Monitoring
metrics:
	curl http://localhost:8000/metrics

# Quick start for development
quickstart: setup
	@echo "========================================="
	@echo "Messaging Service is ready!"
	@echo "========================================="
	@echo "API: http://localhost:8000"
	@echo "Docs: http://localhost:8000/docs"
	@echo "Prometheus: http://localhost:9090"
	@echo "Grafana: http://localhost:3000 (admin/admin)"
	@echo "========================================="
