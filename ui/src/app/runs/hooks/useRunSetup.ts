import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import debounce from 'lodash.debounce';

import { useViewerCredits } from '@/contexts/ViewerCreditsContext';
import { useRuns } from '@/contexts/RunsContext';
import { getRunsApi } from '@/api/RunsApi';
import { getRunFromApi } from '@/types/Run';
import { uploadToGCS as uploadFileToGCS } from '@/api/gcsUpload';

export const MCTS_SELECTION = {
    UCB1_RECURSIVE: { value: 'ucb1_recursive', label: 'UCB1 Recursive' },
    PROGRESSIVE_WIDENING: {
        value: 'pw',
        label: 'MCTS with Progressive Widening',
    },
};

export type Dataset = {
    filename: string;
    description: string;
    path?: string;
};

type Settings = {
    // metadata
    name: string;
    datasetsDescription: string;
    domain: string;
    datasets: Dataset[];
    intent: string;

    // advanced settings
    nExperiments: number;
    explorationWeight: number;
    mctsSelection: string;
    surprisalWidth: number;
    evidenceWeight: number;
    warmstartExperiments: string;
    nWarmstart: number;
};

interface UseRunSetupProps {
    runid: string;
    onSubmitSuccess: () => void;
    debounceSaveMs?: number;
}

export interface SelectedFile {
    file: File;
    description: string;
}

export enum UploadStatus {
    PENDING = 'pending',
    UPLOADING = 'uploading',
    COMPLETED = 'completed',
    ERROR = 'error',
}

export interface FileUploadState {
    file: File;
    description: string;
    status: UploadStatus;
    progress: number; // 0-100
    uploadedBytes: number;
    totalBytes: number;
    secondsRemaining: number | null; // seconds, null while calculating
    uploadStartTime: number | null;
    uploadUrl: string | null;
    gcsPath: string | null;
    error: string | null;
    abortController: AbortController | null;
}

interface FieldErrors {
    name?: string;
    datasets?: string;
    datasetsDescription?: string;
    nExperiments?: string;
}

export function useRunSetup({ runid, onSubmitSuccess, debounceSaveMs = 3000 }: UseRunSetupProps) {
    const { credits } = useViewerCredits();
    const { updateViewerRun } = useRuns();
    const api = getRunsApi();

    const creditsRemaining = credits?.remaining ?? 500;

    // Dataset upload state
    const [fileUploads, setFileUploads] = useState<FileUploadState[]>([]);
    const [settings, setSettings] = useState<Settings>({
        name: '',
        datasetsDescription: '',
        domain: '',
        datasets: [],
        nExperiments: 4,
        intent: '',
        explorationWeight: 2,
        mctsSelection: MCTS_SELECTION.UCB1_RECURSIVE.value,
        surprisalWidth: 0.2,
        evidenceWeight: 2,
        warmstartExperiments: '',
        nWarmstart: 8,
    });

    // Field validation errors
    const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});

    // Submission state
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [formError, setFormError] = useState<string | null>(null);

    // Loading state for initial run fetch
    const [isLoading, setIsLoading] = useState(true);

    // Saving state for debounced saves
    const [isSaving, setIsSaving] = useState(false);
    const savingTimeoutRef = useRef<NodeJS.Timeout | null>(null);

    // Fetch run metadata on mount and prepopulate form
    useEffect(() => {
        const fetchRunMetadata = async () => {
            setIsLoading(true);
            try {
                const { data } = await api.getRun(runid);
                const { metadata, args } = getRunFromApi(data);

                if (metadata || args) {
                    setSettings((prev) => ({
                        ...prev,
                        name: metadata?.name || '',
                        datasetsDescription: metadata?.description || '',
                        domain: metadata?.domain || '',
                        intent: metadata?.intent || '',
                        nExperiments: args?.nExperiments || prev.nExperiments,
                        explorationWeight: args?.explorationWeight || prev.explorationWeight,
                        mctsSelection: args?.mctsSelection || prev.mctsSelection,
                        surprisalWidth: args?.surprisalWidth || prev.surprisalWidth,
                        evidenceWeight: args?.evidenceWeight || prev.evidenceWeight,
                        warmstartExperiments:
                            args?.warmstartExperiments || prev.warmstartExperiments,
                        nWarmstart: args?.nWarmstart || prev.nWarmstart,
                    }));

                    // Populate fileUploads from saved datasets
                    if (metadata?.datasets && metadata.datasets.length > 0) {
                        const uploadStates: FileUploadState[] = metadata.datasets.map((dataset) => {
                            // Use saved content_type and file_size_bytes if available
                            const contentType = dataset.contentType || 'application/octet-stream';
                            const fileSize = dataset.fileSizeBytes || 0;

                            // Create placeholder File object from filename
                            // The actual file content is already in GCS, so we just need the metadata
                            const placeholderFile = new File([], dataset.name, {
                                type: contentType,
                            });

                            return {
                                file: placeholderFile,
                                description: dataset.description || '',
                                status: UploadStatus.COMPLETED,
                                progress: 100,
                                uploadedBytes: fileSize,
                                totalBytes: fileSize,
                                secondsRemaining: 0,
                                uploadStartTime: null,
                                uploadUrl: null,
                                gcsPath: null, // Could reconstruct from userid/runid/filename if needed
                                error: null,
                                abortController: null,
                            };
                        });

                        setFileUploads(uploadStates);
                    }
                }
            } catch (err) {
                console.error('Error fetching run metadata:', err);
            } finally {
                setIsLoading(false);
            }
        };

        fetchRunMetadata();
    }, [runid, api]);

    // Warn user before leaving page if uploads are in progress
    useEffect(() => {
        const handleBeforeUnload = (e: BeforeUnloadEvent) => {
            const hasActiveUploads = fileUploads.some((u) => u.status === UploadStatus.UPLOADING);
            if (hasActiveUploads) {
                e.preventDefault();
                e.returnValue = true;
                return e.returnValue;
            }
        };

        window.addEventListener('beforeunload', handleBeforeUnload);
        return () => window.removeEventListener('beforeunload', handleBeforeUnload);
    }, [fileUploads]);

    // Auto-start pending uploads with ref to track started uploads by filename+size
    const startedUploadsRef = useRef<Set<string>>(new Set());

    // Track if metadata save is in progress to prevent concurrent saves
    const isSavingMetadata = useRef<boolean>(false);

    // Keep refs to latest state for saveDatasetMetadata to avoid stale closures
    const fileUploadsRef = useRef(fileUploads);
    const settingsRef = useRef(settings);

    useEffect(() => {
        fileUploadsRef.current = fileUploads;
    }, [fileUploads]);

    useEffect(() => {
        settingsRef.current = settings;
    }, [settings]);

    useEffect(() => {
        fileUploads.forEach((upload, index) => {
            // Create unique key for this upload
            const uploadKey = `${upload.file.name}-${upload.file.size}-${index}`;

            if (
                upload.status === UploadStatus.PENDING &&
                !startedUploadsRef.current.has(uploadKey)
            ) {
                startedUploadsRef.current.add(uploadKey);
                // Use setTimeout to ensure state is fully committed
                setTimeout(() => {
                    startUpload(index);
                    // Clean up ref after starting
                    startedUploadsRef.current.delete(uploadKey);
                }, 10);
            }
        });
    }, [fileUploads]);

    const updateUploadState = (index: number, updates: Partial<FileUploadState>) => {
        setFileUploads((prev) =>
            prev.map((upload, i) => (i === index ? { ...upload, ...updates } : upload))
        );
    };

    const saveDatasetMetadata = useCallback(async () => {
        // Prevent concurrent saves
        if (isSavingMetadata.current) {
            return;
        }

        const saveStartTime = Date.now();
        setIsSaving(true);

        try {
            isSavingMetadata.current = true;

            // Build datasets array from current fileUploads state (via ref to get latest)
            // Only include COMPLETED uploads (not PENDING/UPLOADING/ERROR)
            const datasets = fileUploadsRef.current
                .filter((upload) => upload.status === UploadStatus.COMPLETED)
                .map((upload) => ({
                    name: upload.file.name,
                    description: upload.description || '',
                    content_type: upload.file.type || 'application/octet-stream',
                    file_size_bytes: upload.file.size,
                }));

            // Build metadata from current settings (via ref to get latest)
            const currentSettings = settingsRef.current;
            const metadata = {
                name: currentSettings.name.trim(),
                description: currentSettings.datasetsDescription.trim(),
                domain: currentSettings.domain.trim(),
                intent: currentSettings.intent.trim(),
                datasets,
            };

            await api.saveMetadata(runid, metadata);
        } catch (err) {
            console.error('Failed to save dataset metadata:', err);
            // Show error notification to user
            setFormError(
                `Failed to save file metadata: ${err instanceof Error ? err.message : 'Unknown error'}`
            );
            // Note: Don't throw - this is a background save, shouldn't block workflow
        } finally {
            isSavingMetadata.current = false;

            // Ensure indicator shows for at least 1000ms
            const elapsed = Date.now() - saveStartTime;
            const remainingTime = Math.max(0, 1000 - elapsed);

            if (savingTimeoutRef.current) {
                clearTimeout(savingTimeoutRef.current);
            }

            savingTimeoutRef.current = setTimeout(() => {
                setIsSaving(false);
            }, remainingTime);
        }
    }, [api, runid]);

    const uploadToGCS = async (
        index: number,
        uploadUrl: string,
        file: File,
        uploadStartTime: number
    ): Promise<void> => {
        const abortController = new AbortController();
        updateUploadState(index, { abortController });

        await uploadFileToGCS({
            file,
            uploadUrl,
            uploadStartTime,
            onProgress: (progressEvent) => {
                updateUploadState(index, {
                    progress: progressEvent.progress,
                    uploadedBytes: progressEvent.uploadedBytes,
                    secondsRemaining: progressEvent.secondsRemaining,
                });
            },
            onComplete: () => {
                updateUploadState(index, {
                    status: UploadStatus.COMPLETED,
                    progress: 100,
                    secondsRemaining: 0,
                });
                // Save metadata immediately after upload completes
                // Use setTimeout to ensure state update completes first
                setTimeout(() => saveDatasetMetadata(), 100);
            },
            onError: (error) => {
                updateUploadState(index, {
                    status: UploadStatus.ERROR,
                    error: error.message,
                });
            },
            abortSignal: abortController.signal,
        });
    };

    const startUpload = useCallback(
        async (index: number) => {
            const currentUpload: FileUploadState = fileUploads[index];
            if (!currentUpload) {
                // Upload not found - may have been removed or timing issue
                return;
            }

            // Skip if already uploading or completed
            if (currentUpload.status !== UploadStatus.PENDING) {
                return;
            }

            // Store file info before async operations
            const { file } = currentUpload;
            const uploadStartTime = Date.now();

            try {
                updateUploadState(index, {
                    status: UploadStatus.UPLOADING,
                    uploadStartTime,
                    error: null,
                });

                // Request presigned URL from backend
                const { data } = await api.generateUploadUrl({
                    runid,
                    filename: file.name,
                    contentType: file.type || 'application/octet-stream',
                    fileSizeBytes: file.size,
                });

                updateUploadState(index, {
                    uploadUrl: data.upload_url,
                    gcsPath: data.gcs_path,
                });

                // Upload directly to GCS
                await uploadToGCS(index, data.upload_url, file, uploadStartTime);
            } catch (err) {
                console.error('Upload failed:', err);
                const errorMessage = err instanceof Error ? err.message : 'Upload failed';
                updateUploadState(index, {
                    status: UploadStatus.ERROR,
                    error: errorMessage,
                });
            }
        },
        [fileUploads, runid]
    );

    const handleFileSelect = (files: File[]) => {
        if (!files.length) return;

        const newUploads = Array.from(files).map((file) => {
            const newUpload: FileUploadState = {
                file,
                description: '',
                status: UploadStatus.PENDING,
                progress: 0,
                uploadedBytes: 0,
                totalBytes: file.size,
                secondsRemaining: null,
                uploadStartTime: null,
                uploadUrl: null,
                gcsPath: null,
                error: null,
                abortController: null,
            };
            return newUpload;
        });

        setFileUploads((prev) => [...prev, ...newUploads]);

        setFieldErrors((prev) => {
            const { datasets, ...rest } = prev;
            return rest;
        });
        setFormError(null);
    };

    const handleFileDescriptionChange = (index: number, description: string) => {
        setFieldErrors((prev) => {
            const { datasets, ...rest } = prev;
            return rest;
        });
        setFormError(null);
        updateUploadState(index, { description });
        debouncedSaveDatasetMetadata();
    };

    const handleRemoveFileUpload = (index: number) => {
        const upload = fileUploads[index];

        if (upload && upload.status === UploadStatus.UPLOADING && upload.abortController) {
            upload.abortController.abort();
        }

        setFileUploads((prev) => prev.filter((_, i) => i !== index));

        // Save metadata to reflect removed file
        // Use setTimeout to ensure state update completes first
        setTimeout(() => saveDatasetMetadata(), 100);
    };

    const cancelUpload = (index: number) => {
        const upload = fileUploads[index];

        if (upload && upload.abortController) {
            upload.abortController.abort();
        }
    };

    const retryUpload = async (index: number) => {
        updateUploadState(index, {
            status: UploadStatus.PENDING,
            progress: 0,
            uploadedBytes: 0,
            error: null,
            abortController: null,
            uploadStartTime: null,
            uploadUrl: null,
        });

        await startUpload(index);
    };

    const updateSettings = <K extends keyof Settings>(key: K, value: Settings[K]) => {
        setFieldErrors((prev) => {
            const { [key]: _, ...rest } = prev;
            return rest;
        });
        setSettings((prev) => ({ ...prev, [key]: value }));
        setFormError(null);
    };

    const saveMetadata = useCallback(async () => {
        const saveStartTime = Date.now();
        setIsSaving(true);

        try {
            // Use refs to get latest state
            const currentSettings = settingsRef.current;
            const currentFileUploads = fileUploadsRef.current;

            const metadata = {
                name: currentSettings.name.trim(),
                description: currentSettings.datasetsDescription.trim(),
                domain: currentSettings.domain.trim(),
                intent: currentSettings.intent.trim(),
                datasets: currentFileUploads.map((upload) => ({
                    name: upload.file.name,
                    description: upload.description,
                    content_type: upload.file.type || 'application/octet-stream',
                    file_size_bytes: upload.file.size,
                })),
            };

            await api.saveMetadata(runid, metadata);
        } finally {
            // Ensure indicator shows for at least 1000ms
            const elapsed = Date.now() - saveStartTime;
            const remainingTime = Math.max(0, 1000 - elapsed);

            if (savingTimeoutRef.current) {
                clearTimeout(savingTimeoutRef.current);
            }

            savingTimeoutRef.current = setTimeout(() => {
                setIsSaving(false);
            }, remainingTime);
        }
    }, [api, runid]);

    const saveJobArgs = useCallback(
        async (overrides?: Partial<Settings>) => {
            const saveStartTime = Date.now();
            setIsSaving(true);

            try {
                // Use ref to get latest state
                const currentSettings = settingsRef.current;
                const effectiveSettings = { ...currentSettings, ...overrides };
                const jobArgs = {
                    n_experiments: effectiveSettings.nExperiments,
                    exploration_weight: effectiveSettings.explorationWeight,
                    mcts_selection: effectiveSettings.mctsSelection,
                    surprisal_width: effectiveSettings.surprisalWidth,
                    evidence_weight: effectiveSettings.evidenceWeight,
                    warmstart_experiments: effectiveSettings.warmstartExperiments,
                    n_warmstart: effectiveSettings.nWarmstart,
                };
                await api.saveJobArgs(runid, jobArgs);
            } finally {
                // Ensure indicator shows for at least 1000ms
                const elapsed = Date.now() - saveStartTime;
                const remainingTime = Math.max(0, 1000 - elapsed);

                if (savingTimeoutRef.current) {
                    clearTimeout(savingTimeoutRef.current);
                }

                savingTimeoutRef.current = setTimeout(() => {
                    setIsSaving(false);
                }, remainingTime);
            }
        },
        [api, runid]
    );

    // Create debounced versions of save functions
    const debouncedSaveMetadata = useMemo(
        () => debounce(() => saveMetadata(), debounceSaveMs),
        [saveMetadata, debounceSaveMs]
    );

    const debouncedSaveJobArgs = useMemo(
        () => debounce(() => saveJobArgs(), debounceSaveMs),
        [saveJobArgs, debounceSaveMs]
    );

    const debouncedSaveDatasetMetadata = useMemo(
        () => debounce(() => saveDatasetMetadata(), debounceSaveMs),
        [saveDatasetMetadata, debounceSaveMs]
    );

    // Cleanup debounced functions and saving timeout on unmount
    useEffect(() => {
        return () => {
            debouncedSaveMetadata.cancel();
            debouncedSaveJobArgs.cancel();
            debouncedSaveDatasetMetadata.cancel();
            if (savingTimeoutRef.current) {
                clearTimeout(savingTimeoutRef.current);
            }
        };
    }, [debouncedSaveMetadata, debouncedSaveJobArgs, debouncedSaveDatasetMetadata]);

    const handleExperimentsChange = (value: string) => {
        if (value === '') {
            setFieldErrors((prev) => ({
                ...prev,
                nExperiments: 'Number of experiments is required',
            }));
            setSettings((prev) => ({ ...prev, nExperiments: '' as any }));
            return;
        }

        const num = parseInt(value, 10);

        if (isNaN(num) || num < 1 || num > creditsRemaining) {
            setFieldErrors((prev) => ({
                ...prev,
                nExperiments: `Must be between 1 and ${creditsRemaining}`,
            }));
        } else {
            updateSettings('nExperiments', num);
            saveJobArgs({ nExperiments: num });
            setFormError(null);
        }
    };

    const isFormInvalid = () => {
        // Validate all required fields
        const errors: FieldErrors = {};

        if (!settings.name.trim()) {
            errors.name = 'Run name is required';
        }

        if (!settings.datasetsDescription.trim()) {
            errors.datasetsDescription = 'Description for datasets is required';
        }

        if (!fileUploads.length) {
            errors.datasets = 'Please upload at least one dataset';
        }

        // Validate file descriptions
        const hasValidationErrors = Object.values(errors).length > 0;

        if (settings.nExperiments < 1 || settings.nExperiments > creditsRemaining) {
            errors.nExperiments = `Number of experiments must be between 1 and ${creditsRemaining}`;
        }

        if (hasValidationErrors) {
            setFieldErrors(errors);
            setFormError('Please fill in all required fields');
        }

        return hasValidationErrors;
    };

    const handleSubmit = async () => {
        setIsSubmitting(true);

        // Flush any pending debounced saves
        debouncedSaveMetadata.flush();
        debouncedSaveJobArgs.flush();
        debouncedSaveDatasetMetadata.flush();

        if (isFormInvalid()) {
            setIsSubmitting(false);
            return;
        }

        try {
            // Check if all uploads are complete
            const pendingUploads = fileUploads.filter(
                (u) => u.status === UploadStatus.UPLOADING || u.status === UploadStatus.PENDING
            );

            if (pendingUploads.length > 0) {
                setFormError('Please wait for all uploads to complete');
                setIsSubmitting(false);
                return;
            }

            const failedUploads = fileUploads.filter((u) => u.status === UploadStatus.ERROR);
            if (failedUploads.length > 0) {
                setFormError('Some uploads failed. Please remove failed files or retry them.');
                setIsSubmitting(false);
                return;
            }

            // Save metadata
            await saveMetadata();

            // Update the run name in the sidebar list
            updateViewerRun({ id: runid, name: settings.name.trim() });

            // Submit run
            await api.submitRun(runid, {
                n_experiments: settings.nExperiments,
                intent: settings.intent,
            });

            // Notify parent of success
            onSubmitSuccess();
        } catch (err) {
            console.error('Error submitting run:', err);
            setFormError(err instanceof Error ? err.message : 'Failed to submit run');
        } finally {
            setIsSubmitting(false);
        }
    };

    return {
        // Computed values
        creditsRemaining,

        // Dataset upload state
        fileUploads,

        // Run configuration state
        settings,
        fieldErrors,

        // Submission state
        isSubmitting,
        formError,

        // Loading state
        isLoading,

        // Saving state
        isSaving,

        // Setters
        updateSettings,
        saveMetadata,
        saveJobArgs,

        // Debounced save functions
        debouncedSaveMetadata,
        debouncedSaveJobArgs,
        debouncedSaveDatasetMetadata,

        // Handlers
        handleFileSelect,
        handleFileDescriptionChange,
        handleRemoveFileUpload,
        cancelUpload,
        retryUpload,
        handleExperimentsChange,
        handleSubmit,
    };
}
