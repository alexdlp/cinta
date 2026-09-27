SWIFT_PKG := swift/cintarec

# SwiftPM's default build system loses the swift-testing macro plugin on
# incremental builds with the Command Line Tools ("plugin for module
# 'TestingMacros' not found" from the second run on). Naming its directory
# explicitly makes every run find it. CI builds from clean and does not need it.
SWIFT_TESTING_PLUGINS := $(shell dirname "$$(xcrun -f swift)")/../lib/swift/host/plugins/testing

.PHONY: help build-swift test test-swift fmt

help:
	@echo "uv run cinta ...   run the CLI, e.g. uv run cinta devices"
	@echo
	@echo "make build-swift   build the screen recorder (needed once)"
	@echo "make test          run the Python tests"
	@echo "make test-swift    run the recorder's tests"
	@echo "make fmt           format and autofix"

build-swift:
	@swift build -c release --package-path $(SWIFT_PKG) 2>&1 | grep -v "search path" || true

test:
	uv run pytest

test-swift:
	@# pipefail, or the exit status would be grep's and a failing test would pass.
	@set -o pipefail; swift test --package-path $(SWIFT_PKG) \
		-Xswiftc -plugin-path -Xswiftc "$(SWIFT_TESTING_PLUGINS)" 2>&1 | grep -v "search path"

fmt:
	uv run ruff format
	uv run ruff check --fix
