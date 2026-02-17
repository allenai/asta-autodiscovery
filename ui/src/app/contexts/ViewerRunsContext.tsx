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
    viewerRuns: Record<string, Run> | null;
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
    const [viewerRuns, setViewerRuns] = useState<Record<string, Run> | null>(null);
    const [isViewerRunsLoading, setIsViewerRunsLoading] = useState<boolean>(false);

    const addViewerRun = useCallback((run: Run) => {
        setViewerRuns((prevRuns) => ({
            ...(prevRuns ?? {}),
            [run.id]: run,
        }));
    }, []);

    const updateViewerRun = useCallback((updatedRun: Partial<Run> & { id: string }) => {
        setViewerRuns((prevRuns) => {
            if (!prevRuns) return prevRuns;
            const existing = prevRuns[updatedRun.id];
            if (!existing) return prevRuns;
            return { ...prevRuns, [updatedRun.id]: { ...existing, ...updatedRun } };
        });
    }, []);

    const removeViewerRun = useCallback((runId: string) => {
        setViewerRuns((prevRuns) => {
            if (!prevRuns) return prevRuns;
            const { [runId]: _, ...rest } = prevRuns;
            return rest;
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
            setViewerRuns(Object.fromEntries(runs.map((run) => [run.id, run])));
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
