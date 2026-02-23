'use client';

import {
    createContext,
    useCallback,
    useContext,
    useEffect,
    useRef,
    useState,
    PropsWithChildren,
    useMemo,
} from 'react';

import { useAuth0 } from '@/contexts/Auth0Context';
import { getUserApi, ViewerCreditsFromApi } from '@/api/UserApi';

export interface ViewerCreditsState {
    credits: ViewerCreditsFromApi | null;
    lastError: string | null;
    isPolling: boolean;
    isLoading: boolean;
    isLoadingInitial: boolean;
    updateViewerCredits: () => Promise<void>;
    startPolling: () => void;
    stopPolling: () => void;
}

export const REFRESH_INTERVAL_MS = 60000; // 60 seconds

export const DEFAULT_STATE: ViewerCreditsState = {
    credits: null,
    lastError: null,
    isPolling: false,
    isLoading: false,
    isLoadingInitial: true,
    updateViewerCredits: async () => {},
    startPolling: () => {},
    stopPolling: () => {},
};

const ViewerCreditsContext = createContext<ViewerCreditsState>(DEFAULT_STATE);

export const useViewerCredits = (): ViewerCreditsState => {
    const context = useContext(ViewerCreditsContext);
    if (!context) {
        throw new Error('useViewerCredits must be used within a ViewerCreditsProvider');
    }
    return context;
};

export type ViewerCreditsProviderProps = PropsWithChildren<{}>;

export const ViewerCreditsProvider = ({ children }: ViewerCreditsProviderProps) => {
    const userApi = getUserApi();

    const [credits, setCredits] = useState<ViewerCreditsFromApi | null>(null);
    const [lastError, setLastError] = useState<string | null>(null);
    const [isPolling, setIsPolling] = useState(false);
    const [isLoading, setIsLoading] = useState(false);
    const [isLoadingInitial, setIsLoadingInitial] = useState(true);
    const hasLoadedOnce = useRef(false);

    const { isAuthenticated } = useAuth0();

    const startPolling = useCallback(() => setIsPolling(true), []);
    const stopPolling = useCallback(() => setIsPolling(false), []);

    const updateViewerCredits = useCallback(async () => {
        if (!isAuthenticated) {
            return;
        }
        setIsLoading(true);
        try {
            const { data } = await userApi.getViewerCredits();
            setCredits(data.credits);
            if (lastError) {
                setLastError(null);
            } else if (!hasLoadedOnce.current) {
                hasLoadedOnce.current = true;
                setIsLoadingInitial(false);
            }
        } catch (error: any) {
            setLastError(error.message);
        } finally {
            setIsLoading(false);
        }
    }, [isAuthenticated, lastError]);

    useEffect(() => {
        if (isAuthenticated) {
            setIsPolling(true);
        } else {
            setIsPolling(false);
            setIsLoadingInitial(true);
            hasLoadedOnce.current = false;
        }
    }, [isAuthenticated]);

    useEffect(() => {
        if (!isAuthenticated || !isPolling) {
            return;
        }
        updateViewerCredits();
        const interval = setInterval(updateViewerCredits, REFRESH_INTERVAL_MS);
        return () => clearInterval(interval);
    }, [isAuthenticated, isPolling, updateViewerCredits]);

    const memoizedState = useMemo<ViewerCreditsState>(
        () => ({
            credits,
            lastError,
            isPolling,
            isLoading,
            isLoadingInitial,
            updateViewerCredits,
            startPolling,
            stopPolling,
        }),
        [
            credits,
            lastError,
            isPolling,
            isLoading,
            isLoadingInitial,
            updateViewerCredits,
            startPolling,
            stopPolling,
        ]
    );

    return (
        <ViewerCreditsContext.Provider value={memoizedState}>
            {children}
        </ViewerCreditsContext.Provider>
    );
};
