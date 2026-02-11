'use client';

import { useCallback, useEffect, useState, useRef } from 'react';
import {
    Box,
    Button,
    Typography,
    CircularProgress,
    Alert,
    styled,
    List,
    ListItem,
    useMediaQuery,
    Link,
} from '@mui/material';
import StopCircleOutlinedIcon from '@mui/icons-material/StopCircleOutlined';
import CloseIcon from '@mui/icons-material/Close';
import CloseFullscreenOutlinedIcon from '@mui/icons-material/CloseFullscreenOutlined';
import IconButton from '@mui/material/IconButton';
import HourglassTopOutlinedIcon from '@mui/icons-material/HourglassTopOutlined';
import OpenInFullOutlinedIcon from '@mui/icons-material/OpenInFullOutlined';
import SettingsOutlinedIcon from '@mui/icons-material/SettingsOutlined';
import ShareOutlinedIcon from '@mui/icons-material/ShareOutlined';

import { getRunsApi } from '@/api/RunsApi';
import { Run, getRunFromApi } from '@/types/Run';
import { ExperimentGraph } from '@/runs/components/ExperimentGraph';
import { ExperimentsTable } from '@/runs/components/ExperimentsTable';
import { ExperimentDetails } from '@/runs/components/ExperimentDetails';
import { RunExperimentsProvider, useRunExperiments } from '@/contexts/RunExperimentsContext';
import { TopSurprisalsList } from '@/runs/components/TopSurprisalsList';
import { useSearchValue, useURLSearchParams } from '@/contexts/URLSearchParamsContext';
import { StatusChip } from '@/runs/components/StatusChip';
import { RunParametersModal } from '@/runs/components/RunParametersModal';
import {
    mkCloseExperimentDetailsPanelAttrs,
    mkSessionConfigBtnAttrs,
} from '@/analytics/runDetails';
import { getRunStatusString } from '@/runs/utils/runUtils';
import { useToasts } from '@/contexts/ToastsContext';

const toSentenceCase = (str: string): string => {
    return str.charAt(0).toUpperCase() + str.slice(1).toLowerCase();
};

interface RunStatusProps {
    runid: string;
    onRunCancelled?: () => void;
    /** Optional user ID for viewing public runs (e.g., "samples") */
    userid?: string;
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
export default function RunStatus({ runid, onRunCancelled, userid }: RunStatusProps) {
    const api = getRunsApi();

    const [run, setRun] = useState<Run | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [cancelling, setCancelling] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [, setTick] = useState(0);

    const fetchStatus = async () => {
        setIsLoading(true);
        setError(null);

        try {
            // Pass userid (can be undefined for authenticated user's own runs)
            const response = await api.getRun({ userid, runId: runid });
            const run = getRunFromApi(response.data);

            setRun(run);
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

    // Run is read-only if viewing another user's run (userid prop is provided)
    const isReadOnly = !!userid;
    const canStop = !isReadOnly && run?.details?.status === 'RUNNING';
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
        <RunExperimentsProvider runid={runid} userid={userid} autoStart>
            <RunStatusContent
                run={run as Run & { details: NonNullable<Run['details']> }}
                error={error}
                canStop={canStop}
                cancelling={cancelling}
                handleStop={handleStop}
                experimentsLabel={experimentsLabel}
                isReadOnly={isReadOnly}
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
    isReadOnly: boolean;
}

function RunStatusContent({
    run,
    error,
    canStop,
    cancelling,
    handleStop,
    experimentsLabel,
    isReadOnly,
}: RunStatusContentProps) {
    const runsApi = getRunsApi();
    const {
        experiments,
        selectedExperiment,
        selectExperiment,
        isLoading: isLoadingExperiments,
    } = useRunExperiments();
    const [isParametersModalOpen, setIsParametersModalOpen] = useState(false);
    const [isTableExpanded, setIsTableExpanded] = useState(false);
    const [isDetailsExpanded, setIsDetailsExpanded] = useState(false);
    const isTreeVisible = useMediaQuery('(min-width:1000px)');
    const { addSuccessToast, addErrorToast } = useToasts();

    // URL synchronization
    const { setSearchParam, deleteSearchParam } = useURLSearchParams();
    const expParam = useSearchValue('exp');
    const hasInitiallySelected = useRef(false);

    const onShareClick = useCallback(
        async (event: React.MouseEvent<HTMLButtonElement>) => {
            event.preventDefault();

            const shareUrl = `${window.location.origin}/runs/shared/${run.id}`;
            const sharePromise = navigator.clipboard.writeText(shareUrl);

            const apiPromise = runsApi.shareRun({
                runId: run.id,
                isShared: true,
            });

            try {
                await sharePromise;
                addSuccessToast('Share URL copied to clipboard.', shareUrl);
                await apiPromise;
            } catch (err) {
                addErrorToast('Error sharing run.');
                console.error('Error sharing run:', err);
            }
        },
        [run.id]
    );

    // Read from URL: Initial selection when exp param is present
    useEffect(() => {
        if (hasInitiallySelected.current || !expParam) return;
        if (isLoadingExperiments || experiments.length === 0) return;

        const expId = parseInt(expParam, 10);
        if (!expId || expId <= 0 || isNaN(expId)) return;

        const experimentToSelect = experiments.find((exp) => exp.idInRun === expId);
        if (experimentToSelect) {
            selectExperiment(experimentToSelect);
            hasInitiallySelected.current = true;
        }
    }, [expParam, experiments, isLoadingExperiments, selectExperiment]);

    // Write to URL: Update URL when selection changes
    useEffect(() => {
        if (selectedExperiment) {
            setSearchParam('exp', selectedExperiment.idInRun.toString());
        } else if (hasInitiallySelected.current) {
            // Only delete if we've previously selected (don't delete on initial load)
            deleteSearchParam('exp');
        }
    }, [selectedExperiment, setSearchParam, deleteSearchParam]);

    const isRunning = !!run.stats?.pendingExperiments && run.details.status !== 'FAILED';

    return (
        <Container>
            <PanelLayout>
                {isTreeVisible && (
                    <Background>
                        <ExperimentGraph />
                    </Background>
                )}
                <TablePanel $isExpanded={isTableExpanded}>
                    <RunHeader>
                        <Box>
                            <RunHeaderName>{run.name}</RunHeaderName>
                            <RunHeaderSubtitle>
                                <StyledListItem>
                                    {getRunStatusString(run.details, experiments)}
                                </StyledListItem>

                                <StyledListItem>
                                    <StatusChip
                                        label={toSentenceCase(run.details.status)}
                                        size="small"
                                        $status={run.details.status}
                                    />
                                </StyledListItem>
                            </RunHeaderSubtitle>

                            {isRunning && (
                                <>
                                    <Typography variant="caption">
                                        AutoDiscovery is running. New findings will populate the
                                        table below automatically. You can click on any hypothesis
                                        to review the details while the run continues.
                                    </Typography>
                                    <br />
                                    <Typography variant="caption">
                                        Feel free to navigate away; your results will be here when
                                        the analysis is complete.
                                    </Typography>
                                </>
                            )}
                            {run.details.status === 'FAILED' && (
                                <Typography variant="caption">
                                    AutoDiscovery failed. We weren't able to finish this analysis.
                                    You might want to try again. If you keep seeing this message,
                                    please share your feedback with us{' '}
                                    <Link
                                        href="https://docs.google.com/forms/d/e/1FAIpQLScmKqOj9EuOrfNlO0ySm_5ITPH80anDgC3FDBuSEeesgztv1Q/viewform"
                                        rel="noopener noreferrer"
                                        target="_blank">
                                        via this form.
                                    </Link>
                                </Typography>
                            )}
                            {error && <Alert severity="error">{error}</Alert>}
                        </Box>
                        <LargeScreenAction>
                            <RunHeaderExpandButton
                                onClick={() => setIsTableExpanded(!isTableExpanded)}>
                                {isTableExpanded ? (
                                    <CloseFullscreenOutlinedIcon />
                                ) : (
                                    <OpenInFullOutlinedIcon />
                                )}
                            </RunHeaderExpandButton>
                        </LargeScreenAction>
                    </RunHeader>

                    <RunContent>
                        <TopSurprisalsList />

                        <RunToolbar>
                            {run.stats && (
                                <ExperimentCount>
                                    <HourglassTopOutlinedIcon />
                                    {isLoadingExperiments ? (
                                        'Loading experiments...'
                                    ) : (
                                        <>
                                            {experiments.length}/{run.stats.requestedExperiments}{' '}
                                            {experimentsLabel}
                                        </>
                                    )}
                                </ExperimentCount>
                            )}
                            <RunToolbarButtons>
                                <ParametersButton
                                    variant="outlined"
                                    startIcon={<SettingsOutlinedIcon />}
                                    onClick={() => setIsParametersModalOpen(true)}
                                    {...mkSessionConfigBtnAttrs({ runId: run.id })}>
                                    Session Configuration
                                </ParametersButton>
                                {!isReadOnly && (
                                    <ParametersButton
                                        variant="outlined"
                                        startIcon={<ShareOutlinedIcon />}
                                        onClick={onShareClick}>
                                        Share
                                    </ParametersButton>
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
                            </RunToolbarButtons>
                        </RunToolbar>

                        <ExperimentsTable runStats={run.stats} />
                    </RunContent>
                </TablePanel>

                {!!selectedExperiment && (
                    <DetailsPanel $isExpanded={isDetailsExpanded}>
                        <DetailsActions>
                            <LargeScreenAction>
                                <DetailsActionButton
                                    onClick={() => setIsDetailsExpanded(!isDetailsExpanded)}
                                    size="small">
                                    {isDetailsExpanded ? (
                                        <CloseFullscreenOutlinedIcon />
                                    ) : (
                                        <OpenInFullOutlinedIcon />
                                    )}
                                </DetailsActionButton>
                            </LargeScreenAction>
                            <DetailsActionButton
                                onClick={() => selectExperiment(null)}
                                size="small"
                                {...mkCloseExperimentDetailsPanelAttrs({ runId: run.id })}>
                                <CloseIcon />
                            </DetailsActionButton>
                        </DetailsActions>
                        <ExperimentDetails experiment={selectedExperiment} />
                    </DetailsPanel>
                )}
            </PanelLayout>

            <RunParametersModal
                open={isParametersModalOpen}
                onClose={() => setIsParametersModalOpen(false)}
                metadata={run.metadata}
            />
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
    padding: ${({ theme }) => theme.spacing(0, 2, 2)};
    justify-content: space-between;
    position: relative;

    @container run-status (width < 1000px) {
        display: grid;
    }

    @container run-status (width < 600px) {
        padding: ${({ theme }) => theme.spacing(0, 1, 1)};
    }

    @container run-status (width < 425px) {
        padding: 0;
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
    min-width: 0;
    width: ${({ $isExpanded }) => ($isExpanded ? '100%' : '500px')};
    background-color: #163638f3;
    border-radius: 12px;
    display: flex;
    flex-direction: column;
    gap: ${({ theme }) => theme.spacing(2)};
    overflow: auto;
    z-index: 2;

    @container run-status (width < 1000px) {
        flex: initial;
        width: calc(100cqw - 20px);
        grid-row: 1;
        grid-column: 1;
    }

    @container run-status (width < 600px) {
        width: 100%;
    }
`;

const DetailsPanel = styled('div')<{ $isExpanded: boolean }>`
    flex: 0 1 auto;
    max-width: ${({ $isExpanded }) => ($isExpanded ? 'initial' : '500px')};
    background-color: #163638f3;
    border-radius: 12px;
    position: ${({ $isExpanded }) => ($isExpanded ? 'absolute' : 'relative')};
    overflow-y: auto;
    z-index: 2;
    top: 0;
    bottom: 0;

    @container run-status (width < 1000px) {
        flex: 1 1 auto;
        max-width: initial;
        position: relative;
        width: calc(100cqw - 20px);
        grid-row: 1;
        grid-column: 1;
    }

    @container run-status (width < 600px) {
        width: 100%;
    }
`;

const DetailsActions = styled('div')`
    display: flex;
    gap: ${({ theme }) => theme.spacing(1)};
    position: absolute;
    top: ${({ theme }) => theme.spacing(2)};
    right: ${({ theme }) => theme.spacing(2)};
`;

const DetailsActionButton = styled(IconButton)`
    color: ${({ theme }) => theme.color['cream-50'].rgba.toString()};
`;

const StopButton = styled(Button)`
    border: 1px solid ${({ theme }) => theme.color['error-red-60'].rgba.toString()};
    color: ${({ theme }) => theme.color['error-red-100'].hex};

    &.Mui-disabled {
        color: ${({ theme }) => theme.color['error-red-60'].hex};
    }
`;

const RunToolbarButtons = styled('div')`
    display: flex;
    gap: ${({ theme }) => theme.spacing(1)};
`;

const ParametersButton = styled(Button)`
    border: 1px solid ${({ theme }) => theme.color['cream-20'].rgba.toString()};
    color: ${({ theme }) => theme.color['cream-100'].hex};

    &:hover {
        border: 1px solid ${({ theme }) => theme.color['cream-40'].rgba.toString()};
    }
`;

const RunHeader = styled('div')`
    border-bottom: 1px solid ${({ theme }) => theme.color['cream-10'].rgba.toString()};
    color: ${({ theme }) => theme.color['cream-100'].hex};
    display: flex;
    justify-content: space-between;
    padding: ${({ theme }) => theme.spacing(3)};
`;

const RunHeaderName = styled('h1')`
    color: ${({ theme }) => theme.color['green-100'].hex};
    font-family: 'PP Telegraf', Manrope, sans-serif;
    font-weight: 700;
    font-size: 20px;
    line-height: 24px;
    margin: 0;
    flex: 1 1 auto;
`;

const RunContent = styled(Box)`
    padding: ${({ theme }) => theme.spacing(3)};

    @container run-status (width < 700px) {
        padding: ${({ theme }) => theme.spacing(1)};
    }

    @container run-status (width < 500px) {
        padding: ${({ theme }) => theme.spacing(0.5)};
    }
`;

const RunHeaderExpandButton = styled(IconButton)`
    color: ${({ theme }) => theme.color['cream-50'].rgba.toString()};
`;

const LargeScreenAction = styled('div')`
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
    font-weight: normal;
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

const RunToolbar = styled('div')`
    display: flex;
    justify-content: space-between;
`;
