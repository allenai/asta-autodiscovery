# Asta AutoDiscovery

> AutoDiscovery for Asta

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

### Onboarding

To deploy your application to Skiff it'll need to be [onboarded](https://***REMOVED***/onboarding.html).
Start by editing the `skiff.json` file in your repository:

- change `appName` to a short, unique identifier that's valid DNS subdomain
- set `contact` to your AI2 email address without the `@allenai.org` suffix
- set `team` to the name of the AI2 team that's responsible for the application

After making and committing those changes, submit a [request to be onboarded](https://github.com/allenai/skiff/issues/new/choose).

### Deploys

Commits to the `main` branch are automatically deployed to the development environment. 

**Environments:**
- **Development:** `main` branch → https://autodiscovery-dev.example.com/
  - Automatically deployed.
- **Production:** `env/prod` branch → https://autodiscovery.example.com/
  - Manually deployed by pointing the branch at a good commit. 

You can find more details about your application via [Marina](https://deploy.example.com/a/asta-autodiscovery).

## Getting Help

See [Skiff's Documentation](https://***REMOVED***/) for more information.
