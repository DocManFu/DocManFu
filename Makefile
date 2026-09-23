FRONTEND_URL := http://localhost:5180
API_URL      := http://localhost:8100
SERVICE      ?= api

.DEFAULT_GOAL := help
.PHONY: help up down restart build rebuild logs ps shell migrate seed clean \
	open api-docs health lint format check test fe-check

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

# --- Docker ---

up: ## Start containers, run migrations, open the app
	./dev up -d
	./dev migrate
	@echo "Waiting for frontend at $(FRONTEND_URL)..."
	@for i in $$(seq 1 60); do \
		curl -sf -o /dev/null $(FRONTEND_URL) && break; \
		sleep 2; \
	done
	@$(MAKE) --no-print-directory open

down: ## Stop and remove containers
	./dev down

restart: ## Restart containers
	./dev restart -d

build: ## Build images without starting
	./dev build

rebuild: ## Full rebuild (--no-cache) and start
	./dev rebuild -d

logs: ## Follow logs (SERVICE=worker for one service)
	./dev logs $(if $(filter command line,$(origin SERVICE)),$(SERVICE))

ps: ## Show container status
	./dev ps

shell: ## Shell into a container (SERVICE=api by default)
	./dev shell $(SERVICE)

migrate: ## Run alembic migrations
	./dev migrate

seed: ## Load sample data
	./dev seed

clean: ## Stop containers and delete volumes (asks first)
	./dev clean

# --- Browser ---

open: ## Open the frontend in a browser
	@open $(FRONTEND_URL) 2>/dev/null || xdg-open $(FRONTEND_URL)

api-docs: ## Open the API Swagger docs
	@open $(API_URL)/docs 2>/dev/null || xdg-open $(API_URL)/docs

health: ## Check API + DB health
	@curl -s $(API_URL)/health; echo

# --- Code quality (local tools from requirements-dev.txt) ---

lint: ## Check Python + frontend formatting and lint
	black --check app/
	ruff check app/
	cd frontend && npx prettier --check "src/**/*.{svelte,ts,js,css,html}"

format: ## Auto-format Python + frontend
	black app/
	ruff check app/ --fix
	cd frontend && npx prettier --write "src/**/*.{svelte,ts,js,css,html}"

test: ## Run Python tests
	pytest

fe-check: ## Run svelte-check in the frontend container
	docker compose -p docmanfu -f docker-compose.dev.yml exec frontend npm run check

check: lint test ## Lint + test
