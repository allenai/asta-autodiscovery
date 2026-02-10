'use client';

import { useState, useEffect } from 'react';
import { Box, Alert } from '@mui/material';

import { useAuth0 } from '@/contexts/Auth0Context';
import { URLSearchParamsProvider } from '@/contexts/URLSearchParamsContext';
import { LoadingSpinner } from '@/components/LoadingSpinner';
import RunStatus from '@/runs/components/RunStatus';
import { getRunsApi } from '@/api/RunsApi';

interface SharedRunPageProps {
    params: {
        runId: string;
    };
}

/**
 * Page for viewing shared runs via /runs/shared/[runId].
 * Fetches the run owner and displays in read-only mode.
 */
export default function SharedRunPage({ params }: SharedRunPageProps) {
    const api = getRunsApi();
    const { isAuthenticated, isLoading: authLoading } = useAuth0();
    const { runId } = params;
    const [userid, setUserid] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [isLoadingOwner, setIsLoadingOwner] = useState(true);

    useEffect(() => {
        if (!isAuthenticated || authLoading) return;

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
    }, [runId, isAuthenticated, authLoading]);

    if (authLoading || isLoadingOwner) {
        return <LoadingSpinner />;
    }

    if (!isAuthenticated) {
        return (
            <Box sx={{ p: 3 }}>
                <Alert severity="warning">Please log in to view this run.</Alert>
            </Box>
        );
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
            <RunStatus runid={runId} userid={userid} />
        </URLSearchParamsProvider>
    );
}
