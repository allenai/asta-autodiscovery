'use client';

import {
    createContext,
    MutableRefObject,
    PropsWithChildren,
    useCallback,
    useContext,
    useEffect,
    useMemo,
    useRef,
    useState,
} from 'react';

import { getRunsApi } from '@/api/RunsApi';
import { Experiment, getExperimentFromApi } from '@/types/Run';

export interface RunExperimentsState {
    isPolling: boolean;
    startPolling: () => void;
    stopPolling: () => void;
    isLoading: boolean;
    isLoadingInitial: boolean;
    runid: string | null;
    experiments: Experiment[];
    lastError: string | null;
    hasJobCompleted: boolean;
    selectedExperiment: Experiment | null;
    selectedExperimentError: string | null;
    isLoadingSelectedExperiment: boolean;
    selectExperiment: (experiment: Experiment | null, options?: { scroll?: boolean }) => void;
    shouldScrollToSelected: MutableRefObject<boolean>;
}

export const DEFAULT_STATE: RunExperimentsState = {
    isPolling: false,
    startPolling: () => {},
    stopPolling: () => {},
    isLoading: false,
    isLoadingInitial: false,
    runid: null,
    experiments: [],
    lastError: null,
    hasJobCompleted: false,
    selectedExperiment: null,
    selectedExperimentError: null,
    isLoadingSelectedExperiment: false,
    selectExperiment: () => {},
    shouldScrollToSelected: { current: true },
};

export const DEFAULT_REFRESH_INTERVAL_MS = 15000; // 15 seconds

const RunExperimentsContext = createContext<RunExperimentsState>(DEFAULT_STATE);
export default RunExperimentsContext;

export const useRunExperiments = (): RunExperimentsState => {
    const context = useContext(RunExperimentsContext);
    if (!context) {
        throw new Error('useRunExperiments must be used within a RunExperimentsProvider');
    }
    return context;
};

export type RunExperimentsProps = PropsWithChildren<{
    runid: string | null;
    /** Optional user ID for viewing public runs (e.g., "samples"). Defaults to authenticated user. */
    userid?: string;
    autoStart?: boolean;
    refreshIntervalMs?: number;
}>;

export const RunExperimentsProvider = ({
    runid,
    userid,
    children,
    autoStart = false,
    refreshIntervalMs = DEFAULT_REFRESH_INTERVAL_MS,
}: RunExperimentsProps) => {
    const runsApi = getRunsApi();

    const [isPolling, setIsPolling] = useState<boolean>(false);
    const [isLoading, setIsLoading] = useState<boolean>(false);
    const [isLoadingInitial, setIsLoadingInitial] = useState<boolean>(true);
    const hasLoadedOnce = useRef<boolean>(false);
    const [experiments, setExperiments] = useState<Experiment[]>([]);
    const [lastError, setLastError] = useState<string | null>(null);
    const [hasJobCompleted, setHasJobCompleted] = useState<boolean>(false);
    const [selectedExperiment, setSelectedExperiment] = useState<Experiment | null>(null);
    const [selectedExperimentError, setSelectedExperimentError] = useState<string | null>(null);
    const [isLoadingSelectedExperiment, setIsLoadingSelectedExperiment] = useState<boolean>(false);

    const knownExperimentIds = useRef<Set<string>>(new Set());
    const selectedExperimentRequestId = useRef<number>(0);
    const refreshIntervalMsRef = useRef<number>(refreshIntervalMs);
    const shouldScrollToSelected = useRef<boolean>(true);

    // Keep ref in sync with prop
    useEffect(() => {
        refreshIntervalMsRef.current = refreshIntervalMs;
    }, [refreshIntervalMs]);

    const startPolling = useCallback(() => {
        if (!runid) {
            return;
        }
        setIsPolling(true);
    }, [runid]);

    const stopPolling = useCallback(() => {
        if (!runid) {
            return;
        }
        setIsPolling(false);
    }, [runid]);

    const selectExperiment = useCallback(
        (experiment: Experiment | null, options?: { scroll?: boolean }) => {
            shouldScrollToSelected.current = options?.scroll ?? true;
            // Prevent redundant selections - check before setting state
            setSelectedExperiment((prev) => {
                if (prev?.experimentId === experiment?.experimentId) {
                    return prev; // No change needed
                }
                return experiment;
            });

            setSelectedExperimentError(null);

            if (!experiment || !runid) {
                selectedExperimentRequestId.current += 1;
                setIsLoadingSelectedExperiment(false);
                return;
            }

            selectedExperimentRequestId.current += 1;
            const requestId = selectedExperimentRequestId.current;
            setIsLoadingSelectedExperiment(true);

            runsApi
                .getRunExperimentDetails({
                    userid,
                    runid,
                    experimentId: experiment.experimentId,
                })
                .then(({ data }) => {
                    if (selectedExperimentRequestId.current !== requestId) {
                        return;
                    }
                    if (data?.experiment) {
                        const detailedExperiment = getExperimentFromApi(data.experiment);
                        setSelectedExperiment((prev) =>
                            prev?.experimentId === detailedExperiment.experimentId
                                ? detailedExperiment
                                : prev
                        );
                    }
                })
                .catch((error: any) => {
                    if (selectedExperimentRequestId.current !== requestId) {
                        return;
                    }
                    setSelectedExperimentError(
                        error?.message || 'Failed to fetch experiment details'
                    );
                })
                .finally(() => {
                    if (selectedExperimentRequestId.current !== requestId) {
                        return;
                    }
                    setIsLoadingSelectedExperiment(false);
                });
        },
        [runid, userid, runsApi]
    );

    // Discard the previous run's accumulated state whenever runid changes, not just
    // when it goes null: the provider stays mounted across a client-side navigation
    // between two runs, so without this the new run inherits the old experiments and
    // the old fetch position (known ids). Declared before the fetch effect so the
    // refs are already cleared when that effect runs in the same commit.
    useEffect(() => {
        setExperiments(DEFAULT_STATE.experiments);
        setIsLoading(DEFAULT_STATE.isLoading);
        setIsLoadingInitial(true);
        hasLoadedOnce.current = false;
        setLastError(DEFAULT_STATE.lastError);
        setHasJobCompleted(DEFAULT_STATE.hasJobCompleted);
        setSelectedExperiment(DEFAULT_STATE.selectedExperiment);
        setSelectedExperimentError(DEFAULT_STATE.selectedExperimentError);
        setIsLoadingSelectedExperiment(DEFAULT_STATE.isLoadingSelectedExperiment);
        knownExperimentIds.current = new Set();
        selectedExperimentRequestId.current += 1;
        // Restarting polling here (rather than in its own effect reading isPolling)
        // keeps the reset from silently stopping an autoStart provider.
        setIsPolling(Boolean(runid) && autoStart);
    }, [runid, autoStart]);

    useEffect(() => {
        if (!runid || !isPolling) {
            return;
        }

        // A request issued for the previous runid must not append its results to the
        // new run's list, so drop anything that resolves after this effect is torn down.
        let cancelled = false;

        const fetchLatestExperiments = async () => {
            if (cancelled) {
                return;
            }
            try {
                setIsLoading(true);
                const { data } = await runsApi.getRunExperiments({
                    userid,
                    runid,
                    knownExperimentIds: Array.from(knownExperimentIds.current),
                });
                if (cancelled) {
                    return;
                }
                const newExperiments = data.experiments.map((exp) => getExperimentFromApi(exp));
                if (newExperiments.length > 0) {
                    setExperiments((prevExperiments) => {
                        // Deduplicate: only add experiments we don't already have
                        const existingIds = new Set(prevExperiments.map((e) => e.experimentId));
                        const trulyNewExperiments = newExperiments.filter(
                            (exp) => !existingIds.has(exp.experimentId)
                        );

                        // Update the ref with new IDs
                        trulyNewExperiments.forEach((exp) => {
                            knownExperimentIds.current.add(exp.experimentId);
                        });

                        return [...prevExperiments, ...trulyNewExperiments];
                    });
                }

                // Handle job completion
                if (data.has_job_completed && !hasJobCompleted) {
                    setHasJobCompleted(true);
                    setIsPolling(false);
                }

                if (lastError !== null) {
                    setLastError(null);
                }
            } catch (error: any) {
                if (cancelled) {
                    return;
                }
                setLastError(error.message || 'Failed to fetch experiments');
            } finally {
                if (!cancelled) {
                    setIsLoading(false);
                    if (!hasLoadedOnce.current) {
                        hasLoadedOnce.current = true;
                        setIsLoadingInitial(false);
                    }
                }
            }
        };

        fetchLatestExperiments();
        const interval = setInterval(fetchLatestExperiments, refreshIntervalMsRef.current);
        return () => {
            cancelled = true;
            clearInterval(interval);
        };
    }, [runid, userid, isPolling, runsApi, lastError, hasJobCompleted]);

    const memoizedState = useMemo<RunExperimentsState>(
        () => ({
            runid,
            isPolling,
            isLoading,
            isLoadingInitial,
            experiments,
            lastError,
            hasJobCompleted,
            selectedExperiment,
            selectedExperimentError,
            isLoadingSelectedExperiment,
            startPolling,
            stopPolling,
            selectExperiment,
            shouldScrollToSelected,
        }),
        [
            runid,
            isPolling,
            isLoading,
            isLoadingInitial,
            experiments,
            lastError,
            hasJobCompleted,
            selectedExperiment,
            selectedExperimentError,
            isLoadingSelectedExperiment,
            startPolling,
            stopPolling,
            selectExperiment,
            shouldScrollToSelected,
        ]
    );

    return (
        <RunExperimentsContext.Provider value={memoizedState}>
            {children}
        </RunExperimentsContext.Provider>
    );
};
