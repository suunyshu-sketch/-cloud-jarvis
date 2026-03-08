# ═══════════════════════════════════════════════════════════
#  J.A.R.V.I.S — Developer Commands
# ═══════════════════════════════════════════════════════════

.PHONY: dev test seed migrate install help

help:
	@echo "JARVIS Developer Commands"
	@echo "  make install   Install Python dependencies"
	@echo "  make dev       Run local development server"
	@echo "  make seed      Seed family users into database (run once)"
	@echo "  make migrate   Apply SQL migrations only"
	@echo "  make test      Run all unit tests"
	@echo "  make test-v    Run tests with verbose output"

install:
	pip install -r requirements.txt

dev:
	uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

seed:
	python -m backend.db.seed

migrate:
	python -c "import asyncio; from backend.db.seed import run_migrations, main as seed_main; import asyncio; \
	from backend import config; from backend.db.connection import init_pool; config.validate(); \
	asyncio.run(init_pool()); from backend.db.seed import run_migrations; asyncio.run(run_migrations())"

test:
	pytest tests/ -q

test-v:
	pytest tests/ -v --tb=short
