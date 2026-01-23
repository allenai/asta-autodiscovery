'use client';

import { useEffect, useState } from 'react';
import { Box, Button, Typography, CircularProgress, Alert, Chip, styled } from '@mui/material';
import CancelIcon from '@mui/icons-material/Cancel';
import CloseIcon from '@mui/icons-material/Close';
import IconButton from '@mui/material/IconButton';

import { getRunsApi } from '@/api/RunsApi';
import { Experiment, RunDetails, getRunFromApi } from '@/types/Run';
import { RunExperiments } from '@/runs/components/RunExperiments';
import { ExperimentDetails } from './ExperimentDetails';

interface RunStatusProps {
    runid: string;
    onRunCancelled?: () => void;
}

/**
 * Component for displaying the status of a submitted run.
 *
 * Features:
 * - Display run status (based on Cloud Run phase) and timestamps
 * - Refresh button to check status
 * - Stop Run button (only shown when status is RUNNING)
 * - Auto-refresh every 30 seconds for active runs
 */
export default function RunStatus({ runid, onRunCancelled }: RunStatusProps) {
    const api = getRunsApi();

    const [runDetails, setRunDetails] = useState<RunDetails | null>(null);
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);
    const [cancelling, setCancelling] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [selectedExperiment, setSelectedExperiment] = useState<Experiment | null>(null);

    const fetchStatus = async (isRefresh = false) => {
        if (isRefresh) {
            setRefreshing(true);
        } else {
            setLoading(true);
        }
        setError(null);

        try {
            const response = await api.getRunStatus(runid);
            const run = getRunFromApi(response.data);

            setRunDetails(run.details);
        } catch (err) {
            console.error('Error fetching run status:', err);
            setError(err instanceof Error ? err.message : 'Failed to load run status');
        } finally {
            setLoading(false);
            setRefreshing(false);
        }
    };

    useEffect(() => {
        fetchStatus();

        // Auto-refresh every 30 seconds if run is still running
        const interval = setInterval(() => {
            if (
                runDetails?.status === 'RUNNING' ||
                runDetails?.status === 'PENDING' ||
                runDetails?.status === 'QUEUED'
            ) {
                fetchStatus(true);
            }
        }, 30000);

        return () => clearInterval(interval);
    }, [runid]);

    const handleSelectExperiment = (experiment: Experiment) => {
        setSelectedExperiment(experiment);
    };

    const handleCloseDetails = () => {
        setSelectedExperiment(null);
    };

    const handleStop = async () => {
        if (!confirm('Are you sure you want to stop this run?')) {
            return;
        }

        setCancelling(true);
        setError(null);

        try {
            await api.cancelRun(runid);

            // Refresh status
            await fetchStatus(true);

            if (onRunCancelled) {
                onRunCancelled();
            }
        } catch (err) {
            console.error('Error stopping run:', err);
            setError(err instanceof Error ? err.message : 'Failed to stop run');
        } finally {
            setCancelling(false);
        }
    };

    const getStatusColor = (status: string) => {
        const upperStatus = status.toUpperCase();
        switch (upperStatus) {
            case 'CREATED':
                return 'default';
            case 'RUNNING':
            case 'PENDING':
            case 'QUEUED':
                return 'primary';
            case 'COMPLETED':
            case 'SUCCEEDED':
                return 'success';
            case 'FAILED':
            case 'ERROR':
                return 'error';
            case 'CANCELLED':
                return 'warning';
            default:
                return 'default';
        }
    };

    const canStop = runDetails?.status === 'RUNNING';

    if (loading) {
        return (
            <Box
                sx={{
                    display: 'flex',
                    justifyContent: 'center',
                    alignItems: 'center',
                    p: 3,
                }}>
                <CircularProgress />
            </Box>
        );
    }

    if (!runDetails) {
        return (
            <Box sx={{ p: 3 }}>
                <Alert severity="error">Run details not found</Alert>
            </Box>
        );
    }

    return (
        <>
            <ExperimentLayout $isDetailsOpen={!!selectedExperiment}>
                <MainContent>
                    <Box>
                        {error && <Alert severity="error">{error}</Alert>}
                        <Chip
                            label={runDetails.status.toUpperCase()}
                            color={getStatusColor(runDetails.status)}
                            size="medium"
                        />
                        {runDetails.statusCheckedAt && (
                            <Box>
                                <Typography variant="caption">
                                    Last Checked:{' '}
                                    {new Date(runDetails.statusCheckedAt).toLocaleString()}
                                </Typography>
                            </Box>
                        )}
                        {canStop && (
                            <Button
                                variant="outlined"
                                color="error"
                                startIcon={
                                    cancelling ? <CircularProgress size={16} /> : <CancelIcon />
                                }
                                onClick={handleStop}
                                disabled={refreshing || cancelling}
                                sx={{ flex: 1 }}>
                                {cancelling ? 'Stopping...' : 'Stop Run'}
                            </Button>
                        )}
                    </Box>

                    <Box sx={{ flex: 1, minHeight: 0 }}>
                        <RunExperiments runId={runid} onSelectExperiment={handleSelectExperiment} />
                    </Box>
                </MainContent>

                <DetailsWrapper>
                    {!!selectedExperiment && (
                        <>
                            <CloseDetailButton onClick={handleCloseDetails} size="small">
                                <CloseIcon />
                            </CloseDetailButton>
                            <ExperimentDetails experiment={selectedExperiment} />
                        </>
                    )}
                </DetailsWrapper>
            </ExperimentLayout>
        </>
    );
}

const ExperimentLayout = styled('div')<{ $isDetailsOpen: boolean }>`
    color: ${({ theme }) => theme.color['cream-100'].hex};
    display: grid;
    grid-template-columns: minmax(40px, 2fr) 1fr;
    grid-template-areas: 'main-content details';
    gap: ${({ theme }) => theme.spacing(2)};
    height: 100%;
    padding: ${({ theme }) => theme.spacing(2)};

    ${({ $isDetailsOpen }) => !$isDetailsOpen && `grid-template-columns: 1fr 0;`}
`;

const MainContent = styled('div')`
    grid-area: main-content;
    display: flex;
    flex-direction: column;
    gap: ${({ theme }) => theme.spacing(2)};
`;

const DetailsWrapper = styled('div')`
    background-color: ${({ theme }) => theme.color['cream-4'].rgba.toString()};
    grid-area: details;
    padding: ${({ theme }) => theme.spacing(3)};
    position: relative;
`;

const CloseDetailButton = styled(IconButton)`
    color: ${({ theme }) => theme.color['cream-50'].rgba.toString()};
    position: absolute;
    top: ${({ theme }) => theme.spacing(2)};
    right: ${({ theme }) => theme.spacing(2)};
`;
