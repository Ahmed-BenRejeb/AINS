# Makefile — Sentinel
# Single source of truth for all commands.
# Run `make help` to see all available targets.

.PHONY: help setup env dev test test-core test-uc1 test-uc2 test-uc3 test-e2e \
        lint format typecheck check check-docs seed eval eval-report \
        deploy-cf deploy-forge deploy-remote tunnel langfuse \
        clean logs status

# ─── Config ──────────────────────────────────────────────────────────────────

PYTHON := python3
UV     := uv
NPM    := npm
PNPM   := pnpm

# OTel GenAI experimental conventions (required)
export OTEL_SEMCONV_STABILITY_OPT_IN := gen_ai_latest_experimental

# Load .env if it exists
ifneq (,$(wildcard .env))
  include .env
  export
endif

# ─── Help ────────────────────────────────────────────────────────────────────

help: ## Show this help message
	@echo ""
	@echo "  Sentinel — AI Agent Reliability Platform"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""

# ─── Setup ───────────────────────────────────────────────────────────────────

setup: ## Install all dependencies (Python + Node)
	@echo "→ Installing Python dependencies..."
	$(UV) sync --all-packages
	@echo "→ Installing Node dependencies..."
	$(PNPM) install
	@echo "→ Installing Forge CLI..."
	$(NPM) install -g @forge/cli
	@echo "→ Installing Wrangler (Cloudflare)..."
	$(NPM) install -g wrangler
	@echo "✓ Setup complete. Run 'make env' next."

env: ## Copy .env.example to .env (run once)
	@if [ -f .env ]; then \
	  echo "⚠️  .env already exists. Delete it first if you want a fresh copy."; \
	else \
	  cp .env.example .env; \
	  echo "✓ .env created. Fill in your values before running anything."; \
	fi

# ─── Development ─────────────────────────────────────────────────────────────

dev: ## Start all local development services
	@echo "→ Starting development services..."
	@$(MAKE) -j3 _dev-tunnel _dev-eval-api _dev-remote-api

_dev-tunnel:
	cloudflared tunnel run sentinel

_dev-eval-api:
	cd packages/eval-engine && $(UV) run uvicorn api:app --reload --port 8000

_dev-remote-api:
	cd packages/atlassian-remote && $(UV) run uvicorn api:app --reload --port 8080

tunnel: ## Start Cloudflare Tunnel only
	cloudflared tunnel run sentinel

langfuse: ## Open Langfuse UI in browser
	@echo "→ Opening Langfuse at $(LANGFUSE_HOST)"
	open $(LANGFUSE_HOST) 2>/dev/null || xdg-open $(LANGFUSE_HOST)

# ─── Testing ─────────────────────────────────────────────────────────────────

test: ## Run ALL tests across all packages
	@echo "→ Running all tests..."
	$(UV) run pytest packages/ tests/ -v --tb=short
	@echo "→ Running TypeScript tests..."
	$(PNPM) --filter atlassian-agent test
	$(PNPM) --filter dashboard test

test-core: ## Run packages/trace-core tests only
	$(UV) run pytest packages/trace-core/tests/ -v --tb=short

test-uc1: ## Run packages/eval-engine tests only
	$(UV) run pytest packages/eval-engine/tests/ -v --tb=short --cov=packages/eval-engine/src --cov-report=term-missing

test-uc2: ## Run packages/flight-recorder tests only
	$(UV) run pytest packages/flight-recorder/tests/ -v --tb=short --cov=packages/flight-recorder/src --cov-report=term-missing

test-uc3: ## Run packages/atlassian-remote + atlassian-agent tests only
	$(UV) run pytest packages/atlassian-remote/tests/ -v --tb=short
	$(PNPM) --filter atlassian-agent test

test-e2e: ## Run end-to-end integration tests (requires dev services running)
	@echo "⚠️  E2E tests require all services running. Run 'make dev' in another terminal first."
	$(UV) run pytest tests/e2e/ -v --tb=short -m "e2e"

# ─── Code Quality ─────────────────────────────────────────────────────────────

lint: ## Run ruff (Python) + eslint (TypeScript) across all packages
	@echo "→ Linting Python..."
	$(UV) run ruff check packages/ scripts/
	@echo "→ Linting TypeScript..."
	$(PNPM) --filter atlassian-agent lint
	$(PNPM) --filter dashboard lint

format: ## Auto-format all code (black + isort for Python, prettier for TS)
	@echo "→ Formatting Python..."
	$(UV) run black packages/ scripts/
	$(UV) run isort packages/ scripts/
	@echo "→ Formatting TypeScript..."
	$(PNPM) --filter atlassian-agent format
	$(PNPM) --filter dashboard format

typecheck: ## Run mypy (Python) + tsc --noEmit (TypeScript)
	@echo "→ Type checking Python (per package)..."
	@# Each package keeps api.py / tests/conftest.py at its root; a single
	@# recursive `mypy packages/` would see duplicate module names. Check each
	@# workspace package separately so module roots stay unique.
	@for pkg in trace-core flight-recorder eval-engine atlassian-remote; do \
	  echo "  → mypy packages/$$pkg"; \
	  $(UV) run mypy packages/$$pkg --ignore-missing-imports || exit 1; \
	done
	@echo "→ Type checking TypeScript..."
	$(PNPM) --filter atlassian-agent typecheck
	$(PNPM) --filter dashboard typecheck

check-docs: ## Verify .env.example + docs haven't drifted from the code
	@$(UV) run python scripts/check_docs.py

check: check-docs lint typecheck ## Run doc-drift + lint + typecheck (run before every commit)
	@echo "✓ All checks passed."

# ─── Data & Evaluation ───────────────────────────────────────────────────────

seed: ## Seed Atlassian dev site with 100 synthetic incidents + 20 runbooks
	@echo "→ Seeding Atlassian dev site..."
	@echo "   Site: $(ATLASSIAN_SITE)"
	$(UV) run python scripts/seed_atlassian.py
	@echo "✓ Seeding complete."

seed-xqdrant: ## Embed AO incidents + SENT runbooks (BGE-768) and load into xqdrant
	@echo "→ Seeding xqdrant from Jira AO + Confluence SENT..."
	$(UV) run python scripts/seed_xqdrant.py
	@echo "✓ xqdrant seeding complete."

eval: ## Run the eval suite — outputs pass^k report to stdout + docs/eval_report.md
	@echo "→ Running eval suite (k=8 trials)..."
	$(UV) run python scripts/run_synthetic_eval.py --k 8 --output docs/eval_report.md
	@echo "✓ Eval report written to docs/eval_report.md"

eval-report: eval ## Generate and open the evaluation report
	open docs/eval_report.md 2>/dev/null || xdg-open docs/eval_report.md

# ─── Deployment ──────────────────────────────────────────────────────────────

deploy-cf: ## Deploy Cloudflare Workers + run D1 migrations
	@echo "→ Running D1 migrations..."
	wrangler d1 migrations apply sentinel-traces --env production
	@echo "→ Deploying Cloudflare Workers..."
	wrangler deploy --config infra/cloudflare/wrangler.toml --env production
	@echo "✓ Cloudflare deployment complete."

deploy-forge: ## Deploy Forge app to Atlassian dev environment
	@echo "→ Deploying Forge app..."
	cd packages/atlassian-agent && forge deploy --environment development
	@echo "→ Installing app on dev site..."
	cd packages/atlassian-agent && forge install --environment development --site $(ATLASSIAN_SITE)
	@echo "✓ Forge deployment complete."

deploy-remote: ## Deploy Forge Remote backend to Azure VM (git pull + restart systemd unit)
	@echo "→ Deploying atlassian-remote to Azure VM..."
	# The services run from the repo checkout at /home/<user>/AINS via the
	# sentinel-{eval,remote,flight} systemd units, so deploy = pull + sync + restart.
	ssh $(AZURE_VM_USER)@$(AZURE_VM_HOST) \
	  "cd /home/$(AZURE_VM_USER)/AINS && \
	   git pull --ff-only && \
	   /home/$(AZURE_VM_USER)/.local/bin/uv sync --all-packages && \
	   sudo systemctl restart sentinel-remote"
	@echo "✓ Forge Remote deployment complete."

# ─── Utilities ───────────────────────────────────────────────────────────────

clean: ## Remove build artifacts, __pycache__, .next, dist
	@echo "→ Cleaning build artifacts..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache"   -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache"   -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "dist"          -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".next"         -exec rm -rf {} + 2>/dev/null || true
	@echo "✓ Clean complete."

logs: ## Tail logs from all services (requires tmux or multiple terminals)
	@echo "→ Tailing logs... (Ctrl-C to stop)"
	tail -f /var/log/sentinel/*.log 2>/dev/null || \
	  journalctl -f -u sentinel-eval -u sentinel-remote 2>/dev/null || \
	  echo "No log files found. Are the services running?"

status: ## Show status of all services + Cloudflare resources
	@echo ""
	@echo "=== Sentinel Status ==="
	@echo ""
	@echo "--- Cloudflare ---"
	wrangler d1 list 2>/dev/null | grep sentinel || echo "  D1: not configured"
	wrangler r2 bucket list 2>/dev/null | grep sentinel || echo "  R2: not configured"
	wrangler vectorize list 2>/dev/null | grep sentinel || echo "  Vectorize: not configured"
	@echo ""
	@echo "--- Atlassian ---"
	@curl -s -u "$(ATLASSIAN_EMAIL):$(ATLASSIAN_API_TOKEN)" \
	  "$(ATLASSIAN_SITE)/rest/api/3/myself" 2>/dev/null | \
	  python3 -c "import sys,json; d=json.load(sys.stdin); print(f'  Authenticated as: {d[\"displayName\"]}')" || \
	  echo "  Atlassian: not configured or unreachable"
	@echo ""
	@echo "--- Langfuse ---"
	@curl -s "$(LANGFUSE_HOST)/api/public/health" 2>/dev/null | \
	  python3 -c "import sys,json; d=json.load(sys.stdin); print(f'  Langfuse: {d.get(\"status\", \"unknown\")}')" || \
	  echo "  Langfuse: not reachable (is the Azure VM running?)"
	@echo ""
