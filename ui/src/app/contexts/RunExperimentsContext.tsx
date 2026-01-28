'use client';

import {
    createContext,
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
    runid: string | null;
    experiments: Experiment[];
    lastError: string | null;
    hasJobCompleted: boolean;
    selectedExperiment: Experiment | null;
    selectedExperimentError: string | null;
    isLoadingSelectedExperiment: boolean;
    selectExperiment: (experiment: Experiment | null) => void;
}

export const DEFAULT_STATE: RunExperimentsState = {
    isPolling: false,
    startPolling: () => {},
    stopPolling: () => {},
    isLoading: false,
    runid: null,
    experiments: [],
    lastError: null,
    hasJobCompleted: false,
    selectedExperiment: null,
    selectedExperimentError: null,
    isLoadingSelectedExperiment: false,
    selectExperiment: () => {},
};

export const DEFAULT_REFRESH_INTERVAL_MS = 15000; // 15 seconds

const RunExperimentsContext = createContext<RunExperimentsState>(DEFAULT_STATE);
export default RunExperimentsContext;

export const useRunExperiments = () => {
    const context = useContext(RunExperimentsContext);
    if (!context) {
        throw new Error('useRunExperiments must be used within a RunExperimentsProvider');
    }
    return context;
};

export type RunExperimentsProps = PropsWithChildren<{
    runid: string | null;
    autoStart?: boolean;
    refreshIntervalMs?: number;
}>;

export const RunExperimentsProvider = ({
    runid,
    children,
    autoStart = false,
    refreshIntervalMs = DEFAULT_REFRESH_INTERVAL_MS,
}: RunExperimentsProps) => {
    const runsApi = getRunsApi();

    const [isPolling, setIsPolling] = useState<boolean>(false);
    const [isLoading, setIsLoading] = useState<boolean>(false);
    const [experiments, setExperiments] = useState<Experiment[]>([]);
    const [lastError, setLastError] = useState<string | null>(null);
    const [hasJobCompleted, setHasJobCompleted] = useState<boolean>(false);
    const [selectedExperiment, setSelectedExperiment] = useState<Experiment | null>(null);
    const [selectedExperimentError, setSelectedExperimentError] = useState<string | null>(null);
    const [isLoadingSelectedExperiment, setIsLoadingSelectedExperiment] = useState<boolean>(false);

    const afterExperimentId = useRef<string | null>(null);
    const selectedExperimentRequestId = useRef<number>(0);

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
        (experiment: Experiment | null) => {
            setSelectedExperiment(experiment);
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
        [runid, runsApi]
    );

    // Auto-start polling on mount if autoStart is true
    useEffect(() => {
        if (autoStart && runid && !isPolling) {
            setIsPolling(true);
        }
    }, [autoStart, runid]);

    useEffect(() => {
        if (!runid) {
            setIsPolling(DEFAULT_STATE.isPolling);
            setExperiments(DEFAULT_STATE.experiments);
            setIsLoading(DEFAULT_STATE.isLoading);
            setLastError(DEFAULT_STATE.lastError);
            setHasJobCompleted(DEFAULT_STATE.hasJobCompleted);
            setSelectedExperiment(DEFAULT_STATE.selectedExperiment);
            setSelectedExperimentError(DEFAULT_STATE.selectedExperimentError);
            setIsLoadingSelectedExperiment(DEFAULT_STATE.isLoadingSelectedExperiment);
            afterExperimentId.current = null;
            selectedExperimentRequestId.current += 1;
            return;
        }
        if (!isPolling) {
            return;
        }

        const fetchLatestExperiments = async () => {
            if (!isPolling) {
                return;
            }
            try {
                setIsLoading(true);
                const { data } = await runsApi.getRunExperiments({
                    runid,
                    afterExperimentId: afterExperimentId.current ?? undefined,
                });
                const newExperiments = data.experiments.map((exp) => getExperimentFromApi(exp));
                if (newExperiments.length > 0) {
                    setExperiments((prevExperiments) => [...prevExperiments, ...newExperiments]);
                    afterExperimentId.current = newExperiments.at(-1)?.experimentId ?? null;
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
                setLastError(error.message || 'Failed to fetch experiments');
            } finally {
                setIsLoading(false);
            }
        };

        fetchLatestExperiments();
        const interval = setInterval(fetchLatestExperiments, refreshIntervalMs);
        return () => {
            clearInterval(interval);
        };
    }, [runid, isPolling]);

    const memoizedState = useMemo<RunExperimentsState>(
        () => ({
            runid,
            isPolling,
            isLoading,
            experiments,
            lastError,
            hasJobCompleted,
            selectedExperiment,
            selectedExperimentError,
            isLoadingSelectedExperiment,
            startPolling,
            stopPolling,
            selectExperiment,
        }),
        [
            runid,
            isPolling,
            isLoading,
            experiments,
            lastError,
            hasJobCompleted,
            selectedExperiment,
            selectedExperimentError,
            isLoadingSelectedExperiment,
            startPolling,
            stopPolling,
            selectExperiment,
        ]
    );

    return (
        <RunExperimentsContext.Provider value={memoizedState}>
            {children}
        </RunExperimentsContext.Provider>
    );
};
