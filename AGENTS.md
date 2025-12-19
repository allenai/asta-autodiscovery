# General Guidance

- Assume backwards compatibility is not required unless explicitly stated.
- Always use the `adk-docs` MCP server to verify the correct syntax for Google ADK agents and tools.
- Documentation for packages provided by this project is in `docs/`

# Repository Actions

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

To apply Ruff's formatter use:

```sh
uv run ruff format
```

## Typing

Run the static type checker with:

```sh
uv run pyright
```