# Dilla AI Makefile
# Comprehensive build and management system

.PHONY: help build install clean test run stop dev prod docker health check-deps setup-env

# Colors for output
RED := \033[0;31m
GREEN := \033[0;32m
YELLOW := \033[1;33m
BLUE := \033[0;34m
NC := \033[0m # No Color

# Project paths
PROJECT_ROOT := $(shell pwd)
BACKEND_DIR := $(PROJECT_ROOT)/backend
FRONTEND_DIR := $(PROJECT_ROOT)/frontend
VENV := $(BACKEND_DIR)/venv

# Python
PYTHON := python3
PIP := $(VENV)/bin/pip
UVICORN := $(VENV)/bin/uvicorn

# Default target
help:
	@echo "$(BLUE)╔════════════════════════════════════════╗$(NC)"
	@echo "$(BLUE)║     Dilla AI - Build Management        ║$(NC)"
	@echo "$(BLUE)╚════════════════════════════════════════╝$(NC)"
	@echo ""
	@echo "$(YELLOW)Available commands:$(NC)"
	@echo "  $(GREEN)make setup$(NC)      - Complete initial setup"
	@echo "  $(GREEN)make build$(NC)      - Build entire project"
	@echo "  $(GREEN)make install$(NC)    - Install all dependencies"
	@echo "  $(GREEN)make run$(NC)        - Run both frontend and backend"
	@echo "  $(GREEN)make dev$(NC)        - Run in development mode"
	@echo "  $(GREEN)make test$(NC)       - Run all tests"
	@echo "  $(GREEN)make clean$(NC)      - Clean build artifacts"
	@echo "  $(GREEN)make docker$(NC)     - Build and run with Docker"
	@echo "  $(GREEN)make health$(NC)     - Check system health"
	@echo ""
	@echo "$(YELLOW)Individual services:$(NC)"
	@echo "  $(GREEN)make backend$(NC)    - Run backend only"
	@echo "  $(GREEN)make frontend$(NC)   - Run frontend only"
	@echo "  $(GREEN)make redis$(NC)      - Start Redis server"
	@echo ""
	@echo "$(YELLOW)Database:$(NC)"
	@echo "  $(GREEN)make db-setup$(NC)   - Setup database"
	@echo "  $(GREEN)make db-migrate$(NC) - Run migrations"
	@echo "  $(GREEN)make db-reset$(NC)   - Reset database"
	@echo ""
	@echo "$(YELLOW)Testing:$(NC)"
	@echo "  $(GREEN)make test-backend$(NC)  - Test backend"
	@echo "  $(GREEN)make test-frontend$(NC) - Test frontend"
	@echo "  $(GREEN)make test-integration$(NC) - Integration tests"
	@echo ""

# Complete setup
setup: check-deps setup-env install db-setup
	@echo "$(GREEN)✓ Setup complete!$(NC)"
	@echo "$(YELLOW)Next: Update .env files with your API keys$(NC)"

# Check dependencies
check-deps:
	@echo "$(BLUE)Checking dependencies...$(NC)"
	@command -v python3 >/dev/null 2>&1 || { echo "$(RED)Python 3 required$(NC)"; exit 1; }
	@command -v node >/dev/null 2>&1 || { echo "$(RED)Node.js required$(NC)"; exit 1; }
	@command -v npm >/dev/null 2>&1 || { echo "$(RED)npm required$(NC)"; exit 1; }
	@echo "$(GREEN)✓ All dependencies found$(NC)"

# Setup environment files
setup-env:
	@echo "$(BLUE)Setting up environment files...$(NC)"
	@./build.sh
	@echo "$(GREEN)✓ Environment files created$(NC)"

# Install all dependencies
install: install-backend install-frontend install-root
	@echo "$(GREEN)✓ All dependencies installed$(NC)"

# Install backend dependencies
install-backend:
	@echo "$(BLUE)Installing backend dependencies...$(NC)"
	@cd $(BACKEND_DIR) && \
		$(PYTHON) -m venv venv && \
		$(PIP) install --upgrade pip && \
		$(PIP) install -r requirements.txt && \
		$(PIP) install numpy pandas scipy scikit-learn
	@echo "$(GREEN)✓ Backend dependencies installed$(NC)"

# Install frontend dependencies
install-frontend:
	@echo "$(BLUE)Installing frontend dependencies...$(NC)"
	@cd $(FRONTEND_DIR) && npm install
	@echo "$(GREEN)✓ Frontend dependencies installed$(NC)"

# Install root dependencies
install-root:
	@echo "$(BLUE)Installing root dependencies...$(NC)"
	@if [ -f "package.json" ]; then npm install; fi
	@echo "$(GREEN)✓ Root dependencies installed$(NC)"

# Build project
build: build-frontend
	@echo "$(GREEN)✓ Build complete$(NC)"

# Build frontend
build-frontend:
	@echo "$(BLUE)Building frontend...$(NC)"
	@cd $(FRONTEND_DIR) && npm run build
	@echo "$(GREEN)✓ Frontend built$(NC)"

# Run everything
run:
	@echo "$(BLUE)Starting all services...$(NC)"
	@./start_all.sh

# Run in development mode
dev:
	@echo "$(BLUE)Starting development servers...$(NC)"
	@make -j2 backend-dev frontend-dev

# Run backend
backend:
	@echo "$(BLUE)Starting backend...$(NC)"
	@cd $(BACKEND_DIR) && \
		. venv/bin/activate && \
		uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run backend in dev mode
backend-dev:
	@cd $(BACKEND_DIR) && \
		. venv/bin/activate && \
		uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run frontend
frontend:
	@echo "$(BLUE)Starting frontend...$(NC)"
	@cd $(FRONTEND_DIR) && npm run dev -- -p 3001

# Run frontend in dev mode
frontend-dev:
	@cd $(FRONTEND_DIR) && npm run dev -- -p 3001

# Start Redis
redis:
	@echo "$(BLUE)Starting Redis...$(NC)"
	@redis-server

# Database setup
db-setup:
	@echo "$(BLUE)Setting up database...$(NC)"
	@cd $(BACKEND_DIR) && \
		if [ -f "setup_database.sql" ]; then \
			echo "$(YELLOW)Run setup_database.sql in your database$(NC)"; \
		fi
	@echo "$(GREEN)✓ Database setup complete$(NC)"

# Run migrations
db-migrate:
	@echo "$(BLUE)Running database migrations...$(NC)"
	@cd $(BACKEND_DIR) && \
		. venv/bin/activate && \
		alembic upgrade head || echo "$(YELLOW)Alembic not configured$(NC)"

# Reset database
db-reset:
	@echo "$(RED)⚠️  This will delete all data! Press Ctrl+C to cancel...$(NC)"
	@sleep 3
	@make db-setup
	@make db-migrate
	@echo "$(GREEN)✓ Database reset complete$(NC)"

# Run tests
test: test-backend test-frontend test-integration
	@echo "$(GREEN)✓ All tests complete$(NC)"

# Test backend
test-backend:
	@echo "$(BLUE)Testing backend...$(NC)"
	@cd $(BACKEND_DIR) && \
		. venv/bin/activate && \
		pytest tests/ -v || echo "$(YELLOW)No tests found$(NC)"

# Test frontend
test-frontend:
	@echo "$(BLUE)Testing frontend...$(NC)"
	@cd $(FRONTEND_DIR) && npm test || echo "$(YELLOW)No tests configured$(NC)"

# Integration tests
test-integration:
	@echo "$(BLUE)Running integration tests...$(NC)"
	@node test_enhanced_analytics.js || echo "$(YELLOW)Servers must be running$(NC)"

# Clean build artifacts
clean:
	@echo "$(BLUE)Cleaning build artifacts...$(NC)"
	@rm -rf $(FRONTEND_DIR)/.next
	@rm -rf $(FRONTEND_DIR)/node_modules
	@rm -rf $(BACKEND_DIR)/venv
	@rm -rf $(BACKEND_DIR)/__pycache__
	@rm -rf $(BACKEND_DIR)/**/__pycache__
	@rm -rf $(BACKEND_DIR)/**/**/__pycache__
	@find . -type f -name "*.pyc" -delete
	@find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@echo "$(GREEN)✓ Clean complete$(NC)"

# Docker build and run
docker:
	@echo "$(BLUE)Building and starting Docker containers...$(NC)"
	@docker-compose up --build

# Docker build only
docker-build:
	@echo "$(BLUE)Building Docker images...$(NC)"
	@docker-compose build

# Docker run only
docker-run:
	@echo "$(BLUE)Starting Docker containers...$(NC)"
	@docker-compose up

# Docker stop
docker-stop:
	@echo "$(BLUE)Stopping Docker containers...$(NC)"
	@docker-compose down

# Docker clean
docker-clean:
	@echo "$(BLUE)Cleaning Docker resources...$(NC)"
	@docker-compose down -v
	@docker system prune -f

# Health check
health:
	@echo "$(BLUE)Checking system health...$(NC)"
	@echo -n "Backend: "
	@curl -s http://localhost:8000/health >/dev/null 2>&1 && \
		echo "$(GREEN)✓ Healthy$(NC)" || echo "$(RED)✗ Not running$(NC)"
	@echo -n "Frontend: "
	@curl -s http://localhost:3001 >/dev/null 2>&1 && \
		echo "$(GREEN)✓ Healthy$(NC)" || echo "$(RED)✗ Not running$(NC)"
	@echo -n "Redis: "
	@redis-cli ping >/dev/null 2>&1 && \
		echo "$(GREEN)✓ Connected$(NC)" || echo "$(YELLOW)⚠ Not running (optional)$(NC)"

# Validate configuration
validate:
	@echo "$(BLUE)Validating configuration...$(NC)"
	@cd $(BACKEND_DIR) && \
		. venv/bin/activate && \
		python -c "from app.main import app; print('✓ Backend valid')" || \
		echo "$(RED)✗ Backend validation failed$(NC)"
	@cd $(FRONTEND_DIR) && \
		npm run lint || echo "$(YELLOW)⚠ Linting issues found$(NC)"
	@echo "$(GREEN)✓ Validation complete$(NC)"

# Show logs
logs:
	@echo "$(BLUE)Showing logs...$(NC)"
	@tail -f $(BACKEND_DIR)/server.log 2>/dev/null || \
		echo "$(YELLOW)No log file found$(NC)"

# Backend logs
logs-backend:
	@docker-compose logs -f backend 2>/dev/null || \
		tail -f $(BACKEND_DIR)/server.log 2>/dev/null || \
		echo "$(YELLOW)No logs available$(NC)"

# Frontend logs
logs-frontend:
	@docker-compose logs -f frontend 2>/dev/null || \
		echo "$(YELLOW)Check terminal running frontend$(NC)"

# Format code
format:
	@echo "$(BLUE)Formatting code...$(NC)"
	@cd $(BACKEND_DIR) && \
		. venv/bin/activate && \
		black app/ || echo "$(YELLOW)Black not installed$(NC)"
	@cd $(FRONTEND_DIR) && \
		npm run format || echo "$(YELLOW)Formatter not configured$(NC)"
	@echo "$(GREEN)✓ Formatting complete$(NC)"

# Lint code
lint:
	@echo "$(BLUE)Linting code...$(NC)"
	@cd $(BACKEND_DIR) && \
		. venv/bin/activate && \
		pylint app/ || echo "$(YELLOW)Pylint not installed$(NC)"
	@cd $(FRONTEND_DIR) && \
		npm run lint || echo "$(YELLOW)Linter not configured$(NC)"
	@echo "$(GREEN)✓ Linting complete$(NC)"

# Update dependencies
update:
	@echo "$(BLUE)Updating dependencies...$(NC)"
	@cd $(BACKEND_DIR) && \
		. venv/bin/activate && \
		pip install --upgrade -r requirements.txt
	@cd $(FRONTEND_DIR) && npm update
	@echo "$(GREEN)✓ Dependencies updated$(NC)"

# Production build
prod:
	@echo "$(BLUE)Building for production...$(NC)"
	@make clean
	@make install
	@cd $(FRONTEND_DIR) && npm run build
	@echo "$(GREEN)✓ Production build complete$(NC)"

# Deploy (placeholder)
deploy:
	@echo "$(BLUE)Deploying to production...$(NC)"
	@echo "$(YELLOW)Configure your deployment strategy$(NC)"
	@echo "Options:"
	@echo "  - Vercel for frontend"
	@echo "  - Railway/Render for backend"
	@echo "  - Docker Swarm/Kubernetes"

# Show project stats
stats:
	@echo "$(BLUE)Project Statistics:$(NC)"
	@echo -n "Backend Python files: "
	@find $(BACKEND_DIR) -name "*.py" | wc -l
	@echo -n "Frontend TypeScript files: "
	@find $(FRONTEND_DIR) -name "*.ts" -o -name "*.tsx" | wc -l
	@echo -n "Total lines of code: "
	@find . -name "*.py" -o -name "*.ts" -o -name "*.tsx" | xargs wc -l | tail -1 | awk '{print $$1}'
	@echo -n "API endpoints: "
	@grep -r "router\." $(BACKEND_DIR)/app/api/endpoints/ | wc -l
	@echo -n "React components: "
	@find $(FRONTEND_DIR) -name "*.tsx" | wc -l

# Quick start for development
quick-start: check-deps
	@echo "$(BLUE)Quick starting development environment...$(NC)"
	@make install
	@echo "$(YELLOW)Remember to update .env files with your API keys!$(NC)"
	@make dev

.DEFAULT_GOAL := help