import { defineConfig } from '@playwright/test';

export default defineConfig({
    testDir: './e2e',
    fullyParallel: true,
    workers: 2,
    retries: 1,
    timeout: 60000,
    globalSetup: './e2e/global-setup.ts',
    reporter: [['html', { outputFolder: 'public/e2e-results', open: 'never' }]],
    outputDir: 'public/e2e-artifacts',
    use: {
        baseURL: 'http://localhost:8080/',
        screenshot: 'on',
        video: 'on',
    },
});
