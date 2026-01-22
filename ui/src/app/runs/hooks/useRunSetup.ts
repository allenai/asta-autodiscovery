import { useState } from 'react';

import { useAuth0 } from '@/contexts/Auth0Context';
import { useViewerCredits } from '@/contexts/ViewerCreditsContext';
import { uploadDataset, saveMetadata, submitRun } from '../actions';

export const MODEL_OPTIONS = [
    { value: 'gpt-4o', label: 'GPT-4o' },
    { value: 'o4-mini', label: 'o4-mini' },
    { value: 'gpt-5-mini', label: 'GPT-5 Mini' },
    { value: 'gpt-5-nano', label: 'GPT-5 Nano' },
];

export const BELIEF_MODES = {
    BOOLEAN: { value: 'boolean', label: 'Boolean' },
    BOOLEAN_CAT: { value: 'boolean_cat', label: 'Boolean Categorical' },
    CATEGORICAL: { value: 'categorical', label: 'Categorical' },
    CATEGORICAL_NUMERIC: { value: 'categorical_numeric', label: 'Categorical Numeric' },
    GAUSSIAN: { value: 'gaussian', label: 'Gaussian' },
};

export const MCTS_SELECTION = {
    UCB1: { value: 'ucb1', label: 'UCB1' },
    BEAM_SEARCH: { value: 'beam_search', label: 'Beam Search' },
    PW: { value: 'pw', label: 'Progressive Widening' },
    PW_ALL: { value: 'pw_all', label: 'Progressive Widening All' },
    UCB1_RECURSIVE: { value: 'ucb1_recursive', label: 'UCB1 Recursive' },
};

export interface Dataset {
    filename: string;
    description: string;
    path?: string;
}

export interface RunMetadata {
    name: string;
    intent: string;
    domain: string;
    datasetDescription: string;
    nExperiments: number;
    model: string;
    beliefMode: string;
    explorationWeight: number;
    useBeamSearch: boolean;
    mctsSelection: string;
    surprisalWidth: number;
    evidenceWeight: number;
    warmstartExperiments: string;
}

interface UseRunSetupProps {
    runid: string;
    onSubmitSuccess: () => void;
}

export interface SelectedFile {
    file: File;
    description: string;
}

export function useRunSetup({ runid, onSubmitSuccess }: UseRunSetupProps) {
    const { getAccessToken } = useAuth0();
    const { credits } = useViewerCredits();

    const creditsRemaining = credits?.remaining ?? 500;

    // Dataset upload state
    const [datasets, setDatasets] = useState<Dataset[]>([]);
    const [selectedFiles, setSelectedFiles] = useState<SelectedFile[]>([]);
    const [uploading, setUploading] = useState(false);
    const [uploadError, setUploadError] = useState<string | null>(null);

    // Run configuration state
    const [metadata, setMetadata] = useState<RunMetadata>({
        name: '',
        intent: '',
        domain: '',
        datasetDescription: '',
        nExperiments: 4,
        model: 'gpt-4o',
        beliefMode: BELIEF_MODES.BOOLEAN_CAT.value,
        explorationWeight: 2,
        useBeamSearch: false,
        mctsSelection: MCTS_SELECTION.UCB1_RECURSIVE.value,
        surprisalWidth: 0.2,
        evidenceWeight: 2,
        warmstartExperiments: '',
    });
    const [experimentsError, setExperimentsError] = useState<string | null>(null);

    // Field validation errors
    const [fieldErrors, setFieldErrors] = useState<{
        name?: string;
        intent?: string;
        datasetDescription?: string;
        datasets?: string;
    }>({});

    // Submission state
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleFileSelect = (file: File) => {
        if (file) {
            setSelectedFiles((prev) => [...prev, { file, description: '' }]);
            setUploadError(null);
        }
    };

    const handleFileDescriptionChange = (index: number, description: string) => {
        setSelectedFiles((prev) =>
            prev.map((selectedFile, i) =>
                i === index ? { ...selectedFile, description } : selectedFile
            )
        );
    };

    const handleUploadDataset = async () => {
        if (selectedFiles.length === 0 || !metadata.datasetDescription.trim()) {
            setUploadError('Please select files and provide a description');
            return;
        }

        setUploading(true);
        setUploadError(null);

        try {
            const token = await getAccessToken();

            // Upload all selected files
            for (const selectedFile of selectedFiles) {
                const formData = new FormData();
                formData.append('file', selectedFile.file);
                formData.append('runid', runid);

                const response = await uploadDataset(formData, token);

                // Add to datasets list
                const newDataset: Dataset = {
                    filename: response.filename,
                    description: selectedFile.description.trim(),
                    path: response.path,
                };

                setDatasets((prev) => [...prev, newDataset]);
            }

            // Reset form
            setSelectedFiles([]);
        } catch (err) {
            console.error('Error uploading dataset:', err);
            setUploadError(err instanceof Error ? err.message : 'Failed to upload dataset');
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

    const updateMetadata = <K extends keyof RunMetadata>(key: K, value: RunMetadata[K]) => {
        setMetadata((prev) => ({ ...prev, [key]: value }));
    };

    const handleExperimentsChange = (value: string) => {
        const num = parseInt(value, 10);

        if (value === '') {
            updateMetadata('nExperiments', 0);
            setExperimentsError('Number of experiments is required');
            return;
        }

        if (isNaN(num) || num < 1 || num > creditsRemaining) {
            setExperimentsError(`Must be between 1 and ${creditsRemaining}`);
        } else {
            setExperimentsError(null);
        }

        updateMetadata('nExperiments', num);
    };

    const handleSubmit = async () => {
        // Validate all required fields
        const errors: {
            name?: string;
            intent?: string;
            datasetDescription?: string;
            datasets?: string;
        } = {};

        if (!metadata.name.trim()) {
            errors.name = 'Run name is required';
        }

        if (!metadata.intent.trim()) {
            errors.intent = 'Intent is required';
        }

        if (!metadata.datasetDescription.trim()) {
            errors.datasetDescription = 'Dataset description is required';
        }

        if (datasets.length === 0) {
            errors.datasets = 'Please upload at least one dataset';
        }

        // Validate that all selected files have descriptions
        if (selectedFiles.length > 0) {
            const filesWithoutDescription = selectedFiles.filter(
                (file) => !file.description.trim()
            );
            if (filesWithoutDescription.length > 0) {
                setUploadError('Please provide a description for all selected files');
            }
        }

        if (Object.keys(errors).length > 0 || uploadError) {
            setFieldErrors(errors);
            setError('Please fill in all required fields');
            return;
        }

        if (metadata.nExperiments < 1 || metadata.nExperiments > creditsRemaining) {
            setError(`Number of experiments must be between 1 and ${creditsRemaining}`);
            return;
        }

        setSubmitting(true);
        setError(null);
        setFieldErrors({});

        try {
            const token = await getAccessToken();
            // upload files
            handleUploadDataset();

            // Prepare metadata
            const submissionMetadata = {
                name: metadata.name.trim(),
                intent: metadata.intent.trim(),
                domain: metadata.domain.trim(),
                dataset_description: metadata.datasetDescription.trim() || undefined,
                datasets: datasets.map((ds) => ({
                    name: ds.filename,
                    intent: ds.description,
                })),
                nExperiments: metadata.nExperiments,
                beliefMode: metadata.beliefMode,
                explorationWeight: metadata.explorationWeight,
                useBeamSearch: metadata.useBeamSearch,
                mctsSelection: metadata.mctsSelection,
                surprisalWidth: metadata.surprisalWidth,
                evidenceWeight: metadata.evidenceWeight,
                warmstartExperiments: metadata.warmstartExperiments,
            };

            // Save metadata
            await saveMetadata(runid, submissionMetadata, token);

            // Submit run
            await submitRun(
                runid,
                {
                    n_experiments: metadata.nExperiments,
                    model: metadata.model,
                    belief_model: metadata.beliefMode,
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

    return {
        // Computed values
        creditsRemaining,

        // Dataset upload state
        datasets,
        selectedFiles,
        uploading,
        uploadError,

        // Run configuration state
        metadata,
        experimentsError,
        fieldErrors,

        // Submission state
        submitting,
        error,

        // Setters
        updateMetadata,

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
