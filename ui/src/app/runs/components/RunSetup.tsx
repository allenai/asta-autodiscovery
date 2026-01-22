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
    Switch,
    Chip,
    FormLabel,
    Accordion,
    AccordionSummary,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import PlayCircleFilledWhiteOutlinedIcon from '@mui/icons-material/PlayCircleFilledWhiteOutlined';

import { BELIEF_MODES, MCTS_SELECTION, useRunSetup } from '@/runs/hooks/useRunSetup';
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
        creditsRemaining,
        datasets,
        selectedFiles,
        uploading,
        uploadError,
        metadata,
        experimentsError,
        fieldErrors,
        submitting,
        error,
        updateMetadata,
        handleFileSelect,
        handleFileDescriptionChange,
        handleRemoveDataset,
        handleRemoveSelectedFile,
        handleExperimentsChange,
        handleSubmit,
    } = useRunSetup({ runid, onSubmitSuccess });

    return (
        <Box sx={{ maxWidth: 'md', mx: 'auto', p: 3 }}>
            <SectionHeader>
                <SectionHeaderTitle>Configure a new run</SectionHeaderTitle>
                Provide datasets and describe your discovery context. The system will autonomously
                explore these datasets to find surprising patterns and hypotheses based on Bayesian
                surprise.
            </SectionHeader>

            <ConfigurationBox>
                <FormControl fullWidth>
                    <StyledFormLabel>Run Name</StyledFormLabel>
                    <HelperText>
                        A name to help you identify this run later. This doesn't affect the
                        exploration results.
                    </HelperText>
                    <TextField
                        value={metadata.name}
                        onChange={(e) => updateMetadata('name', e.target.value)}
                        placeholder="Name"
                        disabled={uploading || submitting}
                        required
                        error={!!fieldErrors.name}
                        helperText={fieldErrors.name}
                    />
                </FormControl>

                <FormControl fullWidth>
                    <StyledFormLabel>Intent</StyledFormLabel>
                    <HelperText>
                        Provide high-level guidance to loosely condition the exploration without
                        specifying exact hypotheses. The system will still autonomously navigate the
                        hypothesis space, but can consider your areas of interest during generation.
                    </HelperText>
                    <TextField
                        multiline
                        rows={3}
                        value={metadata.intent}
                        onChange={(e) => updateMetadata('intent', e.target.value)}
                        placeholder="e.g., Focus on relationships between demographic factors and outcomes"
                        disabled={uploading || submitting}
                        required
                        error={!!fieldErrors.intent}
                        helperText={fieldErrors.intent}
                    />
                </FormControl>

                <FormControl fullWidth>
                    <StyledFormLabel>Domain (Optional)</StyledFormLabel>
                    <HelperText>
                        Specify the research domain to help contextualize hypothesis generation.
                        This guides the system's understanding of your data.
                    </HelperText>
                    <TextField
                        value={metadata.domain}
                        onChange={(e) => updateMetadata('domain', e.target.value)}
                        placeholder="Example: Computer Science"
                        disabled={uploading || submitting}
                        required
                    />
                </FormControl>

                <FormControl fullWidth>
                    <StyledFormLabel>Description of datasets</StyledFormLabel>
                    <HelperText>
                        Describe what your datasets contain. This context helps the system generate
                        more meaningful hypotheses.
                    </HelperText>
                    <TextField
                        value={metadata.datasetDescription}
                        onChange={(e) => updateMetadata('datasetDescription', e.target.value)}
                        placeholder="e.g., Customer purchase history with demographics, product categories, and timestamp data from 2020-2023

"
                        disabled={uploading || submitting}
                        required
                        error={!!fieldErrors.datasetDescription}
                        helperText={fieldErrors.datasetDescription}
                    />
                </FormControl>

                <FormControl fullWidth>
                    <StyledFormLabel>Datasets</StyledFormLabel>
                    <DatasetUpload
                        datasets={datasets.map((ds) => ({
                            filename: ds.filename,
                            description: ds.description,
                            path: ds.path,
                        }))}
                        selectedFiles={selectedFiles}
                        onFileSelect={handleFileSelect}
                        onRemove={handleRemoveDataset}
                        onRemoveSelectedFile={handleRemoveSelectedFile}
                        onDescriptionChange={handleFileDescriptionChange}
                        disabled={uploading || submitting}
                        error={fieldErrors.datasets}
                    />

                    {uploadError && (
                        <Alert severity="error" sx={{ mt: 2 }}>
                            {uploadError}
                        </Alert>
                    )}
                    {fieldErrors.datasets && (
                        <Alert severity="error" sx={{ mt: 2 }}>
                            {fieldErrors.datasets}
                        </Alert>
                    )}
                </FormControl>
            </ConfigurationBox>

            <SectionHeader sx={{ mt: 3 }}>
                <SectionHeaderTitle>Run Settings</SectionHeaderTitle>
                Configure how AutoDiscovery explores the hypothesis space. If this is your first
                run, we suggest starting with a smaller test run to learn how the system works.
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
                        value={metadata.nExperiments}
                        onChange={(e) => handleExperimentsChange(e.target.value)}
                        inputProps={{
                            min: 1,
                            max: creditsRemaining,
                            step: 1,
                        }}
                        disabled={submitting}
                        required
                        error={!!experimentsError}
                        helperText={experimentsError}
                        fullWidth
                    />
                    <RemainingCreditsChip
                        label={`Your credits after this run: ${creditsRemaining - metadata.nExperiments}`}
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
                        <StyledFormLabel>Exploration Weight</StyledFormLabel>
                        <HelperText>Exploration weight for UCB1 selection method</HelperText>
                        <TextField
                            value={metadata.explorationWeight}
                            onChange={(e) =>
                                updateMetadata('explorationWeight', parseFloat(e.target.value))
                            }
                            disabled={uploading || submitting}
                        />
                    </FormControl>

                    <FormControl fullWidth>
                        <StyledFormLabel>Use Beam Search</StyledFormLabel>
                        <HelperText>Use beam search selection method</HelperText>
                        <Switch
                            checked={metadata.useBeamSearch}
                            onChange={(e) => updateMetadata('useBeamSearch', e.target.checked)}
                            disabled={uploading || submitting}
                        />
                    </FormControl>

                    <FormControl fullWidth>
                        <StyledFormLabel>MCTS Selection</StyledFormLabel>
                        <HelperText>
                            Selection method to use in MCTS (UCB1 beam search progressive widening
                            progressive widening with all nodes)
                        </HelperText>
                        <Select
                            value={metadata.mctsSelection}
                            onChange={(e) => updateMetadata('mctsSelection', e.target.value)}>
                            {Object.values(MCTS_SELECTION).map((option) => (
                                <MenuItem key={option.value} value={option.value}>
                                    {option.label}
                                </MenuItem>
                            ))}
                        </Select>
                    </FormControl>

                    <FormControl fullWidth>
                        <StyledFormLabel>Surprisal Width</StyledFormLabel>
                        <HelperText>
                            Minimum difference in mean prior and posterior probabilities required to
                            count as a surprisal.
                        </HelperText>
                        <TextField
                            value={metadata.surprisalWidth}
                            onChange={(e) =>
                                updateMetadata('surprisalWidth', parseFloat(e.target.value))
                            }
                            disabled={uploading || submitting}
                        />
                    </FormControl>

                    <FormControl fullWidth>
                        <StyledFormLabel>Belief Mode</StyledFormLabel>
                        <HelperText>
                            Minimum difference in mean prior and posterior probabilities required to
                            count as a surprisal.
                        </HelperText>
                        <Select
                            value={metadata.beliefMode}
                            onChange={(e) => updateMetadata('beliefMode', e.target.value)}>
                            {Object.values(BELIEF_MODES).map((option) => (
                                <MenuItem key={option.value} value={option.value}>
                                    {option.label}
                                </MenuItem>
                            ))}
                        </Select>
                    </FormControl>

                    <FormControl fullWidth>
                        <StyledFormLabel>Evidence Weight</StyledFormLabel>
                        <HelperText>
                            Weight for the experimental evidence when computing posterior beliefs
                        </HelperText>
                        <TextField
                            value={metadata.evidenceWeight}
                            onChange={(e) =>
                                updateMetadata('evidenceWeight', parseFloat(e.target.value))
                            }
                            disabled={uploading || submitting}
                        />
                    </FormControl>

                    <FormControl fullWidth>
                        <StyledFormLabel>Warmstart Experiments</StyledFormLabel>
                        <HelperText>A list of warmstart experiments to run before MCTS</HelperText>
                        <TextField
                            value={metadata.warmstartExperiments}
                            onChange={(e) => updateMetadata('warmstartExperiments', e.target.value)}
                            disabled={uploading || submitting}
                        />
                    </FormControl>
                </StyledAccordian>
            </ConfigurationBox>

            {error && (
                <Alert severity="error" sx={{ mt: 2 }}>
                    {error}
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
                disabled={
                    submitting ||
                    uploading ||
                    selectedFiles.length === 0 ||
                    !!experimentsError ||
                    metadata.nExperiments < 1
                }>
                {submitting ? 'Starting...' : 'Start Run'}
            </SubmitButton>
            <TimeEstimate>Estimated time: 60 min</TimeEstimate>
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

    '.MuiAccordionSummary-content, .Mui-expanded': {
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

const TimeEstimate = styled(Typography)(({ theme }) => ({
    color: theme.color['cream-100'].hex,
    marginTop: theme.spacing(1),
}));
