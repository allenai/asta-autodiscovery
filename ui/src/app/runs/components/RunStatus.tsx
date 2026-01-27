'use client';

import { useEffect, useState } from 'react';
import { Box, Button, Typography, CircularProgress, Alert, Chip, styled } from '@mui/material';
import StopCircleOutlinedIcon from '@mui/icons-material/StopCircleOutlined';
import CloseIcon from '@mui/icons-material/Close';
import IconButton from '@mui/material/IconButton';
import HourglassTopOutlinedIcon from '@mui/icons-material/HourglassTopOutlined';
import ScienceOutlinedIcon from '@mui/icons-material/ScienceOutlined';

import { getRunsApi } from '@/api/RunsApi';
import { Run, getRunFromApi } from '@/types/Run';
import { ExperimentGraph } from '@/runs/components/ExperimentGraph';
import { ExperimentsTable } from '@/runs/components/ExperimentsTable';
import { ExperimentDetails } from './ExperimentDetails';
import { RunExperimentsProvider, useRunExperiments } from '@/contexts/RunExperimentsContext';

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

    const [run, setRun] = useState<Run | null>(null);
    const [loading, setLoading] = useState(true);
    const [cancelling, setCancelling] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const fetchStatus = async () => {
        setLoading(true);
        setError(null);

        try {
            const response = await api.getRun(runid);
            const run = getRunFromApi(response.data);

            setRun(run);
        } catch (err) {
            console.error('Error fetching run status:', err);
            setError(err instanceof Error ? err.message : 'Failed to load run status');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchStatus();

        // Auto-refresh every 30 seconds if run is still running
        const interval = setInterval(() => {
            if (
                run?.details?.status === 'RUNNING' ||
                run?.details?.status === 'PENDING' ||
                run?.details?.status === 'QUEUED'
            ) {
                fetchStatus();
            }
        }, 30000);

        return () => clearInterval(interval);
    }, [runid]);

    const handleStop = async () => {
        if (!confirm('Are you sure you want to stop this run?')) {
            return;
        }

        setCancelling(true);
        setError(null);

        try {
            await api.cancelRun(runid);

            // Refresh status
            await fetchStatus();

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

    const canStop = run?.details?.status === 'RUNNING';
    const experimentsLabel = run?.stats?.requestedExperiments === 1 ? 'experiment' : 'experiments';

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

    if (!run?.details) {
        return (
            <Box sx={{ p: 3 }}>
                <Alert severity="error">Run details not found</Alert>
            </Box>
        );
    }

    return (
        <RunExperimentsProvider runid={runid} autoStart>
            <RunStatusContent
                run={run as Run & { details: NonNullable<Run['details']> }}
                error={error}
                canStop={canStop}
                cancelling={cancelling}
                handleStop={handleStop}
                getStatusColor={getStatusColor}
                experimentsLabel={experimentsLabel}
            />
        </RunExperimentsProvider>
    );
}

interface RunStatusContentProps {
    run: Run & { details: NonNullable<Run['details']> };
    error: string | null;
    canStop: boolean;
    cancelling: boolean;
    handleStop: () => void;
    getStatusColor: (status: string) => any;
    experimentsLabel: string;
}

function RunStatusContent({
    run,
    error,
    canStop,
    cancelling,
    handleStop,
    getStatusColor,
    experimentsLabel,
}: RunStatusContentProps) {
    const { selectedExperiment, selectExperiment } = useRunExperiments();
    const [isTableExpanded, setIsTableExpanded] = useState(false);

    return (
        <Container>
            <PanelLayout>
                <Background>
                    <ExperimentGraph />
                </Background>
                <TablePanel
                    $isExpanded={isTableExpanded}
                    key={`${isTableExpanded ? 'expanded' : 'collapsed'} ${selectedExperiment?.experimentId ?? ''}`}>
                    <RunHeader>
                        <RunHeaderName>{run.name}</RunHeaderName>
                        <RunHeaderExpandButton onClick={() => setIsTableExpanded(!isTableExpanded)}>
                            {isTableExpanded ? 'Collapse' : 'Expand'}
                        </RunHeaderExpandButton>
                    </RunHeader>

                    <Box sx={{ padding: 3 }}>
                        {error && <Alert severity="error">{error}</Alert>}
                        <Chip
                            label={run.details.status.toUpperCase()}
                            color={getStatusColor(run.details.status)}
                            size="medium"
                        />
                        {run.details.statusCheckedAt && (
                            <Box>
                                <Typography variant="caption">
                                    Last Checked:{' '}
                                    {new Date(run.details.statusCheckedAt).toLocaleString()}
                                </Typography>
                            </Box>
                        )}
                        {run.stats && (
                            <Box display="flex" gap={1.5}>
                                <ExperimentCount>
                                    <ScienceOutlinedIcon />
                                    {run.stats.requestedExperiments ? (
                                        <>
                                            {run.stats.requestedExperiments} {experimentsLabel}
                                        </>
                                    ) : (
                                        'Loading experiments...'
                                    )}
                                </ExperimentCount>
                                {!!run.stats.pendingExperiments && (
                                    <ExperimentCount>
                                        <HourglassTopOutlinedIcon />
                                        {run.stats.pendingExperiments} pending
                                    </ExperimentCount>
                                )}
                            </Box>
                        )}
                        {canStop && (
                            <StopButton
                                variant="text"
                                startIcon={
                                    cancelling ? (
                                        <CircularProgress size={16} />
                                    ) : (
                                        <StopCircleOutlinedIcon />
                                    )
                                }
                                onClick={handleStop}
                                disabled={cancelling}>
                                {cancelling ? 'Stopping...' : 'Stop'}
                            </StopButton>
                        )}
                        <ExperimentsTable />
                    </Box>
                </TablePanel>

                {!!selectedExperiment && (
                    <DetailsPanel>
                        <>
                            <CloseDetailButton onClick={() => selectExperiment(null)} size="small">
                                <CloseIcon />
                            </CloseDetailButton>
                            <ExperimentDetails experiment={selectedExperiment} />
                        </>
                    </DetailsPanel>
                )}
            </PanelLayout>
        </Container>
    );
}

const Container = styled('div')`
    container: run-status / inline-size;
    height: 100%;
`;

const PanelLayout = styled('div')`
    color: ${({ theme }) => theme.color['cream-100'].hex};
    display: flex;
    gap: ${({ theme }) => theme.spacing(2)};
    height: 100%;
    padding: ${({ theme }) => theme.spacing(2)};
    justify-content: space-between;
    position: relative;

    @container run-status (width < 1000px) {
        display: grid;
    }
`;

const Background = styled('div')`
    position: absolute;
    inset: 0;
    z-index: 1;

    @container run-status (width < 1000px) {
        display: none;
    }
`;

const TablePanel = styled('div')<{ $isExpanded: boolean }>`
    flex: 0 1 auto;
    width: ${({ $isExpanded }) => ($isExpanded ? '100%' : '400px')};
    background-color: #163638f3;
    border-radius: ${({ theme }) => theme.shape.borderRadius}px;
    display: flex;
    flex-direction: column;
    gap: ${({ theme }) => theme.spacing(2)};
    z-index: 2;

    @container run-status (width < 1000px) {
        flex: initial;
        width: calc(100cqw - 20px);
        grid-row: 1;
        grid-column: 1;
    }
`;

const DetailsPanel = styled('div')`
    flex: 0 1 auto;
    max-width: 500px;
    background-color: #163638f3;
    border-radius: ${({ theme }) => theme.shape.borderRadius}px;
    padding: ${({ theme }) => theme.spacing(3)};
    position: relative;
    z-index: 2;

    @container run-status (width < 1000px) {
        flex: 1 1 auto;
        max-width: initial;
        width: calc(100cqw - 20px);
        grid-row: 1;
        grid-column: 1;
    }
`;

const CloseDetailButton = styled(IconButton)`
    color: ${({ theme }) => theme.color['cream-50'].rgba.toString()};
    position: absolute;
    top: ${({ theme }) => theme.spacing(2)};
    right: ${({ theme }) => theme.spacing(2)};
`;

const StopButton = styled(Button)`
    color: ${({ theme }) => theme.color['error-red-100'].hex};

    &.Mui-disabled {
        color: ${({ theme }) => theme.color['error-red-60'].hex};
    }
`;

const RunHeader = styled('div')`
    border-bottom: 1px solid ${({ theme }) => theme.color['cream-10'].rgba.toString()};
    display: flex;
    justify-content: space-between;
    padding: ${({ theme }) => theme.spacing(3)};
`;

const RunHeaderName = styled('div')`
    flex: 1 1 auto;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    color: ${({ theme }) => theme.color['green-100'].hex};
    font-size: 1.25rem;
`;

const RunHeaderExpandButton = styled(Button)`
    color: ${({ theme }) => theme.color['green-100'].hex};

    @container run-status (width < 1000px) {
        display: none;
    }
`;

const ExperimentCount = styled('div')`
    align-items: center;
    color: ${({ theme }) => theme.color['green-40'].rgba.toString()};
    display: flex;
    font-weight: 700;
    gap: ${({ theme }) => theme.spacing(0.5)};

    .MuiSvgIcon-root {
        font-size: 1.2rem;
    }
`;
