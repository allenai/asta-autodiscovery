'use client';

import { useState } from 'react';
import {
    Alert,
    Box,
    Button,
    FormHelperText,
    InputAdornment,
    MenuItem,
    Select,
    Stack,
    TextField,
    Typography,
    styled,
} from '@mui/material';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import FolderOpenOutlinedIcon from '@mui/icons-material/FolderOpenOutlined';
import prettyBytes from 'pretty-bytes';

import { LocalDatasetInfo } from '@/api/RunsApi';

const OTHER_DATASET = '__other_dataset__';

interface LocalDatasetPickerProps {
    datasets: LocalDatasetInfo[];
    selectedDataset: string;
    folderPath: string;
    activeDataset: string;
    selectedFileCount: number;
    loading: boolean;
    error: string | null;
    disabled: boolean;
    onDatasetChange: (value: string) => void;
    onFolderPathChange: (value: string) => void;
    onBrowse: () => void;
    onUseFolderPath: () => void;
}

export default function LocalDatasetPicker({
    datasets,
    selectedDataset,
    folderPath,
    activeDataset,
    selectedFileCount,
    loading,
    error,
    disabled,
    onDatasetChange,
    onFolderPathChange,
    onBrowse,
    onUseFolderPath,
}: LocalDatasetPickerProps) {
    const [showOtherDataset, setShowOtherDataset] = useState(false);

    const handleDatasetChange = (value: string) => {
        if (value === OTHER_DATASET) {
            setShowOtherDataset(true);
            onBrowse();
            return;
        }
        setShowOtherDataset(false);
        onDatasetChange(value);
    };

    return (
        <Stack spacing={2}>
            <Select
                displayEmpty
                fullWidth
                value={showOtherDataset ? OTHER_DATASET : selectedDataset}
                onChange={(event) => handleDatasetChange(event.target.value)}
                disabled={disabled || loading}>
                <MenuItem value="" disabled>
                    Choose a dataset
                </MenuItem>
                {datasets.map((dataset) => (
                    <MenuItem key={dataset.name} value={dataset.name}>
                        {dataset.name} ({dataset.file_count} files,{' '}
                        {prettyBytes(dataset.size_bytes)})
                    </MenuItem>
                ))}
                <MenuItem value={OTHER_DATASET}>Choose another dataset…</MenuItem>
            </Select>

            {showOtherDataset && (
                <Box>
                    <DatasetHelperText>
                        Enter a dataset path and press Enter, or choose a dataset with Browse.
                    </DatasetHelperText>
                    <TextField
                        fullWidth
                        value={folderPath}
                        onChange={(event) => onFolderPathChange(event.target.value)}
                        onKeyDown={(event) => {
                            if (event.key === 'Enter' && folderPath.trim()) {
                                event.preventDefault();
                                onUseFolderPath();
                            }
                        }}
                        placeholder="~/Data/my-dataset"
                        disabled={disabled || loading}
                        InputProps={{
                            endAdornment: (
                                <InputAdornment position="end">
                                    <Button
                                        startIcon={<FolderOpenOutlinedIcon />}
                                        onClick={onBrowse}
                                        disabled={disabled || loading}
                                        sx={(theme) => ({ color: theme.color['green-100'].hex })}>
                                        Browse…
                                    </Button>
                                </InputAdornment>
                            ),
                        }}
                    />
                </Box>
            )}

            {activeDataset && (
                <SelectedDatasetSummary direction="row" spacing={1} alignItems="center">
                    <CheckCircleOutlineIcon color="success" fontSize="small" />
                    <Typography variant="body2">
                        Using <strong>{activeDataset}</strong> ({selectedFileCount} files)
                    </Typography>
                </SelectedDatasetSummary>
            )}
            {error && <Alert severity="error">{error}</Alert>}
        </Stack>
    );
}

const DatasetHelperText = styled(FormHelperText)(({ theme }) => ({
    color: theme.color['cream-80'].rgba.toString(),
    margin: theme.spacing(0.5, 0, 1, 0),
}));

const SelectedDatasetSummary = styled(Stack)(({ theme }) => ({
    color: theme.color['cream-100'].hex,
}));
