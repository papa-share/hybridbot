UV ?= uv

.PHONY: help install install-dev run run-watch test test-cov lint lint-fix format format-check typecheck deadcode check clean db-up db-init db-down

help:
	@echo "Commandes disponibles:"
	@echo "  make install-dev  - uv sync (deps + dev)"
	@echo "  make run          - Lancer Chainlit"
	@echo "  make run-watch    - Chainlit avec rechargement auto"
	@echo "  make db-up        - PostgreSQL local (docker compose)"
	@echo "  make db-init      - Creer le schema Chainlit"
	@echo "  make db-down      - Arreter PostgreSQL"
	@echo "  make test         - Tests"
	@echo "  make test-cov     - Tests avec couverture"
	@echo "  make lint         - ruff check"
	@echo "  make lint-fix     - ruff --fix"
	@echo "  make format       - black"
	@echo "  make format-check - black --check"
	@echo "  make typecheck    - pyright"
	@echo "  make deadcode     - vulture"
	@echo "  make check        - lint + format + tests"
	@echo "  make clean        - Fichiers temporaires"

install install-dev:
	$(UV) sync --extra dev

run:
	$(UV) run python -m chainlit run src/chatbot/app.py

run-watch:
	$(UV) run python -m chainlit run src/chatbot/app.py --watch

db-up:
	docker compose up -d postgres

db-init: db-up
	$(UV) run python scripts/init_db.py

db-down:
	docker compose down

test:
	$(UV) run python -m pytest tests/ -v

test-cov:
	$(UV) run python -m pytest tests/ -v --cov=src/chatbot --cov-report=term-missing

lint:
	$(UV) run python -m ruff check src/ tests/

lint-fix:
	$(UV) run python -m ruff check src/ tests/ --fix

format:
	$(UV) run python -m black src/ tests/

format-check:
	$(UV) run python -m black --check src/ tests/

typecheck:
	$(UV) run python -m pyright src/

deadcode:
	$(UV) run python -m vulture src/

check: lint format-check test
	@echo "OK"

clean:
	$(UV) run python -c "import pathlib, shutil; \
[shutil.rmtree(p, ignore_errors=True) for p in ('build', 'dist', '.pytest_cache', '.ruff_cache', '.mypy_cache') if pathlib.Path(p).exists()]; \
[shutil.rmtree(p, ignore_errors=True) for p in pathlib.Path('.').rglob('__pycache__')]; \
[shutil.rmtree(p, ignore_errors=True) for p in pathlib.Path('.').rglob('*.egg-info')]; \
[p.unlink(missing_ok=True) for p in pathlib.Path('.').rglob('*.pyc')]; \
[shutil.rmtree(p, ignore_errors=True) for p in pathlib.Path('.').glob('pytest-cache-files-*') if p.is_dir()]"
