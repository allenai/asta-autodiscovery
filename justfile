test:
  uv run pytest -m "not modal"

test-modal:
  uv run pytest -m "modal"

test-all:
  uv run pytest

lint:
  uv run ruff check

format:
  uv run ruff check --fix

type-check:
  uv run pyright

modal-deploy:
  uv run modal deploy -m autodiscovery_modal.ipython_session

sync:
  uv sync --all-packages --all-extras