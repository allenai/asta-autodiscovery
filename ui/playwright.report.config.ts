import { defineConfig, devices } from '@playwright/test';

/**
 * Smoke test of the standalone HTML report (e2e-report/). Unlike the e2e suite it
 * needs no running stack: it opens a report from disk. Run it with
 * `make test-report-viewer` from the repository root.
 */
export default defineConfig({
    testDir: './e2e-report',
    forbidOnly: !!process.env.CI,
    reporter: [['html', { outputFolder: 'playwright-report', open: 'never' }], ['list']],
    outputDir: 'test-results',
    use: {
        screenshot: 'only-on-failure',
    },
    projects: [
        {
            name: 'chromium',
            use: { ...devices['Desktop Chrome'], viewport: { width: 1600, height: 1000 } },
        },
    ],
});
