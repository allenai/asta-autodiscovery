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
        settings,
        creditsRemaining,
        datasets,
        selectedFiles,
        uploading,
        uploadError,
        fieldErrors,
        submitting,
        formError,
        updateSettings,
        handleFileSelect,
        handleFileDescriptionChange,
        handleRemoveDataset,
        handleRemoveSelectedFile,
        handleExperimentsChange,
        handleSubmit,
    } = useRunSetup({ runid, onSubmitSuccess });

    const datasetErrors =
        uploadError || fieldErrors.datasets || fieldErrors.datasetFileDescriptions;

    return (
        <Box sx={{ maxWidth: 'md', mx: 'auto', p: 3 }}>
            <SectionHeader>
                <SectionHeaderTitle>Configure a new discovery session</SectionHeaderTitle>
                Provide datasets and describe your discovery context. The system will autonomously
                explore these datasets to find surprising patterns and hypotheses based on Bayesian
                surprise.
            </SectionHeader>

            <ConfigurationBox>
                <FormControl fullWidth>
                    <StyledFormLabel>Discovery session name</StyledFormLabel>
                    <HelperText>
                        A name to help you identify this session later. This doesn't affect the
                        results.
                    </HelperText>
                    <TextField
                        value={settings.name}
                        onChange={(e) => updateSettings('name', e.target.value)}
                        placeholder="Name"
                        disabled={uploading || submitting}
                        required
                        error={!!fieldErrors.name}
                        helperText={fieldErrors.name}
                    />
                </FormControl>

                <FormControl fullWidth>
                    <StyledFormLabel>Description of datasets</StyledFormLabel>
                    <HelperText>
                        Describe what your datasets contain. This context helps the system generate
                        more meaningful hypotheses.
                    </HelperText>
                    <TextField
                        multiline
                        rows={3}
                        value={settings.datasetsDescription}
                        onChange={(e) => updateSettings('datasetsDescription', e.target.value)}
                        placeholder="e.g., Customer purchase history with demographics, product categories, and timestamp data from 2020-2023"
                        disabled={uploading || submitting}
                        required
                        error={!!fieldErrors.datasetsDescription}
                        helperText={fieldErrors.datasetsDescription}
                    />
                </FormControl>

                <FormControl fullWidth>
                    <StyledFormLabel>Domain of datasets (Optional)</StyledFormLabel>
                    <HelperText>
                        Specify the research domain to help contextualize hypothesis generation.
                    </HelperText>
                    <TextField
                        value={settings.domain}
                        onChange={(e) => updateSettings('domain', e.target.value)}
                        placeholder="e.g., Computer Science"
                        disabled={uploading || submitting}
                        required
                    />
                </FormControl>

                <FormControl fullWidth>
                    <StyledFormLabel>Dataset Files</StyledFormLabel>
                    <DatasetUpload
                        datasets={datasets}
                        selectedFiles={selectedFiles}
                        onFileSelect={handleFileSelect}
                        onRemove={handleRemoveDataset}
                        onRemoveSelectedFile={handleRemoveSelectedFile}
                        onDescriptionChange={handleFileDescriptionChange}
                        disabled={uploading || submitting}
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
                How AutoDiscovery explores the hypothesis space. If this is your first session, we
                suggest starting with a smaller experiment budget to learn how the system works.
            </SectionHeader>
            <ConfigurationBox>
                <FormControl>
                    <StyledFormLabel>Experiment Budget</StyledFormLabel>
                    <HelperText>
                        Maximum number of experiments to execute during this run. Each experiment
                        costs 1 experiment credit.
                    </HelperText>
                    <TextField
                        type="number"
                        value={settings.nExperiments}
                        onChange={(e) => handleExperimentsChange(e.target.value)}
                        disabled={submitting}
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
                        <StyledFormLabel>Intent</StyledFormLabel>
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
                            disabled={uploading || submitting}
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
                            value={settings.explorationWeight}
                            onChange={(e) =>
                                updateSettings('explorationWeight', parseFloat(e.target.value))
                            }
                            disabled={uploading || submitting}
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
                            onChange={(e) => updateSettings('mctsSelection', e.target.value)}>
                            {Object.values(MCTS_SELECTION).map((option) => (
                                <MenuItem key={option.value} value={option.value}>
                                    {option.label}
                                </MenuItem>
                            ))}
                        </Select>
                    </FormControl>

                    <FormControl fullWidth>
                        <StyledFormLabel>Surprise threshold</StyledFormLabel>
                        <HelperText>
                            Sets the minimum belief shift required for a discovery to count as
                            "surprising." Higher values (e.g., 0.3-0.5) only flag dramatic findings,
                            while lower values (e.g., 0.05-0.1) capture more subtle discoveries.
                            This affects which hypotheses the system considers worth pursuing.
                        </HelperText>
                        <TextField
                            value={settings.surprisalWidth}
                            onChange={(e) =>
                                updateSettings('surprisalWidth', parseFloat(e.target.value))
                            }
                            disabled={uploading || submitting}
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
                            value={settings.evidenceWeight}
                            onChange={(e) =>
                                updateSettings('evidenceWeight', parseFloat(e.target.value))
                            }
                            disabled={uploading || submitting}
                        />
                    </FormControl>

                    <FormControl fullWidth>
                        <StyledFormLabel>Warmstart Experiments</StyledFormLabel>
                        <HelperText>
                            Initial experiments to run before autonomous exploration begins. These
                            "seed" the system with baseline findings that inform subsequent
                            hypothesis generation. Useful for testing known relationships or
                            establishing a starting point for discovery.
                        </HelperText>
                        <TextField
                            value={settings.warmstartExperiments}
                            onChange={(e) => updateSettings('warmstartExperiments', e.target.value)}
                            disabled={uploading || submitting}
                            placeholder="Path to json file"
                        />
                    </FormControl>

                    <FormControl fullWidth>
                        <StyledFormLabel>Number of warmstarts</StyledFormLabel>
                        <HelperText>
                            How many initial experiments to run before autonomous exploration
                            begins. These provide the system with baseline findings to inform its
                            hypothesis generation.
                        </HelperText>
                        <TextField
                            type="number"
                            value={settings.nWarmstart}
                            onChange={(e) => updateSettings('nWarmstart', parseInt(e.target.value))}
                            disabled={uploading || submitting}
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
                    submitting ? (
                        <CircularProgress size={16} />
                    ) : (
                        <PlayCircleFilledWhiteOutlinedIcon />
                    )
                }
                onClick={handleSubmit}
                disabled={submitting || uploading || Object.keys(fieldErrors).length > 0}>
                {submitting ? 'Starting...' : 'Start Run'}
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
        borderRadius: theme.shape.borderRadius,
        color: theme.color['cream-100'].hex,
        padding: theme.spacing(2.25),

        '&:hover, &:focus': {
            border: '1px solid ' + theme.color['green-100'].hex,
            transition: 'all 250ms ease-in-out',
        },

        '&.Mui-disabled': {
            backgroundColor: theme.color['cream-10'].rgba.toString(),
            color: theme.color['cream-60'].rgba.toString(),
            '-webkit-text-fill-color': theme.color['cream-60'].rgba.toString(),

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
}));

const HelperText = styled(FormHelperText)(({ theme }) => ({
    color: theme.color['cream-80'].rgba.toString(),
    margin: theme.spacing(0.5, 0, 1, 0),
}));

const SubmitButton = styled(Button)(({ theme }) => ({
    '&.MuiButton-root': {
        backgroundColor: theme.color['green-100'].hex,
        color: theme.color['teal-100'].hex,
        marginTop: theme.spacing(3),
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
    borderRadius: theme.shape.borderRadius,
    color: theme.color['cream-100'].hex,
    marginTop: theme.spacing(1),
}));
