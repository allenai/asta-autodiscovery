/**
 * Runtime auth configuration, fetched from the backend (GET /api/auth/config),
 * so a single UI build can run against any provider without rebuilding.
 */

export type AuthProviderKind = 'auth0' | 'password_file' | 'none';

export interface AuthConfig {
    provider: AuthProviderKind;
    // auth0 only:
    domain?: string;
    clientId?: string;
    audience?: string;
    requiredPermission?: string | null;
}

// Build-time fallbacks (used if the config endpoint is unreachable). Keeps the
// app working in the historical Auth0 setup even without the new endpoint.
export const fallbackAuthConfig: AuthConfig = {
    provider: (process.env.NEXT_PUBLIC_AUTH_PROVIDER as AuthProviderKind) || 'auth0',
    domain: process.env.NEXT_PUBLIC_AUTH0_DOMAIN || 'auth0.allenai.org',
    clientId: process.env.NEXT_PUBLIC_AUTH0_CLIENT_ID || '6EQ7FtDfVFMdGCWa8SMnGGX3W7p6XVNa',
    audience: process.env.NEXT_PUBLIC_AUTH0_AUDIENCE || 'https://asta-core.allen.ai',
    requiredPermission: process.env.NEXT_PUBLIC_AUTH0_REQUIRED_PERMISSION || undefined,
};

export async function fetchAuthConfig(): Promise<AuthConfig> {
    try {
        const resp = await fetch('/api/auth/config', { headers: { Accept: 'application/json' } });
        if (!resp.ok) {
            return fallbackAuthConfig;
        }
        const data = (await resp.json()) as Partial<AuthConfig>;
        if (!data.provider) {
            return fallbackAuthConfig;
        }
        // Merge so missing auth0 fields fall back to build-time defaults.
        return { ...fallbackAuthConfig, ...data };
    } catch {
        return fallbackAuthConfig;
    }
}

/** Decode a JWT payload without verifying (UI gating only; backend is authoritative). */
export function decodeJwtPayload(token: string): Record<string, unknown> | null {
    try {
        const part = token.split('.')[1];
        const normalized = part.replace(/-/g, '+').replace(/_/g, '/');
        const padding = '='.repeat((4 - (normalized.length % 4)) % 4);
        return JSON.parse(atob(`${normalized}${padding}`));
    } catch {
        return null;
    }
}
