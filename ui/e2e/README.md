# E2E Tests

End-to-end tests for the AutoDiscovery application using Playwright.

## Prerequisites

1. **Install dependencies**:
   ```bash
   cd ui
   yarn install
   yarn playwright install chromium
   ```

2. **Start the application stack**:
   ```bash
   # From the repository root
   docker-compose up --build
   ```

   The application should be running at `http://localhost:8080` (or `http://localhost:3000` for the UI directly).

## Running Tests

### Against local stack (default)

```bash
cd ui
yarn test:e2e
```

### Against dev environment

```bash
cd ui
E2E_BASE_URL=https://autodiscovery-dev.example.com yarn test:e2e
```

### Against prod environment

```bash
cd ui
E2E_BASE_URL=https://autodiscovery.example.com yarn test:e2e
```

### Run tests in UI mode (interactive)

```bash
cd ui
yarn test:e2e:ui
```

### Run specific test file

```bash
cd ui
yarn playwright test e2e/public-sample.spec.ts
```

### Run against custom host

```bash
cd ui
E2E_BASE_URL=https://your-custom-host.example.com yarn test:e2e
```

## Public subset (`@public`)

Tests that require **no third-party credentials** (no Auth0/GCP/Modal) are tagged
`@public`. This is the subset safe to run in the public repo / on PRs. Run just that set:

```bash
# Start the stack under the auth backend you want to exercise, then:
AUTH_PROVIDER=password_file docker compose up --build   # or AUTH_PROVIDER=none
E2E_AUTH_PROVIDER=password_file yarn test:e2e:public     # matches the running stack
```

The full suite (all tags), including the credentialed integration tests, runs on internal
infra (triggered from the private repo) against real dependencies.

## Test Suites

### 1. Public Sample Test (`public-sample.spec.ts`)

Tests that the public shared sample run at `/shared/samples/nls_bmi` loads correctly without authentication.

**No environment variables required.**

### 2. Auth Provider Tests (`auth-providers.spec.ts`) — `@public`

Exercises the login UX of the swappable auth backends without any third-party
credentials. Select the backend with `E2E_AUTH_PROVIDER` (must match how the stack was
started):

- `password_file`: opens the login form, shows an inline error on a wrong password
  (and asserts the global "Access Denied" dialog is *not* triggered), and — with a seeded
  user — signs in and out.
- `none`: asserts there is no sign-in affordance and the app is already authenticated.

**Environment variables:**
- `E2E_AUTH_PROVIDER`: `password_file` | `none` (non-matching blocks skip)
- `E2E_TEST_USER` / `E2E_TEST_PASSWORD`: only for the `password_file` happy-path sign-in.
  Seed the user first: `uv run api/scripts/auth_admin.py useradd "$E2E_TEST_USER" --password "$E2E_TEST_PASSWORD"`. These are ephemeral test creds, not secrets.

### 3. Authenticated Flow Test (`authenticated-flow.spec.ts`)

Tests the complete user workflow including:
- Login with Auth0
- Creating a new run
- Uploading a data file
- Submitting the run
- Verifying the run is in progress

**Required environment variables:**
- `E2E_TEST_USER`: Test user email for Auth0 login
- `E2E_TEST_PASSWORD`: Test user password for Auth0 login

**Optional environment variables:**
- `E2E_TEST_DATAFILE`: Path to a test CSV file (if not provided, a minimal test file will be generated)
- `E2E_BASE_URL`: Base URL of the application (default: `http://localhost:8080`)
  - Local: `http://localhost:8080` (full stack via proxy)
  - Dev: `https://autodiscovery-dev.example.com`
  - Prod: `https://autodiscovery.example.com`

Example:
```bash
export E2E_TEST_USER="test@example.com"
export E2E_TEST_PASSWORD="test-password"
export E2E_TEST_DATAFILE="./test-data/sample.csv"
yarn test:e2e
```

## Workflow: Testing Before Prod Promotion

Before promoting a commit from dev to prod:

1. **Deploy to dev** (happens automatically on merge to main)

2. **Run e2e tests against dev**:
   ```bash
   cd ui
   E2E_BASE_URL=https://autodiscovery-dev.example.com \
   E2E_TEST_USER="your-test-user@example.com" \
   E2E_TEST_PASSWORD="your-password" \
   yarn test:e2e
   ```

3. **If tests pass**, promote the commit to prod (via Skiff deployment or manual process)

4. **(Optional) Verify prod** after deployment:
   ```bash
   E2E_BASE_URL=https://autodiscovery.example.com yarn test:e2e
   ```

## CI Integration

To run e2e tests in CI:

1. Ensure the application stack is running
2. Set the required environment variables as secrets
3. Run the tests:
   ```bash
   cd ui
   yarn test:e2e --reporter=github
   ```

## Configuration

The Playwright configuration is in `playwright.config.ts`. Key settings:

- **baseURL**: `http://localhost:8080` (configurable via `E2E_BASE_URL`)
- **Test timeout**: 30 seconds for most tests, 10 minutes for the authenticated flow
- **Retries**: 2 in CI, 0 locally
- **Browser**: Chromium (Desktop Chrome)

## Troubleshooting

### Tests are slow or timing out

- Increase the test timeout in the spec file: `test.setTimeout(600000);` (10 minutes)
- Check that the application is running and accessible
- Verify the Auth0 credentials are correct

### Authentication fails

- Verify `E2E_TEST_USER` and `E2E_TEST_PASSWORD` are set correctly
- Check that the test user exists in Auth0 and has the required permissions
- Ensure the Auth0 configuration matches the application environment

### File upload fails

- Verify the file path in `E2E_TEST_DATAFILE` is correct and accessible
- Check that the file is a valid CSV format
- If no file is provided, the test will generate a minimal CSV automatically

## Debugging

To debug tests:

1. Run in UI mode: `yarn test:e2e:ui`
2. Use Playwright Inspector: `yarn playwright test --debug`
3. Enable trace on all tests (in `playwright.config.ts`): `trace: 'on'`
4. View traces: `yarn playwright show-report`
