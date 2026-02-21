import { styled } from '@mui/material';
import BookmarkIcon from '@mui/icons-material/Bookmark';
import BookmarkBorderIcon from '@mui/icons-material/BookmarkBorder';
import IconButton from '@mui/material/IconButton';
import { ReactNode, useCallback, useMemo, useState, MouseEvent } from 'react';

import { useViewerRuns } from '@/contexts/ViewerRunsContext';
import { getRunsApi } from '@/api/RunsApi';
import { useToasts } from '@/contexts/ToastsContext';

export const ExperimentBookmarkControl = ({
    runId,
    experimentId,
    hasBookmark = true,
    noBookmark = true,
    onChange,
    isTaggable: isToggleable = true,
}: {
    runId?: string | null;
    experimentId?: string | null;
    hasBookmark?: ReactNode;
    noBookmark?: ReactNode;
    onChange?: (newValue: boolean) => void;
    isTaggable?: boolean;
}) => {
    const runsApi = getRunsApi();
    const { viewerRuns } = useViewerRuns();
    const { addErrorToast } = useToasts();

    // Determine if the experiment is currently bookmarked based on viewerRuns context
    const isBookmarkedInRun = useMemo(() => {
        if (!runId || !experimentId) {
            return false; // Can't be bookmarked without both runId and experimentId
        }
        const run = viewerRuns ? viewerRuns[runId] : null;
        const bookmarkedExperimentIds = new Set(run?.metadata?.bookmarkedExperimentIds || []);
        return bookmarkedExperimentIds.has(experimentId);
    }, [viewerRuns, runId, experimentId]);

    // Allow for optimistic UI update by keeping local state in sync with prop, but decoupled to avoid UI lag during API call
    const [isBookmarked, setIsBookmarked] = useState(isBookmarkedInRun);
    const viewHasBookmark =
        hasBookmark !== true ? (
            hasBookmark
        ) : (
            <IconButton>
                <BookmarkIcon />
            </IconButton>
        );
    const viewNoBookmark =
        noBookmark !== true ? (
            noBookmark
        ) : (
            <IconButton>
                <BookmarkBorderIcon />
            </IconButton>
        );

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
                return;
            }

            onChange?.(isNowBookmarked);
        },
        [isBookmarked, onChange, runId, experimentId, addErrorToast]
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
