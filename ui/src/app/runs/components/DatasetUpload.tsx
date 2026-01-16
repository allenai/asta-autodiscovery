'use client';

import { useState, useRef } from 'react';
import {
  Box,
  Stack,
  TextField,
  Button,
  Typography,
  Paper,
  IconButton,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  CircularProgress,
  Alert,
} from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';
import CloudUploadIcon from '@mui/icons-material/CloudUpload';

import { useAuth0 } from '@/contexts/Auth0Context';
import { uploadDataset } from '../actions';

export interface Dataset {
  filename: string;
  description: string;
  path?: string;
}

interface DatasetUploadProps {
  runid: string;
  datasets: Dataset[];
  onDatasetsChange: (datasets: Dataset[]) => void;
  onContinue: () => void;
}

/**
 * Component for uploading datasets with descriptions.
 *
 * Features:
 * - File selection and upload
 * - Description input for each dataset
 * - List of uploaded datasets
 * - Remove dataset functionality
 * - Continue button when at least one dataset uploaded
 */
export default function DatasetUpload({
  runid,
  datasets,
  onDatasetsChange,
  onContinue,
}: DatasetUploadProps) {
  const { getAccessToken } = useAuth0();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [description, setDescription] = useState('');
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      setSelectedFile(file);
      setError(null);
    }
  };

  const handleUpload = async () => {
    if (!selectedFile || !description.trim()) {
      setError('Please select a file and provide a description');
      return;
    }

    setUploading(true);
    setError(null);

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

      onDatasetsChange([...datasets, newDataset]);

      // Reset form
      setSelectedFile(null);
      setDescription('');
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    } catch (err) {
      console.error('Error uploading dataset:', err);
      setError(err instanceof Error ? err.message : 'Failed to upload dataset');
    } finally {
      setUploading(false);
    }
  };

  const handleRemove = (index: number) => {
    const newDatasets = datasets.filter((_, i) => i !== index);
    onDatasetsChange(newDatasets);
  };

  const handleBrowseClick = () => {
    fileInputRef.current?.click();
  };

  return (
    <Box sx={{ maxWidth: 'md', mx: 'auto', p: 3 }}>
      <Typography variant="h5" gutterBottom>
        Upload Datasets
      </Typography>
      <Typography variant="body2" color="text.secondary" paragraph>
        Upload one or more datasets with descriptions. You&apos;ll configure run
        parameters in the next step.
      </Typography>

      <Paper sx={{ p: 3, mb: 3 }}>
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
            fullWidth
          >
            {selectedFile ? selectedFile.name : 'Select File'}
          </Button>

          <TextField
            label="Description"
            multiline
            rows={4}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Describe this dataset..."
            fullWidth
            required
          />

          {error && <Alert severity="error">{error}</Alert>}

          <Button
            variant="contained"
            color="primary"
            onClick={handleUpload}
            disabled={!selectedFile || !description.trim() || uploading}
            startIcon={uploading ? <CircularProgress size={16} /> : null}
          >
            {uploading ? 'Uploading...' : 'Upload Dataset'}
          </Button>
        </Stack>
      </Paper>

      {datasets.length > 0 && (
        <Box sx={{ mb: 3 }}>
          <Typography variant="h6" gutterBottom>
            Uploaded Datasets ({datasets.length})
          </Typography>
          <List>
            {datasets.map((dataset, index) => (
              <Paper key={index} sx={{ mb: 1 }}>
                <ListItem>
                  <ListItemText
                    primary={dataset.filename}
                    secondary={dataset.description}
                    primaryTypographyProps={{ fontWeight: 'medium' }}
                  />
                  <ListItemSecondaryAction>
                    <IconButton
                      edge="end"
                      onClick={() => handleRemove(index)}
                      disabled={uploading}
                    >
                      <DeleteIcon />
                    </IconButton>
                  </ListItemSecondaryAction>
                </ListItem>
              </Paper>
            ))}
          </List>

          <Button
            variant="contained"
            color="success"
            size="large"
            fullWidth
            onClick={onContinue}
            disabled={uploading}
          >
            Continue to Configuration
          </Button>
        </Box>
      )}

      {datasets.length === 0 && (
        <Alert severity="info">
          Upload at least one dataset to continue to the configuration step.
        </Alert>
      )}
    </Box>
  );
}
