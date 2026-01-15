'use client';

import { useState } from 'react';
import {
    Box,
    Grid,
    Typography,
    CircularProgress,
    Alert,
    Button,
    Paper,
} from '@mui/material';
import { useAuth0 } from '@/app/contexts/Auth0Context';
import RunsList from './components/RunsList';
import RunSetup from './components/RunSetup';
import RunStatus from './components/RunStatus';
import { getRun, type RunDetails } from './actions';

type Step = 'idle' | 'setup' | 'submitted';

/**
 * Main runs page for creating and managing autodiscovery runs.
 *
 * Layout:
 * - Left sidebar: RunsList component (25% width)
 * - Right content: Run setup or status view (75% width)
 *
 * Flow:
 * 1. User creates new run → setup page (datasets + configuration)
 * 2. User submits run → status view
 */
export default function RunsPage() {
    const { isAuthenticated, isLoading, user, getAccessToken } = useAuth0();

    const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
    const [currentStep, setCurrentStep] = useState<Step>('idle');
    const [runDetails, setRunDetails] = useState<RunDetails | null>(null);
    const [checkingRun, setCheckingRun] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleRunCreated = (runid: string) => {
        setSelectedRunId(runid);
        setCurrentStep('setup');
        setRunDetails(null);
    };

    const handleSelectRun = async (runid: string) => {
        setSelectedRunId(runid);
        setCheckingRun(true);
        setError(null);

        try {
            const token = await getAccessToken();
            const runData = await getRun(runid, token);

            setRunDetails(runData.run_details || null);

            // Check if run has been submitted
            if (
                runData.run_details?.execution_id ||
                (runData.run_details?.status &&
                    runData.run_details.status.toUpperCase() !== 'CREATED')
            ) {
                // Run has been submitted, show status
                setCurrentStep('submitted');
            } else {
                // Run hasn't been submitted yet, allow setup
                setCurrentStep('setup');
            }
        } catch (err) {
            console.error('Error loading run:', err);
            setError(err instanceof Error ? err.message : 'Failed to load run');
            setCurrentStep('setup');
        } finally {
            setCheckingRun(false);
        }
    };

    const handleSubmitSuccess = async () => {
        // Fetch the updated run details to get execution_id
        try {
            const token = await getAccessToken();
            const runData = await getRun(selectedRunId!, token);
            setRunDetails(runData.run_details || null);
        } catch (err) {
            console.error('Error fetching run details after submission:', err);
        }
        setCurrentStep('submitted');
    };

    const handleStartNewRun = () => {
        setSelectedRunId(null);
        setCurrentStep('idle');
        setRunDetails(null);
    };

    if (isLoading) {
        return (
            <Box
                sx={{
                    display: 'flex',
                    justifyContent: 'center',
                    alignItems: 'center',
                    minHeight: '100vh',
                }}>
                <CircularProgress />
            </Box>
        );
    }

    if (!isAuthenticated) {
        return (
            <Box sx={{ p: 3 }}>
                <Alert severity="warning">
                    Please log in to create and manage runs.
                </Alert>
            </Box>
        );
    }

    return (
        <Box sx={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
            <Grid container sx={{ height: '100%' }}>
                {/* Sidebar */}
                <Grid
                    item
                    xs={12}
                    md={3}
                    sx={{
                        height: '100%',
                        overflow: 'auto',
                        borderRight: 1,
                        borderColor: 'divider',
                    }}>
                    <RunsList
                        selectedRunId={selectedRunId}
                        onSelectRun={handleSelectRun}
                        onRunCreated={handleRunCreated}
                    />
                </Grid>

                {/* Main content */}
                <Grid
                    item
                    xs={12}
                    md={9}
                    sx={{
                        height: '100%',
                        overflow: 'auto',
                        bgcolor: 'grey.50',
                    }}>
                    {error && (
                        <Box sx={{ p: 3 }}>
                            <Alert severity="error" onClose={() => setError(null)}>
                                {error}
                            </Alert>
                        </Box>
                    )}

                    {checkingRun && (
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
                    )}

                    {!checkingRun && currentStep === 'idle' && (
                        <Box
                            sx={{
                                display: 'flex',
                                justifyContent: 'center',
                                alignItems: 'center',
                                height: '100%',
                                p: 3,
                            }}>
                            <Paper sx={{ p: 4, maxWidth: 'sm', textAlign: 'center' }}>
                                <Typography variant="h5" gutterBottom>
                                    Welcome to Autodiscovery Runs
                                </Typography>
                                <Typography variant="body1" color="text.secondary" paragraph>
                                    Create a new run or select an existing run from the sidebar to
                                    get started.
                                </Typography>
                                <Typography variant="body2" color="text.secondary">
                                    {user?.name && `Logged in as: ${user.name}`}
                                </Typography>
                            </Paper>
                        </Box>
                    )}

                    {!checkingRun && currentStep === 'setup' && selectedRunId && (
                        <RunSetup runid={selectedRunId} onSubmitSuccess={handleSubmitSuccess} />
                    )}

                    {!checkingRun && currentStep === 'submitted' && selectedRunId && (
                        <RunStatus runid={selectedRunId} onRunCancelled={handleStartNewRun} />
                    )}
                </Grid>
            </Grid>
        </Box>
    );
}
