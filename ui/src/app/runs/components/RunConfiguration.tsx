'use client';

import { useState } from 'react';
import {
    Box,
    Stack,
    TextField,
    Button,
    Typography,
    Paper,
    FormControl,
    InputLabel,
    Select,
    MenuItem,
    CircularProgress,
    Alert,
    FormHelperText,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';

import { useAuth0 } from '@/app/contexts/Auth0Context';
import { saveMetadata, submitRun } from '../actions';
import type { Dataset } from './DatasetUpload';

interface RunConfigurationProps {
    runid: string;
    datasets: Dataset[];
    onBack: () => void;
    onSubmitSuccess: () => void;
}

const MODEL_OPTIONS = [
    { value: 'gpt-4o', label: 'GPT-4o' },
    { value: 'o4-mini', label: 'o4-mini' },
    { value: 'gpt-5-mini', label: 'GPT-5 Mini' },
    { value: 'gpt-5-nano', label: 'GPT-5 Nano' },
];

const BELIEF_MODEL_OPTIONS = [
    { value: 'gpt-4o', label: 'GPT-4o' },
    { value: 'o4-mini', label: 'o4-mini' },
    { value: 'gpt-5-mini', label: 'GPT-5 Mini' },
    { value: 'gpt-5-nano', label: 'GPT-5 Nano' },
];

/**
 * Component for configuring run parameters.
 *
 * Features:
 * - Title input (optional)
 * - Number of experiments text input
 * - Model dropdown (for all agents except belief)
 * - Belief model dropdown (for belief distribution agent)
 * - Submit button to start run
 * - Back button to return to dataset upload
 */
export default function RunConfiguration({
    runid,
    datasets,
    onBack,
    onSubmitSuccess,
}: RunConfigurationProps) {
    const { getAccessToken } = useAuth0();

    const [title, setTitle] = useState('');
    const [nExperiments, setNExperiments] = useState(4);
    const [model, setModel] = useState('gpt-4o');
    const [beliefModel, setBeliefModel] = useState('gpt-4o');
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [experimentsError, setExperimentsError] = useState<string | null>(null);

    const handleExperimentsChange = (value: string) => {
        const num = parseInt(value, 10);

        if (value === '') {
            setNExperiments(0);
            setExperimentsError('Number of experiments is required');
            return;
        }

        if (isNaN(num) || num < 1 || num > 500) {
            setExperimentsError('Must be between 1 and 500');
        } else {
            setExperimentsError(null);
        }

        setNExperiments(num);
    };

    const handleSubmit = async () => {
        // Validate experiments before submitting
        if (nExperiments < 1 || nExperiments > 500) {
            setError('Number of experiments must be between 1 and 500');
            return;
        }

        setSubmitting(true);
        setError(null);

        try {
            const token = await getAccessToken();

            // Prepare metadata
            const metadata = {
                title: title.trim() || undefined,
                datasets: datasets.map((ds) => ({
                    name: ds.filename,
                    description: ds.description,
                })),
            };

            // Save metadata
            await saveMetadata(runid, metadata, token);

            // Submit run
            await submitRun(
                runid,
                {
                    n_experiments: nExperiments,
                    model,
                    belief_model: beliefModel,
                },
                token
            );

            // Notify parent of success
            onSubmitSuccess();
        } catch (err) {
            console.error('Error submitting run:', err);
            setError(err instanceof Error ? err.message : 'Failed to submit run');
            setSubmitting(false);
        }
    };

    return (
        <Box sx={{ maxWidth: 'md', mx: 'auto', p: 3 }}>
            <Typography variant="h5" gutterBottom>
                Configure Run
            </Typography>
            <Typography variant="body2" color="text.secondary" paragraph>
                Set the parameters for your autodiscovery run. You can adjust these settings based
                on your experimental requirements.
            </Typography>

            <Paper sx={{ p: 3, mb: 3 }}>
                <Stack spacing={3}>
                    <TextField
                        label="Title (optional)"
                        value={title}
                        onChange={(e) => setTitle(e.target.value)}
                        placeholder="Give your run a descriptive name..."
                        fullWidth
                        helperText="Optional. This helps you identify the run later."
                    />

                    <TextField
                        label="Number of Experiments"
                        type="number"
                        value={nExperiments}
                        onChange={(e) => handleExperimentsChange(e.target.value)}
                        inputProps={{
                            min: 1,
                            max: 500,
                            step: 1,
                        }}
                        fullWidth
                        required
                        error={!!experimentsError}
                        helperText={experimentsError || 'Enter a number between 1 and 500'}
                    />

                    <FormControl fullWidth>
                        <InputLabel id="model-label">Model</InputLabel>
                        <Select
                            labelId="model-label"
                            value={model}
                            label="Model"
                            onChange={(e) => setModel(e.target.value)}>
                            {MODEL_OPTIONS.map((option) => (
                                <MenuItem key={option.value} value={option.value}>
                                    {option.label}
                                </MenuItem>
                            ))}
                        </Select>
                        <FormHelperText>
                            LLM to use for all agents (except belief distribution agent).
                        </FormHelperText>
                    </FormControl>

                    <FormControl fullWidth>
                        <InputLabel id="belief-model-label">Belief Model</InputLabel>
                        <Select
                            labelId="belief-model-label"
                            value={beliefModel}
                            label="Belief Model"
                            onChange={(e) => setBeliefModel(e.target.value)}>
                            {BELIEF_MODEL_OPTIONS.map((option) => (
                                <MenuItem key={option.value} value={option.value}>
                                    {option.label}
                                </MenuItem>
                            ))}
                        </Select>
                        <FormHelperText>LLM to use for belief distribution agent.</FormHelperText>
                    </FormControl>

                    {error && <Alert severity="error">{error}</Alert>}

                    <Stack direction="row" spacing={2}>
                        <Button
                            variant="outlined"
                            startIcon={<ArrowBackIcon />}
                            onClick={onBack}
                            disabled={submitting}
                            sx={{ flex: 1 }}>
                            Back
                        </Button>
                        <Button
                            variant="contained"
                            color="success"
                            size="large"
                            startIcon={
                                submitting ? <CircularProgress size={16} /> : <PlayArrowIcon />
                            }
                            onClick={handleSubmit}
                            disabled={submitting || !!experimentsError || nExperiments < 1}
                            sx={{ flex: 2 }}>
                            {submitting ? 'Submitting...' : 'Run'}
                        </Button>
                    </Stack>
                </Stack>
            </Paper>

            <Paper sx={{ p: 2, bgcolor: 'grey.50' }}>
                <Typography variant="caption" color="text.secondary">
                    <strong>Note:</strong> Once submitted, your run will be queued for execution.
                    You&apos;ll receive an execution ID to track the progress of your run.
                </Typography>
            </Paper>
        </Box>
    );
}
