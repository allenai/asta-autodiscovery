'use client';

import { ReactNode } from 'react';

import { Auth0Provider } from '@/contexts/Auth0Context';
import { ViewerCreditsProvider } from '@/contexts/ViewerCreditsContext';
import { ToastsContextProvider } from '@/contexts/ToastsContext';

interface ClientProvidersProps {
    children: ReactNode;
}

export default function ClientProviders({ children }: ClientProvidersProps) {
    return (
        <Auth0Provider>
            <ToastsContextProvider>
                <ViewerCreditsProvider>{children}</ViewerCreditsProvider>
            </ToastsContextProvider>
        </Auth0Provider>
    );
}
