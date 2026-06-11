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

export interface ExampleRunsState {
    exampleRuns: Run[] | null;
    isExampleRunsLoading: boolean;
    updateExampleRuns: () => Promise<void>;
    lastError: string | null;
}

export const DEFAULT_STATE: ExampleRunsState = {
    exampleRuns: null,
    isExampleRunsLoading: false,
    updateExampleRuns: async () => {},
    lastError: null,
};

const ExampleRunsContext = createContext<ExampleRunsState>(DEFAULT_STATE);

export const useExampleRuns = (): ExampleRunsState => {
    const context = useContext(ExampleRunsContext);
    if (!context) {
        throw new Error('useExampleRuns must be used within an ExampleRunsContextProvider');
    }
    return context;
};

export type ExampleRunsProviderProps = PropsWithChildren<{}>;

export const ExampleRunsContextProvider = ({ children }: ExampleRunsProviderProps) => {
    const runsApi = getRunsApi();

    const [exampleRuns, setExampleRuns] = useState<Run[] | null>(null);
    const [isExampleRunsLoading, setIsExampleRunsLoading] = useState<boolean>(false);

    const updateExampleRuns = useCallback(async () => {
        setIsExampleRunsLoading(true);
        try {
            const { data } = await runsApi.listRuns({ userid: 'samples' });
            const runs = data.runs.map((runData) => getRunFromApi(runData));
            setExampleRuns(runs);
        } catch {
            // Sample runs are optional - don't set error if they fail
            setExampleRuns([]);
        } finally {
            setIsExampleRunsLoading(false);
        }
    }, [runsApi]);

    // Fetch immediately on mount - no authentication check
    useEffect(() => {
        updateExampleRuns();
    }, [updateExampleRuns]);

    const memoizedState = useMemo<ExampleRunsState>(
        () => ({
            lastError: null,
            exampleRuns,
            isExampleRunsLoading,
            updateExampleRuns,
        }),
        [exampleRuns, isExampleRunsLoading, updateExampleRuns]
    );

    return (
        <ExampleRunsContext.Provider value={memoizedState}>{children}</ExampleRunsContext.Provider>
    );
};
