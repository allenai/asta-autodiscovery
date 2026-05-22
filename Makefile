.PHONY: test test-modal test-all lint format type-check sync adk-web serve-docs deploy-docs \
        build-docker-compose build-ui build-scripts-image push-scripts-image update-scripts-jobs \
        build-autodiscovery-image push-autodiscovery-image update-autodiscovery-job deploy-autodiscovery \
        show-version set-version push-version-tag

# Test targets
test:
	uv run pytest -m "not modal and not adc"

test-modal:
	uv run pytest -m "modal"

test-all:
	uv run pytest

# Code quality targets
lint:
	uv run ruff check --fix

format:
	uv run ruff format

type-check:
	uv run pyright

# Deployment targets
deploy-autodiscovery:
	cd packages/autodiscovery && ./scripts/rebuild_and_deploy.sh

# Setup targets
sync:
	uv sync --all-packages --all-extras

# Development server targets
adk-web:
	uv run adk web packages/devtools/adk --port 8000

# Documentation targets
serve-docs:
	uv run mkdocs serve

deploy-docs:
	uv run mkdocs gh-deploy --force

# Docker build targets (CI)
build-docker-compose:
	GOOGLE_APPLICATION_CREDENTIALS=/dev/null \
	GCS_BUCKET="" \
	GCP_PROJECT="" \
	GOOGLE_ACCESS_KEY_ID="" \
	GOOGLE_ACCESS_KEY_SECRET="" \
	docker compose build

build-ui:
	cd ui && yarn install --frozen-lockfile && yarn build

# Image build/push targets
IMAGE_TAG ?= dev
SCRIPTS_IMAGE = us-west1-docker.pkg.dev/example-gcp-project/autodiscovery/autodiscovery-scripts
AUTODISCOVERY_IMAGE = us-west1-docker.pkg.dev/example-gcp-project/autodiscovery/autodiscovery

build-scripts-image:
	docker build \
		--platform linux/amd64 \
		-t $(SCRIPTS_IMAGE):$(IMAGE_TAG) \
		-f scripts/Dockerfile \
		.

push-scripts-image: build-scripts-image
	docker push $(SCRIPTS_IMAGE):$(IMAGE_TAG)

update-scripts-jobs:
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

build-autodiscovery-image:
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

push-autodiscovery-image: build-autodiscovery-image
	docker push $(AUTODISCOVERY_IMAGE):$(IMAGE_TAG)

update-autodiscovery-job:
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
show-version:
	@uv run python scripts/manage-version.py show

# Set version in all workspace pyproject.toml files (requires VERSION=x.y.z)
set-version:
	@uv run python scripts/manage-version.py set $(VERSION)

# Create and push git tag using current version
push-version-tag:
	@if ! uv run python scripts/manage-version.py check; then \
		exit 1; \
	fi; \
	VERSION=$$(uv run python scripts/manage-version.py show); \
	git tag v$$VERSION && \
	git push origin v$$VERSION && \
	echo "Pushed tag v$$VERSION"
