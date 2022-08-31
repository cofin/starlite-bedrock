.DEFAULT_GOAL:=help
.ONESHELL:
ENV_PREFIX=$(shell python3 -c "if __import__('pathlib').Path('.venv/bin/pip').exists(): print('.venv/bin/')")
USING_POETRY=$(shell grep "tool.poetry" pyproject.toml && echo "yes")
USING_DOCKER=$(shell grep "USE_DOCKER=true" .env && echo "yes")
PYTHON_PACKAGES=$(shell poetry export -f requirements.txt  --without-hashes |cut -d'=' -f1 |cut -d ' ' -f1)
GRPC_PYTHON_BUILD_SYSTEM_ZLIB=true

.EXPORT_ALL_VARIABLES:

ifndef VERBOSE
.SILENT:
endif


REPO_INFO ?= $(shell git config --get remote.origin.url)
COMMIT_SHA ?= git-$(shell git rev-parse --short HEAD)

help:  ## Display this help
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n"} /^[a-zA-Z0-9_-]+:.*?##/ { printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)


.PHONY: upgrade-dependencies
upgrade-dependencies:          ## Upgrade all dependencies to the latest stable versions
	@if [ "$(USING_POETRY)" ]; then poetry update; fi
	@echo "Python Dependencies Updated"

###############
# lint & test #
###############
format-source: ## Format source code
	@echo 'Formatting and cleaning source...'
	./scripts/format-source-code.sh

.PHONY: install
install:          ## Install the project in dev mode.
	@if ! poetry --version > /dev/null; then echo 'poetry is required, install from https://python-poetry.org/'; exit 1; fi
	@if [ "$(USING_POETRY)" ]; then poetry config virtualenvs.in-project true && poetry config virtualenvs.create false && python3 -m venv --copies .venv && source .venv/bin/activate && .venv/bin/pip install -U wheel setuptools cython pip && poetry install && exit; fi
