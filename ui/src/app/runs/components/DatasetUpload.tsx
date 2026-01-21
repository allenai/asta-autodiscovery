'use client';

import { useState, useRef, DragEvent } from 'react';
import { Box, Chip, Stack, Typography, styled, alpha } from '@mui/material';
import CloudUploadOutlinedIcon from '@mui/icons-material/CloudUploadOutlined';
import DescriptionIcon from '@mui/icons-material/Description';

export interface Dataset {
    filename: string;
    description: string;
    path?: string;
}

interface DatasetUploadProps {
    datasets: Dataset[];
    selectedFiles: File[];
    onFileSelect: (file: File) => void;
    onRemove: (index: number) => void;
    onRemoveSelectedFile: (index: number) => void;
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
    onRemove,
    onRemoveSelectedFile,
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
                    {isDragging
                        ? 'Drop file here'
                        : 'Click, or drag & drop to add datasets to explore'}
                </Typography>
                <Typography variant="caption" sx={{ mt: 1, opacity: 0.5 }}>
                    Supported formats: CSV, JSON, TXT, TSV
                </Typography>
            </DropZone>

            {(selectedFiles.length > 0 || datasets.length > 0) && (
                <ChipsContainer>
                    {selectedFiles.map((file, index) => (
                        <StyledChip
                            key={`selected-${index}`}
                            icon={<DescriptionIcon />}
                            label={file.name}
                            onDelete={disabled ? undefined : () => onRemoveSelectedFile(index)}
                            disabled={disabled}
                            color="default"
                        />
                    ))}
                    {datasets.map((dataset, index) => (
                        <UploadedChip
                            key={`dataset-${index}`}
                            icon={<DescriptionIcon />}
                            label={dataset.filename}
                            onDelete={disabled ? undefined : () => onRemove(index)}
                            disabled={disabled}
                        />
                    ))}
                </ChipsContainer>
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

const ChipsContainer = styled(Stack)(({ theme }) => ({
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: theme.spacing(1),
    marginTop: theme.spacing(2),
}));

const StyledChip = styled(Chip)(({ theme }) => ({
    backgroundColor: theme.color['cream-10'].rgba.toString(),
    color: theme.color['cream-100'].hex,
    borderRadius: theme.shape.borderRadius,

    '& .MuiChip-icon': {
        color: theme.color['cream-60'].rgba.toString(),
    },

    '& .MuiChip-deleteIcon': {
        color: theme.color['cream-60'].rgba.toString(),
        '&:hover': {
            color: theme.color['cream-100'].hex,
        },
    },
}));

const UploadedChip = styled(Chip)(({ theme }) => ({
    backgroundColor: alpha(theme.color['green-100'].hex, 0.15),
    color: theme.color['green-100'].hex,
    borderRadius: theme.shape.borderRadius,

    '& .MuiChip-icon': {
        color: theme.color['green-100'].hex,
    },

    '& .MuiChip-deleteIcon': {
        color: theme.color['green-100'].hex,
        '&:hover': {
            color: theme.color['green-60'].hex,
        },
    },
}));
