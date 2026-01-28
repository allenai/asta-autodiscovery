import { useState, useEffect } from 'react';

import { useViewerCredits } from '@/contexts/ViewerCreditsContext';
import { getRunsApi } from '@/api/RunsApi';
import { getRunFromApi } from '@/types/Run';

export const MCTS_SELECTION = {
    UCB1: { value: 'ucb1', label: 'UCB1' },
    BEAM_SEARCH: { value: 'beam_search', label: 'Beam Search' },
    PW: { value: 'pw', label: 'Progressive Widening' },
    PW_ALL: { value: 'pw_all', label: 'Progressive Widening All' },
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
};

interface UseRunSetupProps {
    runid: string;
    onSubmitSuccess: () => void;
}

export interface SelectedFile {
    file: File;
    description: string;
}

interface FieldErrors {
    name?: string;
    datasets?: string;
    datasetFileDescriptions?: string;
    nExperiments?: string;
}

export function useRunSetup({ runid, onSubmitSuccess }: UseRunSetupProps) {
    const { credits } = useViewerCredits();
    const api = getRunsApi();

    const creditsRemaining = credits?.remaining ?? 500;

    // Dataset upload state
    const [datasets, setDatasets] = useState<Dataset[]>([]);
    const [selectedFiles, setSelectedFiles] = useState<SelectedFile[]>([]);
    const [uploading, setUploading] = useState(false);
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
                }
            } catch (err) {
                console.error('Error fetching run metadata:', err);
            } finally {
                setIsLoading(false);
            }
        };

        fetchRunMetadata();
    }, [runid, api]);

    const handleFileSelect = (file: File) => {
        if (file) {
            setSelectedFiles((prev) => [...prev, { file, description: '' }]);
            setFieldErrors((prev) => {
                const { datasets, datasetFileDescriptions, ...rest } = prev;
                return rest;
            });
            setFormError(null);
        }
    };

    const handleFileDescriptionChange = (index: number, description: string) => {
        setFieldErrors((prev) => {
            const { datasets, datasetFileDescriptions, ...rest } = prev;
            return rest;
        });
        setFormError(null);
        setSelectedFiles((prev) =>
            prev.map((selectedFile, i) =>
                i === index ? { ...selectedFile, description } : selectedFile
            )
        );
    };

    const handleUploadDataset = async (): Promise<boolean> => {
        setUploading(true);

        try {
            // Upload all selected files
            const uploadReq = selectedFiles.map((selectedFile) => {
                return api.uploadDataset(runid, selectedFile.file);
            });
            const uploadResp = await Promise.all(uploadReq);
            const datasets = uploadResp.map(({ data }, i) => {
                return {
                    filename: data.filename,
                    description: selectedFiles[i].description.trim(),
                    path: data.path,
                };
            });
            setDatasets(datasets);

            // Reset form
            setSelectedFiles([]);
            return true;
        } catch (err) {
            console.error('Error uploading dataset:', err);
            setFieldErrors((prev) => ({
                ...prev,
                datasets: err instanceof Error ? err.message : 'Failed to upload dataset',
            }));
            return false;
        } finally {
            setUploading(false);
        }
    };

    const handleRemoveDataset = (index: number) => {
        const newDatasets = datasets.filter((_, i) => i !== index);
        setDatasets(newDatasets);
    };

    const handleRemoveSelectedFile = (index: number) => {
        const newFiles = selectedFiles.filter((_, i) => i !== index);
        setSelectedFiles(newFiles);
    };

    const updateSettings = <K extends keyof Settings>(key: K, value: Settings[K]) => {
        setFieldErrors((prev) => {
            const { [key]: _, ...rest } = prev;
            return rest;
        });
        setSettings((prev) => ({ ...prev, [key]: value }));
        setFormError(null);
    };

    const saveMetadata = async () => {
        const metadata = {
            name: settings.name.trim(),
            description: settings.datasetsDescription.trim(),
            domain: settings.domain.trim(),
            intent: settings.intent.trim(),
            datasets: selectedFiles.map((ds) => ({
                name: ds.file.name,
                description: ds.description,
            })),
        };

        await api.saveMetadata(runid, metadata);
    };

    const saveJobArgs = async () => {
        const jobArgs = {
            n_experiments: settings.nExperiments,
            exploration_weight: settings.explorationWeight,
            mcts_selection: settings.mctsSelection,
            surprisal_width: settings.surprisalWidth,
            evidence_weight: settings.evidenceWeight,
            warmstart_experiments: settings.warmstartExperiments,
            n_warmstart: settings.nWarmstart,
        };
        await api.saveJobArgs(runid, jobArgs);
    };

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
            saveJobArgs();
            setFormError(null);
        }
    };

    const isFormInvalid = () => {
        // Validate all required fields
        const errors: FieldErrors = {};

        if (!settings.name.trim()) {
            errors.name = 'Run name is required';
        }

        if (!selectedFiles.length) {
            errors.datasets = 'Please upload at least one dataset';
        }

        // Validate file descriptions
        const fileValidation = validateFileDescriptions(selectedFiles);
        const hasValidationErrors = Object.values(errors).length > 0 || !fileValidation.isValid;

        if (!fileValidation.isValid) {
            errors.datasetFileDescriptions = 'Please provide a description for all selected files';
        }

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
        if (isFormInvalid()) {
            setIsSubmitting(false);
            return;
        }

        try {
            // upload files
            const isSuccessfulUpload = await handleUploadDataset();
            if (!isSuccessfulUpload) {
                return;
            }

            // Save metadata
            await saveMetadata();

            // // Submit run
            await api.submitRun(runid, {
                n_experiments: settings.nExperiments,
            });

            // Notify parent of success
            onSubmitSuccess();
        } catch (err) {
            console.error('Error isSubmitting run:', err);
            setFormError(err instanceof Error ? err.message : 'Failed to submit run');
            setIsSubmitting(false);
        } finally {
            setIsSubmitting(false);
        }
    };

    return {
        // Computed values
        creditsRemaining,

        // Dataset upload state
        datasets,
        selectedFiles,
        uploading,

        // Run configuration state
        settings,
        fieldErrors,

        // Submission state
        isSubmitting,
        formError,

        // Loading state
        isLoading,

        // Setters
        updateSettings,
        saveMetadata,
        saveJobArgs,

        // Handlers
        handleFileSelect,
        handleFileDescriptionChange,
        handleUploadDataset,
        handleRemoveDataset,
        handleRemoveSelectedFile,
        handleExperimentsChange,
        handleSubmit,
    };
}

// Helpers

// Validates that all selected files have non-empty descriptions
const validateFileDescriptions = (selectedFiles: SelectedFile[]) => {
    const filesWithoutDescription = selectedFiles.filter((file) => !file.description.trim());

    return {
        isValid: filesWithoutDescription.length === 0,
        filesWithoutDescription,
        missingCount: filesWithoutDescription.length,
    };
};
