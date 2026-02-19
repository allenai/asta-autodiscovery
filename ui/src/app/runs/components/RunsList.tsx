'use client';

import { useState, useMemo } from 'react';
import {
    Box,
    List,
    ListItem,
    ListItemButton,
    ListItemText,
    ListItemIcon,
    Typography,
    Divider,
    styled,
    Skeleton,
    IconButton,
    Menu,
    MenuItem,
} from '@mui/material';
import BookmarkIcon from '@mui/icons-material/Bookmark';
import BookmarkBorderOutlinedIcon from '@mui/icons-material/BookmarkBorderOutlined';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import DeleteIcon from '@mui/icons-material/Delete';
import CircularProgress from '@mui/material/CircularProgress';

import Link from 'next/link';
import { useRouter } from 'next/navigation';

import { useViewerRuns } from '@/contexts/ViewerRunsContext';
import { CreateRunButton } from '@/runs/components/CreateRunButton';
import { getRunsApi } from '@/api/RunsApi';
import { mkBookmarkRunBtnAttrs, mkDeleteRunBtnAttrs, mkRunListItemAttrs } from '@/analytics/run';
import { scrollbarStyles } from '@/utils/scrollbar';
import { useToasts } from '@/contexts/ToastsContext';

interface RunsListProps {
    selectedRunId: string | null;
    onSelectRun: (runid: string) => void;
}

/**
 * Sidebar component that displays a list of user's runs.
 *
 * Features:
 * - Lists all runs for authenticated user
 * - "Create New Run" button
 * - Highlights currently selected run
 * - Loading and error states
 */
export default function RunsList({ selectedRunId, onSelectRun }: RunsListProps) {
    const { viewerRuns, isViewerRunsLoading, removeViewerRun, updateViewerRun } = useViewerRuns();
    const { addErrorToast, addSuccessToast } = useToasts();
    const router = useRouter();
    const api = getRunsApi();

    const sortedRuns = useMemo(
        () =>
            Object.values(viewerRuns ?? {}).sort((a, b) => {
                // First, sort by bookmarked status (bookmarked runs first)
                const aBookmarked = a.metadata?.isBookmarked ?? false;
                const bBookmarked = b.metadata?.isBookmarked ?? false;
                if (aBookmarked !== bBookmarked) {
                    return bBookmarked ? 1 : -1; // bookmarked comes first
                }

                // Then sort by time (newest first)
                const aTime = a.details?.statusCheckedAt || a.details?.createdAt || '';
                const bTime = b.details?.statusCheckedAt || b.details?.createdAt || '';
                return bTime.localeCompare(aTime); // descending (newest first)
            }),
        [viewerRuns]
    );

    const [menuAnchorEl, setMenuAnchorEl] = useState<null | HTMLElement>(null);
    const [menuRunId, setMenuRunId] = useState<string | null>(null);
    const [deletingRunId, setDeletingRunId] = useState<string | null>(null);

    const handleMenuOpen = (event: React.MouseEvent<HTMLElement>, runId: string) => {
        event.preventDefault();
        event.stopPropagation();
        setMenuAnchorEl(event.currentTarget);
        setMenuRunId(runId);
    };

    const handleMenuClose = () => {
        setMenuAnchorEl(null);
        setMenuRunId(null);
    };

    const getIsRunBookmarked = () => {
        if (!menuRunId) return false;
        const run = viewerRuns?.[menuRunId];
        return run?.metadata?.isBookmarked ?? false;
    };

    const handleBookmark = async () => {
        if (!menuRunId) return;

        const run = viewerRuns?.[menuRunId];
        if (!run?.metadata) return;

        const newBookmarkStatus = !run.metadata.isBookmarked;
        handleMenuClose();

        // Optimistically update
        updateViewerRun({
            id: run.id,
            metadata: {
                ...run.metadata,
                isBookmarked: newBookmarkStatus,
            },
        });

        try {
            await api.bookmarkRun({ runId: run.id, isBookmarked: newBookmarkStatus });
            addSuccessToast(newBookmarkStatus ? 'Run bookmarked' : 'Run removed from bookmarks');
        } catch (err) {
            // Rollback on error
            updateViewerRun({
                id: run.id,
                metadata: {
                    ...run.metadata,
                    isBookmarked: !newBookmarkStatus,
                },
            });
            addErrorToast('Error updating bookmark status');
        }
    };

    const handleDelete = async () => {
        if (!menuRunId) return;

        const runIdToDelete = menuRunId;
        handleMenuClose();
        setDeletingRunId(runIdToDelete);

        try {
            await api.deleteRun(runIdToDelete);
            removeViewerRun(runIdToDelete);

            if (selectedRunId === runIdToDelete) {
                router.push('/runs');
            }
        } catch (err) {
            addErrorToast(err instanceof Error ? err.message : 'Failed to delete run');
        } finally {
            setDeletingRunId(null);
        }
    };

    return (
        <Box
            sx={{
                height: '100%',
                display: 'flex',
                flexDirection: 'column',
            }}>
            <StyledDivider />

            <Box sx={{ p: 2 }}>
                <CreateRunButton />
            </Box>

            {isViewerRunsLoading ? (
                <SkeletonWrapper>
                    {Array.from({ length: 5 }).map((_, index) => (
                        <RunSkeleton key={index} animation="wave" />
                    ))}
                </SkeletonWrapper>
            ) : Object.keys(viewerRuns ?? {}).length === 0 ? (
                <Box sx={{ p: 2 }}>
                    <Typography
                        variant="body2"
                        align="center"
                        sx={{ color: (theme) => theme.color['cream-100'].hex }}>
                        No runs yet. Create your first run to get started.
                    </Typography>
                </Box>
            ) : (
                <ScrollableListContainer>
                    <SectionTitle>Your sessions</SectionTitle>
                    <List disablePadding>
                        {sortedRuns.map((run) => (
                            <ListItem
                                key={run.id}
                                disablePadding
                                {...mkRunListItemAttrs({ runId: run.id })}>
                                <Link
                                    href={`/runs/${run.id}`}
                                    style={{
                                        textDecoration: 'none',
                                        color: 'inherit',
                                        width: '100%',
                                    }}>
                                    <RunItemButton
                                        selected={selectedRunId === run.id}
                                        onClick={() => onSelectRun(run.id)}>
                                        {run.metadata?.isBookmarked && (
                                            <BookmarkButton>
                                                <BookmarkIcon fontSize="small" />
                                            </BookmarkButton>
                                        )}
                                        <ListItemText
                                            primary={run.name || run.id}
                                            primaryTypographyProps={{
                                                variant: 'body2',
                                                noWrap: true,
                                                sx: {
                                                    fontFamily: 'monospace',
                                                    fontSize: '0.85rem',
                                                },
                                            }}
                                        />
                                        {deletingRunId === run.id ? (
                                            <CircularProgress size={20} sx={{ mx: 1 }} />
                                        ) : (
                                            <MenuButton
                                                size="small"
                                                onClick={(e: React.MouseEvent<HTMLElement>) =>
                                                    handleMenuOpen(e, run.id)
                                                }>
                                                <MoreVertIcon fontSize="small" />
                                            </MenuButton>
                                        )}
                                    </RunItemButton>
                                </Link>
                            </ListItem>
                        ))}
                    </List>
                </ScrollableListContainer>
            )}

            <Menu anchorEl={menuAnchorEl} open={Boolean(menuAnchorEl)} onClose={handleMenuClose}>
                <MenuItem
                    onClick={handleBookmark}
                    {...(menuRunId &&
                        mkBookmarkRunBtnAttrs({
                            runId: menuRunId,
                            isBookmarked: !getIsRunBookmarked(),
                        }))}>
                    <ListItemIcon>
                        {getIsRunBookmarked() ? (
                            <BookmarkBorderOutlinedIcon fontSize="small" />
                        ) : (
                            <BookmarkIcon fontSize="small" />
                        )}
                    </ListItemIcon>
                    {getIsRunBookmarked() ? 'Unbookmark' : 'Bookmark'}
                </MenuItem>
                <MenuItem
                    onClick={handleDelete}
                    {...(menuRunId && mkDeleteRunBtnAttrs({ runId: menuRunId }))}>
                    <ListItemIcon>
                        <DeleteIcon fontSize="small" />
                    </ListItemIcon>
                    Delete
                </MenuItem>
            </Menu>
        </Box>
    );
}

const StyledDivider = styled(Divider)`
    border-color: ${({ theme }) => theme.color['cream-10'].rgba.toString()};
`;

const ScrollableListContainer = styled(Box)`
    flex-grow: 1;
    overflow: auto;
    ${({ theme }) => scrollbarStyles(theme)}
`;

const SectionTitle = styled(Typography)`
    color: ${({ theme }) => theme.color['green-100'].hex};
    font-family: 'PP Telegraf', Manrope, sans-serif;
    font-size: 14px;
    font-weight: 700;
    padding: ${({ theme }) => theme.spacing(2, 2, 1, 2)};
`;

const RunItemButton = styled(ListItemButton)`
    color: ${({ theme }) => theme.color['cream-100'].hex};

    &.Mui-selected {
        background-color: ${({ theme }) => theme.color['cream-10'].rgba.toString()};
    }

    &:hover {
        background-color: ${({ theme }) => theme.color['cream-4'].rgba.toString()};
    }
`;

const SkeletonWrapper = styled(Box)`
    display: flex;
    flex-direction: column;
    gap: ${({ theme }) => theme.spacing(0.5)};
    padding: ${({ theme }) => theme.spacing(2)};
`;

const RunSkeleton = styled(Skeleton)`
    background-color: ${({ theme }) => theme.color['cream-20'].rgba.toString()};
    height: 35px;
    width: 100%;
`;

const MenuButton = styled(IconButton)`
    color: ${({ theme }) => theme.color['cream-60'].hex};
    opacity: 0;
    transition: opacity 0.2s;

    .MuiListItemButton-root:hover & {
        opacity: 1;
    }

    &:hover {
        color: ${({ theme }) => theme.color['cream-100'].hex};
        background-color: ${({ theme }) => theme.color['cream-10'].rgba.toString()};
    }
`;

const BookmarkButton = styled(IconButton)`
    color: ${({ theme }) => theme.color['green-100'].hex};
    margin-right: ${({ theme }) => theme.spacing(0.5)};
    padding: 0;
`;
