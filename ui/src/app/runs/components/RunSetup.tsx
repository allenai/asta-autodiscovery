'use client';

import { useState, useRef } from 'react';
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
  IconButton,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  Divider,
} from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';

import { useAuth0 } from '@/contexts/Auth0Context';
import { uploadDataset, saveMetadata, submitRun } from '../actions';

export interface Dataset {
  filename: string;
  description: string;
  path?: string;
}

interface RunSetupProps {
  runid: string;
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
 * Combined component for dataset upload and run configuration.
 *
 * Features:
 * - Upload multiple datasets with descriptions
 * - Configure run parameters (experiments, models)
 * - Single page experience with all settings
 * - Submit run when ready
 */
export default function RunSetup({ runid, onSubmitSuccess }: RunSetupProps) {
  const { getAccessToken } = useAuth0();
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Dataset upload state
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [description, setDescription] = useState('');
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  // Run configuration state
  const [title, setTitle] = useState('');
  const [nExperiments, setNExperiments] = useState(4);
  const [model, setModel] = useState('gpt-4o');
  const [beliefModel, setBeliefModel] = useState('gpt-4o');
  const [experimentsError, setExperimentsError] = useState<string | null>(null);

  // Submission state
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      setSelectedFile(file);
      setUploadError(null);
    }
  };

  const handleUploadDataset = async () => {
    if (!selectedFile || !description.trim()) {
      setUploadError('Please select a file and provide a description');
      return;
    }

    setUploading(true);
    setUploadError(null);

    try {
      const token = await getAccessToken();
      const formData = new FormData();
      formData.append('file', selectedFile);
      formData.append('runid', runid);

      const response = await uploadDataset(formData, token);

      // Add to datasets list
      const newDataset: Dataset = {
        filename: response.filename,
        description: description.trim(),
        path: response.path,
      };

      setDatasets([...datasets, newDataset]);

      // Reset form
      setSelectedFile(null);
      setDescription('');
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    } catch (err) {
      console.error('Error uploading dataset:', err);
      setUploadError(
        err instanceof Error ? err.message : 'Failed to upload dataset'
      );
    } finally {
      setUploading(false);
    }
  };

  const handleRemoveDataset = (index: number) => {
    const newDatasets = datasets.filter((_, i) => i !== index);
    setDatasets(newDatasets);
  };

  const handleBrowseClick = () => {
    fileInputRef.current?.click();
  };

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
    // Validate
    if (datasets.length === 0) {
      setError('Please upload at least one dataset');
      return;
    }

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
        Setup Run
      </Typography>
      <Typography variant="body2" color="text.secondary" paragraph>
        Upload your datasets and configure run parameters below.
      </Typography>

      <Paper sx={{ p: 3, mb: 3 }}>
        <Stack spacing={3}>
          {/* Dataset Upload Section */}
          <Box>
            <Typography variant="h6" gutterBottom>
              Datasets
            </Typography>
            <Typography variant="body2" color="text.secondary" paragraph>
              Upload one or more datasets with descriptions.
            </Typography>

            <Stack spacing={2}>
              <input
                ref={fileInputRef}
                type="file"
                onChange={handleFileSelect}
                style={{ display: 'none' }}
                accept=".csv,.json,.txt,.tsv"
              />

              <Button
                variant="outlined"
                onClick={handleBrowseClick}
                startIcon={<CloudUploadIcon />}
                disabled={uploading || submitting}
                fullWidth
              >
                {selectedFile ? selectedFile.name : 'Select File'}
              </Button>

              <TextField
                label="Description"
                multiline
                rows={3}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Describe this dataset..."
                disabled={uploading || submitting}
                fullWidth
              />

              <Button
                variant="contained"
                color="primary"
                onClick={handleUploadDataset}
                disabled={
                  !selectedFile ||
                  !description.trim() ||
                  uploading ||
                  submitting
                }
                startIcon={uploading ? <CircularProgress size={16} /> : null}
              >
                {uploading ? 'Uploading...' : 'Add Dataset'}
              </Button>

              {uploadError && <Alert severity="error">{uploadError}</Alert>}
            </Stack>

            {datasets.length > 0 && (
              <Box sx={{ mt: 3 }}>
                <Typography variant="subtitle2" gutterBottom>
                  Uploaded Datasets ({datasets.length})
                </Typography>
                <List>
                  {datasets.map((dataset, index) => (
                    <Paper key={index} sx={{ mb: 1 }}>
                      <ListItem>
                        <ListItemText
                          primary={dataset.filename}
                          secondary={dataset.description}
                          primaryTypographyProps={{
                            fontWeight: 'medium',
                          }}
                        />
                        <ListItemSecondaryAction>
                          <IconButton
                            edge="end"
                            onClick={() => handleRemoveDataset(index)}
                            disabled={uploading || submitting}
                          >
                            <DeleteIcon />
                          </IconButton>
                        </ListItemSecondaryAction>
                      </ListItem>
                    </Paper>
                  ))}
                </List>
              </Box>
            )}
          </Box>

          <Divider />

          {/* Run Configuration Section */}
          <Box>
            <Typography variant="h6" gutterBottom>
              Run Configuration
            </Typography>

            <Stack spacing={3}>
              <TextField
                label="Title (optional)"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Give your run a descriptive name..."
                disabled={submitting}
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
                disabled={submitting}
                fullWidth
                required
                error={!!experimentsError}
                helperText={
                  experimentsError || 'Enter a number between 1 and 500'
                }
              />

              <FormControl fullWidth disabled={submitting}>
                <InputLabel id="model-label">Model</InputLabel>
                <Select
                  labelId="model-label"
                  value={model}
                  label="Model"
                  onChange={(e) => setModel(e.target.value)}
                >
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

              <FormControl fullWidth disabled={submitting}>
                <InputLabel id="belief-model-label">Belief Model</InputLabel>
                <Select
                  labelId="belief-model-label"
                  value={beliefModel}
                  label="Belief Model"
                  onChange={(e) => setBeliefModel(e.target.value)}
                >
                  {BELIEF_MODEL_OPTIONS.map((option) => (
                    <MenuItem key={option.value} value={option.value}>
                      {option.label}
                    </MenuItem>
                  ))}
                </Select>
                <FormHelperText>
                  LLM to use for belief distribution agent.
                </FormHelperText>
              </FormControl>
            </Stack>
          </Box>

          {error && <Alert severity="error">{error}</Alert>}

          <Button
            variant="contained"
            color="success"
            size="large"
            startIcon={
              submitting ? <CircularProgress size={16} /> : <PlayArrowIcon />
            }
            onClick={handleSubmit}
            disabled={
              submitting ||
              uploading ||
              datasets.length === 0 ||
              !!experimentsError ||
              nExperiments < 1
            }
            fullWidth
          >
            {submitting ? 'Submitting...' : 'Submit Run'}
          </Button>
        </Stack>
      </Paper>

      <Paper sx={{ p: 2, bgcolor: 'grey.50' }}>
        <Typography variant="caption" color="text.secondary">
          <strong>Note:</strong> Once submitted, your run will be queued for
          execution. You&apos;ll be able to monitor its progress and stop it if
          needed.
        </Typography>
      </Paper>
    </Box>
  );
}
