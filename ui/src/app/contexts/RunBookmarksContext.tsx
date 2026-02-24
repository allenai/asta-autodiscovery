'use client';

import { createContext, PropsWithChildren, useCallback, useContext, useMemo } from 'react';

import { getRunsApi } from '@/api/RunsApi';
import { useToasts } from '@/contexts/ToastsContext';
import { useViewerRuns } from '@/contexts/ViewerRunsContext';

export interface RunBookmarksState {
    isRunBookmarksEnabled: boolean;
    checkRunBookmarked: (runId: string) => boolean;
    bookmarkRun: (runId: string) => Promise<void>;
    unbookmarkRun: (runId: string) => Promise<void>;
}

const DEFAULT_STATE: RunBookmarksState = {
    isRunBookmarksEnabled: false,
    checkRunBookmarked: () => false,
    bookmarkRun: async () => {},
    unbookmarkRun: async () => {},
};

const RunBookmarksContext = createContext<RunBookmarksState>(DEFAULT_STATE);
export default RunBookmarksContext;

export const useRunBookmarks = (): RunBookmarksState => {
    const context = useContext(RunBookmarksContext);
    if (!context) {
        throw new Error('useRunBookmarks must be used within a RunBookmarksProvider');
    }
    return context;
};

export type RunBookmarksProps = PropsWithChildren<{
    isRunBookmarksEnabled: boolean;
}>;

export const RunBookmarksProvider = ({ isRunBookmarksEnabled, children }: RunBookmarksProps) => {
    const runsApi = getRunsApi();
    const { viewerRuns, updateViewerRun } = useViewerRuns();
    const { addSuccessToast, addErrorToast } = useToasts();

    const checkRunBookmarked = useCallback(
        (runId: string): boolean => {
            return viewerRuns?.[runId]?.metadata?.isBookmarked ?? false;
        },
        [viewerRuns]
    );

    const bookmarkRun = useCallback(
        async (runId: string) => {
            if (!isRunBookmarksEnabled) return;
            const run = viewerRuns?.[runId];
            if (!run?.metadata) return;

            updateViewerRun({ id: runId, metadata: { ...run.metadata, isBookmarked: true } });

            try {
                await runsApi.bookmarkRun({ runId, isBookmarked: true });
                addSuccessToast('Run bookmarked');
            } catch (err) {
                updateViewerRun({ id: runId, metadata: { ...run.metadata, isBookmarked: false } });
                addErrorToast('Error updating bookmark status.');
                throw err;
            }
        },
        [
            isRunBookmarksEnabled,
            viewerRuns,
            updateViewerRun,
            runsApi,
            addSuccessToast,
            addErrorToast,
        ]
    );

    const unbookmarkRun = useCallback(
        async (runId: string) => {
            if (!isRunBookmarksEnabled) return;
            const run = viewerRuns?.[runId];
            if (!run?.metadata) return;

            updateViewerRun({ id: runId, metadata: { ...run.metadata, isBookmarked: false } });

            try {
                await runsApi.bookmarkRun({ runId, isBookmarked: false });
                addSuccessToast('Run removed from bookmarks');
            } catch (err) {
                updateViewerRun({ id: runId, metadata: { ...run.metadata, isBookmarked: true } });
                addErrorToast('Error updating bookmark status.');
                throw err;
            }
        },
        [
            isRunBookmarksEnabled,
            viewerRuns,
            updateViewerRun,
            runsApi,
            addSuccessToast,
            addErrorToast,
        ]
    );

    const memoizedState = useMemo<RunBookmarksState>(
        () => ({
            isRunBookmarksEnabled,
            checkRunBookmarked,
            bookmarkRun,
            unbookmarkRun,
        }),
        [isRunBookmarksEnabled, checkRunBookmarked, bookmarkRun, unbookmarkRun]
    );

    return (
        <RunBookmarksContext.Provider value={memoizedState}>
            {children}
        </RunBookmarksContext.Provider>
    );
};
