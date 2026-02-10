'use client';

import { ReactNode } from 'react';

import { Auth0Provider } from '@/contexts/Auth0Context';
import { ViewerCreditsProvider } from '@/contexts/ViewerCreditsContext';
import { ToastsContextProvider } from '@/contexts/ToastsContext';
import { ExampleRunsContextProvider } from '@/contexts/ExampleRunsContext';
import { ViewerRunsContextProvider } from '@/contexts/ViewerRunsContext';

interface ClientProvidersProps {
    children: ReactNode;
}

export default function ClientProviders({ children }: ClientProvidersProps) {
    return (
        <Auth0Provider>
            <ToastsContextProvider>
                <ExampleRunsContextProvider>
                    <ViewerCreditsProvider>
                        <ViewerRunsContextProvider>{children}</ViewerRunsContextProvider>
                    </ViewerCreditsProvider>
                </ExampleRunsContextProvider>
            </ToastsContextProvider>
        </Auth0Provider>
    );
}
