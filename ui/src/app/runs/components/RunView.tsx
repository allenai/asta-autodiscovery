'use client';

import { useCallback, useEffect, useState, useRef } from 'react';
import { useRouter } from 'next/navigation';
import {
    Box,
    Button,
    Typography,
    CircularProgress,
    Alert,
    styled,
    List,
    ListItem,
    Menu,
    MenuItem,
    ListItemIcon,
    ListItemText,
    Tooltip,
    useMediaQuery,
    Link,
    IconButton,
} from '@mui/material';
import FileDownloadOutlinedIcon from '@mui/icons-material/FileDownloadOutlined';
import RestartAltIcon from '@mui/icons-material/RestartAlt';
import BookmarkIcon from '@mui/icons-material/Bookmark';
import BookmarkBorderOutlinedIcon from '@mui/icons-material/BookmarkBorderOutlined';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import StopCircleOutlinedIcon from '@mui/icons-material/StopCircleOutlined';
import CloseIcon from '@mui/icons-material/Close';
import CloseFullscreenOutlinedIcon from '@mui/icons-material/CloseFullscreenOutlined';
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
    mkDownloadBtnAttrs,
    mkDownloadCsvMenuItemAttrs,
    mkDownloadJsonMenuItemAttrs,
    mkSessionConfigBtnAttrs,
} from '@/analytics/runDetails';
import {
    downloadCsv,
    downloadJson,
    ExportFormat,
    generateFilename,
    generateRunCsv,
    generateRunJson,
} from '@/utils/exportUtils';
import { getRunStatusString } from '@/runs/utils/runUtils';
import { useToasts } from '@/contexts/ToastsContext';
import { useRunBookmarks } from '@/contexts/RunBookmarksContext';
import {
    PanelGroup,
    Background,
    RunPanel,
    ExperimentPanel,
    ExperimentPanelBackdrop,
    LargeScreenAction,
    PanelDragHandle,
    usePanelWidthPx,
} from '@/runs/components/RunViewPanels';
import { useViewerRuns } from '@/contexts/ViewerRunsContext';
import { mkBookmarkRunBtnAttrs } from '@/analytics/run';
import {
    TEST_ID_SESSION_CONFIG_BUTTON,
    TEST_ID_SESSION_CONFIG_MODAL,
    TEST_ID_EXPERIMENT_DETAILS_PANEL,
    TEST_ID_EXPERIMENT_DETAILS_CLOSE,
} from '@/testIds';

const toSentenceCase = (str: string): string => {
    return str.charAt(0).toUpperCase() + str.slice(1).toLowerCase();
};

const getDatasetExpiryLabel = (expiresAt: string | null | undefined): string | null => {
    if (!expiresAt) return null;
    const now = new Date();
    const expiry = new Date(expiresAt);

    if (expiry <= now) {
        return 'Dataset expired';
    }

    const diffMs = expiry.getTime() - now.getTime();
    const diffHours = Math.ceil(diffMs / (1000 * 60 * 60));

    if (diffHours <= 24) {
        return `Dataset expires in ${diffHours} hour${diffHours === 1 ? '' : 's'}`;
    }

    const diffDays = Math.ceil(diffMs / (1000 * 60 * 60 * 24));
    const expiryFormatted = expiry.toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
    });
    return `Dataset available until ${expiryFormatted} (${diffDays} day${diffDays === 1 ? '' : 's'})`;
};

const isDatasetExpired = (expiresAt: string | null | undefined): boolean => {
    if (!expiresAt) return false;
    return new Date(expiresAt) <= new Date();
};

interface RunViewProps {
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
export default function RunView({ runid, onRunCancelled, userid }: RunViewProps) {
    const api = getRunsApi();
    const { viewerRuns, addViewerRun, updateViewerRun } = useViewerRuns();

    const run = viewerRuns?.[runid] ?? null;
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
            const fetchedRun = getRunFromApi(response.data);

            if (viewerRuns?.[runid]) {
                updateViewerRun(fetchedRun);
            } else {
                addViewerRun(fetchedRun);
            }
        } catch (err) {
            console.error('Error fetching run status:', err);
            setError(err instanceof Error ? err.message : 'Failed to load run status');
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        fetchStatus();

        // Auto-refresh every 30 seconds; also update relative time display
        const interval = setInterval(() => {
            setTick((prev) => prev + 1);
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
            <RunViewContent
                run={run as Run & { details: NonNullable<Run['details']> }}
                error={error}
                canStop={canStop}
                cancelling={cancelling}
                handleStop={handleStop}
                experimentsLabel={experimentsLabel}
            />
        </RunExperimentsProvider>
    );
}

interface RunViewContentProps {
    run: Run & { details: NonNullable<Run['details']> };
    error: string | null;
    canStop: boolean;
    cancelling: boolean;
    handleStop: () => void;
    experimentsLabel: string;
}

function RunViewContent({
    run,
    error,
    canStop,
    cancelling,
    handleStop,
    experimentsLabel,
}: RunViewContentProps) {
    const { isRunBookmarksEnabled, checkRunBookmarked, updateRunBookmark } = useRunBookmarks();
    const runsApi = getRunsApi();
    const router = useRouter();
    const { addViewerRun } = useViewerRuns();
    const {
        experiments,
        selectedExperiment,
        selectExperiment,
        isLoadingInitial: isLoadingInitialExperiments,
    } = useRunExperiments();
    const [isParametersModalOpen, setIsParametersModalOpen] = useState(false);
    const [isExpPanelExpanded, setIsExpPanelExpanded] = useState(false);
    const [downloadAnchorEl, setDownloadAnchorEl] = useState<null | HTMLElement>(null);
    const [overflowAnchorEl, setOverflowAnchorEl] = useState<null | HTMLElement>(null);
    const [isForking, setIsForking] = useState(false);
    const isTreeVisible = useMediaQuery('(min-width:1000px)');
    const isDragEnabled = useMediaQuery('(min-width:1200px)');
    const showCompactActions = useMediaQuery('(max-width:799px)');
    const { addSuccessToast, addErrorToast } = useToasts();

    const datasetExpired = isDatasetExpired(run.datasetExpiresAt);
    const datasetExpiryLabel = getDatasetExpiryLabel(run.datasetExpiresAt);
    const canFork = !datasetExpired && !isForking;

    const handleFork = useCallback(async () => {
        setIsForking(true);
        try {
            const { data } = await runsApi.forkRun({ parentRunId: run.id });
            const newRun = getRunFromApi(data);
            addViewerRun(newRun);
            router.push(`/runs/${newRun.id}`);
        } catch (err) {
            console.error('Fork error:', err);
            const message =
                err instanceof Error && err.message.includes('410')
                    ? 'Dataset has expired. Please create a new run and re-upload your data.'
                    : 'Failed to create new run from session.';
            addErrorToast(message);
        } finally {
            setIsForking(false);
        }
    }, [run.id, runsApi, addViewerRun, router, addErrorToast]);

    const [runPanelWidthPx, setRunPanelWidthPx] = usePanelWidthPx('runPanelWidthPx', 700);
    const [expPanelWidthPx, setExpPanelWidthPx] = usePanelWidthPx('expPanelWidthPx', 500);
    const [isClosingPanel, setIsClosingPanel] = useState(false);

    // URL synchronization
    const { setSearchParam, deleteSearchParam } = useURLSearchParams();
    const expParam = useSearchValue('exp');
    const hasInitiallySelected = useRef(false);
    const isUpdatingFromURL = useRef(false);
    const lastSyncedExpId = useRef<number | null>(null);

    const handleClosePanel = useCallback(() => {
        setIsClosingPanel(true);
        setTimeout(() => {
            selectExperiment(null);
            setIsExpPanelExpanded(false);
            setIsClosingPanel(false);
        }, 300);
    }, [selectExperiment]);

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
                addSuccessToast('Session URL copied to clipboard.', shareUrl);
                await apiPromise;
            } catch (err) {
                addErrorToast('Error sharing run.');
                console.error('Error sharing run:', err);
            }
        },
        [run.id, runsApi, addSuccessToast, addErrorToast]
    );

    const onShareExperimentClick = useCallback(async () => {
        if (!selectedExperiment) return;

        const shareUrl = `${window.location.origin}/runs/shared/${run.id}?exp=${selectedExperiment.idInRun}`;
        const sharePromise = navigator.clipboard.writeText(shareUrl);

        const apiPromise = runsApi.shareRun({
            runId: run.id,
            isShared: true,
        });

        try {
            await sharePromise;
            addSuccessToast('Experiment URL copied to clipboard.', shareUrl);
            await apiPromise;
        } catch (err) {
            addErrorToast('Error sharing experiment.');
            console.error('Error sharing experiment:', err);
        }
    }, [run.id, selectedExperiment?.idInRun, runsApi, addSuccessToast, addErrorToast]);

    const handleDownload = useCallback(
        (format: ExportFormat) => {
            setDownloadAnchorEl(null);

            try {
                const filename = generateFilename(run.name, format);

                switch (format) {
                    case 'json': {
                        const content = generateRunJson(experiments);
                        downloadJson(content, filename);
                        break;
                    }
                    case 'csv': {
                        const content = generateRunCsv(experiments);
                        downloadCsv(content, filename);
                        break;
                    }
                    default:
                        throw new Error(`Unsupported export format: ${format}`);
                }
            } catch (error) {
                console.error(`Failed to download ${format.toUpperCase()}:`, error);
                addErrorToast(`Failed to download ${format.toUpperCase()}`);
            }
        },
        [run.name, experiments, addErrorToast]
    );

    // Read from URL: Initial selection when exp param is present
    useEffect(() => {
        if (hasInitiallySelected.current || !expParam) return;
        if (isLoadingInitialExperiments || experiments.length === 0) return;

        const expId = parseInt(expParam, 10);
        if (!expId || expId <= 0 || isNaN(expId)) return;
        if (lastSyncedExpId.current === expId) return; // Prevent redundant

        const experimentToSelect = experiments.find((exp) => exp.idInRun === expId);
        if (experimentToSelect) {
            isUpdatingFromURL.current = true;
            selectExperiment(experimentToSelect);
            lastSyncedExpId.current = expId;
            hasInitiallySelected.current = true;
            isUpdatingFromURL.current = false;
        }
    }, [expParam, experiments, isLoadingInitialExperiments, selectExperiment]);

    // Write to URL: Update URL when selection changes
    useEffect(() => {
        if (isUpdatingFromURL.current) return; // BREAK CIRCULAR DEPENDENCY

        const currentExpId = selectedExperiment?.idInRun ?? null;
        if (lastSyncedExpId.current === currentExpId) return; // Already synced

        if (selectedExperiment) {
            setSearchParam('exp', selectedExperiment.idInRun.toString());
            lastSyncedExpId.current = selectedExperiment.idInRun;
        } else if (hasInitiallySelected.current) {
            // Only delete if we've previously selected (don't delete on initial load)
            deleteSearchParam('exp');
            lastSyncedExpId.current = null;
        }
    }, [selectedExperiment, setSearchParam, deleteSearchParam]);

    const isRunning = !!run.stats?.pendingExperiments && run.details.status !== 'FAILED';
    const isComplete =
        run.details.status === 'SUCCEEDED' ||
        run.details.status === 'FAILED' ||
        run.details.status === 'ERROR' ||
        run.details.status === 'CANCELLED';

    return (
        <Container>
            <PanelGroup>
                {isTreeVisible && (
                    <Background>
                        <ExperimentGraph />
                    </Background>
                )}
                <RunPanel
                    style={
                        {
                            '--run-panel-width': runPanelWidthPx ? `${runPanelWidthPx}px` : '700px',
                        } as React.CSSProperties
                    }>
                    <RunHeader>
                        <RunHeaderTopRow>
                            <Box sx={{ flex: '1 1 auto', minWidth: 0 }}>
                                <RunHeaderName>
                                    {isRunBookmarksEnabled && (
                                        <BookmarkButton
                                            size="small"
                                            aria-label={
                                                checkRunBookmarked(run.id)
                                                    ? 'Remove bookmark'
                                                    : 'Bookmark this session'
                                            }
                                            $isBookmarked={checkRunBookmarked(run.id)}
                                            onClick={() =>
                                                updateRunBookmark(run.id, {
                                                    isBookmarked: !checkRunBookmarked(run.id),
                                                })
                                            }
                                            {...mkBookmarkRunBtnAttrs({
                                                runId: run.id,
                                                isBookmarked: !checkRunBookmarked(run.id),
                                            })}>
                                            {checkRunBookmarked(run.id) ? (
                                                <BookmarkIcon />
                                            ) : (
                                                <BookmarkBorderOutlinedIcon />
                                            )}
                                        </BookmarkButton>
                                    )}
                                    {run.name}
                                </RunHeaderName>
                                {run.parentRunId && (
                                    <ParentRunInfo>
                                        Parent:{' '}
                                        <ParentRunLink
                                            href={`/runs/${run.parentRunId}`}
                                            underline="hover">
                                            {run.parentRunName || run.parentRunId}
                                        </ParentRunLink>
                                    </ParentRunInfo>
                                )}
                                {error && <Alert severity="error">{error}</Alert>}
                            </Box>
                            {isRunBookmarksEnabled && isComplete && (
                                <RunHeaderActions>
                                    {showCompactActions ? (
                                        <>
                                            <OverflowButton
                                                size="small"
                                                aria-label="More actions"
                                                onClick={(e) =>
                                                    setOverflowAnchorEl(e.currentTarget)
                                                }>
                                                <MoreVertIcon />
                                            </OverflowButton>
                                            <OverflowMenu
                                                anchorEl={overflowAnchorEl}
                                                open={!!overflowAnchorEl}
                                                onClose={() => setOverflowAnchorEl(null)}>
                                                <MenuItem
                                                    onClick={(
                                                        e: React.MouseEvent<HTMLLIElement>
                                                    ) => {
                                                        setOverflowAnchorEl(null);
                                                        onShareClick(
                                                            e as unknown as React.MouseEvent<HTMLButtonElement>
                                                        );
                                                    }}>
                                                    <ListItemIcon>
                                                        <ShareOutlinedIcon fontSize="small" />
                                                    </ListItemIcon>
                                                    <ListItemText>Share session</ListItemText>
                                                </MenuItem>
                                                <MenuItem
                                                    disabled={experiments.length === 0}
                                                    onClick={(e) => {
                                                        setOverflowAnchorEl(null);
                                                        setDownloadAnchorEl(e.currentTarget);
                                                    }}>
                                                    <ListItemIcon>
                                                        <FileDownloadOutlinedIcon fontSize="small" />
                                                    </ListItemIcon>
                                                    <ListItemText>Download</ListItemText>
                                                </MenuItem>
                                                <Tooltip
                                                    title={datasetExpiryLabel || ''}
                                                    placement="left">
                                                    <span>
                                                        <MenuItem
                                                            disabled={!canFork}
                                                            onClick={() => {
                                                                setOverflowAnchorEl(null);
                                                                handleFork();
                                                            }}>
                                                            <ListItemIcon>
                                                                {isForking ? (
                                                                    <CircularProgress
                                                                        size={16}
                                                                        sx={(theme) => ({
                                                                            color: theme.color[
                                                                                'green-100'
                                                                            ].hex,
                                                                        })}
                                                                    />
                                                                ) : (
                                                                    <RestartAltIcon fontSize="small" />
                                                                )}
                                                            </ListItemIcon>
                                                            <ListItemText>
                                                                {isForking
                                                                    ? 'Duplicating...'
                                                                    : 'Duplicate to new session'}
                                                            </ListItemText>
                                                        </MenuItem>
                                                    </span>
                                                </Tooltip>
                                            </OverflowMenu>
                                            <DownloadMenu
                                                anchorEl={downloadAnchorEl}
                                                open={!!downloadAnchorEl}
                                                onClose={() => setDownloadAnchorEl(null)}>
                                                <MenuItem
                                                    {...mkDownloadCsvMenuItemAttrs({
                                                        runId: run.id,
                                                    })}
                                                    onClick={() => handleDownload('csv')}>
                                                    CSV
                                                </MenuItem>
                                                <MenuItem
                                                    {...mkDownloadJsonMenuItemAttrs({
                                                        runId: run.id,
                                                    })}
                                                    onClick={() => handleDownload('json')}>
                                                    JSON
                                                </MenuItem>
                                            </DownloadMenu>
                                        </>
                                    ) : (
                                        <>
                                            <Tooltip
                                                title={
                                                    datasetExpiryLabel || 'Duplicate to new session'
                                                }
                                                placement="bottom">
                                                <span>
                                                    <ExpandingActionButton
                                                        onClick={handleFork}
                                                        disabled={!canFork}
                                                        size="small"
                                                        variant="outlined">
                                                        {isForking ? (
                                                            <CircularProgress
                                                                size={16}
                                                                sx={(theme) => ({
                                                                    color: theme.color['green-100']
                                                                        .hex,
                                                                })}
                                                            />
                                                        ) : (
                                                            <RestartAltIcon fontSize="small" />
                                                        )}
                                                        <ButtonLabel className="button-label">
                                                            {isForking
                                                                ? 'Duplicating...'
                                                                : 'Duplicate to new session'}
                                                        </ButtonLabel>
                                                    </ExpandingActionButton>
                                                </span>
                                            </Tooltip>
                                            <ExpandingActionButton
                                                className={downloadAnchorEl ? 'expanded' : ''}
                                                {...mkDownloadBtnAttrs({ runId: run.id })}
                                                onClick={(e) =>
                                                    setDownloadAnchorEl(e.currentTarget)
                                                }
                                                disabled={experiments.length === 0}
                                                size="small"
                                                variant="outlined">
                                                <FileDownloadOutlinedIcon fontSize="small" />
                                                <ButtonLabel className="button-label">
                                                    Download
                                                </ButtonLabel>
                                            </ExpandingActionButton>
                                            <DownloadMenu
                                                anchorEl={downloadAnchorEl}
                                                open={!!downloadAnchorEl}
                                                onClose={() => setDownloadAnchorEl(null)}>
                                                <MenuItem
                                                    {...mkDownloadCsvMenuItemAttrs({
                                                        runId: run.id,
                                                    })}
                                                    onClick={() => handleDownload('csv')}>
                                                    CSV
                                                </MenuItem>
                                                <MenuItem
                                                    {...mkDownloadJsonMenuItemAttrs({
                                                        runId: run.id,
                                                    })}
                                                    onClick={() => handleDownload('json')}>
                                                    JSON
                                                </MenuItem>
                                            </DownloadMenu>
                                            <Tooltip title="Share session" placement="bottom">
                                                <ExpandingActionButton
                                                    onClick={onShareClick}
                                                    size="small"
                                                    variant="outlined">
                                                    <ShareOutlinedIcon fontSize="small" />
                                                    <ButtonLabel className="button-label">
                                                        Share session
                                                    </ButtonLabel>
                                                </ExpandingActionButton>
                                            </Tooltip>
                                        </>
                                    )}
                                </RunHeaderActions>
                            )}
                        </RunHeaderTopRow>
                        {isRunning && (
                            <RunHeaderMessage>
                                <Typography variant="caption">
                                    AutoDiscovery is running. New findings will populate the table
                                    below automatically. You can click on any hypothesis to review
                                    the details while the run continues.
                                </Typography>
                                <br />
                                <Typography variant="caption">
                                    Feel free to navigate away; your results will be here when the
                                    analysis is complete.
                                </Typography>
                            </RunHeaderMessage>
                        )}
                        {run.details.status === 'FAILED' && (
                            <RunHeaderMessage>
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
                            </RunHeaderMessage>
                        )}
                    </RunHeader>
                    <RunHeaderSubtitle>
                        <StyledListItem>
                            <StatusChip
                                label={toSentenceCase(run.details.status)}
                                size="small"
                                $status={run.details.status}
                            />
                        </StyledListItem>
                        <StyledListItem>
                            {getRunStatusString(run.details, experiments)}
                        </StyledListItem>
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
                                {cancelling ? 'Stopping...' : 'Stop run'}
                            </StopButton>
                        )}
                    </RunHeaderSubtitle>

                    <RunContent>
                        <TopSurprisalsList />

                        <RunToolbar>
                            {run.stats && (
                                <ExperimentCount>
                                    <HourglassTopOutlinedIcon />
                                    {isLoadingInitialExperiments ? (
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
                                    variant="text"
                                    startIcon={<SettingsOutlinedIcon />}
                                    onClick={() => setIsParametersModalOpen(true)}
                                    data-test-id={TEST_ID_SESSION_CONFIG_BUTTON}
                                    {...mkSessionConfigBtnAttrs({ runId: run.id })}>
                                    Session configuration
                                </ParametersButton>
                            </RunToolbarButtons>
                        </RunToolbar>

                        <ExperimentsTable
                            runStats={run.stats}
                            surprisalWidth={run.metadata?.surprisalWidth}
                        />
                    </RunContent>
                    {isDragEnabled && (
                        <PanelDragHandle
                            side="right"
                            dragWidthPx={runPanelWidthPx ?? undefined}
                            minWidthPx={300}
                            onWidthPxChange={setRunPanelWidthPx}
                        />
                    )}
                </RunPanel>

                <ExperimentPanelBackdrop
                    $isVisible={!!selectedExperiment}
                    onClick={handleClosePanel}
                />

                {(!!selectedExperiment || isClosingPanel) && (
                    <ExperimentPanel
                        $isExpanded={isExpPanelExpanded}
                        $isClosing={isClosingPanel}
                        data-test-id={TEST_ID_EXPERIMENT_DETAILS_PANEL}
                        style={
                            {
                                '--experiment-panel-width': expPanelWidthPx
                                    ? `${expPanelWidthPx}px`
                                    : '500px',
                            } as React.CSSProperties
                        }>
                        {selectedExperiment && (
                            <ExperimentDetails
                                experiment={selectedExperiment}
                                surprisalWidth={run.metadata?.surprisalWidth}
                                actions={
                                    <>
                                        <Tooltip title="Share experiment" placement="bottom">
                                            <ExpandingActionButton
                                                onClick={onShareExperimentClick}
                                                size="small"
                                                variant="outlined">
                                                <ShareOutlinedIcon fontSize="small" />
                                                <ButtonLabel className="button-label">
                                                    Share experiment
                                                </ButtonLabel>
                                            </ExpandingActionButton>
                                        </Tooltip>
                                        <LargeScreenAction>
                                            <Tooltip
                                                title={isExpPanelExpanded ? 'Collapse' : 'Expand'}
                                                placement="bottom">
                                                <ExpandingActionButton
                                                    aria-label={
                                                        isExpPanelExpanded
                                                            ? 'Collapse panel'
                                                            : 'Expand panel'
                                                    }
                                                    onClick={() =>
                                                        setIsExpPanelExpanded(!isExpPanelExpanded)
                                                    }
                                                    size="small"
                                                    variant="outlined">
                                                    {isExpPanelExpanded ? (
                                                        <CloseFullscreenOutlinedIcon fontSize="small" />
                                                    ) : (
                                                        <OpenInFullOutlinedIcon fontSize="small" />
                                                    )}
                                                    <ButtonLabel className="button-label">
                                                        {isExpPanelExpanded ? 'Collapse' : 'Expand'}
                                                    </ButtonLabel>
                                                </ExpandingActionButton>
                                            </Tooltip>
                                        </LargeScreenAction>
                                        <Tooltip title="Close" placement="bottom">
                                            <ExpandingActionButton
                                                aria-label="Close experiment details"
                                                onClick={handleClosePanel}
                                                size="small"
                                                variant="outlined"
                                                data-test-id={TEST_ID_EXPERIMENT_DETAILS_CLOSE}
                                                {...mkCloseExperimentDetailsPanelAttrs({
                                                    runId: run.id,
                                                })}>
                                                <CloseIcon fontSize="small" />
                                                <ButtonLabel className="button-label">
                                                    Close
                                                </ButtonLabel>
                                            </ExpandingActionButton>
                                        </Tooltip>
                                    </>
                                }
                            />
                        )}
                        {!isExpPanelExpanded && isDragEnabled && (
                            <PanelDragHandle
                                side="left"
                                dragWidthPx={expPanelWidthPx ?? undefined}
                                minWidthPx={300}
                                onWidthPxChange={setExpPanelWidthPx}
                            />
                        )}
                    </ExperimentPanel>
                )}
            </PanelGroup>

            <RunParametersModal
                open={isParametersModalOpen}
                onClose={() => setIsParametersModalOpen(false)}
                metadata={run.metadata}
                testId={TEST_ID_SESSION_CONFIG_MODAL}
                canFork={canFork}
                forkTooltip={datasetExpiryLabel || undefined}
                datasetExpired={datasetExpired}
                onFork={isRunBookmarksEnabled ? handleFork : undefined}
                isForking={isForking}
            />
        </Container>
    );
}

const Container = styled('div')`
    container: run-view / inline-size;
    height: 100%;
`;

const StopButton = styled(Button)`
    color: ${({ theme }) => theme.color['error-red-100'].hex};
    margin-left: auto;

    &.Mui-disabled {
        color: ${({ theme }) => theme.color['error-red-60'].hex};
    }
`;

const RunToolbarButtons = styled('div')`
    display: flex;
    gap: ${({ theme }) => theme.spacing(1)};
`;

const ParametersButton = styled(Button)`
    color: ${({ theme }) => theme.color['cream-100'].hex};
    cursor: pointer;

    &:hover {
        color: ${({ theme }) => theme.color['green-100'].hex};
        background-color: transparent;
    }
`;

const RunHeader = styled('div')`
    border-bottom: 1px solid ${({ theme }) => theme.color['cream-10'].rgba.toString()};
    color: ${({ theme }) => theme.color['cream-100'].hex};
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: ${({ theme }) => theme.spacing(3)};
`;

const RunHeaderTopRow = styled('div')`
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
`;

const RunHeaderMessage = styled('div')``;

const RunHeaderActions = styled('div')`
    display: flex;
    align-items: center;
    flex-shrink: 0;
    justify-content: flex-end;
    gap: ${({ theme }) => theme.spacing(1)};
    margin-left: auto;
`;

const DownloadMenu = styled(Menu)`
    .MuiPaper-root {
        background-color: ${({ theme }) => theme.color['teal-100'].hex};
        color: ${({ theme }) => theme.color['cream-100'].hex};
    }

    .MuiMenuItem-root:hover {
        background-color: ${({ theme }) => theme.color['cream-10'].rgba.toString()};
    }
`;

const ExpandingActionButton = styled(Button)`
    border: 1px solid ${({ theme }) => theme.color['cream-20'].rgba.toString()};
    border-radius: 4px;
    color: ${({ theme }) => theme.color['cream-100'].hex};
    height: 32px;
    min-width: 32px;
    padding: 0 7px;
    overflow: hidden;
    transition:
        max-width 0.25s ease-in-out,
        padding 0.25s ease-in-out;
    max-width: 32px;

    &:hover,
    &.expanded {
        border: 1px solid ${({ theme }) => theme.color['cream-40'].rgba.toString()};
        max-width: 250px;
        padding: 0 12px;

        .button-label {
            max-width: 200px;
            opacity: 1;
            margin-left: 6px;
        }
    }

    &.Mui-disabled {
        border: 1px solid ${({ theme }) => theme.color['cream-10'].rgba.toString()};
        color: ${({ theme }) => theme.color['cream-80'].rgba.toString()};
    }

    .MuiButton-startIcon {
        margin: 0;
    }
`;

const ButtonLabel = styled('span')`
    white-space: nowrap;
    overflow: hidden;
    max-width: 0;
    opacity: 0;
    margin-left: 0;
    transition:
        max-width 0.25s ease-in-out,
        opacity 0.2s ease-in-out,
        margin-left 0.25s ease-in-out;
`;

const OverflowButton = styled(IconButton)`
    border: 1px solid ${({ theme }) => theme.color['cream-20'].rgba.toString()};
    border-radius: 4px;
    color: ${({ theme }) => theme.color['cream-100'].hex};
    width: 32px;
    height: 32px;

    &:hover {
        border: 1px solid ${({ theme }) => theme.color['cream-40'].rgba.toString()};
    }
`;

const OverflowMenu = styled(Menu)`
    .MuiPaper-root {
        background-color: ${({ theme }) => theme.color['teal-100'].hex};
        color: ${({ theme }) => theme.color['cream-100'].hex};
    }

    .MuiMenuItem-root:hover {
        background-color: ${({ theme }) => theme.color['cream-10'].rgba.toString()};
    }

    .MuiListItemIcon-root {
        color: ${({ theme }) => theme.color['cream-100'].hex};
    }

    .MuiMenuItem-root.Mui-disabled {
        opacity: 0.5;
    }
`;

const ParentRunInfo = styled('span')`
    color: ${({ theme }) => theme.color['cream-60'].hex};
    font-size: 0.8125rem;
    display: flex;
    align-items: center;
    gap: 4px;
    margin-top: 4px;
    margin-left: 28px;
`;

const ParentRunLink = styled(Link)`
    color: ${({ theme }) => theme.color['green-40'].rgba.toString()};
`;

const RunHeaderName = styled('h1')`
    color: ${({ theme }) => theme.color['green-100'].hex};
    display: flex;
    font-family: 'PP Telegraf', Manrope, sans-serif;
    font-weight: 700;
    font-size: 20px;
    gap: ${({ theme }) => theme.spacing(0.5)};
    line-height: 24px;
    margin: 0;
    flex: 1 1 auto;
`;

const BookmarkButton = styled(IconButton)<{ $isBookmarked?: boolean }>`
    color: ${({ theme, $isBookmarked }) =>
        $isBookmarked ? theme.color['green-100'].hex : theme.color['gray-50'].hex};
    padding: 0;
    transition: color 0.2s ease-in-out;

    &:hover {
        color: ${({ theme, $isBookmarked }) =>
            $isBookmarked ? theme.color['green-40'].rgba.toString() : theme.color['gray-30'].hex};
    }
`;

const RunContent = styled(Box)`
    padding: ${({ theme }) => theme.spacing(3)};

    @container run-view (width < 700px) {
        padding: ${({ theme }) => theme.spacing(3)};
    }

    @container run-view (width < 500px) {
        padding: ${({ theme }) => theme.spacing(3)};
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
    border-bottom: 1px solid ${({ theme }) => theme.color['cream-10'].rgba.toString()};
    color: ${({ theme }) => theme.color['cream-100'].hex};
    display: flex;
    flex-direction: row;
    font-weight: normal;
    gap: ${({ theme }) => theme.spacing(1)};
    padding: ${({ theme }) => theme.spacing(1.5, 3)};

    @media (max-width: 600px) {
        flex-direction: column;
        align-items: flex-start;
    }
`;

const StyledListItem = styled(ListItem)`
    display: inline-flex;
    padding: 0;
    width: auto;
`;

const RunToolbar = styled('div')`
    display: flex;
    justify-content: space-between;

    @media (max-width: 600px) {
        flex-direction: column;
        align-items: flex-start;
        gap: ${({ theme }) => theme.spacing(1)};
    }
`;
