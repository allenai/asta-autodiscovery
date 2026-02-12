'use client';

import { useEffect, useState } from 'react';
import { Box, CircularProgress, Alert, Button } from '@mui/material';
import { useRouter } from 'next/navigation';

import { LoadingSpinner } from '@/components/LoadingSpinner';

import { useAuth0 } from '@/contexts/Auth0Context';
import { URLSearchParamsProvider } from '@/contexts/URLSearchParamsContext';
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
 * Individual run page - shows RunSetup or RunStatus based on run state.
 * This page is for the current user's own runs only.
 * For viewing shared/public runs, use /shared/{userid}/{runid} instead.
 */
export default function RunPage({ params }: RunPageProps) {
    const { isAuthenticated, isLoading, getAccessToken, loginWithRedirect } = useAuth0();
    const router = useRouter();
    const runId = params.runId;
    const api = getRunsApi();

    const [checkingRun, setCheckingRun] = useState(true);
    const [runState, setRunState] = useState<'setup' | 'submitted'>('setup');
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const checkRunStatus = async () => {
            if (!isAuthenticated) return;

            setCheckingRun(true);
            setError(null);

            try {
                // No userid needed - API will use authenticated user
                const response = await api.getRun({ runId });
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
    }, [runId, isAuthenticated, getAccessToken]);

    const handleSubmitSuccess = () => {
        setRunState('submitted');
    };

    const handleRunCancelled = () => {
        router.push('/runs');
    };

    if (isLoading) {
        return <LoadingSpinner />;
    }

    if (!isAuthenticated) {
        return (
            <Box sx={{ p: 3 }}>
                <Alert severity="warning">
                    Please log in to view this run.
                    <Box sx={{ mt: 2 }}>
                        <Button
                            variant="contained"
                            color="primary"
                            onClick={() => loginWithRedirect()}>
                            Log In
                        </Button>
                    </Box>
                </Alert>
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
        <URLSearchParamsProvider>
            {runState === 'setup' && (
                <RunSetup runid={runId} onSubmitSuccess={handleSubmitSuccess} />
            )}
            {runState === 'submitted' && (
                <RunStatus runid={runId} onRunCancelled={handleRunCancelled} />
            )}
        </URLSearchParamsProvider>
    );
}
