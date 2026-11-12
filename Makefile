# Makefile — quality gate shortcuts for Warframe Archives (Linux / macOS / WSL)
# On Windows use scripts/check.ps1 instead.

.PHONY: check lint compile test test-fast test-rag test-discord test-scraper

## Full quality gate (ruff + compile + all tests)
check:
	python -m ruff check
	python -m compileall -q warframe_lore
	python -m pytest -q

## Ruff lint only
lint:
	python -m ruff check

## Compile check only
compile:
	python -m compileall -q warframe_lore

## Full test suite
test:
	python -m pytest -q

## Fast subset: RAG + Discord tests only
test-fast:
	python -m pytest tests/rag/ tests/discord/ -q

## Domain-scoped test targets
test-rag:
	python -m pytest tests/rag/ -q

test-discord:
	python -m pytest tests/discord/ -q

test-scraper:
	python -m pytest tests/scraper/ -q

