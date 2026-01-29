'use client';

import RunsLayout from '@/runs/layout';

/**
 * Layout for shared runs pages - reuses RunsLayout.
 * Since the pathname is /shared/... (not /runs/...), the sidebar
 * won't highlight any run, which is the desired behavior.
 */
export default function SharedLayout({ children }: { children: React.ReactNode }) {
    return <RunsLayout>{children}</RunsLayout>;
}
