'use client';

import { createContext, PropsWithChildren, useCallback, useContext, useMemo } from 'react';

import { getRunsApi } from '@/api/RunsApi';
import { useToasts } from '@/contexts/ToastsContext';
import { useViewerRuns } from '@/contexts/ViewerRunsContext';
import { Experiment } from '@/types/Run';

export interface ExperimentBookmarksState {
    isExperimentBookmarksEnabled: boolean;
    bookmarkedExperimentIds: Set<string>;
    checkExperimentBookmarked: (experimentId: string) => boolean;
    bookmarkExperiment: (experiment: Experiment) => Promise<void>;
    unbookmarkExperiment: (experiment: Experiment) => Promise<void>;
}

const DEFAULT_STATE: ExperimentBookmarksState = {
    isExperimentBookmarksEnabled: false,
    bookmarkedExperimentIds: new Set(),
    checkExperimentBookmarked: () => false,
    bookmarkExperiment: async () => {},
    unbookmarkExperiment: async () => {},
};

const ExperimentBookmarksContext = createContext<ExperimentBookmarksState>(DEFAULT_STATE);
export default ExperimentBookmarksContext;

export const useExperimentBookmarks = (): ExperimentBookmarksState => {
    const context = useContext(ExperimentBookmarksContext);
    if (!context) {
        throw new Error(
            'useExperimentBookmarks must be used within an ExperimentBookmarksProvider'
        );
    }
    return context;
};

export type ExperimentBookmarksProps = PropsWithChildren<{
    isExperimentBookmarksEnabled: boolean;
    runid: string | null;
}>;

export const ExperimentBookmarksProvider = ({
    isExperimentBookmarksEnabled,
    runid,
    children,
}: ExperimentBookmarksProps) => {
    const runsApi = getRunsApi();
    const { viewerRuns, updateViewerRun } = useViewerRuns();
    const { addErrorToast } = useToasts();

    const bookmarkedExperimentIds = useMemo(() => {
        if (!runid || !viewerRuns) {
            return new Set<string>();
        }
        const run = viewerRuns[runid];
        return new Set(run?.metadata?.bookmarkedExperimentIds || []);
    }, [runid, viewerRuns]);

    const checkExperimentBookmarked = useCallback(
        (experimentId: string): boolean => {
            return bookmarkedExperimentIds.has(experimentId);
        },
        [bookmarkedExperimentIds]
    );

    const bookmarkExperiment = useCallback(
        async (experiment: Experiment) => {
            if (!isExperimentBookmarksEnabled || !runid) return;
            const metadata = viewerRuns?.[runid]?.metadata;
            if (!metadata) return;

            const updatedIds = new Set(bookmarkedExperimentIds);
            updatedIds.add(experiment.experimentId);
            updateViewerRun({
                id: runid,
                metadata: { ...metadata, bookmarkedExperimentIds: Array.from(updatedIds) },
            });

            try {
                await runsApi.bookmarkExperiment({
                    runId: runid,
                    experimentId: experiment.experimentId,
                    isBookmarked: true,
                });
            } catch (err) {
                const revertedIds = new Set(bookmarkedExperimentIds);
                revertedIds.delete(experiment.experimentId);
                updateViewerRun({
                    id: runid,
                    metadata: { ...metadata, bookmarkedExperimentIds: Array.from(revertedIds) },
                });
                addErrorToast('Failed to update bookmark. Please try again.');
                throw err;
            }
        },
        [
            isExperimentBookmarksEnabled,
            runid,
            viewerRuns,
            bookmarkedExperimentIds,
            updateViewerRun,
            runsApi,
            addErrorToast,
        ]
    );

    const unbookmarkExperiment = useCallback(
        async (experiment: Experiment) => {
            if (!isExperimentBookmarksEnabled || !runid) return;
            const metadata = viewerRuns?.[runid]?.metadata;
            if (!metadata) return;

            const updatedIds = new Set(bookmarkedExperimentIds);
            updatedIds.delete(experiment.experimentId);
            updateViewerRun({
                id: runid,
                metadata: { ...metadata, bookmarkedExperimentIds: Array.from(updatedIds) },
            });

            try {
                await runsApi.bookmarkExperiment({
                    runId: runid,
                    experimentId: experiment.experimentId,
                    isBookmarked: false,
                });
            } catch (err) {
                const revertedIds = new Set(bookmarkedExperimentIds);
                revertedIds.add(experiment.experimentId);
                updateViewerRun({
                    id: runid,
                    metadata: { ...metadata, bookmarkedExperimentIds: Array.from(revertedIds) },
                });
                addErrorToast('Failed to update bookmark. Please try again.');
                throw err;
            }
        },
        [
            isExperimentBookmarksEnabled,
            runid,
            viewerRuns,
            bookmarkedExperimentIds,
            updateViewerRun,
            runsApi,
            addErrorToast,
        ]
    );

    const memoizedState = useMemo<ExperimentBookmarksState>(
        () => ({
            isExperimentBookmarksEnabled,
            bookmarkedExperimentIds,
            checkExperimentBookmarked,
            bookmarkExperiment,
            unbookmarkExperiment,
        }),
        [
            isExperimentBookmarksEnabled,
            bookmarkedExperimentIds,
            checkExperimentBookmarked,
            bookmarkExperiment,
            unbookmarkExperiment,
        ]
    );

    return (
        <ExperimentBookmarksContext.Provider value={memoizedState}>
            {children}
        </ExperimentBookmarksContext.Provider>
    );
};
