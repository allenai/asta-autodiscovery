'use client';

import {
    createContext,
    useCallback,
    useContext,
    useEffect,
    useState,
    PropsWithChildren,
    useMemo,
} from 'react';

import { getRunsApi } from '@/api/RunsApi';
import { Run } from '@/types/Run';

const EXAMPLE_RUNS: Run[] = [
    {
        id: 'run-1',
        name: 'Melanoma',
        path: '/path/to/run-1',
        details: {
            executionId: 'exec-1',
            createdAt: '2024-01-01T12:00:00Z',
            status: 'completed',
            statusCheckedAt: '2024-01-01T14:00:00Z',
        },
        executionStatus: {
            accuracy: 0.95,
            loss: 0.05,
        },
    },
    {
        id: 'run-2',
        name: 'Breast Cancer',
        path: '/path/to/run-2',
        details: {
            executionId: 'exec-2',
            createdAt: '2024-01-02T12:00:00Z',
            status: 'completed',
            statusCheckedAt: '2024-01-02T14:00:00Z',
        },
        executionStatus: {
            accuracy: 0.9,
            loss: 0.1,
        },
    },
    {
        id: 'run-3',
        name: 'Reef Notes',
        path: '/path/to/run-3',
        details: {
            executionId: 'exec-3',
            createdAt: '2024-01-03T12:00:00Z',
            status: 'completed',
            statusCheckedAt: '2024-01-03T14:00:00Z',
        },
        executionStatus: {
            accuracy: 0.85,
            loss: 0.15,
        },
    },
];

export interface RunsState {
    viewerRuns: Run[] | null;
    isViewerRunsLoading?: boolean;
    updateViewerRuns: () => Promise<void>;
    addViewerRun: (run: Run) => void;
    exampleRuns: Run[] | null;
    isExampleRunsLoading?: boolean;
    updateExampleRuns: () => Promise<void>;
    lastError: string | null;
}

export const DEFAULT_STATE: RunsState = {
    viewerRuns: null,
    isViewerRunsLoading: false,
    updateViewerRuns: async () => {},
    addViewerRun: () => {},
    exampleRuns: null,
    updateExampleRuns: async () => {},
    isExampleRunsLoading: false,
    lastError: null,
};

const RunsContext = createContext<RunsState>(DEFAULT_STATE);

export const useRuns = (): RunsState => {
    const context = useContext(RunsContext);
    if (!context) {
        throw new Error('useRuns must be used within a RunsProvider');
    }
    return context;
};

export type RunsProviderProps = PropsWithChildren<{}>;

export const RunsContextProvider = ({ children }: RunsProviderProps) => {
    const runsApi = getRunsApi();

    const [lastError, setLastError] = useState<string | null>(null);
    const [viewerRuns, setViewerRuns] = useState<Run[] | null>(null);
    const [isViewerRunsLoading, setIsViewerRunsLoading] = useState<boolean>(false);
    const [exampleRuns, setExampleRuns] = useState<Run[] | null>(null);
    const [isExampleRunsLoading, setIsExampleRunsLoading] = useState<boolean>(false);

    const addViewerRun = useCallback((run: Run) => {
        setViewerRuns((prevRuns) => {
            if (!prevRuns) {
                return [run];
            }
            return [run, ...prevRuns];
        });
    }, []);

    const updateViewerRuns = useCallback(async () => {
        setIsViewerRunsLoading(true);
        try {
            const { data } = await runsApi.listRuns();
            // TODO: Add details to API for fetching
            const runs: Run[] = data.runs.map((runData) => ({
                id: runData,
                name: `Run ${runData}`,
                path: `/path/to/${runData}`,
                details: {
                    executionId: `exec-${runData}`,
                    createdAt: new Date().toISOString(),
                    status: 'completed',
                    statusCheckedAt: new Date().toISOString(),
                },
                executionStatus: {},
            }));
            setViewerRuns(runs);
        } catch (error: any) {
            setLastError(error.message || 'Failed to fetch viewer runs');
        } finally {
            setIsViewerRunsLoading(false);
        }
    }, [runsApi]);

    const updateExampleRuns = useCallback(async () => {
        setIsExampleRunsLoading(true);
        try {
            // const { data } = await runsApi.getExampleRuns();
            setExampleRuns(EXAMPLE_RUNS);
        } catch (error: any) {
            setLastError(error.message || 'Failed to fetch example runs');
        } finally {
            setIsExampleRunsLoading(false);
        }
    }, [runsApi]);

    useEffect(() => {
        updateViewerRuns();
        updateExampleRuns();
    }, [updateViewerRuns, updateExampleRuns]);

    const memoizedState = useMemo<RunsState>(
        () => ({
            lastError,
            viewerRuns,
            isViewerRunsLoading,
            exampleRuns,
            isExampleRunsLoading,
            addViewerRun,
            updateViewerRuns,
            updateExampleRuns,
        }),
        [
            lastError,
            viewerRuns,
            isViewerRunsLoading,
            exampleRuns,
            isExampleRunsLoading,
            addViewerRun,
            updateViewerRuns,
            updateExampleRuns,
        ]
    );

    return <RunsContext.Provider value={memoizedState}>{children}</RunsContext.Provider>;
};
