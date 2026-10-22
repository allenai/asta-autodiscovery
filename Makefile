.PHONY: help dev dev-host check-model test lint lint-fix format type-check sync report-viewer adk-web \
        test-report-viewer serve-docs deploy-docs build-docker-compose build-ui modal-deploy \
        show-version set-version push-version-tag

# Self-documenting help. The README covers the common targets in prose; this
# lists all of them, sourced from the `## ` comment on each target line.
help: ## List all targets
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| sort \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-28s\033[0m %s\n", $$1, $$2}'

# Test targets
# --all-packages installs every workspace member (the root project has no
# dependencies, so a plain `uv run` would omit each package's own deps, e.g.
# IPython / asta_sandbox). This makes the targets work from a cold environment,
# so CI can invoke `make test` directly.
#
# api/ is not a workspace member -- its image installs api/requirements.txt -- so
# those requirements are layered on with --with-requirements; without them the
# api/tests modules skip on a missing Flask. pytest runs as `python -m pytest`
# because the `pytest` entry point would use the base venv's interpreter and
# miss the layered packages.
#
# PYTEST_ARGS forwards extra flags to pytest, e.g. `make test PYTEST_ARGS=--cov`.
# Make treats bare trailing words as goals, so `make test -- --cov` cannot work.
PYTEST_ARGS ?=

test: ## Run the test suite
	uv run --all-packages --with-requirements api/requirements.txt python -m pytest $(PYTEST_ARGS)

# Code quality targets
lint: ## Run Ruff lint + format checks (no changes)
	uv run ruff check
	uv run ruff format --check

lint-fix: ## Apply Ruff autofixes and formatting
	uv run ruff check --fix
	uv run ruff format

format: ## Run the Ruff formatter
	uv run ruff format

type-check: ## Run pyright
	uv run pyright

# Deployment targets
modal-deploy: ## Deploy the Modal IPython session app
	uv run modal deploy -m autodiscovery_modal.ipython_session

# Setup targets
sync: ## Install all workspace packages and extras
	uv sync --all-packages --all-extras

# The HTML report every run writes (autodiscovery/report.py) is the web UI's run
# view, built from ui/ into package data of asta-autodiscovery. It is not checked
# in: the job image and the PyPI build make their own, and a source checkout needs
# this before `auto-discovery` can write a viewable report. A file target, so it
# rebuilds only when the UI's sources or dependencies change.
REPORT_VIEWER := packages/autodiscovery/src/autodiscovery/report_viewer/index.html
REPORT_VIEWER_SOURCES := $(shell find ui/src -type f) ui/report.html ui/vite.config.ts \
	ui/vite.report.config.ts ui/package.json ui/yarn.lock

report-viewer: $(REPORT_VIEWER) ## Build the HTML report's run view (needs Node.js and Yarn)

$(REPORT_VIEWER): $(REPORT_VIEWER_SOURCES)
	cd ui && yarn install --frozen-lockfile && yarn build:report

# Opens a synthetic run's report from disk in Chromium (ui/e2e-report). report.py
# needs only the standard library, so this runs it from source without installing
# the engine's dependencies. Needs Playwright's Chromium once:
# `cd ui && yarn playwright install chromium`.
test-report-viewer: $(REPORT_VIEWER) ## Smoke-test the HTML report in a browser
	out=$$(mktemp -d) && \
	PYTHONPATH=packages/autodiscovery/src uv run --no-project --python 3.13 \
		python ui/e2e-report/make_report.py "$$out" && \
	cd ui && REPORT_DIR="$$out/output/report" yarn test:report

# Local stack targets
# The `autodiscovery` service is behind compose's `jobs` profile, so it is not
# built or started by `docker compose up --build` -- only by naming it. Building
# it here is the point of this target: without it the API launches whatever
# `autodiscovery:dev` was last built, which silently runs stale job code.
#
# There is no default model, so `make dev` refuses to start until one is chosen
# -- otherwise the stack comes up only to fail on the first run. The variable is
# accepted from the shell or from .env (the file compose reads); the API repeats
# the check at startup, including the chosen provider's own variables.
check-model: ## Fail unless a model is chosen (AUTODISCOVERY_MODEL in the shell or .env)
	@if [ -z "$$AUTODISCOVERY_MODEL" ] \
	    && ! grep -qE '^AUTODISCOVERY_MODEL=[^[:space:]#]' .env 2>/dev/null; then \
		echo "error: no model chosen. Set AUTODISCOVERY_MODEL=<provider>/<model> in .env" >&2; \
		echo "       (for example openai/gpt-5.4-mini) plus that provider's variables." >&2; \
		echo "       See docs/quickstart.md." >&2; \
		exit 1; \
	fi

dev: check-model ## Build the job image and start the local stack
	docker compose build autodiscovery
	docker compose up --build

# The same stack with no Docker: the API under gunicorn and the UI under Vite, both
# on this host, with Vite forwarding /api to the API (nginx's job under compose).
# Runs are launched as host subprocesses (JOB_BACKEND=process) that read the store
# in place, which is single-user by design: auth is off and both servers listen on
# localhost only. .env is read as compose reads it (shell values win), except that
# STORAGE_DIR comes from the shell, defaulting to ./data like compose's. Ctrl-C
# stops both servers; a run in progress keeps going, and the API reports its
# outcome once restarted.
DEV_HOST_API_PORT ?= 8000
DEV_HOST_UI_PORT ?= 3000

dev-host: check-model $(REPORT_VIEWER) ## Start the local stack on this host, without Docker
	cd ui && yarn install --frozen-lockfile
	trap 'kill 0' EXIT; \
	(cd ui && API_PROXY_TARGET=http://127.0.0.1:$(DEV_HOST_API_PORT) \
		yarn dev --host 127.0.0.1 --port $(DEV_HOST_UI_PORT)) & \
	AUTH_PROVIDER=none JOB_BACKEND=process STORAGE_BACKEND=local \
	STORAGE_DIR="$${STORAGE_DIR:-$(CURDIR)/data}" \
	uv run --all-packages --with-requirements api/requirements.txt \
		$(if $(wildcard .env),--env-file .env) \
		gunicorn --chdir api --workers 2 --timeout 0 --reload \
		--bind 127.0.0.1:$(DEV_HOST_API_PORT) 'app:create_app()'

# Development server targets
adk-web: ## Serve Google ADK Web against packages/devtools/adk
	uv run adk web packages/devtools/adk --port 8000

# Documentation targets
serve-docs: ## Serve the docs locally
	uv run mkdocs serve

deploy-docs: ## Publish the docs to GitHub Pages
	uv run mkdocs gh-deploy --force

# Docker build targets (CI)
build-docker-compose: ## Build every compose service (CI)
	GOOGLE_APPLICATION_CREDENTIALS=/dev/null \
	GCS_BUCKET="" \
	GCP_PROJECT="" \
	GOOGLE_ACCESS_KEY_ID="" \
	GOOGLE_ACCESS_KEY_SECRET="" \
	docker compose build

build-ui: ## Install UI deps and build the UI and the report's run view (CI)
	cd ui && yarn install --frozen-lockfile && yarn build && yarn build:report

# Show current version
show-version: ## Print the current workspace version
	@uv run python scripts/manage-version.py show

# Set version in all workspace pyproject.toml files (requires VERSION=x.y.z)
set-version: ## Set the version everywhere (requires VERSION=x.y.z)
	@uv run python scripts/manage-version.py set $(VERSION)

# Create and push git tag using current version
push-version-tag: ## Tag the current version and push the tag
	@if ! uv run python scripts/manage-version.py check; then \
		exit 1; \
	fi; \
	VERSION=$$(uv run python scripts/manage-version.py show); \
	git tag v$$VERSION && \
	git push origin v$$VERSION && \
	echo "Pushed tag v$$VERSION"
