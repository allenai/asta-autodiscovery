import { Content, Footer, VarnishApp } from '@allenai/varnish2/components';
import { AppRouterCacheProvider } from '@mui/material-nextjs/v14-appRouter';
import type { Metadata } from 'next';
import type { ReactNode } from 'react';

import '@fontsource/lato/300-italic.css';
import '@fontsource/lato/300.css';
import '@fontsource/lato/400-italic.css';
import '@fontsource/lato/400.css';
import '@fontsource/lato/700-italic.css';
import '@fontsource/lato/700.css';

import Header from './components/Header';

export const metadata: Metadata = {
    title: 'Next Skiff Template',
    description: 'An AI2 Skiff template to bootstrap a NextJS application',
};

// This layout will be applied to every page in the app.
// To learn more about layouts in NextJS, see their docs: https://nextjs.org/docs/app/building-your-application/routing/pages-and-layouts#layouts
export default function RootLayout({ children }: { children: ReactNode }) {
    return (
        <html lang="en">
            <body>
                <AppRouterCacheProvider>
                    <VarnishApp>
                        <Header />
                        <Content main>{children}</Content>
                        <Footer />
                    </VarnishApp>
                </AppRouterCacheProvider>
            </body>
        </html>
    );
}
