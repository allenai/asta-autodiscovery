import { useState } from 'react';

import { useViewerCredits } from '@/contexts/ViewerCreditsContext';
import { getRunsApi } from '@/api/RunsApi';
import { submitRun } from '../actions';
import { useAuth0 } from '@/contexts/Auth0Context';

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

    // advanced settings
    nExperiments: number;
    intent: string;
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
    datasetsDescription?: string;
    datasets?: string;
    datasetFileDescriptions?: string;
    nExperiments?: string;
}

export function useRunSetup({ runid, onSubmitSuccess }: UseRunSetupProps) {
    const { credits } = useViewerCredits();
    const { getAccessToken } = useAuth0();
    const api = getRunsApi();

    const creditsRemaining = credits?.remaining ?? 500;

    // Dataset upload state
    const [datasets, setDatasets] = useState<Dataset[]>([]);
    const [selectedFiles, setSelectedFiles] = useState<SelectedFile[]>([]);
    const [uploading, setUploading] = useState(false);
    const [uploadError, setUploadError] = useState<string | null>(null);
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
    const [submitting, setSubmitting] = useState(false);
    const [formError, setFormError] = useState<string | null>(null);

    const handleFileSelect = (file: File) => {
        if (file) {
            setSelectedFiles((prev) => [...prev, { file, description: '' }]);
            setUploadError(null);
        }
    };

    const handleFileDescriptionChange = (index: number, description: string) => {
        setFieldErrors((prev) => {
            const { datasetFileDescriptions, ...rest } = prev;
            return rest;
        });
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
            for (const selectedFile of selectedFiles) {
                const { data } = await api.uploadDataset(runid, selectedFile.file);

                // Add to datasets list
                const newDataset: Dataset = {
                    filename: data.filename,
                    description: selectedFile.description.trim(),
                    path: data.path,
                };

                setDatasets((prev) => [...prev, newDataset]);
            }

            // Reset form
            setSelectedFiles([]);
            return true;
        } catch (err) {
            console.error('Error uploading dataset:', err);
            setUploadError(err instanceof Error ? err.message : 'Failed to upload dataset');
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
        setFieldErrors({});
        setSettings((prev) => ({ ...prev, [key]: value }));
    };

    const handleExperimentsChange = (value: string) => {
        const num = parseInt(value, 10);

        if (value === '') {
            setFieldErrors((prev) => ({
                ...prev,
                nExperiments: 'Number of experiments is required',
            }));

            return;
        }

        if (isNaN(num) || num < 1 || num > creditsRemaining) {
            setFieldErrors((prev) => ({
                ...prev,
                nExperiments: `Must be between 1 and ${creditsRemaining}`,
            }));
        } else {
            setFieldErrors((prev) => {
                const { nExperiments, ...rest } = prev;
                return rest;
            });
        }
    };

    const isFormInvalid = () => {
        // Validate all required fields
        const errors: FieldErrors = {};
        setUploadError(null);

        if (!settings.name.trim()) {
            errors.name = 'Run name is required';
        }

        if (!settings.datasetsDescription.trim()) {
            errors.datasetsDescription = 'Description for datasets is required';
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
        setSubmitting(true);
        if (isFormInvalid()) {
            return;
        }

        try {
            // upload files
            const isSuccessfulUpload = await handleUploadDataset();
            if (!isSuccessfulUpload) {
                setSubmitting(false);
                return;
            }

            // Prepare metadata
            const submissionMetadata = {
                name: settings.name.trim(),
                datasets_description: settings.datasetsDescription.trim(),
                domain: settings.domain.trim(),
                datasets: selectedFiles.map((ds) => ({
                    name: ds.file.name,
                    description: ds.description,
                })),
            };

            // Save metadata
            await api.saveMetadata(runid, submissionMetadata);

            // // Submit run
            await api.submitRun(runid, {
                n_experiments: settings.nExperiments,
            });
            // Submit run
            const token = await getAccessToken();
            // await submitRun(
            //     runid,
            //     {
            //         n_experiments: settings.nExperiments,
            //     },
            //     token
            // );

            // Notify parent of success
            onSubmitSuccess();
        } catch (err) {
            console.error('Error submitting run:', err);
            setFormError(err instanceof Error ? err.message : 'Failed to submit run');
            setSubmitting(false);
        }
    };

    return {
        // Computed values
        creditsRemaining,

        // Dataset upload state
        datasets,
        selectedFiles,
        uploading,
        uploadError,

        // Run configuration state
        settings,
        fieldErrors,

        // Submission state
        submitting,
        formError,

        // Setters
        updateSettings,

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
