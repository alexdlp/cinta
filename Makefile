SWIFT_PKG := swift/cintarec

.PHONY: help build-swift test fmt

help:
	@echo "uv run cinta ...   run the CLI, e.g. uv run cinta devices"
	@echo
	@echo "make build-swift   build the screen recorder (needed once)"
	@echo "make test          run the tests"
	@echo "make fmt           format and autofix"

build-swift:
	@swift build -c release --package-path $(SWIFT_PKG) 2>&1 | grep -v "search path" || true

test:
	uv run pytest

fmt:
	uv run ruff format
	uv run ruff check --fix
