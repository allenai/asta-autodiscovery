import { Auth0Client } from '@auth0/auth0-spa-js';

// Auth0 configuration - these should match your Auth0 application settings
export const auth0Config = {
    domain: process.env.NEXT_PUBLIC_AUTH0_DOMAIN || 'auth0.allenai.org',
    clientId: process.env.NEXT_PUBLIC_AUTH0_CLIENT_ID || '6EQ7FtDfVFMdGCWa8SMnGGX3W7p6XVNa',
    audience: process.env.NEXT_PUBLIC_AUTH0_AUDIENCE || 'https://ai2-autodiscovery.allen.ai',
    requiredPermission:
        process.env.NEXT_PUBLIC_AUTH0_REQUIRED_PERMISSION || 'enroll:autodiscovery_v0',
};

export const auth0Client =
    typeof window !== 'undefined'
        ? new Auth0Client({
              domain: auth0Config.domain,
              clientId: auth0Config.clientId,
              cacheLocation: 'localstorage',
              useRefreshTokens: true,
              authorizationParams: {
                  redirect_uri: window.location.origin,
                  audience: auth0Config.audience,
                  scope: 'openid profile email offline_access',
              },
          })
        : null;
