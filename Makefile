# No [build-system] yet (DESIGN.md 7.2): the package is not installed into the
# venv, so src/ has to be on the PYTHONPATH to run it.
PY := PYTHONPATH=src uv run

.PHONY: run test fmt

run:
	$(PY) python -m cinta $(ARGS)

test:
	$(PY) pytest

fmt:
	uv run ruff format
	uv run ruff check --fix
