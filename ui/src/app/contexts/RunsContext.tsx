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
import { getRunFromApi, Run } from '@/types/Run';
import { useAuth0 } from '@/contexts/Auth0Context';

export interface RunsState {
    viewerRuns: Run[] | null;
    isViewerRunsLoading?: boolean;
    updateViewerRuns: () => Promise<void>;
    addViewerRun: (run: Run) => void;
    updateViewerRun: (run: Partial<Run> & { id: string }) => void;
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
    updateViewerRun: () => {},
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
    const { isAuthenticated } = useAuth0();

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

    const updateViewerRun = useCallback((updatedRun: Partial<Run> & { id: string }) => {
        setViewerRuns((prevRuns) => {
            if (!prevRuns) return prevRuns;
            return prevRuns.map((run) =>
                run.id === updatedRun.id ? { ...run, ...updatedRun } : run
            );
        });
    }, []);

    const updateViewerRuns = useCallback(async () => {
        setIsViewerRunsLoading(true);
        try {
            const { data } = await runsApi.listRuns();
            const runs = data.runs.map((runData) => getRunFromApi(runData));
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
            const { data } = await runsApi.listRuns({ user: 'samples' });
            const runs = data.runs.map((runData) => getRunFromApi(runData));
            setExampleRuns(runs);
        } catch (error: any) {
            // Sample runs are optional - don't set error if they fail
            setExampleRuns([]);
        } finally {
            setIsExampleRunsLoading(false);
        }
    }, [runsApi]);

    useEffect(() => {
        if (isAuthenticated) {
            updateViewerRuns();
            updateExampleRuns();
        }
    }, [updateViewerRuns, updateExampleRuns, isAuthenticated]);

    const memoizedState = useMemo<RunsState>(
        () => ({
            lastError,
            viewerRuns,
            isViewerRunsLoading,
            exampleRuns,
            isExampleRunsLoading,
            addViewerRun,
            updateViewerRun,
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
            updateViewerRun,
            updateViewerRuns,
            updateExampleRuns,
        ]
    );

    return <RunsContext.Provider value={memoizedState}>{children}</RunsContext.Provider>;
};
