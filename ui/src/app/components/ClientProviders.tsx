'use client';

import { ReactNode } from 'react';

import { Auth0Provider } from '@/contexts/Auth0Context';
import { ViewerCreditsProvider } from '@/contexts/ViewerCreditsContext';

interface ClientProvidersProps {
    children: ReactNode;
}

export default function ClientProviders({ children }: ClientProvidersProps) {
    return (
        <Auth0Provider>
            <ViewerCreditsProvider>{children}</ViewerCreditsProvider>
        </Auth0Provider>
    );
}
