'use client';

import { useState, useRef, DragEvent } from 'react';
import { Box, Stack, Typography, styled, alpha, TextField, IconButton } from '@mui/material';
import CloudUploadOutlinedIcon from '@mui/icons-material/CloudUploadOutlined';
import DescriptionOutlinedIcon from '@mui/icons-material/DescriptionOutlined';
import CloseIcon from '@mui/icons-material/Close';

import { SelectedFile } from '../hooks/useRunSetup';

export interface Dataset {
    filename: string;
    description: string;
    path?: string;
}

interface DatasetUploadProps {
    datasets: Dataset[];
    selectedFiles: SelectedFile[];
    onFileSelect: (file: File) => void;
    onRemove: (index: number) => void;
    onRemoveSelectedFile: (index: number) => void;
    onDescriptionChange: (index: number, description: string) => void;
    disabled?: boolean;
    error?: string;
}

/**
 * Component for uploading datasets with drag and drop.
 *
 * Features:
 * - Drag and drop file upload
 * - Click to open file dialog
 * - Display uploaded files as chips
 * - Remove files by clicking on chip
 */
export default function DatasetUpload({
    datasets,
    selectedFiles,
    onFileSelect,
    onRemoveSelectedFile,
    onDescriptionChange,
    disabled = false,
    error,
}: DatasetUploadProps) {
    const fileInputRef = useRef<HTMLInputElement>(null);
    const [isDragging, setIsDragging] = useState(false);

    const handleDragEnter = (e: DragEvent<HTMLDivElement>) => {
        e.preventDefault();
        e.stopPropagation();
        if (!disabled) {
            setIsDragging(true);
        }
    };

    const handleDragLeave = (e: DragEvent<HTMLDivElement>) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragging(false);
    };

    const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
        e.preventDefault();
        e.stopPropagation();
    };

    const handleDrop = (e: DragEvent<HTMLDivElement>) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragging(false);

        if (disabled) return;

        const files = e.dataTransfer.files;
        if (files && files.length > 0) {
            const file = files[0];
            // Check file type
            const validTypes = ['.csv', '.json', '.txt', '.tsv'];
            const fileExtension = '.' + file.name.split('.').pop()?.toLowerCase();
            if (validTypes.includes(fileExtension)) {
                onFileSelect(file);
            }
        }
    };

    const handleClick = () => {
        if (!disabled) {
            fileInputRef.current?.click();
        }
    };

    const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (file) {
            onFileSelect(file);
        }
    };

    return (
        <Box>
            <input
                ref={fileInputRef}
                type="file"
                onChange={handleFileInputChange}
                style={{ display: 'none' }}
                accept=".csv,.json,.txt,.tsv"
            />

            <DropZone
                onClick={handleClick}
                onDragEnter={handleDragEnter}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                isDragging={isDragging}
                disabled={disabled}
                hasError={!!error}>
                <CloudUploadOutlinedIcon />
                <Typography variant="body1" gutterBottom>
                    Drop files here or browse
                </Typography>
                <Typography variant="caption" sx={{ mt: 1, opacity: 0.6 }}>
                    Max 10GB per file, 20GB total session limit
                </Typography>
            </DropZone>

            {(selectedFiles.length > 0 || datasets.length > 0) && (
                <FilesContainer>
                    {selectedFiles.map((selectedFile, index) => {
                        const fileSizeMB = (selectedFile.file.size / (1024 * 1024)).toFixed(2);
                        const fileType = selectedFile.file.type || 'Unknown';

                        return (
                            <File key={`selected-${index}`}>
                                <FileHeader>
                                    <DescriptionOutlinedIcon />
                                    <Typography variant="subtitle2">
                                        {selectedFile.file.name}
                                    </Typography>
                                    <Typography variant="body2">
                                        {fileType} • {fileSizeMB} MB
                                    </Typography>
                                    <IconButton
                                        size="small"
                                        onClick={() => onRemoveSelectedFile(index)}
                                        sx={{ ml: 'auto' }}>
                                        <CloseIcon fontSize="small" />
                                    </IconButton>
                                </FileHeader>
                                <FileDescription>
                                    <DatasetSchemaTitle>
                                        Dataset Schema (Optional)
                                    </DatasetSchemaTitle>
                                    Help us interpret your data accurately. Our system will analyze
                                    your files automatically. For the best results, please use this
                                    space to clarify any abbreviations, complex structures, or
                                    similar or unclear variables (e.g., column names).
                                    <TextField
                                        multiline
                                        maxRows={3}
                                        fullWidth
                                        value={selectedFile.description}
                                        onChange={(e) => onDescriptionChange(index, e.target.value)}
                                        sx={{ mt: 1 }}
                                        placeholder='e.g., 
1. "n" - count of non-native plant species introductions in each time period,
2. "final_choice_new" - “parcipants final choice in the treatment condition”
3. Each row in this file represents a time-series'
                                    />
                                </FileDescription>
                            </File>
                        );
                    })}
                </FilesContainer>
            )}
        </Box>
    );
}

const DropZone = styled(Box)<{ isDragging: boolean; disabled: boolean; hasError: boolean }>(
    ({ theme, isDragging, disabled, hasError }) => ({
        border: `1px dashed ${
            hasError
                ? theme.palette.error.main
                : isDragging
                  ? theme.color['green-100'].hex
                  : theme.color['cream-20'].rgba.toString()
        }`,
        borderRadius: theme.shape.borderRadius,
        padding: theme.spacing(4),
        textAlign: 'center',
        cursor: disabled ? 'not-allowed' : 'pointer',
        backgroundColor: isDragging ? alpha(theme.color['green-100'].hex, 0.05) : 'transparent',
        transition: 'all 0.2s ease',
        opacity: disabled ? 0.5 : 1,
        color: theme.color['cream-100'].hex,

        '&:hover': {
            backgroundColor: disabled
                ? 'transparent'
                : alpha(theme.color['cream-10'].rgba.toString(), 0.5),
            borderColor: disabled
                ? theme.color['cream-20'].rgba.toString()
                : theme.color['green-40'].hex,
        },
    })
);

const FilesContainer = styled(Stack)(({ theme }) => ({
    flexDirection: 'column',
    gap: theme.spacing(1),
    marginTop: theme.spacing(2),
}));

const File = styled(Box)(({ theme }) => ({
    backgroundColor: theme.color['cream-10'].rgba.toString(),
    borderRadius: theme.shape.borderRadius,
    color: theme.color['cream-100'].hex,
}));

const FileHeader = styled(Box)(({ theme }) => ({
    alignItems: 'center',
    borderBottom: `1px solid ${theme.color['cream-10'].rgba.toString()}`,
    color: theme.color['cream-60'].rgba.toString(),
    display: 'flex',
    gap: theme.spacing(1),
    padding: theme.spacing(2),

    h6: {
        fontSize: '1rem',
        fontWeight: 'bold',
    },

    '.MuiSvgIcon-root': {
        color: theme.color['cream-50'].rgba.toString(),
    },

    '.MuiIconButton-root': {
        color: theme.color['cream-50'].rgba.toString(),
        '&:hover': {
            backgroundColor: alpha(theme.color['cream-50'].rgba.toString(), 0.1),
            color: theme.color['cream-100'].hex,
        },
    },
}));

const FileDescription = styled(Box)(({ theme }) => ({
    color: theme.color['cream-100'].hex,
    fontSize: '0.875rem',
    padding: theme.spacing(2),
}));

const DatasetSchemaTitle = styled(Typography)(({ theme }) => ({
    color: theme.color['green-40'].hex,
    fontWeight: 'bold',
}));
