import AddBoxIcon from '@mui/icons-material/AddBox';
import { Button, CircularProgress, Typography, styled } from '@mui/material';
import { useState } from 'react';
import { useRouter } from 'next/navigation';

import { getRunFromApi } from '@/types/Run';
import { useRuns } from '@/contexts/RunsContext';
import { getRunsApi } from '@/api/RunsApi';

export const CreateRunButton = () => {
    const router = useRouter();
    const api = getRunsApi();
    const { addViewerRun } = useRuns();
    const [isCreating, setIsCreating] = useState(false);
    const [error, setError] = useState<string | null>();

    const handleRunCreated = (runid: string) => {
        router.push(`/runs/${runid}`);
    };

    const handleCreateRun = async () => {
        setIsCreating(true);
        setError(null);

        try {
            const { data } = await api.createRun();
            const run = getRunFromApi(data);

            // Add new run to list
            addViewerRun(run);

            // Notify parent component
            handleRunCreated(run.id);
        } catch (err) {
            console.error('Error creating run:', err);
            setError(err instanceof Error ? err.message : 'Failed to create run');
        } finally {
            setError(null);
        }
    };

    return (
        <>
            <StyledButton
                variant="contained"
                fullWidth
                startIcon={isCreating ? <CircularProgress size={16} /> : <StyledAddBoxIcon />}
                onClick={handleCreateRun}
                disabled={isCreating}>
                {isCreating ? 'isCreating...' : 'New exploration'}
            </StyledButton>
            {error && (
                <Typography variant="body2" color="error" sx={{ mt: 1 }}>
                    {error}
                </Typography>
            )}
        </>
    );
};

const StyledButton = styled(Button)`
    background-color: ${({ theme }) => theme.color['cream-10'].rgba.toString()};
    color: ${({ theme }) => theme.color['cream-100'].hex};

    &:hover {
        background-color: ${({ theme }) => theme.color['cream-20'].rgba.toString()};
    }
`;

const StyledAddBoxIcon = styled(AddBoxIcon)`
    color: ${({ theme }) => theme.color['green-100'].hex};
`;
