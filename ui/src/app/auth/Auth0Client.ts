import { Auth0Client } from '@auth0/auth0-spa-js';

import { AuthConfig } from './authConfig';

/**
 * Build an Auth0 SPA client from runtime config. Returns null during SSR
 * (no window). Constructed by the Auth0 auth provider after config is fetched,
 * rather than at module load, so the active provider/settings are runtime-driven.
 */
export function createAuth0Client(config: AuthConfig): Auth0Client | null {
    if (typeof window === 'undefined') {
        return null;
    }
    return new Auth0Client({
        domain: config.domain || '',
        clientId: config.clientId || '',
        cacheLocation: 'localstorage',
        useRefreshTokens: true,
        useRefreshTokensFallback: true,
        authorizationParams: {
            redirect_uri: window.location.origin,
            audience: config.audience,
            scope: 'openid profile email',
        },
    });
}
