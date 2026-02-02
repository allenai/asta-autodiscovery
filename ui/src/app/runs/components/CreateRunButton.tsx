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
            setIsCreating(false);
        }
    };

    return (
        <>
            <StyledButton
                variant="outlined"
                fullWidth
                startIcon={isCreating ? <CircularProgress size={16} /> : <StyledAddBoxIcon />}
                onClick={handleCreateRun}
                disabled={isCreating}>
                {isCreating ? 'Creating...' : 'New discovery session'}
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
    &.MuiButton-root {
        color: ${({ theme }) => theme.color['cream-100'].hex};
        padding: ${({ theme }) => theme.spacing(0, 2)};
        height: 40px;
        white-space: nowrap;
        overflow: hidden;
        justify-content: flex-start;

        & .MuiButton-startIcon {
            flex-shrink: 0;
        }
    }

    &.MuiButton-outlined {
        border: 1px solid ${({ theme }) => theme.color['cream-20'].rgba.toString()};

        &:hover {
            border: 1px solid ${({ theme }) => theme.color['cream-40'].rgba.toString()};
        }
    }

    & span.MuiButton-label {
        overflow: hidden;
        text-overflow: ellipsis;
    }
`;

const StyledAddBoxIcon = styled(AddBoxIcon)`
    color: ${({ theme }) => theme.color['green-100'].hex};
`;
