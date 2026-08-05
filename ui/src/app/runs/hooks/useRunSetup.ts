import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import debounce from 'lodash.debounce';

import { useViewerCredits } from '@/contexts/ViewerCreditsContext';
import { useRuntimeConfig } from '@/contexts/RuntimeConfigContext';
import { useViewerRuns } from '@/contexts/ViewerRunsContext';
import { useToasts } from '@/contexts/ToastsContext';
import { getRunsApi, LocalDatasetFile, LocalDatasetInfo, ProviderInfo } from '@/api/RunsApi';
import { getMetadataFromApi, getRunFromApi, getRunDetailsFromApi } from '@/types/Run';
import { uploadToGCS as uploadFileToGCS } from '@/api/gcsUpload';
import { PRELOADED_DATASETS } from '@/runs/utils/preloadedDatasets';

export const MCTS_SELECTION = {
    PROGRESSIVE_WIDENING: {
        value: 'pw',
        label: 'MCTS with Progressive Widening',
    },
    UCB1_RECURSIVE: { value: 'ucb1_recursive', label: 'UCB1 Recursive' },
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
    llmProvider: 'current' | 'copilot';
    embeddingProvider: 'current' | 'copilot';
    model: string;
    beliefModel: string;
    visionModel: string;
    embeddingModel: string;
    embeddingDimensions: number;

    // Lineage (read-only, preserved across saves)
    parentRunId: string | null;
    parentRunName: string | null;
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
    relativePath?: string;
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

export function getLocalFilePath(file: File): string {
    return file.webkitRelativePath || file.name;
}

interface FieldErrors {
    name?: string;
    datasets?: string;
    datasetsDescription?: string;
    nExperiments?: string;
    provider?: string;
    embeddingProvider?: string;
}

export function useRunSetup({ runid, onSubmitSuccess, debounceSaveMs = 3000 }: UseRunSetupProps) {
    const { credits } = useViewerCredits();
    const { isLocal, isLoading: isRuntimeLoading } = useRuntimeConfig();
    const { updateViewerRun, viewerRuns } = useViewerRuns();
    const { addErrorToast } = useToasts();
    const api = getRunsApi();
    const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
    const [hasAi1Permission, setHasAi1Permission] = useState(false);
    const [preloadedDescs, setPreloadedDescs] = useState<Record<string, string>>({});
    const selectedPreloadedDatasets = useMemo(() => {
        if (isLocal || !hasAi1Permission) return [];
        return PRELOADED_DATASETS.filter((d) => selectedIds.has(d.id)).map((d) => ({
            ...d,
            description: preloadedDescs[d.id] ?? d.description,
        }));
    }, [selectedIds, preloadedDescs, hasAi1Permission, isLocal]);

    const experimentLimit = isLocal ? 500 : credits?.available ?? 0;

    // Get max file size from the run
    const maxFileSize = viewerRuns?.[runid]?.maxFileSize || null;

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
        mctsSelection: MCTS_SELECTION.PROGRESSIVE_WIDENING.value,
        surprisalWidth: 0.2,
        evidenceWeight: 2,
        warmstartExperiments: '',
        nWarmstart: 0,
        llmProvider: 'copilot',
        embeddingProvider: 'copilot',
        model: 'claude-sonnet-4.6',
        beliefModel: 'claude-sonnet-4.6',
        visionModel: 'claude-sonnet-4.6',
        embeddingModel: 'text-embedding-3-small',
        embeddingDimensions: 1536,
        parentRunId: null,
        parentRunName: null,
    });
    const [providers, setProviders] = useState<ProviderInfo[]>([]);
    const [localDatasets, setLocalDatasets] = useState<LocalDatasetInfo[]>([]);
    const [localCatalogPath, setLocalCatalogPath] = useState('');
    const [selectedLocalDataset, setSelectedLocalDataset] = useState('');
    const [localFolderPath, setLocalFolderPath] = useState('');
    const [activeLocalDataset, setActiveLocalDataset] = useState('');
    const [isSelectingLocalDataset, setIsSelectingLocalDataset] = useState(false);
    const [localDatasetError, setLocalDatasetError] = useState<string | null>(null);

    const refreshProviders = useCallback(() => {
        api.getProviders()
            .then(({ data }) => setProviders(data.providers))
            .catch((error) => {
                console.error('Failed to load providers:', error);
                setProviders([]);
            });
    }, [api]);

    useEffect(() => {
        refreshProviders();
        window.addEventListener('focus', refreshProviders);
        return () => window.removeEventListener('focus', refreshProviders);
    }, [refreshProviders]);

    useEffect(() => {
        if (!isLocal) return;
        api.listLocalDatasets()
            .then(({ data }) => {
                setLocalDatasets(data.datasets);
                setLocalCatalogPath(data.catalog_path);
            })
            .catch((error) => {
                console.error('Failed to load local datasets:', error);
                setLocalDatasetError('Could not read the local dataset folder.');
            });
    }, [api, isLocal]);

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
            if (isRuntimeLoading) return;
            setIsLoading(true);
            try {
                let metadata: ReturnType<typeof getMetadataFromApi>;
                if (isLocal) {
                    const { data } = await api.getRunMetadata({ runid });
                    metadata = getMetadataFromApi(data.metadata);
                    setHasAi1Permission(false);
                } else {
                    const { data } = await api.getRun({ runId: runid });
                    setHasAi1Permission(data.can_view_datasets ?? false);
                    metadata = getRunFromApi(data).metadata ?? null;
                }

                if (metadata) {
                    const loadedMetadata = metadata;
                    setSettings((prev) => ({
                        ...prev,
                        name: loadedMetadata.name || '',
                        datasetsDescription: loadedMetadata.description || '',
                        domain: loadedMetadata.domain || '',
                        intent: loadedMetadata.intent || '',
                        nExperiments: loadedMetadata.nExperiments ?? prev.nExperiments,
                        explorationWeight:
                            loadedMetadata.explorationWeight ?? prev.explorationWeight,
                        mctsSelection: loadedMetadata.mctsSelection ?? prev.mctsSelection,
                        surprisalWidth: loadedMetadata.surprisalWidth ?? prev.surprisalWidth,
                        evidenceWeight: loadedMetadata.evidenceWeight ?? prev.evidenceWeight,
                        warmstartExperiments:
                            loadedMetadata.warmstartExperiments ?? prev.warmstartExperiments,
                        nWarmstart: loadedMetadata.nWarmstart ?? prev.nWarmstart,
                        llmProvider: isLocal
                            ? 'copilot'
                            : loadedMetadata.llmProvider ?? prev.llmProvider,
                        embeddingProvider: isLocal
                            ? 'copilot'
                            : loadedMetadata.embeddingProvider ?? prev.embeddingProvider,
                        model: isLocal
                            ? !loadedMetadata.model ||
                              loadedMetadata.llmProvider === 'current' ||
                              loadedMetadata.model === 'claude-haiku-4.5'
                                ? 'claude-sonnet-4.6'
                                : loadedMetadata.model
                            : loadedMetadata.model ?? prev.model,
                        beliefModel: isLocal
                            ? !loadedMetadata.beliefModel ||
                              loadedMetadata.llmProvider === 'current' ||
                              loadedMetadata.beliefModel === 'claude-haiku-4.5'
                                ? 'claude-sonnet-4.6'
                                : loadedMetadata.beliefModel
                            : loadedMetadata.beliefModel ?? prev.beliefModel,
                        visionModel: isLocal
                            ? !loadedMetadata.visionModel ||
                              loadedMetadata.llmProvider === 'current' ||
                              loadedMetadata.visionModel === 'claude-haiku-4.5'
                                ? 'claude-sonnet-4.6'
                                : loadedMetadata.visionModel
                            : loadedMetadata.visionModel ?? prev.visionModel,
                        embeddingModel: isLocal
                            ? 'text-embedding-3-small'
                            : loadedMetadata.embeddingModel ?? prev.embeddingModel,
                        embeddingDimensions: isLocal
                            ? 1536
                            : loadedMetadata.embeddingDimensions ?? prev.embeddingDimensions,
                        parentRunId: loadedMetadata.parentRunId ?? null,
                        parentRunName: loadedMetadata.parentRunName ?? null,
                    }));

                    // Populate fileUploads from saved datasets
                    if (loadedMetadata.datasets && loadedMetadata.datasets.length > 0) {
                        const uploadStates: FileUploadState[] = loadedMetadata.datasets.map(
                            (dataset) => {
                                // Use saved content_type and file_size_bytes if available
                                const contentType =
                                    dataset.contentType || 'application/octet-stream';
                                const fileSize = dataset.fileSizeBytes || 0;

                                // Create placeholder File object from filename
                                // The actual file content is already in GCS, so we just need the metadata
                                const placeholderFile = new File(
                                    [],
                                    dataset.name.split('/').pop()!,
                                    {
                                        type: contentType,
                                    }
                                );

                                return {
                                    file: placeholderFile,
                                    relativePath: dataset.name,
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
                            }
                        );

                        setFileUploads(uploadStates);
                        if (isLocal) {
                            setActiveLocalDataset(loadedMetadata.datasets[0].name.split('/')[0]);
                        }
                    }
                }
            } catch (err) {
                console.error('Error fetching run metadata:', err);
            } finally {
                setIsLoading(false);
            }
        };

        fetchRunMetadata();
    }, [runid, api, isLocal, isRuntimeLoading]);

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
    const selectedPreloadedRef = useRef(selectedPreloadedDatasets);

    useEffect(() => {
        fileUploadsRef.current = fileUploads;
    }, [fileUploads]);

    useEffect(() => {
        settingsRef.current = settings;
    }, [settings]);

    useEffect(() => {
        selectedPreloadedRef.current = selectedPreloadedDatasets;
    }, [selectedPreloadedDatasets]);

    useEffect(() => {
        fileUploads.forEach((upload, index) => {
            // Create unique key for this upload
            const uploadKey = `${getLocalFilePath(upload.file)}-${upload.file.size}-${index}`;

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

    const getCombinedDatasets = () => {
        const uploads = fileUploadsRef.current
            .filter((upload) => upload.status === UploadStatus.COMPLETED)
            .map((upload) => ({
                name: isLocal
                    ? upload.relativePath || getLocalFilePath(upload.file)
                    : upload.file.name,
                description: upload.description || '',
                content_type: upload.file.type || 'application/octet-stream',
                file_size_bytes: upload.totalBytes || upload.file.size,
                url: null,
                is_preloaded: false,
            }));

        const preloaded = selectedPreloadedRef.current.map((ds) => ({
            name: ds.filename, // This MUST match the filename the agent expects
            description: ds.description,
            content_type: 'application/octet-stream',
            file_size_bytes: 0,
            url: ds.url,
            is_preloaded: true,
        }));

        return [...uploads, ...preloaded];
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

            const datasets = getCombinedDatasets();
            const currentSettings = settingsRef.current;
            const modelPricing = Object.fromEntries(
                (
                    providers.find((provider) => provider.id === currentSettings.llmProvider)
                        ?.models || []
                )
                    .filter((model) => model.pricing)
                    .map((model) => [model.id, model.pricing!])
            );
            const metadata = {
                // Descriptive metadata
                name: currentSettings.name.trim(),
                description: currentSettings.datasetsDescription.trim(),
                domain: currentSettings.domain.trim(),
                intent: currentSettings.intent.trim(),
                datasets,
                // Job configuration parameters
                n_experiments: currentSettings.nExperiments,
                exploration_weight: currentSettings.explorationWeight,
                mcts_selection: currentSettings.mctsSelection,
                surprisal_width: currentSettings.surprisalWidth,
                evidence_weight: currentSettings.evidenceWeight,
                warmstart_experiments: currentSettings.warmstartExperiments,
                n_warmstart: currentSettings.nWarmstart,
                llm_provider: currentSettings.llmProvider,
                embedding_provider: currentSettings.embeddingProvider,
                model: currentSettings.model,
                belief_model: currentSettings.beliefModel,
                vision_model: currentSettings.visionModel,
                embedding_model: currentSettings.embeddingModel,
                embedding_dimensions: currentSettings.embeddingDimensions,
                model_pricing: modelPricing,
                // Lineage
                lineage: {
                    parent_run_id: currentSettings.parentRunId ?? null,
                    parent_run_name: currentSettings.parentRunName ?? null,
                },
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
    }, [api, runid, isLocal, providers]);

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

                const { data: runtimeConfig } = await api.getRuntimeConfig();
                if (runtimeConfig.upload_transport === 'api') {
                    const { data } = await api.uploadDataset(runid, file, getLocalFilePath(file));
                    updateUploadState(index, {
                        status: UploadStatus.COMPLETED,
                        progress: 100,
                        uploadedBytes: file.size,
                        secondsRemaining: 0,
                        gcsPath: data.path,
                    });
                    setTimeout(() => saveDatasetMetadata(), 100);
                    return;
                }

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
        [api, fileUploads, runid, saveDatasetMetadata]
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

    const applyImportedDataset = async (files: LocalDatasetFile[], label: string) => {
        const importedUploads: FileUploadState[] = files.map((dataset) => ({
            file: new File([], dataset.name.split('/').pop()!, {
                type: dataset.content_type,
            }),
            relativePath: dataset.name,
            description: '',
            status: UploadStatus.COMPLETED,
            progress: 100,
            uploadedBytes: dataset.file_size_bytes,
            totalBytes: dataset.file_size_bytes,
            secondsRemaining: 0,
            uploadStartTime: null,
            uploadUrl: null,
            gcsPath: `data/${dataset.name}`,
            error: null,
            abortController: null,
        }));
        fileUploadsRef.current = importedUploads;
        setFileUploads(importedUploads);
        setActiveLocalDataset(label);
        setFieldErrors((previous) => {
            const { datasets, ...rest } = previous;
            return rest;
        });
        await saveDatasetMetadata();
    };

    const importLocalDataset = async (datasetName: string) => {
        if (!datasetName) return;
        setSelectedLocalDataset(datasetName);
        setIsSelectingLocalDataset(true);
        setLocalDatasetError(null);
        try {
            const { data } = await api.importLocalDataset(runid, {
                dataset_name: datasetName,
            });
            await applyImportedDataset(data.files, datasetName);
        } catch (error) {
            setLocalDatasetError(
                error instanceof Error ? error.message : 'Dataset selection failed.'
            );
        } finally {
            setIsSelectingLocalDataset(false);
        }
    };

    const browseLocalDatasetFolder = async () => {
        setLocalDatasetError(null);
        try {
            const { data } = await api.browseLocalDatasetFolder();
            if (data.path) {
                setLocalFolderPath(data.path);
                await importLocalFolderPath(data.path);
            }
        } catch (error) {
            setLocalDatasetError(
                error instanceof Error ? error.message : 'Folder selection failed.'
            );
        }
    };

    const importLocalFolderPath = async (folderPath = localFolderPath) => {
        if (!folderPath.trim()) return;
        setIsSelectingLocalDataset(true);
        setLocalDatasetError(null);
        try {
            const { data } = await api.importLocalDataset(runid, {
                source_path: folderPath.trim(),
            });
            const label = folderPath.trim().replace(/\/$/, '').split('/').pop() || 'Dataset';
            await applyImportedDataset(data.files, label);
        } catch (error) {
            setLocalDatasetError(
                error instanceof Error ? error.message : 'Dataset selection failed.'
            );
        } finally {
            setIsSelectingLocalDataset(false);
        }
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

    const saveMetadata = useCallback(
        async (showIndicator = true) => {
            const saveStartTime = Date.now();
            if (showIndicator) {
                setIsSaving(true);
            }

            try {
                // Use refs to get latest state
                const currentSettings = settingsRef.current;
                const datasets = getCombinedDatasets();
                const modelPricing = Object.fromEntries(
                    (
                        providers.find((provider) => provider.id === currentSettings.llmProvider)
                            ?.models || []
                    )
                        .filter((model) => model.pricing)
                        .map((model) => [model.id, model.pricing!])
                );

                const metadata = {
                    // Descriptive metadata
                    name: currentSettings.name.trim(),
                    description: currentSettings.datasetsDescription.trim(),
                    domain: currentSettings.domain.trim(),
                    intent: currentSettings.intent.trim(),
                    datasets,
                    // Job configuration parameters
                    n_experiments: currentSettings.nExperiments,
                    exploration_weight: currentSettings.explorationWeight,
                    mcts_selection: currentSettings.mctsSelection,
                    surprisal_width: currentSettings.surprisalWidth,
                    evidence_weight: currentSettings.evidenceWeight,
                    warmstart_experiments: currentSettings.warmstartExperiments,
                    n_warmstart: currentSettings.nWarmstart,
                    llm_provider: currentSettings.llmProvider,
                    embedding_provider: currentSettings.embeddingProvider,
                    model: currentSettings.model,
                    belief_model: currentSettings.beliefModel,
                    vision_model: currentSettings.visionModel,
                    embedding_model: currentSettings.embeddingModel,
                    embedding_dimensions: currentSettings.embeddingDimensions,
                    model_pricing: modelPricing,
                    // Lineage
                    lineage: {
                        parent_run_id: currentSettings.parentRunId ?? null,
                        parent_run_name: currentSettings.parentRunName ?? null,
                    },
                };

                await api.saveMetadata(runid, metadata);
            } finally {
                if (showIndicator) {
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
            }
        },
        [api, runid, providers]
    );

    // Create debounced versions of save functions
    const debouncedSaveMetadata = useMemo(
        () => debounce(() => saveMetadata(), debounceSaveMs),
        [saveMetadata, debounceSaveMs]
    );

    const debouncedSaveDatasetMetadata = useMemo(
        () => debounce(() => saveDatasetMetadata(), debounceSaveMs),
        [saveDatasetMetadata, debounceSaveMs]
    );

    // Cleanup debounced functions and saving timeout on unmount
    useEffect(() => {
        return () => {
            debouncedSaveMetadata.cancel();
            debouncedSaveDatasetMetadata.cancel();
            if (savingTimeoutRef.current) {
                clearTimeout(savingTimeoutRef.current);
            }
        };
    }, [debouncedSaveMetadata, debouncedSaveDatasetMetadata]);

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

        if (isNaN(num) || num < 1 || num > experimentLimit) {
            setFieldErrors((prev) => ({
                ...prev,
                nExperiments: `Must be between 1 and ${experimentLimit}`,
            }));
        } else {
            updateSettings('nExperiments', num);
            debouncedSaveMetadata();
            setFormError(null);
        }
    };

    const isFormInvalid = () => {
        const errors: FieldErrors = {};

        // Check Files/Preloaded
        const hasNoFiles = fileUploads.length === 0;
        const hasNoPreloaded = selectedIds.size === 0;

        if (hasNoFiles && hasNoPreloaded) {
            errors.datasets = 'Please upload at least one file or select a preloaded dataset';
        }

        // Check Name & Description
        if (!settings.name.trim()) {
            errors.name = 'Run name is required';
        }

        if (!settings.datasetsDescription.trim()) {
            errors.datasetsDescription = 'Description for datasets is required';
        }

        // Check Experiment Budget
        if (
            !settings.nExperiments ||
            settings.nExperiments < 1 ||
            settings.nExperiments > experimentLimit
        ) {
            errors.nExperiments = `Must be between 1 and ${experimentLimit}`;
        }

        const selectedProvider = providers.find((provider) => provider.id === settings.llmProvider);
        if (!selectedProvider || selectedProvider.status !== 'ready') {
            errors.provider =
                selectedProvider?.remediation || 'Select an available model provider.';
        }
        const selectedEmbeddingProvider = providers.find(
            (provider) => provider.id === settings.embeddingProvider
        );
        if (!selectedEmbeddingProvider?.embedding_ready) {
            errors.embeddingProvider =
                selectedEmbeddingProvider?.remediation || 'Select an available embedding provider.';
        }

        // Check the object keys directly
        const hasErrors = Object.keys(errors).length > 0;

        if (hasErrors) {
            setFieldErrors(errors);
        } else {
            setFieldErrors({});
        }

        return hasErrors;
    };

    const handleSubmit = async () => {
        if (isFormInvalid()) {
            addErrorToast('Please complete the highlighted required fields.');
            return;
        }

        setIsSubmitting(true);

        // Submission persists one complete snapshot, so queued autosaves only create races.
        debouncedSaveMetadata.cancel();
        debouncedSaveDatasetMetadata.cancel();

        try {
            // Check if all uploads are complete
            const pendingUploads = fileUploads.filter(
                (u) => u.status === UploadStatus.UPLOADING || u.status === UploadStatus.PENDING
            );

            if (pendingUploads.length > 0) {
                addErrorToast(
                    `Please wait for ${pendingUploads.length} ${pendingUploads.length === 1 ? 'file' : 'files'} to finish uploading.`
                );
                setIsSubmitting(false);
                return;
            }

            const failedUploads = fileUploads.filter((u) => u.status === UploadStatus.ERROR);
            if (failedUploads.length > 0) {
                setFormError('Some uploads failed. Please remove failed files or retry them.');
                setIsSubmitting(false);
                return;
            }

            // Save metadata (includes all job configuration)
            await saveMetadata(false);

            // Submit run - backend reads configuration from metadata
            const response = await api.submitRun(runid);

            // Update run in context with new details so it moves from Drafts to Sessions
            updateViewerRun({
                id: runid,
                name: settings.name.trim(),
                details: getRunDetailsFromApi(response.data.run_details),
            });

            // Notify parent of success
            onSubmitSuccess();
        } catch (err) {
            console.error('Error submitting run:', err);
            setFormError(err instanceof Error ? err.message : 'Failed to submit run');
        } finally {
            if (savingTimeoutRef.current) {
                clearTimeout(savingTimeoutRef.current);
            }
            setIsSaving(false);
            setIsSubmitting(false);
        }
    };

    const togglePreloadedDataset = (id: string) => {
        setSelectedIds((prev) => {
            const next = new Set(prev);
            if (next.has(id)) next.delete(id);
            else next.add(id);
            return next;
        });
        debouncedSaveMetadata(); // Auto-save when selection changes
    };

    const updatePreloadedDescription = (id: string, desc: string) => {
        setPreloadedDescs((prev) => ({ ...prev, [id]: desc }));
        debouncedSaveMetadata(); // Auto-save when description changes
    };

    return {
        // Computed values
        creditsAvailable: experimentLimit,
        isLocal,
        providers,

        // Dataset upload state
        fileUploads,
        maxFileSize,

        // Run configuration state
        settings,
        fieldErrors,

        // Submission state
        isSubmitting,
        formError,

        // Loading state
        isLoading: isLoading || isRuntimeLoading,

        // Saving state
        isSaving,

        // Setters
        updateSettings,
        saveMetadata,

        // Debounced save functions
        debouncedSaveMetadata,
        debouncedSaveDatasetMetadata,

        // Handlers
        handleFileSelect,
        handleFileDescriptionChange,
        handleRemoveFileUpload,
        cancelUpload,
        retryUpload,
        handleExperimentsChange,
        handleSubmit,
        hasAi1Permission,
        selectedPreloadedDatasets,
        selectedDatasetIds: selectedIds,
        togglePreloadedDataset,
        updatePreloadedDescription,
        localDatasets,
        localCatalogPath,
        selectedLocalDataset,
        setSelectedLocalDataset,
        localFolderPath,
        setLocalFolderPath,
        activeLocalDataset,
        isSelectingLocalDataset,
        localDatasetError,
        importLocalDataset,
        browseLocalDatasetFolder,
        importLocalFolderPath,
    };
}
