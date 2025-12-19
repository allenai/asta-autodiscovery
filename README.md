# Asta AutoDiscovery

> AutoDiscovery for Asta

## Setting Up

Install all required packages (including those for testing and documentation) using:

```sh
uv sync --all-packages --all-extras
```

## Running Tests

Execute the test suite with:

```sh
uv run pytest
```

## Code Coverage

Measure code coverage with:

```sh
uv run pytest --cov
```

## Linting and Formatting

Run Ruff via uv to check code style and lint errors:

```sh
uv run ruff check
```

To apply Ruff's formatter, use:

```sh
uv run ruff format
```

## Typing

Run the static type checker with 

```sh
uv run pyright
```