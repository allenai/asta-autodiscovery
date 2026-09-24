import { VarnishApp } from '@allenai/varnish2/components';
import type { ReactNode } from 'react';

import '@fontsource/lato/300-italic.css';
import '@fontsource/lato/300.css';
import '@fontsource/lato/400-italic.css';
import '@fontsource/lato/400.css';
import '@fontsource/lato/700-italic.css';
import '@fontsource/lato/700.css';
import '@fontsource/manrope/400.css';
import '@fontsource/manrope/700.css';

import ClientProviders from '@/components/ClientProviders';
import AuthErrorDialog from '@/components/AuthErrorDialog';
import ClickTrackingListener from '@/components/ClickTrackingListener';
import HeapAnalyticsLoader from '@/components/HeapAnalyticsLoader';
import { Toasts } from '@/components/Toasts';

// Applied to every page in the app.
export default function RootLayout({ children }: { children: ReactNode }) {
    return (
        <ClientProviders>
            <HeapAnalyticsLoader />
            <ClickTrackingListener />
            <VarnishApp>
                <div
                    style={{
                        overflow: 'hidden',
                        height: '100%',
                        minHeight: '100vh',
                        position: 'relative',
                    }}>
                    <Toasts />
                    {children}
                </div>
            </VarnishApp>
            <AuthErrorDialog />
        </ClientProviders>
    );
}
