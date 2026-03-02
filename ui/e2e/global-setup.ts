import { FullConfig } from '@playwright/test';

export default async function globalSetup(config: FullConfig) {
    const baseURL = config.projects[0].use.baseURL ?? 'http://localhost:8080/';
    const HEALTH_URL = new URL('/api/runs/health', baseURL).toString();
    try {
        const res = await fetch(HEALTH_URL);
        if (!res.ok) {
            throw new Error(`Health check returned HTTP ${res.status}`);
        }
    } catch (err) {
        throw new Error(
            `Server is not running. Start it with "yarn dev -p 8080" before running tests.\n` +
                `Health check URL: ${HEALTH_URL}\n` +
                `Original error: ${err}`
        );
    }
}
