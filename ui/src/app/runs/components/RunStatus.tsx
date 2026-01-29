'use client';

import { useEffect, useState } from 'react';
import {
    Box,
    Button,
    Typography,
    CircularProgress,
    Alert,
    styled,
    List,
    ListItem,
} from '@mui/material';
import StopCircleOutlinedIcon from '@mui/icons-material/StopCircleOutlined';
import CloseIcon from '@mui/icons-material/Close';
import IconButton from '@mui/material/IconButton';
import HourglassTopOutlinedIcon from '@mui/icons-material/HourglassTopOutlined';

import { getRunsApi } from '@/api/RunsApi';
import { Run, getRunFromApi } from '@/types/Run';
import { ExperimentGraph } from '@/runs/components/ExperimentGraph';
import { ExperimentsTable } from '@/runs/components/ExperimentsTable';
import { ExperimentDetails } from './ExperimentDetails';
import { RunExperimentsProvider, useRunExperiments } from '@/contexts/RunExperimentsContext';
import { getRelativeTime } from '@/utils/timeUtils';
import { StatusChip } from '@/runs/components/StatusChip';

interface RunStatusProps {
    runid: string;
    onRunCancelled?: () => void;
}

const ENABLE_GRAPH_VIZ = false; // Hide the graph until we are ready to implement

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
    const [isLoading, setIsLoading] = useState(true);
    const [cancelling, setCancelling] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
    const [, setTick] = useState(0);

    const fetchStatus = async () => {
        setIsLoading(true);
        setError(null);

        try {
            const response = await api.getRun(runid);
            const run = getRunFromApi(response.data);

            setRun(run);
            setLastUpdated(new Date());
        } catch (err) {
            console.error('Error fetching run status:', err);
            setError(err instanceof Error ? err.message : 'Failed to load run status');
        } finally {
            setIsLoading(false);
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
    }, [run?.details?.status]);

    // Update relative time display every 30 seconds
    useEffect(() => {
        const interval = setInterval(() => {
            setTick((prev) => prev + 1);
        }, 30000);

        return () => clearInterval(interval);
    }, []);

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

    const canStop = run?.details?.status === 'RUNNING';
    const experimentsLabel = run?.stats?.requestedExperiments === 1 ? 'experiment' : 'experiments';

    if (isLoading && !run) {
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
                experimentsLabel={experimentsLabel}
                lastUpdated={lastUpdated}
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
    experimentsLabel: string;
    lastUpdated: Date | null;
}

function RunStatusContent({
    run,
    error,
    canStop,
    cancelling,
    handleStop,
    experimentsLabel,
    lastUpdated,
}: RunStatusContentProps) {
    const { experiments, selectedExperiment, selectExperiment } = useRunExperiments();
    // const [isTableExpanded, setIsTableExpanded] = useState(false);
    const isTableExpanded = true;
    const setIsTableExpanded = (...args: any[]) => {}; // eslint-disable-line @typescript-eslint/no-unused-vars

    return (
        <Container>
            <PanelLayout>
                {ENABLE_GRAPH_VIZ && (
                    <Background>
                        <ExperimentGraph />
                    </Background>
                )}
                <TablePanel
                    $isExpanded={isTableExpanded}
                    key={`${isTableExpanded ? 'expanded' : 'collapsed'} ${selectedExperiment?.experimentId ?? ''}`}>
                    <RunHeader>
                        <Box>
                            <RunHeaderName>{run.name}</RunHeaderName>
                            <RunHeaderSubtitle>
                                <StyledListItem>
                                    Started{' '}
                                    {new Date(run.details.createdAt).toLocaleString(undefined, {
                                        dateStyle: 'short',
                                        timeStyle: 'short',
                                    })}
                                </StyledListItem>
                                <StyledListItem>
                                    Last updated {getRelativeTime(lastUpdated)}
                                </StyledListItem>
                                <StyledListItem>
                                    <StatusChip
                                        label={run.details.status}
                                        size="small"
                                        $status={run.details.status}
                                    />
                                </StyledListItem>
                            </RunHeaderSubtitle>

                            {!!run.stats?.pendingExperiments && (
                                <>
                                    <Typography variant="caption">
                                        AutoDiscovery is running. New findings will populate the
                                        table below automatically. You can click on any hypothesis
                                        to review the details while the run continues.
                                    </Typography>
                                    <br />
                                    <Typography variant="caption">
                                        Feel free to close this tab. We will email you when the full
                                        analysis is complete.
                                    </Typography>
                                </>
                            )}
                            {error && <Alert severity="error">{error}</Alert>}
                        </Box>
                        {ENABLE_GRAPH_VIZ && (
                            <RunHeaderExpandButton
                                onClick={() => setIsTableExpanded(!isTableExpanded)}>
                                {isTableExpanded ? 'Collapse' : 'Expand'}
                            </RunHeaderExpandButton>
                        )}
                    </RunHeader>

                    <Box sx={{ padding: 3 }}>
                        <RunStats>
                            {run.stats && (
                                <ExperimentCount>
                                    <HourglassTopOutlinedIcon />
                                    {run.stats.requestedExperiments ? (
                                        <>
                                            {experiments.length}/{run.stats.requestedExperiments}{' '}
                                            {experimentsLabel}
                                        </>
                                    ) : (
                                        'Loading experiments...'
                                    )}
                                </ExperimentCount>
                            )}
                            {canStop && (
                                <StopButton
                                    variant="outlined"
                                    startIcon={
                                        cancelling ? (
                                            <CircularProgress size={16} />
                                        ) : (
                                            <StopCircleOutlinedIcon />
                                        )
                                    }
                                    onClick={handleStop}
                                    disabled={cancelling}>
                                    {cancelling ? 'Stopping...' : 'Stop run'}
                                </StopButton>
                            )}
                        </RunStats>

                        <ExperimentsTable runStats={run.stats} />
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
    overflow-y: scroll;
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
    border: 1px solid ${({ theme }) => theme.color['error-red-60'].rgba.toString()};
    color: ${({ theme }) => theme.color['error-red-100'].hex};

    &.Mui-disabled {
        color: ${({ theme }) => theme.color['error-red-60'].hex};
    }
`;

const RunHeader = styled('div')`
    border-bottom: 1px solid ${({ theme }) => theme.color['cream-10'].rgba.toString()};
    color: ${({ theme }) => theme.color['cream-100'].hex};
    display: flex;
    justify-content: space-between;
    padding: ${({ theme }) => theme.spacing(3)};
`;

const RunHeaderName = styled('div')`
    color: ${({ theme }) => theme.color['green-100'].hex};
    flex: 1 1 auto;
    font-size: 1.25rem;
    font-weight: 700;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
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

const RunHeaderSubtitle = styled(List)`
    align-items: center;
    color: ${({ theme }) => theme.color['cream-100'].hex};
    display: flex;
    flex-direction: row;
    font-weight: 700;
    gap: ${({ theme }) => theme.spacing(1)};
    padding: 0;
`;

const StyledListItem = styled(ListItem)`
    display: inline-flex;
    padding: 0;
    width: auto;

    &:not(:last-child)::after {
        content: '•';
        margin-left: ${({ theme }) => theme.spacing(1)};
        color: ${({ theme }) => theme.color['cream-100'].hex};
    }
`;

const RunStats = styled('div')`
    display: flex;
    justify-content: space-between;
`;
