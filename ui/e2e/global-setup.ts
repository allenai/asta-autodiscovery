const HEALTH_URL = 'http://localhost:8080/api/runs/health';

export default async function globalSetup() {
    try {
        const res = await fetch(HEALTH_URL);
        if (!res.ok) {
            throw new Error(`Health check returned HTTP ${res.status}`);
        }
    } catch (err) {
        throw new Error(
            `Server is not running. Start it with "yarn dev -p 8080" before running tests.\n` +
                `Health endpoint: ${HEALTH_URL}\n` +
                `Original error: ${err}`
        );
    }
}
