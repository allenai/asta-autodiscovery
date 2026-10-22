# Asta AutoDiscovery

> AutoDiscovery for Asta

**Live app:** https://autodiscovery.allen.ai — a public deployment of this repo; nearly all the code behind it lives here.

**Documentation:** https://allenai.github.io/asta-autodiscovery

## Changelog

Release notes for the published packages, including breaking changes, are in
[CHANGELOG.md](CHANGELOG.md).

## Standalone CLI

To run AutoDiscovery against a local dataset without the full web stack, see
[docs/autodiscovery/standalone.md](docs/autodiscovery/standalone.md) for `pip install` and release
instructions.

## Setting Up

Install all workspace packages, including test and documentation dependencies:

```sh
make sync
```

`make help` lists every target; the ones below are the common ones.

## Running the Local Stack

Requires [Docker](https://www.docker.com/get-started) and a `.env` file naming the model to
use -- there is no default model, and `make dev` refuses to start without one. The
[quick start](docs/quickstart.md) has a copy-paste `.env` for OpenAI, Anthropic, Azure OpenAI,
Google Vertex AI, and GitHub Copilot. For example:

```sh
# .env
AUTODISCOVERY_MODEL=openai/gpt-5.4-mini
OPENAI_API_KEY=sk-...
```

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

To run the same stack without Docker — API, UI, and each run as processes on your machine,
single-user — use `make dev-host` instead; see
[docs/configuration.md](docs/configuration.md#process-backend).

## Running Tests

```sh
make test                     # the full test suite
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

### The HTML report

The static HTML report every run writes beside its results is the UI's run view, built from
the same components by `yarn build:report` (see `ui/vite.report.config.ts`) into one
self-contained page that ships with the `asta-autodiscovery` package. The job image and the
PyPI release build it themselves; in a source checkout, build it before running
`auto-discovery` or `make dev-host` (which builds it for you):

```sh
make report-viewer
```

`python -m autodiscovery.report <out_dir>` regenerates the report for an existing run.
`make test-report-viewer` opens a synthetic run's report from disk in Chromium, as CI does.

## Documentation

Published at **https://allenai.github.io/asta-autodiscovery**. Build locally:

```sh
make serve-docs     # serve locally
make deploy-docs    # publish to GitHub Pages
```

## License

This project is licensed under the Apache License, Version 2.0. See the [LICENSE](LICENSE) and [NOTICE](NOTICE) files for details.
