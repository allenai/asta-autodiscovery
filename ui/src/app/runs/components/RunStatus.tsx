'use client';

import { useEffect, useState } from 'react';
import {
    Box,
    Stack,
    Button,
    Typography,
    Paper,
    CircularProgress,
    Alert,
    Chip,
    Divider,
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import CancelIcon from '@mui/icons-material/Cancel';

import { useAuth0 } from '@/app/contexts/Auth0Context';
import { getRunStatus, cancelRun, type RunDetails } from '../actions';

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
    const { getAccessToken } = useAuth0();

    const [runDetails, setRunDetails] = useState<RunDetails | null>(null);
    const [executionStatus, setExecutionStatus] = useState<Record<string, unknown> | null>(null);
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);
    const [cancelling, setCancelling] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const fetchStatus = async (isRefresh = false) => {
        if (isRefresh) {
            setRefreshing(true);
        } else {
            setLoading(true);
        }
        setError(null);

        try {
            const token = await getAccessToken();
            const response = await getRunStatus(runid, token);

            setRunDetails(response.run_details);
            setExecutionStatus(response.execution_status || null);
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

    const handleRefresh = () => {
        fetchStatus(true);
    };

    const handleStop = async () => {
        if (!confirm('Are you sure you want to stop this run?')) {
            return;
        }

        setCancelling(true);
        setError(null);

        try {
            const token = await getAccessToken();
            await cancelRun(runid, token);

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
        <Box sx={{ maxWidth: 'md', mx: 'auto', p: 3 }}>
            <Typography variant="h5" gutterBottom>
                Run Status
            </Typography>
            <Typography variant="body2" color="text.secondary" paragraph>
                This run has been submitted. You can check its status below.
            </Typography>

            <Paper sx={{ p: 3, mb: 3 }}>
                <Stack spacing={3}>
                    <Box>
                        <Typography variant="caption" color="text.secondary">
                            Status
                        </Typography>
                        <Box sx={{ mt: 1 }}>
                            <Chip
                                label={runDetails.status.toUpperCase()}
                                color={getStatusColor(runDetails.status)}
                                size="medium"
                            />
                        </Box>
                    </Box>

                    <Divider />

                    <Box>
                        <Typography variant="caption" color="text.secondary">
                            Execution ID
                        </Typography>
                        <Typography
                            variant="body2"
                            sx={{ fontFamily: 'monospace', wordBreak: 'break-all', mt: 0.5 }}>
                            {runDetails.execution_id || 'Not submitted yet'}
                        </Typography>
                    </Box>

                    <Box>
                        <Typography variant="caption" color="text.secondary">
                            Created At
                        </Typography>
                        <Typography variant="body2" sx={{ mt: 0.5 }}>
                            {new Date(runDetails.created_at).toLocaleString()}
                        </Typography>
                    </Box>

                    {runDetails.status_checked_at && (
                        <Box>
                            <Typography variant="caption" color="text.secondary">
                                Last Checked
                            </Typography>
                            <Typography variant="body2" sx={{ mt: 0.5 }}>
                                {new Date(runDetails.status_checked_at).toLocaleString()}
                            </Typography>
                        </Box>
                    )}

                    {error && <Alert severity="error">{error}</Alert>}

                    <Stack direction="row" spacing={2}>
                        <Button
                            variant="outlined"
                            startIcon={
                                refreshing ? <CircularProgress size={16} /> : <RefreshIcon />
                            }
                            onClick={handleRefresh}
                            disabled={refreshing || cancelling}
                            sx={{ flex: 1 }}>
                            {refreshing ? 'Refreshing...' : 'Refresh Status'}
                        </Button>
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
                    </Stack>
                </Stack>
            </Paper>

            {executionStatus && (
                <Paper sx={{ p: 2, bgcolor: 'grey.50' }}>
                    <Typography variant="caption" color="text.secondary" gutterBottom>
                        Execution Details
                    </Typography>
                    <Box
                        component="pre"
                        sx={{
                            fontSize: '0.75rem',
                            overflow: 'auto',
                            maxHeight: 300,
                            fontFamily: 'monospace',
                        }}>
                        {JSON.stringify(executionStatus, null, 2)}
                    </Box>
                </Paper>
            )}
        </Box>
    );
}
