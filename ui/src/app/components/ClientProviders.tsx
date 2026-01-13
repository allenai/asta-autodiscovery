'use client';

import { ReactNode } from 'react';

import { Auth0Provider } from '../contexts/Auth0Context';

interface ClientProvidersProps {
    children: ReactNode;
}

export default function ClientProviders({ children }: ClientProvidersProps) {
    // Auth0 configuration - these should match your Auth0 application settings
    const auth0Config = {
        domain: process.env.NEXT_PUBLIC_AUTH0_DOMAIN || 'allenai-public.us.auth0.com',
        clientId: process.env.NEXT_PUBLIC_AUTH0_CLIENT_ID || '6EQ7FtDfVFMdGCWa8SMnGGX3W7p6XVNa',
        audience: process.env.NEXT_PUBLIC_AUTH0_AUDIENCE || 'https://ai2-autodiscovery.allen.ai',
    };

    return (
        <Auth0Provider
            domain={auth0Config.domain}
            clientId={auth0Config.clientId}
            audience={auth0Config.audience}>
            {children}
        </Auth0Provider>
    );
}
