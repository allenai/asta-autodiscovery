'use client';

import { useState } from 'react';
import {
    Alert,
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
    Snackbar,
} from '@mui/material';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import DeleteIcon from '@mui/icons-material/Delete';
import CircularProgress from '@mui/material/CircularProgress';

import Link from 'next/link';
import { useRouter } from 'next/navigation';

import { useRuns } from '@/contexts/RunsContext';
import { CreateRunButton } from '@/runs/components/CreateRunButton';
import { getRunsApi } from '@/api/RunsApi';
import { Run, RunStatus } from '@/types/Run';

const isDraftRun = (run: Run): boolean => {
    return run.details?.status === RunStatus.CREATED && !run.details?.executionId;
};

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
    const { viewerRuns, isViewerRunsLoading, removeViewerRun } = useRuns();
    const router = useRouter();
    const api = getRunsApi();

    const draftRuns = viewerRuns?.filter(isDraftRun) ?? [];
    const submittedRuns = viewerRuns?.filter((run) => !isDraftRun(run)) ?? [];

    const [menuAnchorEl, setMenuAnchorEl] = useState<null | HTMLElement>(null);
    const [menuRunId, setMenuRunId] = useState<string | null>(null);
    const [deletingRunId, setDeletingRunId] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);

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
            setError(err instanceof Error ? err.message : 'Failed to delete run');
        } finally {
            setDeletingRunId(null);
        }
    };

    const handleCloseError = () => {
        setError(null);
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
            ) : viewerRuns?.length === 0 ? (
                <Box sx={{ p: 2 }}>
                    <Typography variant="body2" color="text.secondary" align="center">
                        No runs yet. Create your first run to get started.
                    </Typography>
                </Box>
            ) : (
                <Box sx={{ flexGrow: 1, overflow: 'auto' }}>
                    {draftRuns.length > 0 && (
                        <>
                            <SectionTitle>Your Drafts</SectionTitle>
                            <List disablePadding>
                                {draftRuns.map((run) => (
                                    <ListItem key={run.id} disablePadding>
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
                                                        onClick={(
                                                            e: React.MouseEvent<HTMLElement>
                                                        ) => handleMenuOpen(e, run.id)}>
                                                        <MoreVertIcon fontSize="small" />
                                                    </MenuButton>
                                                )}
                                            </RunItemButton>
                                        </Link>
                                    </ListItem>
                                ))}
                            </List>
                        </>
                    )}

                    {submittedRuns.length > 0 && (
                        <>
                            <SectionTitle>Your Sessions</SectionTitle>
                            <List disablePadding>
                                {submittedRuns.map((run) => (
                                    <ListItem key={run.id} disablePadding>
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
                                                        onClick={(
                                                            e: React.MouseEvent<HTMLElement>
                                                        ) => handleMenuOpen(e, run.id)}>
                                                        <MoreVertIcon fontSize="small" />
                                                    </MenuButton>
                                                )}
                                            </RunItemButton>
                                        </Link>
                                    </ListItem>
                                ))}
                            </List>
                        </>
                    )}
                </Box>
            )}

            <Menu anchorEl={menuAnchorEl} open={Boolean(menuAnchorEl)} onClose={handleMenuClose}>
                <MenuItem onClick={handleDelete}>
                    <ListItemIcon>
                        <DeleteIcon fontSize="small" />
                    </ListItemIcon>
                    Delete
                </MenuItem>
            </Menu>

            <Snackbar open={Boolean(error)} autoHideDuration={6000} onClose={handleCloseError}>
                <Alert onClose={handleCloseError} severity="error" sx={{ width: '100%' }}>
                    {`Failed to delete run: ${error}`}
                </Alert>
            </Snackbar>
        </Box>
    );
}

const StyledDivider = styled(Divider)`
    border-color: ${({ theme }) => theme.color['cream-10'].rgba.toString()};
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
