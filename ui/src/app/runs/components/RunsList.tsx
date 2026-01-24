'use client';

import {
    Box,
    List,
    ListItem,
    ListItemButton,
    ListItemText,
    Typography,
    CircularProgress,
    Divider,
    styled,
} from '@mui/material';

import Link from 'next/link';

import { useAuth0 } from '@/contexts/Auth0Context';
import { useRuns } from '@/contexts/RunsContext';
import { CreateRunButton } from '@/runs/components/CreateRunButton';

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
    const { isAuthenticated } = useAuth0();
    const { viewerRuns, isViewerRunsLoading } = useRuns();

    if (!isAuthenticated) {
        return (
            <Box sx={{ p: 2 }}>
                <Typography variant="body2" color="text.secondary">
                    Please log in to view runs
                </Typography>
            </Box>
        );
    }

    return (
        <Box
            sx={{
                height: '100%',
                display: 'flex',
                flexDirection: 'column',
            }}>
            <Box sx={{ p: 2 }}>
                <CreateRunButton />
            </Box>

            <Divider />

            {isViewerRunsLoading ? (
                <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
                    <CircularProgress />
                </Box>
            ) : viewerRuns?.length === 0 ? (
                <Box sx={{ p: 2 }}>
                    <Typography variant="body2" color="text.secondary" align="center">
                        No runs yet. Create your first run to get started.
                    </Typography>
                </Box>
            ) : (
                <List sx={{ flexGrow: 1, overflow: 'auto' }}>
                    {viewerRuns?.map((run) => (
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
                                </RunItemButton>
                            </Link>
                        </ListItem>
                    ))}
                </List>
            )}
        </Box>
    );
}

const RunItemButton = styled(ListItemButton)`
    color: ${({ theme }) => theme.color['cream-100'].hex};

    &.Mui-selected {
        background-color: ${({ theme }) => theme.color['cream-10'].rgba.toString()};
    }

    &:hover {
        background-color: ${({ theme }) => theme.color['cream-4'].rgba.toString()};
    }
`;
