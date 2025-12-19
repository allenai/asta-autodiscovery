# General Guidance

- Assume backwards compatibility is not required unless explicitly stated.
- Add docstrings to all public methods and packages
- Add comments to non-trivial private methods explaining their intent when its not obvious from the method name.
- Use the `adk-docs` MCP server, if you need to access the Google ADK documentation.

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