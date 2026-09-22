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

interface OwnerResult {
    runId: string;
    userid: string | null;
    error: string | null;
}

/**
 * Page for viewing shared runs via /runs/shared/[runId].
 * Fetches the run owner and displays in read-only mode.
 */
export default function SharedRunPage({ params }: SharedRunPageProps) {
    const api = getRunsApi();
    const { isLoading: authLoading } = useAuth0();
    const { runId } = use(params);
    const [ownerResult, setOwnerResult] = useState<OwnerResult | null>(null);

    useEffect(() => {
        if (authLoading) return;

        let cancelled = false;

        const fetchOwner = async () => {
            try {
                const { data } = await api.getSharedRunOwner({ runId });
                if (cancelled) return;
                setOwnerResult({ runId, userid: data.userid, error: null });
            } catch (err) {
                if (cancelled) return;
                console.error('Error fetching shared run owner:', err);
                setOwnerResult({
                    runId,
                    userid: null,
                    error: 'This run is not available or has not been shared.',
                });
            }
        };

        fetchOwner();
        return () => {
            cancelled = true;
        };
    }, [runId, authLoading]);

    if (authLoading || ownerResult?.runId !== runId) {
        return <LoadingSpinner />;
    }

    if (ownerResult.error || !ownerResult.userid) {
        return (
            <Box sx={{ p: 3 }}>
                <Alert severity="error">{ownerResult.error || 'Unable to load shared run.'}</Alert>
            </Box>
        );
    }

    return (
        <URLSearchParamsProvider>
            <RunView key={runId} runid={runId} userid={ownerResult.userid} />
        </URLSearchParamsProvider>
    );
}
