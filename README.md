# Asta AutoDiscovery

> AutoDiscovery for Asta

## Standalone CLI

To run AutoDiscovery against a local dataset without the full Skiff stack, see
[docs/autodiscovery/standalone.md](docs/autodiscovery/standalone.md) for `pip install` and release
instructions.

## Setting Up

Install all required packages (including those for testing and documentation) using:

```sh
make sync
```

## Running Tests

Execute the test suites with:

```sh
make test           # Run main test suite. Excludes Modal Tests
make test-modal     # Run Modal tests only
make test-all       # Run all tests

make test -- --cov  # Run main tests and report coverage
```

## Linting and Formatting

Run Ruff via uv to check code style and lint errors:

```sh
make lint
```

To apply Ruff's formatter, use:

```sh
make format
```

## Typing

Run the static type checker with

```sh
make type-check
```

## Documentation

Serve the documentation with

```sh
make serve-docs
```

# skiff-template-nextjs

This is a template [Skiff](https://github.com/allenai/skiff) application with:

* A [TypeScript](https://www.typescriptlang.org/), [React](https://reactjs.org/)
  and [Shellac](https://***REMOVED***/material-ui/varnish/shellac/) based user interface (uses only HTML and CSS).
* A [NextJS](https://nextjs.org/) HTTP server, that provides capabilities like server rendering.

You can use this template to start a new Skiff application.

## Getting Started

### Local Environment

First make sure you have [Docker](https://www.docker.com/get-started) installed, then
start local environment by running:

```
docker compose up --build
```

The site should be accessible at both http://localhost:3000 and http://localhost:8080. 
As you make edits, the page should automatically refresh with changes.

### Local Development

Most IDEs require the dependencies to be installed locally for things like typechecking
and autocompletion.

To do this install [nodejs.org](https://nodejs.org) and [yarn](https://classic.yarnpkg.com/lang/en/docs/install/#mac-stable) 
(yes, the version we use is EoL) on your machine. Then run:

```
cd app/
yarn install --frozen-lockfile
```

## Getting Help

See [Skiff's Documentation](https://***REMOVED***/) for more information.

## License

This project is licensed under the Apache License, Version 2.0. See the [LICENSE](LICENSE) and [NOTICE](NOTICE) files for details.
