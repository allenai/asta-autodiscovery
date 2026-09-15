.PHONY: help dev test test-modal test-all lint format type-check sync adk-web serve-docs deploy-docs \
        build-docker-compose build-ui build-scripts-image push-scripts-image update-scripts-jobs \
        build-autodiscovery-image push-autodiscovery-image update-autodiscovery-job deploy-autodiscovery \
        modal-deploy \
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
# PYTEST_ARGS forwards extra flags to pytest, e.g. `make test PYTEST_ARGS=--cov`.
# Make treats bare trailing words as goals, so `make test -- --cov` cannot work.
PYTEST_ARGS ?=

test: ## Run the main test suite (excludes Modal tests)
	uv run --all-packages pytest -m "not modal and not adc" $(PYTEST_ARGS)

test-modal: ## Run the Modal tests only
	uv run --all-packages pytest -m "modal" $(PYTEST_ARGS)

test-all: ## Run every test
	uv run --all-packages pytest $(PYTEST_ARGS)

# Code quality targets
lint: ## Run Ruff lint with autofix
	uv run ruff check --fix

format: ## Run the Ruff formatter
	uv run ruff format

type-check: ## Run pyright
	uv run pyright

# Deployment targets
deploy-autodiscovery: ## Rebuild and deploy the autodiscovery image
	cd packages/autodiscovery && ./scripts/rebuild_and_deploy.sh

modal-deploy: ## Deploy the Modal IPython session app
	uv run modal deploy -m autodiscovery_modal.ipython_session

# Setup targets
sync: ## Install all workspace packages and extras
	uv sync --all-packages --all-extras

# Local stack targets
# The `autodiscovery` service is behind compose's `jobs` profile, so it is not
# built or started by `docker compose up --build` -- only by naming it. Building
# it here is the point of this target: without it the API launches whatever
# `autodiscovery:dev` was last built, which silently runs stale job code.
dev: ## Build the job image and start the local stack
	docker compose build autodiscovery
	docker compose up --build

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

build-ui: ## Install UI deps and build the UI (CI)
	cd ui && yarn install --frozen-lockfile && yarn build

# Image build/push targets
IMAGE_TAG ?= dev
SCRIPTS_IMAGE = us-west1-docker.pkg.dev/example-gcp-project/autodiscovery/autodiscovery-scripts
AUTODISCOVERY_IMAGE = us-west1-docker.pkg.dev/example-gcp-project/autodiscovery/autodiscovery

build-scripts-image: ## Build the scripts image
	docker build \
		--platform linux/amd64 \
		-t $(SCRIPTS_IMAGE):$(IMAGE_TAG) \
		-f scripts/Dockerfile \
		.

push-scripts-image: build-scripts-image ## Build and push the scripts image
	docker push $(SCRIPTS_IMAGE):$(IMAGE_TAG)

update-scripts-jobs: ## Point the scripts Cloud Run jobs at IMAGE_TAG
	@echo "Updating Cloud Run jobs to use $(SCRIPTS_IMAGE):$(IMAGE_TAG)..."
	@if [ "$(IMAGE_TAG)" = "dev" ]; then \
		gcloud run jobs update autodiscovery-send-emails-dev \
			--image $(SCRIPTS_IMAGE):$(IMAGE_TAG) \
			--region us-west1 \
			--project example-gcp-project && \
		gcloud run jobs update autodiscovery-dataset-cleanup-dev \
			--image $(SCRIPTS_IMAGE):$(IMAGE_TAG) \
			--region us-west1 \
			--project example-gcp-project; \
	elif [ "$(IMAGE_TAG)" = "prod" ]; then \
		gcloud run jobs update autodiscovery-send-emails-prod \
			--image $(SCRIPTS_IMAGE):$(IMAGE_TAG) \
			--region us-west1 \
			--project example-gcp-project && \
		gcloud run jobs update autodiscovery-dataset-cleanup-prod \
			--image $(SCRIPTS_IMAGE):$(IMAGE_TAG) \
			--region us-west1 \
			--project example-gcp-project; \
	else \
		echo "IMAGE_TAG must be 'dev' or 'prod'"; \
		exit 1; \
	fi

build-autodiscovery-image: ## Build the autodiscovery job image (needs GITHUB_TOKEN)
	@if [ -z "$(GITHUB_TOKEN)" ]; then \
		echo "Error: GITHUB_TOKEN environment variable is required"; \
		echo "Usage: GITHUB_TOKEN=your_token make build-autodiscovery-image"; \
		exit 1; \
	fi
	@echo "$$GITHUB_TOKEN" > .github_token.tmp
	docker build \
		--platform linux/amd64 \
		--secret id=github_token,src=.github_token.tmp \
		-t $(AUTODISCOVERY_IMAGE):$(IMAGE_TAG) \
		-f packages/autodiscovery/Dockerfile \
		.
	@rm -f .github_token.tmp

push-autodiscovery-image: build-autodiscovery-image ## Build and push the autodiscovery job image
	docker push $(AUTODISCOVERY_IMAGE):$(IMAGE_TAG)

update-autodiscovery-job: ## Point the autodiscovery Cloud Run job at IMAGE_TAG
	@echo "Updating Cloud Run job to use $(AUTODISCOVERY_IMAGE):$(IMAGE_TAG)..."
	@if [ "$(IMAGE_TAG)" = "dev" ]; then \
		gcloud run jobs update autodiscovery-job-dev \
			--image $(AUTODISCOVERY_IMAGE):$(IMAGE_TAG) \
			--region us-west1 \
			--project example-gcp-project; \
	elif [ "$(IMAGE_TAG)" = "prod" ]; then \
		gcloud run jobs update autodiscovery-job-prod \
			--image $(AUTODISCOVERY_IMAGE):$(IMAGE_TAG) \
			--region us-west1 \
			--project example-gcp-project; \
	else \
		echo "IMAGE_TAG must be 'dev' or 'prod'"; \
		exit 1; \
	fi

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
