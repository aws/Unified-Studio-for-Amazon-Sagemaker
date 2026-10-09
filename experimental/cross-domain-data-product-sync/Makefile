# Cross-Domain Data Product Sync: build and test entry points.

PYTHON ?= python3
LAMBDA_DIR := lambda
BUILD_DIR := build
FUNCTIONS := glue_table_sync catalog_sync_mirror dq_results_sync lineage_sync

.PHONY: help install test lint package clean verify

help:
	@echo "Targets:"
	@echo "  install   Install dev dependencies"
	@echo "  test      Run unit tests"
	@echo "  lint      Byte-compile all Lambda sources"
	@echo "  package   Build Lambda deployment zips into $(BUILD_DIR)/"
	@echo "  verify    Lint plus tests"
	@echo "  clean     Remove build artifacts"

install:
	$(PYTHON) -m pip install -r requirements-dev.txt

lint:
	$(PYTHON) -m py_compile $(LAMBDA_DIR)/*.py

test:
	$(PYTHON) -m pytest -q

verify: lint test

package: clean
	@mkdir -p $(BUILD_DIR)
	# glue_table_sync is standalone.
	@echo "Packaging glue_table_sync"
	@(cd $(LAMBDA_DIR) && zip -q -j ../$(BUILD_DIR)/glue_table_sync.zip glue_table_sync.py)
	# dq_results_sync is standalone (event-driven DQ path).
	@echo "Packaging dq_results_sync"
	@(cd $(LAMBDA_DIR) && zip -q -j ../$(BUILD_DIR)/dq_results_sync.zip dq_results_sync.py)
	# lineage_sync is standalone (event-driven lineage path).
	@echo "Packaging lineage_sync"
	@(cd $(LAMBDA_DIR) && zip -q -j ../$(BUILD_DIR)/lineage_sync.zip lineage_sync.py)
	# catalog_sync_mirror imports glue_table_sync (shared mirror_table), so it must
	# ship both modules in its deployment package.
	@echo "Packaging catalog_sync_mirror (with glue_table_sync)"
	@(cd $(LAMBDA_DIR) && zip -q -j ../$(BUILD_DIR)/catalog_sync_mirror.zip catalog_sync_mirror.py glue_table_sync.py)
	@echo "Artifacts written to $(BUILD_DIR)/"

clean:
	rm -rf $(BUILD_DIR)
	find . -name '__pycache__' -type d -prune -exec rm -rf {} +
	find . -name '*.pyc' -delete
