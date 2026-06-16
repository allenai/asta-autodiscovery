import { FullConfig } from '@playwright/test';

const RETRY_INTERVAL_MS = 5000;
const REQUEST_TIMEOUT_MS = 10000;
const TIMEOUT_MS = 120000;

/**
 * Render an error from the health-check fetch in a way that is actually
 * diagnosable in CI. A bare `${err}` on a failed `fetch()` stringifies to just
 * "TypeError: fetch failed" and drops `err.cause`, which is where undici stashes
 * the real reason (DNS lookup failure, ECONNREFUSED, ETIMEDOUT, TLS error, …).
 * Without the cause we cannot tell a down/unreachable endpoint apart from a real
 * app-level error, so surface it explicitly.
 */
function describeError(err: unknown): string {
    if (!(err instanceof Error)) return String(err);

    const parts = [`${err.name}: ${err.message}`];
    const cause = (err as { cause?: unknown }).cause;
    if (cause instanceof Error) {
        const code = (cause as { code?: string }).code;
        parts.push(`cause: ${cause.name}: ${cause.message}${code ? ` (${code})` : ''}`);
    } else if (cause !== undefined) {
        parts.push(`cause: ${String(cause)}`);
    }
    return parts.join(' | ');
}

export default async function globalSetup(config: FullConfig) {
    const baseURL = config.projects[0].use.baseURL ?? 'http://localhost:8080/';
    const HEALTH_URL = new URL('/api/runs/health', baseURL).toString();

    const deadline = Date.now() + TIMEOUT_MS;
    let lastError: unknown;
    let attempts = 0;

    while (Date.now() < deadline) {
        attempts++;
        try {
            // Bound each attempt so a single stalled handshake can't hang the
            // whole setup, and so a wedged connection eventually retries.
            const res = await fetch(HEALTH_URL, {
                signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
            });
            if (res.ok) return;
            lastError = new Error(`Health check returned HTTP ${res.status}`);
        } catch (err) {
            lastError = err;
        }
        await new Promise((resolve) => setTimeout(resolve, RETRY_INTERVAL_MS));
    }

    throw new Error(
        `Server health check did not succeed within ${TIMEOUT_MS / 1000}s (${attempts} attempts).\n` +
            `Health check URL: ${HEALTH_URL}\n` +
            `Last error: ${describeError(lastError)}\n` +
            `A connection-level failure (DNS/ECONNREFUSED/ETIMEDOUT/TLS) means the runner ` +
            `could not reach E2E_BASE_URL, not that your change is broken. For a local run, ` +
            `start the app with "yarn dev -p 8080" first.`
    );
}
