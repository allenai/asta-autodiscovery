import { styled } from '@mui/material';
import BookmarkIcon from '@mui/icons-material/Bookmark';
import BookmarkBorderIcon from '@mui/icons-material/BookmarkBorder';
import IconButton from '@mui/material/IconButton';
import { ReactNode, useCallback, useMemo, useState, MouseEvent } from 'react';

import { useViewerRuns } from '@/contexts/ViewerRunsContext';
import { getRunsApi } from '@/api/RunsApi';
import { useToasts } from '@/contexts/ToastsContext';
import { useRunExperiments } from '@/contexts/RunExperimentsContext';

export const ExperimentBookmarkControl = ({
    experimentId,
    hasBookmarkIcon = true,
    noBookmarkIcon = true,
    isToggleable = true,
    onChange,
}: {
    experimentId?: string | null;
    hasBookmarkIcon?: ReactNode;
    noBookmarkIcon?: ReactNode;
    isToggleable?: boolean;
    onChange?: (newValue: boolean) => void;
}) => {
    const runsApi = getRunsApi();
    const { viewerRuns, updateViewerRun } = useViewerRuns();
    const { runid: runId } = useRunExperiments();
    const { addErrorToast } = useToasts();

    const run = runId && viewerRuns ? viewerRuns[runId] : null;

    const isBookmarked = useMemo(() => {
        if (!run || !experimentId) {
            return false;
        }
        const bookmarkedExperimentIds = new Set(run?.metadata?.bookmarkedExperimentIds || []);
        return bookmarkedExperimentIds.has(experimentId);
    }, [run, experimentId]);

    // Update bookmark state locally
    const setIsBookmarked = useCallback(
        (isBookmarked: boolean) => {
            const metadata = run?.metadata;
            if (!metadata || !experimentId) {
                return; // Can't update bookmark without both runId and experimentId
            }

            const bookmarkedExperimentIds = new Set(metadata.bookmarkedExperimentIds || []);
            if (isBookmarked) {
                bookmarkedExperimentIds.add(experimentId);
            } else {
                bookmarkedExperimentIds.delete(experimentId);
            }

            updateViewerRun({
                id: run.id,
                metadata: {
                    ...metadata,
                    bookmarkedExperimentIds: Array.from(bookmarkedExperimentIds),
                },
            });
        },
        [updateViewerRun, run, experimentId]
    );

    // Toggle bookmark state optimistically, then make API call. If API call
    // fails, revert state and show error toast.
    const onClickToggle = useCallback(
        async (event: MouseEvent<HTMLElement>) => {
            event.preventDefault();
            event.stopPropagation(); // Prevent click from propagating to parent elements (e.g., experiment item)

            const isNowBookmarked = !isBookmarked;
            setIsBookmarked(isNowBookmarked);

            try {
                await runsApi.bookmarkExperiment({
                    runId: runId!,
                    experimentId: experimentId!,
                    isBookmarked: isNowBookmarked,
                });
            } catch (error) {
                console.error('Error toggling bookmark:', error);
                addErrorToast('Failed to update bookmark. Please try again.');
                setIsBookmarked(!isNowBookmarked);
                return;
            }

            onChange?.(isNowBookmarked);
        },
        [isBookmarked, onChange, runId, experimentId, addErrorToast, setIsBookmarked]
    );

    // If the caller doesn't provide custom icons, use defaults. If they do
    // provide custom icons, use those instead (even if they are just boolean
    // flags). This allows the caller to control the appearance while we handle
    // the logic.
    const viewHasBookmark =
        hasBookmarkIcon !== true ? (
            hasBookmarkIcon
        ) : (
            <IconButton>
                <BookmarkIcon />
            </IconButton>
        );
    const viewNoBookmark =
        noBookmarkIcon !== true ? (
            noBookmarkIcon
        ) : (
            <IconButton>
                <BookmarkBorderIcon />
            </IconButton>
        );

    if (!runId || !experimentId) {
        return null; // Can't bookmark without both runId and experimentId
    }
    return (
        <ClickableArea
            $isToggleable={isToggleable}
            $isBookmarked={isBookmarked}
            onClick={isToggleable ? onClickToggle : undefined}>
            {isBookmarked ? viewHasBookmark : viewNoBookmark}
        </ClickableArea>
    );
};

const ClickableArea = styled('span')<{ $isToggleable: boolean; $isBookmarked?: boolean }>`
    cursor: ${({ $isToggleable }) => ($isToggleable ? 'pointer' : 'initial')};

    .MuiSvgIcon-root {
        color: ${({ theme, $isBookmarked }) =>
            $isBookmarked ? theme.color['green-100'].hex : theme.color['gray-50'].hex};
    }
`;
