'use client';

import { ReactNode } from 'react';

import { Auth0Provider } from '@/contexts/Auth0Context';
import { ViewerCreditsProvider } from '@/contexts/ViewerCreditsContext';
import { ToastsContextProvider } from '@/contexts/ToastsContext';
import { ExampleRunsContextProvider } from '@/contexts/ExampleRunsContext';
import { ViewerRunsContextProvider } from '@/contexts/ViewerRunsContext';
import { RuntimeConfigProvider } from '@/contexts/RuntimeConfigContext';

interface ClientProvidersProps {
    children: ReactNode;
}

export default function ClientProviders({ children }: ClientProvidersProps) {
    return (
        <RuntimeConfigProvider>
            <Auth0Provider>
                <ToastsContextProvider>
                    <ExampleRunsContextProvider>
                        <ViewerCreditsProvider>
                            <ViewerRunsContextProvider>{children}</ViewerRunsContextProvider>
                        </ViewerCreditsProvider>
                    </ExampleRunsContextProvider>
                </ToastsContextProvider>
            </Auth0Provider>
        </RuntimeConfigProvider>
    );
}
