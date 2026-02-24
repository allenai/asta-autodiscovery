'use client';

import { useAuth0 } from '@/contexts/Auth0Context';
import { URLSearchParamsProvider } from '@/contexts/URLSearchParamsContext';
import { LoadingSpinner } from '@/components/LoadingSpinner';
import RunView from '@/runs/components/RunView';
import { RunBookmarksProvider } from '@/contexts/RunBookmarksContext';
import { ExperimentBookmarksProvider } from '@/contexts/ExperimentBookmarksContext';

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
    const { isLoading } = useAuth0();
    const { userid, runid } = params;

    if (isLoading) {
        return <LoadingSpinner />;
    }

    return (
        <RunBookmarksProvider isRunBookmarksEnabled={false}>
            <ExperimentBookmarksProvider isExperimentBookmarksEnabled={false} runid={runid}>
                <URLSearchParamsProvider>
                    <RunView runid={runid} userid={userid} />
                </URLSearchParamsProvider>
            </ExperimentBookmarksProvider>
        </RunBookmarksProvider>
    );
}
