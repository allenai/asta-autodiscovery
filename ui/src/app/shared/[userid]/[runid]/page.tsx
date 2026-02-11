'use client';

import { useAuth0 } from '@/contexts/Auth0Context';
import { URLSearchParamsProvider } from '@/contexts/URLSearchParamsContext';
import { LoadingSpinner } from '@/components/LoadingSpinner';
import RunStatus from '@/runs/components/RunStatus';
import Header from '@/components/Header';

interface SharedRunPageProps {
    params: {
        userid: string;
        runid: string;
    };
}

/**
 * Page for viewing shared/public runs from other users.
 * These runs are read-only - no setup or cancel actions allowed.
 */
export default function SharedRunPage({ params }: SharedRunPageProps) {
    const { isLoading, isAuthenticated } = useAuth0();
    const { userid, runid } = params;

    if (isLoading) {
        return <LoadingSpinner />;
    }

    return (
        <URLSearchParamsProvider>
            {!isAuthenticated && <Header showBackButton />}
            <RunStatus runid={runid} userid={userid} />
        </URLSearchParamsProvider>
    );
}
