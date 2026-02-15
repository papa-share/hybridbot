# Makefile pour le projet Chatbot Hybride
# Usage: make <command>

.PHONY: help install install-dev sync-dev run run-watch run-direct run-direct-watch test test-cov lint lint-fix format format-check typecheck deadcode check clean clean-db

help:
	@echo "Commandes disponibles:"
	@echo "  make install      - Installer le package en mode production"
	@echo "  make install-dev  - Installer le package en mode developpement (pip)"
	@echo "  make sync-dev     - Synchroniser l'environnement uv avec les deps dev (pytest, ruff, ...)"
	@echo "  make run          - Lancer l'application Chainlit (via uv)"
	@echo "  make run-watch    - Lancer avec rechargement auto (via uv)"
	@echo "  make run-direct   - Lancer sans uv (activer le venv avant: .venv/Scripts/activate)"
	@echo "  make run-direct-watch - Lancer sans uv avec rechargement auto"
	@echo "  make test         - Executer les tests (necessite: make sync-dev ou make install-dev)"
	@echo "  make test-cov     - Tests avec couverture"
	@echo "  make lint         - Verifier la qualite du code (ruff)"
	@echo "  make lint-fix     - Corriger automatiquement (ruff)"
	@echo "  make format       - Formater le code (black)"
	@echo "  make format-check - Verifier le formatage"
	@echo "  make typecheck    - Verification des types (pyright)"
	@echo "  make deadcode     - Detection code mort (vulture)"
	@echo "  make check        - Verifier lint + format + types"
	@echo "  make clean        - Nettoyer les fichiers temporaires"
	@echo "  make clean-db     - Supprimer la base SQLite"

install:
	pip install .

install-dev:
	pip install -e ".[dev]"

sync-dev:
	uv sync --extra dev

run:
	uv run chainlit run src/chatbot/app.py

run-watch:
	uv run chainlit run src/chatbot/app.py --watch

run-direct:
	chainlit run src/chatbot/app.py

run-direct-watch:
	chainlit run src/chatbot/app.py --watch

test:
	python -m pytest tests/ -v

test-cov:
	python -m pytest tests/ -v --cov=src/chatbot --cov-report=term-missing

lint:
	ruff check src/ tests/

lint-fix:
	ruff check src/ tests/ --fix

format:
	black src/ tests/

format-check:
	black --check src/ tests/

typecheck:
	pyright src/

deadcode:
	vulture src/

check: lint format-check typecheck
	@echo "Toutes les verifications passees!"

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf build/ dist/ 2>/dev/null || true
	@echo "Nettoyage termine!"

clean-db:
	rm -f chainlit.db
	@echo "Base de donnees supprimee!"
