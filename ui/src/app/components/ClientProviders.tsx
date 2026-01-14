'use client';

import { ReactNode } from 'react';

import { Auth0Provider } from '../contexts/Auth0Context';

interface ClientProvidersProps {
    children: ReactNode;
}

export default function ClientProviders({ children }: ClientProvidersProps) {
    // Auth0 configuration - these should match your Auth0 application settings
    const auth0Config = {
        domain: process.env.NEXT_PUBLIC_AUTH0_DOMAIN || 'auth.example.com',
        clientId: process.env.NEXT_PUBLIC_AUTH0_CLIENT_ID || 'YOUR_AUTH0_CLIENT_ID',
        audience: process.env.NEXT_PUBLIC_AUTH0_AUDIENCE || 'https://autodiscovery.example.com',
        requiredPermission:
            process.env.NEXT_PUBLIC_AUTH0_REQUIRED_PERMISSION || 'enroll:autodiscovery_v0',
    };

    return (
        <Auth0Provider
            domain={auth0Config.domain}
            clientId={auth0Config.clientId}
            audience={auth0Config.audience}
            requiredPermission={auth0Config.requiredPermission}>
            {children}
        </Auth0Provider>
    );
}
