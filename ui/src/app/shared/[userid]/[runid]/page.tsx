import { useParams } from '@/router';

import { useAuth0 } from '@/contexts/Auth0Context';
import { URLSearchParamsProvider } from '@/contexts/URLSearchParamsContext';
import { LoadingSpinner } from '@/components/LoadingSpinner';
import RunView from '@/runs/components/RunView';
import { RunBookmarksProvider } from '@/contexts/RunBookmarksContext';
import { ExperimentBookmarksProvider } from '@/contexts/ExperimentBookmarksContext';

/**
 * Page for viewing shared/public runs from other users.
 * These runs are read-only - no setup or cancel actions allowed.
 */
export default function SharedRunPage() {
    const { isLoading } = useAuth0();
    const { userid, runid } = useParams();

    if (isLoading) {
        return <LoadingSpinner />;
    }

    if (!userid || !runid) {
        return <div>Invalid shared run URL.</div>;
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
