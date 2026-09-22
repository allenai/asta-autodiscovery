'use client';

import { use, useState, useEffect } from 'react';
import { Box, Alert } from '@mui/material';

import { useAuth0 } from '@/contexts/Auth0Context';
import { URLSearchParamsProvider } from '@/contexts/URLSearchParamsContext';
import { LoadingSpinner } from '@/components/LoadingSpinner';
import RunView from '@/runs/components/RunView';
import { getRunsApi } from '@/api/RunsApi';

interface SharedRunPageProps {
    params: Promise<{
        runId: string;
    }>;
}

/**
 * Page for viewing shared runs via /runs/shared/[runId].
 * Fetches the run owner and displays in read-only mode.
 */
export default function SharedRunPage({ params }: SharedRunPageProps) {
    const api = getRunsApi();
    const { isLoading: authLoading } = useAuth0();
    const { runId } = use(params);
    const [userid, setUserid] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [isLoadingOwner, setIsLoadingOwner] = useState(true);

    useEffect(() => {
        if (authLoading) return;

        // Re-enter the loading state on a runId change so the owner lookup for the new
        // run can't be rendered against the previous run's owner.
        setIsLoadingOwner(true);
        setUserid(null);
        setError(null);

        const fetchOwner = async () => {
            try {
                const { data } = await api.getSharedRunOwner({ runId });
                setUserid(data.userid);
            } catch (err) {
                console.error('Error fetching shared run owner:', err);
                setError('This run is not available or has not been shared.');
            } finally {
                setIsLoadingOwner(false);
            }
        };

        fetchOwner();
    }, [runId, authLoading]);

    if (authLoading || isLoadingOwner) {
        return <LoadingSpinner />;
    }

    if (error || !userid) {
        return (
            <Box sx={{ p: 3 }}>
                <Alert severity="error">{error || 'Unable to load shared run.'}</Alert>
            </Box>
        );
    }

    return (
        <URLSearchParamsProvider>
            <RunView key={runId} runid={runId} userid={userid} />
        </URLSearchParamsProvider>
    );
}
