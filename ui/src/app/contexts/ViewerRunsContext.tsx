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

export interface ViewerRunsState {
    viewerRuns: Run[] | null;
    isViewerRunsLoading: boolean;
    updateViewerRuns: () => Promise<void>;
    addViewerRun: (run: Run) => void;
    updateViewerRun: (run: Partial<Run> & { id: string }) => void;
    removeViewerRun: (runId: string) => void;
    lastError: string | null;
}

export const DEFAULT_STATE: ViewerRunsState = {
    viewerRuns: null,
    isViewerRunsLoading: false,
    updateViewerRuns: async () => {},
    addViewerRun: () => {},
    updateViewerRun: () => {},
    removeViewerRun: () => {},
    lastError: null,
};

const ViewerRunsContext = createContext<ViewerRunsState>(DEFAULT_STATE);

export const useViewerRuns = (): ViewerRunsState => {
    const context = useContext(ViewerRunsContext);
    if (!context) {
        throw new Error('useViewerRuns must be used within a ViewerRunsContextProvider');
    }
    return context;
};

export type ViewerRunsProviderProps = PropsWithChildren<{}>;

export const ViewerRunsContextProvider = ({ children }: ViewerRunsProviderProps) => {
    const runsApi = getRunsApi();
    const { isAuthenticated } = useAuth0();

    const [lastError, setLastError] = useState<string | null>(null);
    const [viewerRuns, setViewerRuns] = useState<Run[] | null>(null);
    const [isViewerRunsLoading, setIsViewerRunsLoading] = useState<boolean>(false);

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

    const removeViewerRun = useCallback((runId: string) => {
        setViewerRuns((prevRuns) => {
            if (!prevRuns) return prevRuns;
            return prevRuns.filter((run) => run.id !== runId);
        });
    }, []);

    const updateViewerRuns = useCallback(async () => {
        if (!isAuthenticated) {
            return;
        }
        setIsViewerRunsLoading(true);
        try {
            // No userid needed - API will use authenticated user
            const { data } = await runsApi.listRuns();
            const runs = data.runs.map((runData) => getRunFromApi(runData));
            setViewerRuns(runs);
        } catch (error: any) {
            setLastError(error.message || 'Failed to fetch viewer runs');
        } finally {
            setIsViewerRunsLoading(false);
        }
    }, [runsApi, isAuthenticated]);

    useEffect(() => {
        if (isAuthenticated) {
            updateViewerRuns();
        }
    }, [updateViewerRuns, isAuthenticated]);

    const memoizedState = useMemo<ViewerRunsState>(
        () => ({
            lastError,
            viewerRuns,
            isViewerRunsLoading,
            addViewerRun,
            updateViewerRun,
            removeViewerRun,
            updateViewerRuns,
        }),
        [
            lastError,
            viewerRuns,
            isViewerRunsLoading,
            addViewerRun,
            updateViewerRun,
            removeViewerRun,
            updateViewerRuns,
        ]
    );

    return (
        <ViewerRunsContext.Provider value={memoizedState}>{children}</ViewerRunsContext.Provider>
    );
};
