# Asta AutoDiscovery

> AutoDiscovery for Asta

## Changelog

Release notes for the published packages, including breaking changes, are in
[CHANGELOG.md](CHANGELOG.md).

## Standalone CLI

To run AutoDiscovery against a local dataset without the full Skiff stack, see
[docs/autodiscovery/standalone.md](docs/autodiscovery/standalone.md) for `pip install` and release
instructions.

## Setting Up

Install all workspace packages, including test and documentation dependencies:

```sh
make sync
```

`make help` lists every target; the ones below are the common ones.

## Running the Local Stack

Requires [Docker](https://www.docker.com/get-started).

```sh
make dev
```

The site is served at both http://localhost:3000 and http://localhost:8080, and the UI
hot-reloads as you edit.

Use `make dev` rather than `docker compose up --build`: the per-run job image sits behind
compose's `jobs` profile, so `up --build` leaves it untouched and the API goes on launching
whatever was last built. See
[docs/configuration.md](docs/configuration.md#docker-backend-default) for the job backends and the
environment they need.

## Running Tests

```sh
make test           # main test suite; excludes Modal tests
make test-modal     # Modal tests only
make test-all       # everything

make test PYTEST_ARGS=--cov   # forward extra flags to pytest
```

## Linting, Formatting and Typing

```sh
make lint           # Ruff lint with autofix
make format         # Ruff formatter
make type-check     # pyright
```

Run `make test` and `make lint` before pushing.

## UI Development

The stack runs the UI in Docker, but most IDEs need the dependencies installed on the host for
typechecking and autocompletion. Install [Node.js](https://nodejs.org) and
[yarn](https://classic.yarnpkg.com/lang/en/docs/install/#mac-stable), then:

```sh
cd ui && yarn install --frozen-lockfile
```

End-to-end tests are documented in [ui/e2e/README.md](ui/e2e/README.md).

## Documentation

```sh
make serve-docs     # serve locally
make deploy-docs    # publish to GitHub Pages
```

## License

This project is licensed under the Apache License, Version 2.0. See the [LICENSE](LICENSE) and [NOTICE](NOTICE) files for details.
