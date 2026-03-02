import { Auth0Client } from '@auth0/auth0-spa-js';

// Auth0 configuration - these should match your Auth0 application settings
export const auth0Config = {
    domain: process.env.NEXT_PUBLIC_AUTH0_DOMAIN || 'auth.example.com',
    clientId: process.env.NEXT_PUBLIC_AUTH0_CLIENT_ID || 'YOUR_AUTH0_CLIENT_ID',
    audience: process.env.NEXT_PUBLIC_AUTH0_AUDIENCE || 'https://autodiscovery.example.com',
    // If not set or empty, no permission is required (any authenticated user can access)
    requiredPermission: process.env.NEXT_PUBLIC_AUTH0_REQUIRED_PERMISSION || undefined,
};

export const auth0Client =
    typeof window !== 'undefined'
        ? new Auth0Client({
              domain: auth0Config.domain,
              clientId: auth0Config.clientId,
              cacheLocation: 'localstorage',
              useRefreshTokens: true,
              useRefreshTokensFallback: true,
              authorizationParams: {
                  redirect_uri: window.location.origin,
                  audience: auth0Config.audience,
                  scope: 'openid profile email offline_access',
              },
          })
        : null;
