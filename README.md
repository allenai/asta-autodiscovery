# Asta AutoDiscovery

> AutoDiscovery for Asta

## Setting Up

Install all required packages (including those for testing and documentation) using:

```sh
just sync
```

## Running Tests

Execute the test suites with:

```sh
just test           # Run main test suite. Excludes Modal Tests
just test-modal     # Run Modal tests only
just test-all       # Run all tests

just test -- --cov  # Run main tests and report coverage
```

## Linting and Formatting

Run Ruff via uv to check code style and lint errors:

```sh
just lint
```

To apply Ruff's formatter, use:

```sh
just format
```

## Typing

Run the static type checker with

```sh
just type-check
```
