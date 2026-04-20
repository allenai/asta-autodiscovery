'use client';

import {
    Box,
    TextField,
    Button,
    Typography,
    FormControl,
    Select,
    MenuItem,
    CircularProgress,
    FormHelperText,
    styled,
    Chip,
    FormLabel,
    Accordion,
    AccordionSummary,
    Slider,
    Fade,
    Checkbox,
    IconButton,
    Collapse,
    Link,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import PlayCircleFilledWhiteOutlinedIcon from '@mui/icons-material/PlayCircleFilledWhiteOutlined';
import CheckBoxOutlineBlankIcon from '@mui/icons-material/CheckBoxOutlineBlank';
import DescriptionOutlinedIcon from '@mui/icons-material/DescriptionOutlined';
import CloseIcon from '@mui/icons-material/Close';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';

import { MCTS_SELECTION, useRunSetup } from '@/runs/hooks/useRunSetup';
import DatasetUpload, {
    File as FileCard,
    FileHeader,
    FileHeaderFilename,
    FileHeaderFileMeta,
    FileHeaderActions,
    FileDescription,
    DatasetSchemaTitle,
} from '@/runs/components/DatasetUpload';
import { mkExpandAdvancedSettingsTrackAttrs, mkSubmitRunBtnTrackAttrs } from '@/analytics/runSetup';
import { PRELOADED_DATASETS } from '@/runs/utils/preloadedDatasets';

const DEBOUNCE_SAVE_MS = 3000;

interface RunSetupProps {
    runid: string;
    onSubmitSuccess: () => void;
}

/**
 * Combined component for dataset upload and run configuration.
 *
 * Features:
 * - Upload multiple datasets with descriptions
 * - Configure run parameters (experiments, models)
 * - Single page experience with all settings
 * - Submit run when ready
 */
export default function RunSetup({ runid, onSubmitSuccess }: RunSetupProps) {
    const {
        settings,
        creditsAvailable,
        fileUploads,
        maxFileSize,
        fieldErrors,
        isSubmitting,
        isLoading,
        isSaving,
        updateSettings,
        debouncedSaveMetadata,
        handleFileSelect,
        handleFileDescriptionChange,
        handleRemoveFileUpload,
        handleExperimentsChange,
        handleSubmit,
        cancelUpload,
        retryUpload,
        hasAi1Permission,
        selectedDatasetIds,
        togglePreloadedDataset,
        updatePreloadedDescription,
    } = useRunSetup({ runid, onSubmitSuccess, debounceSaveMs: DEBOUNCE_SAVE_MS });

    const isFormDisabled = isSubmitting || isLoading;
    const datasetErrors = fieldErrors.datasets;

    if (isLoading) {
        return (
            <Box
                sx={{
                    display: 'flex',
                    justifyContent: 'center',
                    alignItems: 'center',
                    minHeight: '400px',
                }}>
                <CircularProgress />
            </Box>
        );
    }

    return (
        <Box sx={{ maxWidth: 'md', mx: 'auto', p: 3 }}>
            <SectionHeader>
                <SectionHeaderTitle>Create a new discovery session</SectionHeaderTitle>
                Define your context and upload source files. AutoDiscovery will use your data to
                generate hypotheses, run experiments to statistically refute or accept them and
                reveal surprising insights.
            </SectionHeader>

            <ConfigurationBox className={settings.parentRunId ? 'forked' : ''}>
                {settings.parentRunId && (
                    <ForkedFromBanner>
                        <InfoOutlinedIcon fontSize="small" />
                        <span>
                            Duplicated from{' '}
                            <ForkedFromLink
                                href={`/runs/${settings.parentRunId}`}
                                underline="hover">
                                {settings.parentRunName || settings.parentRunId}
                            </ForkedFromLink>
                            . Review the pre-populated fields below.
                        </span>
                    </ForkedFromBanner>
                )}

                <FormControl fullWidth>
                    <StyledFormLabel error={!!fieldErrors.name}>
                        Discovery session name
                    </StyledFormLabel>
                    <HelperText>Create a unique name to identify these results later.</HelperText>
                    <TextField
                        value={settings.name}
                        onChange={(e) => {
                            updateSettings('name', e.target.value);
                            debouncedSaveMetadata();
                        }}
                        placeholder="New Session 1"
                        disabled={isFormDisabled}
                        required
                        error={!!fieldErrors.name}
                    />
                </FormControl>

                <FormControl fullWidth>
                    <StyledFormLabel error={!!fieldErrors.datasetsDescription}>
                        Dataset context
                    </StyledFormLabel>
                    <HelperText>
                        Describe the origin and nature of the data. Explain how the data was
                        gathered (e.g., collection methods, known gaps). This background helps the
                        system generate more meaningful hypotheses.
                    </HelperText>
                    <TextField
                        multiline
                        rows={3}
                        value={settings.datasetsDescription}
                        onChange={(e) => {
                            updateSettings('datasetsDescription', e.target.value);
                            debouncedSaveMetadata();
                        }}
                        placeholder="e.g., Global migratory bird tracking logs (GPS, species, weather) from 2018–2024. Note: 2020 data is sparse for European routes due to regional sensor downtime."
                        disabled={isFormDisabled}
                        required
                        error={!!fieldErrors.datasetsDescription}
                    />
                </FormControl>

                <FormControl fullWidth>
                    <StyledFormLabel>
                        Domain of datasets <OptionalText>(Optional)</OptionalText>
                    </StyledFormLabel>
                    <HelperText>
                        Specify the research domain to help contextualize hypothesis generation.
                    </HelperText>
                    <TextField
                        value={settings.domain}
                        onChange={(e) => {
                            updateSettings('domain', e.target.value);
                            debouncedSaveMetadata();
                        }}
                        placeholder="e.g., Computer Science"
                        disabled={isFormDisabled}
                    />
                </FormControl>
                <FormControl fullWidth>
                    <StyledFormLabel error={!!datasetErrors}>Source files</StyledFormLabel>
                    <HelperText>
                        {hasAi1Permission
                            ? 'Select preloaded datasets and/or upload source files.'
                            : 'Upload source files for your discovery session.'}
                    </HelperText>

                    {hasAi1Permission && (
                        <>
                            <Box sx={{ display: 'flex', gap: 1, mb: 1, width: '100%' }}>
                                {PRELOADED_DATASETS.map((dataset) => (
                                    <PreloadedDatasetLabel
                                        key={dataset.id}
                                        selected={selectedDatasetIds.has(dataset.id)}>
                                        <Checkbox
                                            checked={selectedDatasetIds.has(dataset.id)}
                                            onChange={() => togglePreloadedDataset(dataset.id)}
                                            disabled={isFormDisabled}
                                            size="small"
                                            icon={<CheckBoxOutlineBlankIcon fontSize="small" />}
                                            checkedIcon={<CheckedIcon />}
                                            sx={{ p: 0 }}
                                        />
                                        {dataset.label}
                                    </PreloadedDatasetLabel>
                                ))}
                            </Box>

                            <Box
                                sx={{
                                    display: 'flex',
                                    flexDirection: 'column',
                                    gap: 1,
                                    mb: selectedDatasetIds.size > 0 ? 2 : 0,
                                }}>
                                {PRELOADED_DATASETS.map((dataset) => (
                                    <Collapse
                                        key={dataset.id}
                                        in={selectedDatasetIds.has(dataset.id)}
                                        unmountOnExit>
                                        <FileCard>
                                            <FileHeader>
                                                <DescriptionOutlinedIcon />
                                                <FileHeaderFilename>
                                                    {dataset.filename}
                                                </FileHeaderFilename>
                                                <FileHeaderFileMeta>
                                                    Preloaded dataset
                                                </FileHeaderFileMeta>
                                                <FileHeaderActions>
                                                    <IconButton
                                                        size="small"
                                                        onClick={() =>
                                                            togglePreloadedDataset(dataset.id)
                                                        }
                                                        disabled={isFormDisabled}
                                                        sx={{ ml: 'auto' }}
                                                        title="Remove dataset">
                                                        <CloseIcon fontSize="small" />
                                                    </IconButton>
                                                </FileHeaderActions>
                                            </FileHeader>
                                            <FileDescription>
                                                <DatasetSchemaTitle>
                                                    Dataset Schema (Optional)
                                                </DatasetSchemaTitle>
                                                Feel free to edit or add additional context to help
                                                guide the analysis.
                                                <TextField
                                                    multiline
                                                    maxRows={3}
                                                    fullWidth
                                                    defaultValue={dataset.description}
                                                    onChange={(e) =>
                                                        updatePreloadedDescription(
                                                            dataset.id,
                                                            e.target.value
                                                        )
                                                    }
                                                    disabled={isFormDisabled}
                                                    sx={{ mt: 1 }}
                                                />
                                            </FileDescription>
                                        </FileCard>
                                    </Collapse>
                                ))}
                            </Box>
                        </>
                    )}
                    <DatasetUpload
                        fileUploads={fileUploads}
                        maxFileSize={maxFileSize}
                        onFileSelect={handleFileSelect}
                        onRemoveFileUpload={handleRemoveFileUpload}
                        onDescriptionChange={handleFileDescriptionChange}
                        onCancelUpload={cancelUpload}
                        onRetryUpload={retryUpload}
                        disabled={isFormDisabled}
                        error={datasetErrors}
                    />
                </FormControl>
            </ConfigurationBox>

            <SectionHeader sx={{ mt: 3 }}>
                <SectionHeaderTitle>Session settings</SectionHeaderTitle>
                Define the scope and cost of your discovery session.
            </SectionHeader>
            <ConfigurationBox className={settings.parentRunId ? 'forked' : ''}>
                <FormControl>
                    <StyledFormLabel error={!!fieldErrors.nExperiments}>
                        Experiment budget
                    </StyledFormLabel>
                    <HelperText>
                        Set the maximum number of experiments to generate (
                        <strong>1 Credit = 1 Experiment</strong>) during the exploration. If this is
                        your first session, we recommend starting with a small budget ({'<'}10
                        experiments) to learn how the system works. Once you're familiar with the
                        output, you can confidently scale up to 50–100 experiments per session.
                    </HelperText>
                    <TextField
                        type="number"
                        value={settings.nExperiments}
                        onChange={(e) => handleExperimentsChange(e.target.value)}
                        disabled={isFormDisabled}
                        required
                        error={!!fieldErrors.nExperiments}
                        fullWidth
                    />
                    <RemainingCreditsChip
                        label={`Your credits after this run: ${creditsAvailable - settings.nExperiments}`}
                    />
                </FormControl>

                <StyledAccordian>
                    <AccordionSummary
                        expandIcon={<ExpandMoreIcon />}
                        aria-controls="panel1-content"
                        id="panel1-header"
                        {...mkExpandAdvancedSettingsTrackAttrs({ runId: runid })}>
                        <Typography component="span">Advanced settings</Typography>
                    </AccordionSummary>

                    <FormControl fullWidth>
                        <StyledFormLabel>
                            Intent <OptionalText>(Optional)</OptionalText>
                        </StyledFormLabel>
                        <HelperText>
                            Provide high-level guidance to loosely condition the exploration without
                            specifying exact hypotheses. The system will still autonomously navigate
                            the hypothesis space, but can consider your areas of interest during
                            generation.
                        </HelperText>
                        <TextField
                            value={settings.intent}
                            onChange={(e) => {
                                updateSettings('intent', e.target.value);
                                debouncedSaveMetadata();
                            }}
                            placeholder="e.g., Focus on how weather patterns impact migration timing and route efficiency"
                            disabled={isFormDisabled}
                        />
                    </FormControl>

                    <FormControl fullWidth>
                        <StyledFormLabel>Exploration weight</StyledFormLabel>
                        <HelperText>
                            Controls how the system balances exploring new hypothesis directions
                            versus diving deeper into promising ones. Higher values (e.g., 3-5)
                            encourage broader exploration of diverse hypotheses. Lower values (e.g.,
                            1-2) focus more on refining already-promising directions.
                        </HelperText>
                        <TextField
                            type="number"
                            value={settings.explorationWeight}
                            onChange={(e) => {
                                updateSettings('explorationWeight', parseFloat(e.target.value));
                                debouncedSaveMetadata();
                            }}
                            disabled={isFormDisabled}
                        />
                    </FormControl>

                    <FormControl fullWidth>
                        <StyledFormLabel>Search strategy</StyledFormLabel>
                        <HelperText>
                            Determines how the system navigates through nested hypotheses during
                            exploration. UCB1 Recursive (default) efficiently balances breadth and
                            depth. MCTS with Progressive Widening gradually expands the search space
                            as more experiments run.
                        </HelperText>
                        <Select
                            value={settings.mctsSelection}
                            onChange={(e) => {
                                updateSettings('mctsSelection', e.target.value);
                                debouncedSaveMetadata();
                            }}>
                            {Object.values(MCTS_SELECTION).map((option) => (
                                <MenuItem key={option.value} value={option.value}>
                                    {option.label}
                                </MenuItem>
                            ))}
                        </Select>
                    </FormControl>

                    <FormControl fullWidth>
                        <Box
                            sx={{
                                display: 'flex',
                                justifyContent: 'space-between',
                                alignItems: 'center',
                            }}>
                            <StyledFormLabel>Surprise threshold</StyledFormLabel>
                        </Box>
                        <HelperText>
                            Sets the minimum belief shift required for a discovery to count as
                            "surprising." Higher values (e.g., 0.3-0.5) only flag dramatic findings,
                            while lower values (e.g., 0.05-0.1) capture more subtle discoveries.
                            This affects which hypotheses the system considers worth pursuing.
                        </HelperText>
                        <SurpriseSlider
                            value={settings.surprisalWidth ?? 0}
                            onChange={(_, value) => {
                                updateSettings('surprisalWidth', value as number);
                                debouncedSaveMetadata();
                            }}
                            min={0}
                            max={1}
                            step={0.01}
                            disabled={isFormDisabled}
                            valueLabelDisplay="on"
                        />
                    </FormControl>

                    <FormControl fullWidth>
                        <StyledFormLabel>Evidence weight</StyledFormLabel>
                        <HelperText>
                            Controls how much the system trusts experimental results when updating
                            its beliefs. Higher values (e.g., 2-5) mean the system relies heavily on
                            observed data. Lower values (e.g., 0.5-1) mean it updates its beliefs
                            more cautiously, giving more weight to its initial assumptions.
                        </HelperText>
                        <TextField
                            type="number"
                            value={settings.evidenceWeight}
                            onChange={(e) => {
                                updateSettings('evidenceWeight', parseFloat(e.target.value));
                                debouncedSaveMetadata();
                            }}
                            disabled={isFormDisabled}
                        />
                    </FormControl>
                </StyledAccordian>
            </ConfigurationBox>

            <SubmitButton
                variant="contained"
                size="large"
                startIcon={
                    isSubmitting ? (
                        <CircularProgress size={16} />
                    ) : (
                        <PlayCircleFilledWhiteOutlinedIcon />
                    )
                }
                onClick={handleSubmit}
                disabled={isFormDisabled || Object.keys(fieldErrors).length > 0}
                {...mkSubmitRunBtnTrackAttrs({ runId: runid })}>
                {isSubmitting ? 'Starting...' : 'Start Run'}
            </SubmitButton>

            {/* Save indicator */}
            <Fade in={isSaving} timeout={{ enter: 300, exit: 500 }}>
                <SaveIndicator>
                    <CircularProgress size={20} sx={{ mr: 1 }} />
                    <Typography variant="body2">Saving...</Typography>
                </SaveIndicator>
            </Fade>
        </Box>
    );
}

const SectionHeader = styled(Box)(({ theme }) => ({
    color: theme.color['cream-100'].hex,
    margin: theme.spacing(1, 0),
}));

const ForkedFromBanner = styled(Box)(({ theme }) => ({
    alignItems: 'flex-start',
    backgroundColor: theme.color['cream-10'].rgba.toString(),
    borderRadius: '4px',
    color: theme.color['cream-100'].hex,
    display: 'flex',
    fontSize: '0.875rem',
    gap: theme.spacing(1),
    lineHeight: 1.5,
    padding: theme.spacing(2, 2.5),

    '& .MuiSvgIcon-root': {
        color: theme.color['green-40'].rgba.toString(),
        flexShrink: 0,
        marginTop: '1px',
    },
}));

const ForkedFromLink = styled(Link)(({ theme }) => ({
    color: theme.color['green-40'].rgba.toString(),
    fontWeight: 600,
}));

const SectionHeaderTitle = styled(Typography)(({ theme }) => ({
    color: theme.color['green-100'].hex,
    fontSize: '1.25rem',
    fontWeight: 700,
}));

const ConfigurationBox = styled(Box)(({ theme }) => ({
    backgroundColor: theme.color['cream-4'].rgba.toString(),
    borderRadius: '12px',
    display: 'flex',
    flexDirection: 'column',
    gap: theme.spacing(3),
    padding: theme.spacing(3),

    '.MuiInputBase-input': {
        border: '1px solid ' + theme.color['cream-20'].rgba.toString(),
        borderRadius: theme.shape.borderRadius + 'px',
        color: theme.color['cream-100'].hex,
        padding: theme.spacing(2.25),

        '&:hover, &:focus': {
            border: '1px solid ' + theme.color['green-100'].hex,
            transition: 'all 250ms ease-in-out',
        },
    },

    '&.forked .MuiInputBase-input:not(:placeholder-shown), &.forked .MuiSelect-select': {
        borderColor: theme.color['cream-80'].rgba.toString(),
    },

    '&.forked .MuiInputBase-input:hover, &.forked .MuiInputBase-input:focus, &.forked .MuiSelect-select:hover, &.forked .MuiInputBase-root:has(.MuiSelect-select):focus-within .MuiSelect-select':
        {
            borderColor: theme.color['green-100'].hex,
        },

    '.MuiInputBase-root.Mui-error .MuiInputBase-input': {
        border: '1px solid ' + theme.color['error-red-60'].hex,

        '&::placeholder': {
            color: theme.color['error-red-60'].hex,
            opacity: 1,
        },

        '&:hover, &:focus': {
            border: '1px solid ' + theme.color['error-red-60'].hex,
        },
    },

    '.MuiInputBase-input.Mui-disabled': {
        backgroundColor: theme.color['cream-10'].rgba.toString(),
        color: theme.color['cream-60'].rgba.toString(),
        WebkitTextFillColor: theme.color['cream-60'].rgba.toString(),

        '&:hover': {
            border: '1px solid ' + theme.color['cream-20'].rgba.toString(),
        },
    },

    '.MuiOutlinedInput-notchedOutline': {
        border: 'none',
    },

    '.MuiInputBase-multiline': {
        padding: 0,
    },
}));

const StyledFormLabel = styled(FormLabel)(({ theme }) => ({
    color: theme.color['green-40'].hex,
    fontWeight: 700,
    '&.Mui-focused': {
        color: theme.color['green-40'].hex,
    },
    '&.Mui-error': {
        color: theme.color['error-red-100'].hex,
    },
}));

const HelperText = styled(FormHelperText)(({ theme }) => ({
    color: theme.color['cream-80'].rgba.toString(),
    margin: theme.spacing(0.5, 0, 1, 0),
}));

const OptionalText = styled('span')({
    fontWeight: 400,
});

const PreloadedDatasetLabel = styled('label')<{ selected: boolean }>(({ theme, selected }) => ({
    flex: 1,
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'flex-start',
    gap: theme.spacing(1),
    padding: theme.spacing(1),
    borderRadius: theme.shape.borderRadius + 'px',
    border: '1px solid ' + (selected ? 'transparent' : theme.color['cream-20'].rgba.toString()),
    backgroundColor: selected ? theme.color['teal-100'].hex : 'transparent',
    color: selected ? '#fff' : theme.color['cream-100'].hex,
    fontWeight: 600,
    fontSize: '0.875rem',
    cursor: 'pointer',
    transition: 'all 200ms ease-in-out',
    userSelect: 'none',

    '&:hover': {
        borderColor: theme.color['green-100'].hex,
    },

    '& .MuiCheckbox-root': {
        color: selected ? '#fff' : theme.color['cream-20'].rgba.toString(),
    },
}));

const StyledCheckedIcon = styled('svg')(({ theme }) => ({
    '& .check-bg': {
        fill: theme.color['green-100'].hex,
    },
    '& .check-mark': {
        fill: theme.color['dark-teal-100'].hex,
    },
}));

function CheckedIcon() {
    return (
        <StyledCheckedIcon
            width="20"
            height="20"
            viewBox="0 0 24 24"
            xmlns="http://www.w3.org/2000/svg">
            <rect className="check-bg" x="2" y="2" width="20" height="20" rx="3" />
            <path
                className="check-mark"
                d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41L9 16.17z"
            />
        </StyledCheckedIcon>
    );
}

const SubmitButton = styled(Button)(({ theme }) => ({
    '&.MuiButton-root': {
        backgroundColor: theme.color['green-100'].hex,
        color: theme.color['teal-100'].hex,
        marginTop: theme.spacing(3),

        '&.Mui-disabled': {
            backgroundColor: theme.color['gray-60'].rgba.toString(),
        },
    },
}));

const StyledAccordian = styled(Accordion)(({ theme }) => ({
    backgroundColor: 'transparent',
    color: theme.color['green-100'].hex,

    '&:before': {
        content: 'none',
    },

    '.MuiAccordionSummary-root': {
        justifyContent: 'flex-start',
        padding: 0,
    },

    '.MuiAccordionSummary-content, .MuiAccordionSummary-content.Mui-expanded': {
        flexGrow: 0,
        marginRight: theme.spacing(0.75),
    },

    '.MuiAccordionSummary-expandIconWrapper': {
        backgroundColor: theme.color['cream-10'].rgba.toString(),
        color: theme.color['green-100'].rgba.toString(),
    },

    '.MuiAccordion-region': {
        display: 'flex',
        flexDirection: 'column',
        gap: theme.spacing(3),
    },
}));

const RemainingCreditsChip = styled(Chip)(({ theme }) => ({
    alignSelf: 'flex-start',
    backgroundColor: theme.color['cream-10'].rgba.toString(),
    borderRadius: theme.shape.borderRadius + 'px',
    color: theme.color['cream-100'].hex,
    marginTop: theme.spacing(1),
}));

const SurpriseSlider = styled(Slider)(({ theme }) => ({
    '& .MuiSlider-valueLabel': {
        fontSize: '0.875rem',
        top: 45,
        backgroundColor: 'unset',
        color: theme.palette.text.primary,
        '&::before': {
            display: 'none',
        },
        '& *': {
            background: 'transparent',
            color: theme.color['cream-100'].hex,
        },
    },
}));

const SaveIndicator = styled(Box)(({ theme }) => ({
    position: 'fixed',
    bottom: theme.spacing(3),
    right: theme.spacing(3),
    display: 'flex',
    alignItems: 'center',
    backgroundColor: theme.color['cream-10'].rgba.toString(),
    color: theme.color['cream-100'].hex,
    padding: theme.spacing(1.5, 2.5),
    borderRadius: theme.shape.borderRadius * 2,
    boxShadow: `0 4px 12px rgba(0, 0, 0, 0.15)`,
    zIndex: 1000,

    '.MuiCircularProgress-root': {
        color: theme.color['green-100'].hex,
    },
}));
