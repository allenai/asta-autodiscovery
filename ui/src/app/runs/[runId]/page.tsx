'use client';

import { useEffect, useState } from 'react';
import { Box, CircularProgress, Alert } from '@mui/material';

import { useRouter, useSearchParams } from 'next/navigation';

import { useAuth0 } from '@/contexts/Auth0Context';
import RunSetup from '@/runs/components/RunSetup';
import RunStatus from '@/runs/components/RunStatus';
import { getRunsApi } from '@/api/RunsApi';
import { getRunFromApi } from '@/types/Run';

interface RunPageProps {
    params: {
        runId: string;
    };
}

/**
 * Individual run page - shows RunSetup or RunStatus based on run state
 *
 * Query params:
 *   user: Optional user ID for viewing public runs (e.g., "samples")
 */
export default function RunPage({ params }: RunPageProps) {
    const { isAuthenticated, isLoading, getAccessToken } = useAuth0();
    const router = useRouter();
    const searchParams = useSearchParams();
    const runId = params.runId;
    const api = getRunsApi();

    // Get user from query param (for viewing public/sample runs)
    const userParam = searchParams.get('user') || undefined;

    const [checkingRun, setCheckingRun] = useState(true);
    const [runState, setRunState] = useState<'setup' | 'submitted'>('setup');
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const checkRunStatus = async () => {
            if (!isAuthenticated) return;

            setCheckingRun(true);
            setError(null);

            try {
                const response = await api.getRun(runId, { user: userParam });
                const run = getRunFromApi(response.data);

                // Check if run has been submitted
                if (
                    run.details?.executionId ||
                    (run.details?.status && run.details.status.toUpperCase() !== 'CREATED')
                ) {
                    setRunState('submitted');
                } else {
                    setRunState('setup');
                }
            } catch (err) {
                console.error('Error loading run:', err);
                setError(err instanceof Error ? err.message : 'Failed to load run');
                setRunState('setup');
            } finally {
                setCheckingRun(false);
            }
        };

        checkRunStatus();
    }, [runId, isAuthenticated, getAccessToken, userParam]);

    const handleSubmitSuccess = () => {
        setRunState('submitted');
    };

    const handleRunCancelled = () => {
        router.push('/runs');
    };

    // Sample runs are read-only - don't allow setup
    const isReadOnly = !!userParam;

    if (isLoading) {
        return (
            <Box
                sx={{
                    display: 'flex',
                    justifyContent: 'center',
                    alignItems: 'center',
                    minHeight: '100%',
                }}>
                <CircularProgress />
            </Box>
        );
    }

    if (!isAuthenticated) {
        return (
            <Box sx={{ p: 3 }}>
                <Alert severity="warning">Please log in to view this run.</Alert>
            </Box>
        );
    }

    if (error) {
        return (
            <Box sx={{ p: 3 }}>
                <Alert severity="error" onClose={() => setError(null)}>
                    {error}
                </Alert>
            </Box>
        );
    }

    if (checkingRun) {
        return (
            <Box
                sx={{
                    display: 'flex',
                    justifyContent: 'center',
                    alignItems: 'center',
                    height: '100%',
                    p: 3,
                }}>
                <CircularProgress />
            </Box>
        );
    }

    return (
        <>
            {runState === 'setup' && !isReadOnly && (
                <RunSetup runid={runId} onSubmitSuccess={handleSubmitSuccess} />
            )}
            {(runState === 'submitted' || isReadOnly) && (
                <RunStatus runid={runId} onRunCancelled={handleRunCancelled} user={userParam} />
            )}
        </>
    );
}
