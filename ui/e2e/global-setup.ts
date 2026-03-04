import { FullConfig } from '@playwright/test';

const RETRY_INTERVAL_MS = 5000;
const TIMEOUT_MS = 120000;

export default async function globalSetup(config: FullConfig) {
    const baseURL = config.projects[0].use.baseURL ?? 'http://localhost:8080/';
    const HEALTH_URL = new URL('/api/runs/health', baseURL).toString();

    const deadline = Date.now() + TIMEOUT_MS;
    let lastError: unknown;

    while (Date.now() < deadline) {
        try {
            const res = await fetch(HEALTH_URL);
            if (res.ok) return;
            lastError = new Error(`Health check returned HTTP ${res.status}`);
        } catch (err) {
            lastError = err;
        }
        await new Promise((resolve) => setTimeout(resolve, RETRY_INTERVAL_MS));
    }

    throw new Error(
        `Server did not become ready within ${TIMEOUT_MS / 1000}s. Start it with "yarn dev -p 8080" before running tests.\n` +
            `Health check URL: ${HEALTH_URL}\n` +
            `Last error: ${lastError}`
    );
}
