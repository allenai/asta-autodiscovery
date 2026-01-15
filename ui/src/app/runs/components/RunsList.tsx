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
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';

import { useAuth0 } from '@/app/contexts/Auth0Context';
import { listRuns, createRun } from '../actions';

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
    const { isAuthenticated, getAccessToken } = useAuth0();
    const [runs, setRuns] = useState<string[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [creating, setCreating] = useState(false);

    const fetchRuns = async () => {
        if (!isAuthenticated) return;

        setLoading(true);
        setError(null);

        try {
            const token = await getAccessToken();
            const runsList = await listRuns(token);
            setRuns(runsList);
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
            const token = await getAccessToken();
            const response = await createRun(token);

            // Add new run to list
            setRuns([response.runid, ...runs]);

            // Notify parent component
            onRunCreated(response.runid);
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
                borderRight: 1,
                borderColor: 'divider',
            }}>
            <Box sx={{ p: 2 }}>
                <Typography variant="h6" gutterBottom>
                    Runs
                </Typography>
                <Button
                    variant="contained"
                    color="primary"
                    fullWidth
                    startIcon={creating ? <CircularProgress size={16} /> : <AddIcon />}
                    onClick={handleCreateRun}
                    disabled={creating}>
                    {creating ? 'Creating...' : 'Create New Run'}
                </Button>
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
                            <ListItemButton
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
                            </ListItemButton>
                        </ListItem>
                    ))}
                </List>
            )}
        </Box>
    );
}
