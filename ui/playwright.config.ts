import { defineConfig, devices } from '@playwright/test';

/**
 * E2E test configuration for the AutoDiscovery UI.
 *
 * Target Environment:
 * - Local: E2E_BASE_URL=http://localhost:8080 (default - full stack via proxy)
 * - Dev: E2E_BASE_URL=https://autodiscovery-dev.example.com
 * - Prod: E2E_BASE_URL=https://autodiscovery.example.com
 *
 * Prerequisites:
 * - For local: Start the stack with `docker compose up --build`
 * - For deployed envs: Ensure you have test credentials
 *
 * Run tests with: yarn test:e2e
 */
export default defineConfig({
    testDir: './e2e',
    fullyParallel: true,
    forbidOnly: !!process.env.CI,
    retries: process.env.CI ? 2 : 0,
    workers: process.env.CI ? 1 : undefined,
    reporter: 'html',
    use: {
        baseURL: process.env.E2E_BASE_URL || 'http://localhost:8080',
        trace: 'on-first-retry',
    },
    projects: [
        {
            name: 'chromium',
            use: { ...devices['Desktop Chrome'] },
        },
    ],
});
