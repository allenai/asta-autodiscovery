test:
  uv run pytest -m "not modal"

test-modal:
  uv run pytest -m "modal"

test-all:
  uv run pytest

lint:
  uv run ruff check --fix

format:
  uv run ruff format

type-check:
  uv run pyright

modal-deploy:
  uv run modal deploy -m autodiscovery_modal.ipython_session

sync:
  uv sync --all-packages --all-extras

adk-web:
  adk web devtools --port 8000

serve-docs:
  uv run mkdocs serve

deploy-autodiscovery:
  cd packages/autodiscovery && ./scripts/rebuild_and_deploy.sh
