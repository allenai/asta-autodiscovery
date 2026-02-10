.PHONY: test test-modal test-all lint format type-check modal-deploy sync adk-web serve-docs deploy-docs \
        build-docker-compose build-ui build-scripts-image push-scripts-image build-replay-image push-replay-image \
        build-autodiscovery-image push-autodiscovery-image deploy-autodiscovery

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
modal-deploy:
	uv run modal deploy -m autodiscovery_modal.ipython_session

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
SCRIPTS_IMAGE = us-west1-docker.pkg.dev/example-legacy-project/autodiscovery/autodiscovery-scripts
REPLAY_IMAGE = us-west1-docker.pkg.dev/example-legacy-project/autodiscovery/autodiscovery-replay
AUTODISCOVERY_IMAGE = us-west1-docker.pkg.dev/example-legacy-project/autodiscovery/autodiscovery

build-scripts-image:
	docker build \
		--platform linux/amd64 \
		-t $(SCRIPTS_IMAGE):$(IMAGE_TAG) \
		-f scripts/Dockerfile \
		.

push-scripts-image: build-scripts-image
	docker push $(SCRIPTS_IMAGE):$(IMAGE_TAG)

build-replay-image:
	docker build \
		--platform linux/amd64 \
		-t $(REPLAY_IMAGE):$(IMAGE_TAG) \
		-f packages/devtools/Dockerfile \
		.

push-replay-image: build-replay-image
	docker push $(REPLAY_IMAGE):$(IMAGE_TAG)

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
