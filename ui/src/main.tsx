import { StrictMode, type ComponentType, type ReactNode } from 'react';
import { createRoot } from 'react-dom/client';
import { createBrowserRouter, Outlet, RouterProvider } from 'react-router-dom';

import RootLayout from '@/layout';
import HomePage from '@/page';
import RunsLayout from '@/runs/layout';
import RunsPage from '@/runs/page';
import RunPage from '@/runs/[runId]/page';
import SharedRunByIdPage from '@/runs/shared/[runId]/page';
import SharedLayout from '@/shared/layout';
import SharedRunPage from '@/shared/[userid]/[runid]/page';
import MetricsLayout from '@/metrics/layout';
import MetricsOverviewPage from '@/metrics/page';
import MetricsUsersPage from '@/metrics/users/page';
import UserDetailPage from '@/metrics/users/[userid]/page';
import RunMetricsPage from '@/metrics/runs/[userid]/[runid]/page';
import DebugLayout from '@/debug/layout';
import DebugAuthPage from '@/debug/auth/page';
import DebugUserPage from '@/debug/user/page';

const withLayout = (Layout: ComponentType<{ children: ReactNode }>) => (
    <Layout>
        <Outlet />
    </Layout>
);

// Mirrors the former file-based routes under src/app.
const router = createBrowserRouter([
    {
        element: withLayout(RootLayout),
        children: [
            { path: '/', element: <HomePage /> },
            {
                path: 'runs',
                element: withLayout(RunsLayout),
                children: [
                    { index: true, element: <RunsPage /> },
                    { path: ':runId', element: <RunPage /> },
                    { path: 'shared/:runId', element: <SharedRunByIdPage /> },
                ],
            },
            {
                path: 'shared',
                element: withLayout(SharedLayout),
                children: [{ path: ':userid/:runid', element: <SharedRunPage /> }],
            },
            {
                path: 'metrics',
                element: withLayout(MetricsLayout),
                children: [
                    { index: true, element: <MetricsOverviewPage /> },
                    { path: 'users', element: <MetricsUsersPage /> },
                    { path: 'users/:userid', element: <UserDetailPage /> },
                    { path: 'runs/:userid/:runid', element: <RunMetricsPage /> },
                ],
            },
            {
                path: 'debug',
                element: withLayout(DebugLayout),
                children: [
                    { path: 'auth', element: <DebugAuthPage /> },
                    { path: 'user', element: <DebugUserPage /> },
                ],
            },
        ],
    },
]);

createRoot(document.getElementById('root')!).render(
    <StrictMode>
        <RouterProvider router={router} />
    </StrictMode>
);
