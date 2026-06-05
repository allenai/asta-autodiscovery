'use client';

import {
    Box,
    Button,
    CircularProgress,
    Dialog,
    DialogContent,
    IconButton,
    TextField,
    Typography,
    styled,
} from '@mui/material';
import ArrowOutwardIcon from '@mui/icons-material/ArrowOutward';
import CloseIcon from '@mui/icons-material/Close';
import { useEffect, useState } from 'react';

import { getRunsApi } from '@/api/RunsApi';
import { Experiment } from '@/types/Run';

interface ContinueWithAstaModalProps {
    open: boolean;
    onClose: () => void;
    runId: string;
    experiment?: Experiment | null;
}

const PROMPT_LABEL =
    'Do you want to continue exploring this experiment? The datasets, hypothesis, and results will be passed to Asta as context.';

export function ContinueWithAstaModal({
    open,
    onClose,
    runId,
    experiment,
}: ContinueWithAstaModalProps) {
    const [prompt, setPrompt] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (!open) {
            setPrompt('');
            setError(null);
        }
    }, [open]);

    const handleStart = async () => {
        if (!experiment) return;
        setIsLoading(true);
        setError(null);
        try {
            const result = await getRunsApi().digDeeperWithAsta({
                runId,
                experimentId: experiment.experimentId,
                query: prompt,
            });
            window.open(result.data.asta_url, '_blank', 'noopener,noreferrer');
            onClose();
        } catch {
            setError('Failed to start Asta session. Please try again.');
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <Dialog
            open={open}
            onClose={onClose}
            maxWidth={false}
            PaperProps={{
                sx: {
                    width: '90%',
                    maxWidth: '640px',
                    borderRadius: '12px',
                },
            }}
            slotProps={{
                backdrop: {
                    sx: {
                        backgroundColor: 'rgba(0, 0, 0, 0.8)',
                    },
                },
            }}>
            <CloseButton
                onClick={onClose}
                aria-label="close"
                sx={(theme) => ({
                    color: theme.color['cream-100'].hex,
                    '&:hover': {
                        color: theme.color['green-100'].hex,
                    },
                })}>
                <CloseIcon />
            </CloseButton>
            <StyledDialogContent>
                <SvgSlot aria-hidden="true">
                    <svg
                        role="img"
                        xmlns="http://www.w3.org/2000/svg"
                        width="160"
                        height="60"
                        viewBox="0 0 153.44 57.41"
                        fill="none"
                        aria-labelledby="asta-logo">
                        <title id="asta-logo"> Asta </title>
                        <path
                            fill="#0FCB8C"
                            d="M14.15,24.7h-7.07v-6.84h5.7c.76,0,1.38-.63,1.38-1.4v-5.79h6.73v7.19c0,3.78-3.01,6.84-6.73,6.84ZM7.07,25.4H0v6.84h5.7c.76,0,1.38.63,1.38,1.4v5.79h6.73v-7.19c0-3.78-3.01-6.84-6.73-6.84ZM29.68,25.05c-.76,0-1.38-.63-1.38-1.4v-5.79h-6.73v7.19c0,3.78,3.01,6.84,6.73,6.84h7.07v-6.84h-5.7ZM14.49,39.43v7.19h6.73v-5.79c0-.77.62-1.4,1.38-1.4h5.7v-6.84h-7.07c-3.72,0-6.73,3.06-6.73,6.84Z"></path>
                        <path
                            fill="#0FCB8C"
                            d="M138.49,47.28c-2.76,0-4.95-.7-6.56-2.1-1.58-1.4-2.37-3.33-2.37-5.81,0-2.22.63-4,1.88-5.32,1.29-1.36,3.39-2.29,6.29-2.8l6.72-1.13c1.33-.22,2.28-.56,2.85-1.02.61-.47.91-1.16.91-2.1,0-1.33-.45-2.33-1.34-3.01-.86-.72-2.38-1.08-4.57-1.08s-3.84.43-4.95,1.29c-1.08.86-1.68,2.15-1.83,3.87h-5.38c.04-2.9,1.09-5.18,3.17-6.83s5-2.47,8.76-2.47,6.36.75,8.23,2.26c1.9,1.51,2.85,3.53,2.85,6.08v13.33c0,1.97.09,4.01.27,6.13h-4.89c-.21-2.11-.32-4.14-.32-6.08-.61,1.94-1.72,3.55-3.33,4.84-1.61,1.29-3.75,1.94-6.4,1.94ZM139.62,43.14c2.72,0,4.84-.9,6.34-2.69,1.51-1.83,2.26-4.14,2.26-6.94v-1.61c-.65.47-1.34.84-2.1,1.13-.75.25-1.65.5-2.69.75l-3.71.86c-1.68.39-2.9.95-3.66,1.67-.75.68-1.13,1.63-1.13,2.85s.41,2.24,1.24,2.96c.86.68,2.01,1.02,3.44,1.02Z"></path>
                        <path
                            fill="#0FCB8C"
                            d="M119.96,46.58c-2.15,0-3.82-.27-5-.81-1.15-.57-1.95-1.42-2.42-2.53-.47-1.15-.7-2.67-.7-4.57v-14.84h-5.11v-2.8l5.59-1.94,2.2-5.48h2.69v6.08h8.6v4.14h-8.6v18.44h8.07v4.3h-5.32Z"></path>
                        <path
                            fill="#0FCB8C"
                            d="M85.57,37.6c.11,1.76.79,3.17,2.04,4.25,1.25,1.08,3.12,1.61,5.59,1.61,2.26,0,3.82-.34,4.68-1.02.86-.72,1.29-1.76,1.29-3.12,0-1.11-.34-1.97-1.02-2.58-.65-.65-1.67-1.08-3.06-1.29l-6.67-1.02c-2.33-.36-4.12-1.16-5.38-2.42-1.22-1.25-1.83-2.9-1.83-4.95,0-2.58.99-4.61,2.96-6.08,1.97-1.47,4.71-2.2,8.23-2.2s6.15.79,8.23,2.37c2.08,1.54,3.21,3.6,3.39,6.18h-5.38c-.14-1.33-.75-2.42-1.83-3.28-1.08-.86-2.6-1.29-4.57-1.29s-3.44.36-4.41,1.08c-.93.68-1.4,1.6-1.4,2.74,0,.9.27,1.63.81,2.2.57.57,1.54.97,2.9,1.18l5.81.86c3.15.47,5.36,1.4,6.61,2.8,1.25,1.36,1.88,3.17,1.88,5.43,0,2.8-.93,4.89-2.8,6.29-1.86,1.4-4.73,2.1-8.6,2.1-4.23,0-7.37-.9-9.41-2.69-2.04-1.83-3.06-4.21-3.06-7.15h5Z"></path>
                        <path
                            fill="#0FCB8C"
                            d="M72.56,46.58l-3.17-8.5h-17.31l-3.17,8.5h-5.59l13.28-35.76h8.33l13.28,35.76h-5.65ZM53.74,33.63h13.98l-6.99-18.87-6.99,18.87Z"></path>
                    </svg>
                </SvgSlot>
                <PromptFieldGroup>
                    <PromptLabel htmlFor="continue-with-asta-prompt">{PROMPT_LABEL}</PromptLabel>
                    <PromptField
                        id="continue-with-asta-prompt"
                        multiline
                        minRows={4}
                        maxRows={10}
                        fullWidth
                        value={prompt}
                        onChange={(e) => setPrompt(e.target.value)}
                        variant="outlined"
                        placeholder="Enter a follow-up question, or hypothesis to test."
                    />
                </PromptFieldGroup>
                {error && (
                    <Typography variant="body2" sx={{ color: 'error.main', mt: 0.5 }}>
                        {error}
                    </Typography>
                )}
                <Actions>
                    <StartButton
                        variant="outlined"
                        endIcon={
                            isLoading ? (
                                <CircularProgress size={16} color="inherit" />
                            ) : (
                                <ArrowOutwardIcon />
                            )
                        }
                        onClick={handleStart}
                        disabled={!experiment || isLoading}>
                        Start exploration
                    </StartButton>
                </Actions>
            </StyledDialogContent>
        </Dialog>
    );
}

const CloseButton = styled(IconButton)`
    position: absolute;
    top: 12px;
    right: 12px;
    cursor: pointer;
    transition: color 250ms ease-out;
    z-index: 1;
`;

const StyledDialogContent = styled(DialogContent)`
    background-color: ${({ theme }) => theme.color['extra-dark-teal-100'].hex};
    color: ${({ theme }) => theme.color['cream-100'].hex};
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: ${({ theme }) => theme.spacing(5, 4, 4)} !important;
`;

const SvgSlot = styled(Box)`
    display: flex;
    align-items: center;
    justify-content: flex-start;
    color: ${({ theme }) => theme.color['green-40'].hex};

    svg {
        max-width: 100%;
        height: auto;
    }
`;

const PromptFieldGroup = styled(Box)`
    display: flex;
    flex-direction: column;
    gap: 16px;
`;

const PromptLabel = styled('label')`
    color: ${({ theme }) => theme.color['cream-100'].hex};
    font-size: 1rem;
    line-height: 1.4;
`;

const PromptField = styled(TextField)`
    & .MuiOutlinedInput-root {
        background-color: ${({ theme }) => theme.color['cream-4'].rgba.toString()};
        color: ${({ theme }) => theme.color['cream-100'].hex};
        border-radius: 4px;
        font-size: 0.95rem;
        align-items: flex-start;

        & fieldset {
            border-color: ${({ theme }) => theme.color['cream-10'].rgba.toString()};
        }

        &:hover fieldset {
            border-color: ${({ theme }) => theme.color['cream-20'].rgba.toString()};
        }

        &.Mui-focused fieldset {
            border-color: ${({ theme }) => theme.color['green-100'].hex};
        }
    }

    & .MuiOutlinedInput-input::placeholder {
        color: ${({ theme }) => theme.color['cream-60'].rgba.toString()};
        opacity: 1;
    }
`;

const Actions = styled(Box)`
    display: flex;
    justify-content: flex-end;
`;

const StartButton = styled(Button)`
    &.MuiButton-root {
        color: ${({ theme }) => theme.color['cream-100'].hex};
        padding: ${({ theme }) => theme.spacing(0.75, 2.5)};
        white-space: nowrap;
        text-transform: none;

        & .MuiButton-endIcon {
            margin-left: ${({ theme }) => theme.spacing(0.5)};
        }
    }

    &.MuiButton-outlined {
        border: 1px solid ${({ theme }) => theme.color['green-40'].rgba.toString()};

        &:hover {
            color: ${({ theme }) => theme.color['green-100'].hex};
            border: 1px solid ${({ theme }) => theme.color['green-100'].hex};
        }

        &.Mui-disabled {
            border-color: ${({ theme }) => theme.color['cream-10'].rgba.toString()};
            color: ${({ theme }) => theme.color['cream-20'].rgba.toString()};
        }
    }
`;
