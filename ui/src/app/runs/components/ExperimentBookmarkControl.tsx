import { styled } from '@mui/material';
import BookmarkIcon from '@mui/icons-material/Bookmark';
import BookmarkBorderIcon from '@mui/icons-material/BookmarkBorder';
import IconButton from '@mui/material/IconButton';
import { ReactNode, useCallback, MouseEvent } from 'react';

import { useExperimentBookmarks } from '@/contexts/ExperimentBookmarksContext';
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
    const {
        isExperimentBookmarksEnabled,
        checkExperimentBookmarked,
        bookmarkExperiment,
        unbookmarkExperiment,
    } = useExperimentBookmarks();

    const isBookmarked = experiment ? checkExperimentBookmarked(experiment.experimentId) : false;

    // Toggle bookmark state optimistically via context, then make API call. If API call
    // fails, context reverts state and shows error toast.
    const onClickToggle = useCallback(
        async (event: MouseEvent<HTMLElement>) => {
            event.preventDefault();
            event.stopPropagation(); // Prevent click from propagating to parent elements (e.g., experiment item)

            const isNowBookmarked = !isBookmarked;
            try {
                if (isNowBookmarked) {
                    await bookmarkExperiment(experiment!);
                } else {
                    await unbookmarkExperiment(experiment!);
                }
            } catch {
                return;
            }

            onChange?.(isNowBookmarked);
        },
        [isBookmarked, onChange, experiment, bookmarkExperiment, unbookmarkExperiment]
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

    if (!isExperimentBookmarksEnabled || !experiment) {
        return null;
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
