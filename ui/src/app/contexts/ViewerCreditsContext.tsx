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

import { useAuth0 } from '@/contexts/Auth0Context';
import { getUserApi, ViewerCreditsFromApi } from '@/api/UserApi';

export interface ViewerCreditsState {
    credits: ViewerCreditsFromApi | null;
    lastError: string | null;
    updateViewerCredits: () => Promise<void>;
}

export const REFRESH_INTERVAL_MS = 60000; // 60 seconds

export const DEFAULT_STATE: ViewerCreditsState = {
    credits: null,
    lastError: null,
    updateViewerCredits: async () => {},
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

    const { isAuthenticated } = useAuth0();

    const updateViewerCredits = useCallback(async () => {
        if (!isAuthenticated) {
            return;
        }
        try {
            const { data } = await userApi.getViewerCredits();
            setCredits(data.credits);
            if (lastError) {
                setLastError(null);
            }
        } catch (error: any) {
            setLastError(error.message);
        }
    }, [isAuthenticated, lastError]);
    useEffect(() => {
        if (!isAuthenticated) {
            return;
        }
        updateViewerCredits();
        const interval = setInterval(updateViewerCredits, REFRESH_INTERVAL_MS);
        return () => clearInterval(interval);
    }, [isAuthenticated, updateViewerCredits]);

    const memoizedState = useMemo<ViewerCreditsState>(
        () => ({ credits, lastError, updateViewerCredits }),
        [credits, lastError, updateViewerCredits]
    );

    return (
        <ViewerCreditsContext.Provider value={memoizedState}>
            {children}
        </ViewerCreditsContext.Provider>
    );
};
