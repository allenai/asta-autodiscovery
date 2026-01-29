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
    Alert,
    FormHelperText,
    styled,
    Chip,
    FormLabel,
    Accordion,
    AccordionSummary,
    Slider,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import PlayCircleFilledWhiteOutlinedIcon from '@mui/icons-material/PlayCircleFilledWhiteOutlined';

import { MCTS_SELECTION, useRunSetup } from '@/runs/hooks/useRunSetup';
import DatasetUpload from '@/runs/components/DatasetUpload';

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
        saveMetadata,
        saveJobArgs,
        settings,
        creditsRemaining,
        fileUploads,
        fieldErrors,
        isSubmitting,
        formError,
        isLoading,
        updateSettings,
        handleFileSelect,
        handleFileDescriptionChange,
        handleFileDescriptionBlur,
        handleRemoveFileUpload,
        handleExperimentsChange,
        handleSubmit,
        cancelUpload,
        retryUpload,
    } = useRunSetup({ runid, onSubmitSuccess });

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
                Define your context and upload source files. AutoDiscovery will use your data
                appropriately to generate hypotheses, run experiments to statistically refute or
                accept them and reveal surprising insights.
            </SectionHeader>

            <ConfigurationBox>
                <FormControl fullWidth>
                    <StyledFormLabel>Discovery session name</StyledFormLabel>
                    <HelperText>Create a unique name to identify these results later.</HelperText>
                    <TextField
                        value={settings.name}
                        onChange={(e) => updateSettings('name', e.target.value)}
                        placeholder="New Session 1"
                        disabled={isFormDisabled}
                        required
                        error={!!fieldErrors.name}
                        helperText={fieldErrors.name}
                        onBlur={saveMetadata}
                    />
                </FormControl>

                <FormControl fullWidth>
                    <StyledFormLabel>Dataset context</StyledFormLabel>
                    <HelperText>
                        Describe the origin and nature of the data. Explain how the data was
                        gathered (e.g., collection methods, known gaps). This background helps the
                        system generate more meaningful hypotheses.
                    </HelperText>
                    <TextField
                        multiline
                        rows={3}
                        value={settings.datasetsDescription}
                        onChange={(e) => updateSettings('datasetsDescription', e.target.value)}
                        placeholder="e.g., Customer purchase history with demographics, product categories, and timestamp data from 2020-2023"
                        disabled={isFormDisabled}
                        onBlur={saveMetadata}
                        required
                        error={!!fieldErrors.datasetsDescription}
                        helperText={fieldErrors.datasetsDescription}
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
                        onChange={(e) => updateSettings('domain', e.target.value)}
                        placeholder="e.g., Computer Science"
                        disabled={isFormDisabled}
                        onBlur={saveMetadata}
                    />
                </FormControl>

                <FormControl fullWidth>
                    <StyledFormLabel>Upload source files</StyledFormLabel>
                    <DatasetUpload
                        fileUploads={fileUploads}
                        onFileSelect={handleFileSelect}
                        onRemoveFileUpload={handleRemoveFileUpload}
                        onDescriptionChange={handleFileDescriptionChange}
                        onDescriptionBlur={handleFileDescriptionBlur}
                        onCancelUpload={cancelUpload}
                        onRetryUpload={retryUpload}
                        disabled={isFormDisabled}
                        error={datasetErrors}
                    />

                    {datasetErrors && (
                        <Alert severity="error" sx={{ mt: 2 }}>
                            {datasetErrors}
                        </Alert>
                    )}
                </FormControl>
            </ConfigurationBox>

            <SectionHeader sx={{ mt: 3 }}>
                <SectionHeaderTitle>Session settings</SectionHeaderTitle>
                Define the scope and cost of your discovery session.
            </SectionHeader>
            <ConfigurationBox>
                <FormControl>
                    <StyledFormLabel>Experiment Budget</StyledFormLabel>
                    <HelperText>
                        Set the maximum number of experiments to generate (
                        <strong>1 Credit = 1 Experiment</strong>) during the exploration. If this is
                        your first session, we recommend starting with a smaller budget (50–100
                        experiments) to learn how the system works.
                    </HelperText>
                    <TextField
                        type="number"
                        value={settings.nExperiments}
                        onChange={(e) => handleExperimentsChange(e.target.value)}
                        disabled={isFormDisabled}
                        required
                        error={!!fieldErrors.nExperiments}
                        helperText={fieldErrors.nExperiments}
                        fullWidth
                    />
                    <RemainingCreditsChip
                        label={`Your credits after this run: ${creditsRemaining - settings.nExperiments}`}
                    />
                </FormControl>

                <StyledAccordian>
                    <AccordionSummary
                        expandIcon={<ExpandMoreIcon />}
                        aria-controls="panel1-content"
                        id="panel1-header">
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
                            onChange={(e) => updateSettings('intent', e.target.value)}
                            placeholder="e.g., Focus on relationships between demographic factors and outcomes"
                            disabled={isFormDisabled}
                            onBlur={saveMetadata}
                        />
                    </FormControl>

                    <FormControl fullWidth>
                        <StyledFormLabel>Exploration Weight</StyledFormLabel>
                        <HelperText>
                            Controls how the system balances exploring new hypothesis directions
                            versus diving deeper into promising ones. Higher values (e.g., 3-5)
                            encourage broader exploration of diverse hypotheses. Lower values (e.g.,
                            1-2) focus more on refining already-promising directions.
                        </HelperText>
                        <TextField
                            type="number"
                            value={settings.explorationWeight}
                            onChange={(e) =>
                                updateSettings('explorationWeight', parseFloat(e.target.value))
                            }
                            disabled={isFormDisabled}
                            onBlur={() => saveJobArgs()}
                        />
                    </FormControl>

                    <FormControl fullWidth>
                        <StyledFormLabel>Search strategy</StyledFormLabel>
                        <HelperText>
                            Determines how the system navigates through nested hypotheses during
                            exploration. UCB1_recursive (default) efficiently balances breadth and
                            depth. Beam search focuses on top candidates at each level. Progressive
                            widening gradually expands the search space as more experiments run.
                        </HelperText>
                        <Select
                            value={settings.mctsSelection}
                            onChange={(e) => updateSettings('mctsSelection', e.target.value)}
                            onClose={() => saveJobArgs()}>
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
                            onChange={(_, value) =>
                                updateSettings('surprisalWidth', value as number)
                            }
                            onChangeCommitted={() => saveJobArgs()}
                            min={0}
                            max={1}
                            step={0.01}
                            disabled={isFormDisabled}
                            valueLabelDisplay="on"
                        />
                    </FormControl>

                    <FormControl fullWidth>
                        <StyledFormLabel>Evidence Weight</StyledFormLabel>
                        <HelperText>
                            Controls how much the system trusts experimental results when updating
                            its beliefs. Higher values (e.g., 0.8-1.0) mean the system relies
                            heavily on observed data. Lower values (e.g., 0.3-0.5) mean it updates
                            its beliefs more cautiously, giving more weight to its initial
                            assumptions.
                        </HelperText>
                        <TextField
                            type="number"
                            value={settings.evidenceWeight}
                            onChange={(e) =>
                                updateSettings('evidenceWeight', parseFloat(e.target.value))
                            }
                            disabled={isFormDisabled}
                            onBlur={() => saveJobArgs()}
                        />
                    </FormControl>

                    <FormControl fullWidth>
                        <StyledFormLabel>
                            Warmstart Experiments <OptionalText>(Optional)</OptionalText>
                        </StyledFormLabel>
                        <HelperText>
                            Initial experiments to run before autonomous exploration begins. These
                            "seed" the system with baseline findings that inform subsequent
                            hypothesis generation. Useful for testing known relationships or
                            establishing a starting point for discovery.
                        </HelperText>
                        <TextField
                            value={settings.warmstartExperiments}
                            onChange={(e) => updateSettings('warmstartExperiments', e.target.value)}
                            disabled={isFormDisabled}
                            placeholder="Path to json file"
                            onBlur={() => saveJobArgs()}
                        />
                    </FormControl>

                    <FormControl fullWidth>
                        <StyledFormLabel>
                            Number of warmstarts <OptionalText>(Optional)</OptionalText>
                        </StyledFormLabel>
                        <HelperText>
                            How many initial experiments to run before autonomous exploration
                            begins. These provide the system with baseline findings to inform its
                            hypothesis generation.
                        </HelperText>
                        <TextField
                            type="number"
                            value={settings.nWarmstart}
                            onChange={(e) => updateSettings('nWarmstart', parseInt(e.target.value))}
                            disabled={isFormDisabled}
                            onBlur={() => saveJobArgs()}
                        />
                    </FormControl>
                </StyledAccordian>
            </ConfigurationBox>

            {formError && (
                <Alert severity="error" sx={{ mt: 2 }}>
                    {formError}
                </Alert>
            )}

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
                disabled={isFormDisabled || Object.keys(fieldErrors).length > 0}>
                {isSubmitting ? 'Starting...' : 'Start Run'}
            </SubmitButton>
        </Box>
    );
}

const SectionHeader = styled(Box)(({ theme }) => ({
    color: theme.color['cream-100'].hex,
    margin: theme.spacing(1, 0),
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

        '&.Mui-disabled': {
            backgroundColor: theme.color['cream-10'].rgba.toString(),
            color: theme.color['cream-60'].rgba.toString(),
            WebkitTextFillColor: theme.color['cream-60'].rgba.toString(),

            '&:hover': {
                border: '1px solid ' + theme.color['cream-20'].rgba.toString(),
            },
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
}));

const HelperText = styled(FormHelperText)(({ theme }) => ({
    color: theme.color['cream-80'].rgba.toString(),
    margin: theme.spacing(0.5, 0, 1, 0),
}));

const OptionalText = styled('span')({
    fontWeight: 400,
});

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
