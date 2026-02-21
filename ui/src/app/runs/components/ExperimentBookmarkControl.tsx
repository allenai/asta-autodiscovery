import { styled } from '@mui/material';
import BookmarkIcon from '@mui/icons-material/Bookmark';
import BookmarkBorderIcon from '@mui/icons-material/BookmarkBorder';
import IconButton from '@mui/material/IconButton';
import { ReactNode, useCallback, useMemo, MouseEvent } from 'react';

import { useViewerRuns } from '@/contexts/ViewerRunsContext';
import { getRunsApi } from '@/api/RunsApi';
import { useToasts } from '@/contexts/ToastsContext';
import { useRunExperiments } from '@/contexts/RunExperimentsContext';
import { Experiment } from '@/types/Run';

export const ExperimentBookmarkControl = ({
    experiment,
    hasBookmarkIcon = true,
    noBookmarkIcon = true,
    isToggleable = true,
    onChange,
}: {
    experiment?: Experiment;
    hasBookmarkIcon?: ReactNode;
    noBookmarkIcon?: ReactNode;
    isToggleable?: boolean;
    onChange?: (newValue: boolean) => void;
}) => {
    const runsApi = getRunsApi();
    const { runid: runId, bookmarkedExperimentIds, updateExperimentBookmark } = useRunExperiments();
    const { addErrorToast } = useToasts();

    const isBookmarked = experiment ? bookmarkedExperimentIds.has(experiment.experimentId) : false;

    // Toggle bookmark state optimistically, then make API call. If API call
    // fails, revert state and show error toast.
    const onClickToggle = useCallback(
        async (event: MouseEvent<HTMLElement>) => {
            event.preventDefault();
            event.stopPropagation(); // Prevent click from propagating to parent elements (e.g., experiment item)

            const isNowBookmarked = !isBookmarked;
            updateExperimentBookmark(experiment!, { isBookmarked: isNowBookmarked });

            try {
                await runsApi.bookmarkExperiment({
                    runId: runId!,
                    experimentId: experiment!.experimentId,
                    isBookmarked: isNowBookmarked,
                });
            } catch (error) {
                console.error('Error toggling bookmark:', error);
                addErrorToast('Failed to update bookmark. Please try again.');
                updateExperimentBookmark(experiment!, { isBookmarked: !isNowBookmarked });
                return;
            }

            onChange?.(isNowBookmarked);
        },
        [isBookmarked, onChange, runId, experiment, addErrorToast, updateExperimentBookmark]
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

    if (!runId || !experiment) {
        return null; // Can't bookmark without both runId and experiment
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
