'use client';

import { useState, useRef, DragEvent } from 'react';
import {
    Box,
    Stack,
    Typography,
    styled,
    alpha,
    TextField,
    IconButton,
    LinearProgress,
    Alert,
    Button,
} from '@mui/material';
import CloudUploadOutlinedIcon from '@mui/icons-material/CloudUploadOutlined';
import DescriptionOutlinedIcon from '@mui/icons-material/DescriptionOutlined';
import CloseIcon from '@mui/icons-material/Close';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';
import StopCircleOutlinedIcon from '@mui/icons-material/StopCircleOutlined';
import prettyBytes from 'pretty-bytes';
import prettyMs from 'pretty-ms';

import { FileUploadState, UploadStatus } from '@/runs/hooks/useRunSetup';
import { getFriendlyMimeType, getMimeType } from '@/utils/mimeType';

export interface Dataset {
    filename: string;
    description: string;
    path?: string;
}

/**
 * Displays upload progress with percentage, bytes transferred, and time remaining
 */
const UploadProgress = ({ upload }: { upload: FileUploadState }) => {
    return (
        <Box sx={{ mt: 1, mb: 1 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 0.5 }}>
                <LinearProgress
                    variant="determinate"
                    value={upload.progress}
                    sx={{ flex: 1, mr: 2 }}
                />
                <Typography variant="caption" sx={{ minWidth: 40, textAlign: 'right' }}>
                    {Math.round(upload.progress)}%
                </Typography>
            </Box>
            <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                <Typography variant="caption" color="text">
                    {prettyBytes(upload.uploadedBytes)} / {prettyBytes(upload.totalBytes)}
                </Typography>
                {upload.secondsRemaining !== null && (
                    <Typography variant="caption" color="text">
                        {prettyMs(upload.secondsRemaining * 1000)} remaining
                    </Typography>
                )}
            </Box>
        </Box>
    );
};

interface DatasetUploadProps {
    fileUploads: FileUploadState[];
    onFileSelect: (files: File[]) => void;
    onRemoveFileUpload: (index: number) => void;
    onDescriptionChange: (index: number, description: string) => void;
    onCancelUpload: (index: number) => void;
    onRetryUpload: (index: number) => void;
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
    fileUploads,
    onFileSelect,
    onRemoveFileUpload,
    onDescriptionChange,
    onCancelUpload,
    onRetryUpload,
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
            onFileSelect(Array.from(files));
        }
    };

    const handleClick = () => {
        if (!disabled) {
            fileInputRef.current?.click();
        }
    };

    const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const files = e.target.files;
        if (files?.length) {
            onFileSelect(Array.from(files));
        }
    };

    return (
        <Box>
            <input
                ref={fileInputRef}
                type="file"
                onChange={handleFileInputChange}
                style={{ display: 'none' }}
                multiple
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

            {fileUploads.length > 0 && (
                <FilesContainer>
                    {fileUploads.map((upload, index) => {
                        const fileType = upload.file.type || getMimeType(upload.file.name);
                        const friendlyType = getFriendlyMimeType(fileType);

                        return (
                            <File key={`upload-${index}`}>
                                <FileHeader>
                                    <DescriptionOutlinedIcon />
                                    <FileHeaderFilename>{upload.file.name}</FileHeaderFilename>
                                    <FileHeaderFileMeta>
                                        {friendlyType} • {prettyBytes(upload.totalBytes)}
                                    </FileHeaderFileMeta>
                                    <FileHeaderActions>
                                        {/* Status indicators */}
                                        {upload.status === UploadStatus.COMPLETED && (
                                            <CheckCircleIcon
                                                sx={{ color: 'success.main', mr: 1 }}
                                                titleAccess="Upload completed"
                                            />
                                        )}
                                        {upload.status === UploadStatus.ERROR && (
                                            <ErrorIcon
                                                sx={{ color: 'error.main', mr: 1 }}
                                                titleAccess="Upload failed"
                                            />
                                        )}

                                        {upload.status === UploadStatus.PENDING && (
                                            <Typography
                                                variant="caption"
                                                color="text.secondary"
                                                sx={{ mr: 1 }}>
                                                Starting...
                                            </Typography>
                                        )}

                                        {/* Cancel button */}
                                        {upload.status === UploadStatus.UPLOADING && (
                                            <Button
                                                size="small"
                                                onClick={() => onCancelUpload(index)}
                                                disabled={disabled}
                                                sx={{ ml: 'auto' }}
                                                startIcon={
                                                    <StopCircleOutlinedIcon color="error" />
                                                }>
                                                Cancel
                                            </Button>
                                        )}

                                        {/* Remove button */}
                                        {upload.status !== UploadStatus.UPLOADING && (
                                            <IconButton
                                                size="small"
                                                onClick={() => onRemoveFileUpload(index)}
                                                disabled={disabled}
                                                sx={{ ml: 'auto' }}
                                                title="Remove file">
                                                <CloseIcon fontSize="small" />
                                            </IconButton>
                                        )}
                                    </FileHeaderActions>
                                </FileHeader>

                                {/* Progress bar - only show during upload */}
                                {upload.status === UploadStatus.UPLOADING && (
                                    <Box sx={{ px: 2, py: 1 }}>
                                        <UploadProgress upload={upload} />
                                    </Box>
                                )}

                                {/* Error message with retry button */}
                                {upload.status === UploadStatus.ERROR && (
                                    <Alert
                                        severity="error"
                                        sx={{ mx: 2, mt: 1 }}
                                        action={
                                            <Button
                                                size="small"
                                                onClick={() => onRetryUpload(index)}
                                                sx={{ ml: 1 }}>
                                                Retry
                                            </Button>
                                        }>
                                        {upload.error || 'Upload failed'}
                                    </Alert>
                                )}

                                {/* Description field */}
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
                                        value={upload.description}
                                        onChange={(e) => onDescriptionChange(index, e.target.value)}
                                        disabled={disabled}
                                        sx={{ mt: 1 }}
                                        placeholder='e.g.,
1. "n" - count of non-native plant species introductions in each time period,
2. "final_choice_new" - “participants final choice in the treatment condition”
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

const DropZone = styled(Box, {
    shouldForwardProp: (prop) =>
        prop !== 'isDragging' && prop !== 'disabled' && prop !== 'hasError',
})<{ isDragging: boolean; disabled: boolean; hasError: boolean }>(
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

const FileHeaderActions = styled(Box)(() => ({
    display: 'flex',
    alignItems: 'center',
    marginLeft: 'auto',
}));

const FileHeaderFilename = styled(Typography)(({ theme }) => ({
    fontWeight: 'bold',
    color: theme.color['cream-100'].hex,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
}));

const FileHeaderFileMeta = styled(Typography)(({ theme }) => ({
    flex: '0 0 auto',
    alignItems: 'end',
    marginLeft: theme.spacing(1),
    marginRight: theme.spacing(1),
    opacity: 0.6,
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
