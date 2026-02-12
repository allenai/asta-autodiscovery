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

## Test Suites

### 1. Public Sample Test (`public-sample.spec.ts`)

Tests that the public shared sample run at `/shared/samples/nls_bmi` loads correctly without authentication.

**No environment variables required.**

### 2. Authenticated Flow Test (`authenticated-flow.spec.ts`)

Tests the complete user workflow including:
- Login with Auth0
- Creating a new run
- Uploading a data file
- Submitting the run
- Waiting for completion
- Verifying results

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

- **baseURL**: `http://localhost:3000` (configurable via `E2E_BASE_URL`)
- **Test timeout**: 30 seconds for most tests, 10 minutes for the authenticated flow
- **Retries**: 2 in CI, 0 locally
- **Browser**: Chromium (Desktop Chrome)

## Troubleshooting

### Tests are slow or timing out

- Increase the test timeout in the spec file: `test.setTimeout(600000);` (10 minutes)
- Check that the application is running and accessible
- Verify the Auth0 credentials are correct

### Authentication fails

- Verify `E2E_TEST_EMAIL` and `E2E_TEST_PASSWORD` are set correctly
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
