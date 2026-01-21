'use client';

import { useEffect, useState } from 'react';
import {
    Box,
    List,
    ListItem,
    ListItemButton,
    ListItemText,
    Typography,
    Button,
    CircularProgress,
    Alert,
    Divider,
    styled,
} from '@mui/material';
import AddBoxIcon from '@mui/icons-material/AddBox';

import Link from 'next/link';

import { useAuth0 } from '@/contexts/Auth0Context';
import { getRunsApi } from '@/api/RunsApi';
import { getRunFromApi } from '@/types/Run';

interface RunsListProps {
    selectedRunId: string | null;
    onSelectRun: (runid: string) => void;
    onRunCreated: (runid: string) => void;
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
export default function RunsList({ selectedRunId, onSelectRun, onRunCreated }: RunsListProps) {
    const { isAuthenticated } = useAuth0();
    const [runs, setRuns] = useState<string[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [creating, setCreating] = useState(false);
    const api = getRunsApi();

    const fetchRuns = async () => {
        if (!isAuthenticated) return;

        setLoading(true);
        setError(null);

        try {
            const runsList = await api.listRuns();
            setRuns(runsList.data.runs);
        } catch (err) {
            console.error('Error fetching runs:', err);
            setError(err instanceof Error ? err.message : 'Failed to load runs');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchRuns();
    }, [isAuthenticated]);

    const handleCreateRun = async () => {
        setCreating(true);
        setError(null);

        try {
            const { data } = await api.createRun();
            const run = getRunFromApi(data);

            // Add new run to list
            setRuns([run.id, ...runs]);

            // Notify parent component
            onRunCreated(run.id);
        } catch (err) {
            console.error('Error creating run:', err);
            setError(err instanceof Error ? err.message : 'Failed to create run');
        } finally {
            setCreating(false);
        }
    };

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
                <CreateRunButton
                    variant="contained"
                    fullWidth
                    startIcon={creating ? <CircularProgress size={16} /> : <StyledAddBoxIcon />}
                    onClick={handleCreateRun}
                    disabled={creating}>
                    {creating ? 'Creating...' : 'New exploration'}
                </CreateRunButton>
            </Box>

            <Divider />

            {error && (
                <Box sx={{ p: 2 }}>
                    <Alert severity="error" onClose={() => setError(null)}>
                        {error}
                    </Alert>
                </Box>
            )}

            {loading ? (
                <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
                    <CircularProgress />
                </Box>
            ) : runs.length === 0 ? (
                <Box sx={{ p: 2 }}>
                    <Typography variant="body2" color="text.secondary" align="center">
                        No runs yet. Create your first run to get started.
                    </Typography>
                </Box>
            ) : (
                <List sx={{ flexGrow: 1, overflow: 'auto' }}>
                    {runs.map((runid) => (
                        <ListItem key={runid} disablePadding>
                            <Link
                                href={`/runs/${runid}`}
                                style={{
                                    textDecoration: 'none',
                                    color: 'inherit',
                                    width: '100%',
                                }}>
                                <RunItemButton
                                    selected={selectedRunId === runid}
                                    onClick={() => onSelectRun(runid)}>
                                    <ListItemText
                                        primary={runid}
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

const CreateRunButton = styled(Button)`
    background-color: ${({ theme }) => theme.color['cream-10'].rgba.toString()};
    color: ${({ theme }) => theme.color['cream-100'].hex};
`;

const StyledAddBoxIcon = styled(AddBoxIcon)`
    color: ${({ theme }) => theme.color['green-100'].hex};
`;
