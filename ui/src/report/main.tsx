import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { createHashRouter } from 'react-router';
import { RouterProvider } from 'react-router/dom';
import { VarnishApp } from '@allenai/varnish2/components';

// Latin subsets only: the report inlines every font it imports into one file.
import '@fontsource/lato/latin-300.css';
import '@fontsource/lato/latin-400.css';
import '@fontsource/lato/latin-400-italic.css';
import '@fontsource/lato/latin-700.css';
import '@fontsource/manrope/latin-400.css';
import '@fontsource/manrope/latin-700.css';

import ReportPage from './ReportPage';

// A hash router, because the report is usually opened from disk (file://), where
// only the fragment can change without a navigation. `?exp=` lives after the `#`.
const router = createHashRouter([{ path: '*', element: <ReportPage /> }]);

createRoot(document.getElementById('root')!).render(
    <StrictMode>
        <VarnishApp>
            <RouterProvider router={router} />
        </VarnishApp>
    </StrictMode>
);
