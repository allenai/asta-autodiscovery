'use client';

import {
    Dialog,
    DialogTitle,
    DialogContent,
    IconButton,
    Typography,
    Box,
    Divider,
    Chip,
    styled,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import prettyBytes from 'pretty-bytes';

import { Metadata, RunArgs } from '@/types/Run';
import { MCTS_SELECTION } from '@/runs/hooks/useRunSetup';

interface RunParametersModalProps {
    open: boolean;
    onClose: () => void;
    metadata: Metadata | null | undefined;
    args: RunArgs | null | undefined;
}

/**
 * Modal displaying run parameters in read-only format.
 * Shows metadata (name, description, datasets, domain, intent) and
 * run arguments (experiments, exploration weight, etc.)
 */
export function RunParametersModal({ open, onClose, metadata, args }: RunParametersModalProps) {
    const getMctsSelectionLabel = (value: string | null) => {
        if (!value) return 'Not set';
        const option = Object.values(MCTS_SELECTION).find((opt) => opt.value === value);
        return option?.label ?? value;
    };

    return (
        <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
            <StyledDialogTitle>
                Run Parameters
                <IconButton onClick={onClose} size="small">
                    <CloseIcon />
                </IconButton>
            </StyledDialogTitle>
            <StyledDialogContent dividers>
                {/* Metadata Section */}
                <Section>
                    <SectionTitle>Session Info</SectionTitle>

                    <FieldRow>
                        <FieldLabel>Name</FieldLabel>
                        <FieldValue>{metadata?.name || 'Untitled'}</FieldValue>
                    </FieldRow>

                    {metadata?.description && (
                        <FieldRow>
                            <FieldLabel>Dataset Context</FieldLabel>
                            <FieldValue>{metadata.description}</FieldValue>
                        </FieldRow>
                    )}

                    {metadata?.domain && (
                        <FieldRow>
                            <FieldLabel>Domain</FieldLabel>
                            <FieldValue>{metadata.domain}</FieldValue>
                        </FieldRow>
                    )}

                    {metadata?.intent && (
                        <FieldRow>
                            <FieldLabel>Intent</FieldLabel>
                            <FieldValue>{metadata.intent}</FieldValue>
                        </FieldRow>
                    )}

                    {metadata?.datasets && metadata.datasets.length > 0 && (
                        <FieldRow>
                            <FieldLabel>Datasets</FieldLabel>
                            <DatasetList>
                                {metadata.datasets.map((dataset, index) => (
                                    <DatasetItem key={index}>
                                        <DatasetName>{dataset.name}</DatasetName>
                                        {dataset.fileSizeBytes && (
                                            <DatasetSize>
                                                {prettyBytes(dataset.fileSizeBytes)}
                                            </DatasetSize>
                                        )}
                                        {dataset.description && (
                                            <DatasetDescription>
                                                {dataset.description}
                                            </DatasetDescription>
                                        )}
                                    </DatasetItem>
                                ))}
                            </DatasetList>
                        </FieldRow>
                    )}
                </Section>

                <Divider sx={{ my: 2 }} />

                {/* Run Arguments Section */}
                <Section>
                    <SectionTitle>Session Settings</SectionTitle>

                    <FieldRow>
                        <FieldLabel>Experiment Budget</FieldLabel>
                        <FieldValue>
                            {args?.nExperiments != null ? (
                                <Chip label={`${args.nExperiments} experiments`} size="small" />
                            ) : (
                                'Not set'
                            )}
                        </FieldValue>
                    </FieldRow>

                    <FieldRow>
                        <FieldLabel>Exploration Weight</FieldLabel>
                        <FieldValue>{args?.explorationWeight ?? 'Default'}</FieldValue>
                    </FieldRow>

                    <FieldRow>
                        <FieldLabel>Search Strategy</FieldLabel>
                        <FieldValue>{getMctsSelectionLabel(args?.mctsSelection ?? null)}</FieldValue>
                    </FieldRow>

                    <FieldRow>
                        <FieldLabel>Surprise Threshold</FieldLabel>
                        <FieldValue>{args?.surprisalWidth ?? 'Default'}</FieldValue>
                    </FieldRow>

                    <FieldRow>
                        <FieldLabel>Evidence Weight</FieldLabel>
                        <FieldValue>{args?.evidenceWeight ?? 'Default'}</FieldValue>
                    </FieldRow>

                    {args?.warmstartExperiments && (
                        <FieldRow>
                            <FieldLabel>Warmstart Experiments</FieldLabel>
                            <FieldValue>{args.warmstartExperiments}</FieldValue>
                        </FieldRow>
                    )}

                    {args?.nWarmstart != null && (
                        <FieldRow>
                            <FieldLabel>Warmstart Count</FieldLabel>
                            <FieldValue>{args.nWarmstart}</FieldValue>
                        </FieldRow>
                    )}
                </Section>
            </StyledDialogContent>
        </Dialog>
    );
}

const StyledDialogTitle = styled(DialogTitle)`
    display: flex;
    justify-content: space-between;
    align-items: center;
    background-color: ${({ theme }) => theme.color['extra-dark-teal-100'].hex};
    color: ${({ theme }) => theme.color['cream-100'].hex};
`;

const StyledDialogContent = styled(DialogContent)`
    background-color: ${({ theme }) => theme.color['extra-dark-teal-100'].hex};
    color: ${({ theme }) => theme.color['cream-100'].hex};
`;

const Section = styled(Box)`
    display: flex;
    flex-direction: column;
    gap: ${({ theme }) => theme.spacing(1.5)};
`;

const SectionTitle = styled(Typography)`
    font-size: 1rem;
    font-weight: 600;
    color: ${({ theme }) => theme.color['green-100'].hex};
    margin-bottom: ${({ theme }) => theme.spacing(1)};
`;

const FieldRow = styled(Box)`
    display: flex;
    flex-direction: column;
    gap: ${({ theme }) => theme.spacing(0.5)};
`;

const FieldLabel = styled(Typography)`
    font-size: 0.75rem;
    font-weight: 600;
    color: ${({ theme }) => theme.color['cream-60'].hex};
    text-transform: uppercase;
    letter-spacing: 0.5px;
`;

const FieldValue = styled(Typography)`
    font-size: 0.95rem;
    color: ${({ theme }) => theme.color['cream-100'].hex};
`;

const DatasetList = styled(Box)`
    display: flex;
    flex-direction: column;
    gap: ${({ theme }) => theme.spacing(1)};
`;

const DatasetItem = styled(Box)`
    background-color: ${({ theme }) => theme.color['cream-4'].rgba.toString()};
    border-radius: ${({ theme }) => theme.spacing(1)};
    padding: ${({ theme }) => theme.spacing(1.5)};
`;

const DatasetName = styled(Typography)`
    font-size: 0.9rem;
    font-weight: 600;
    color: ${({ theme }) => theme.color['cream-100'].hex};
`;

const DatasetSize = styled(Typography)`
    font-size: 0.8rem;
    color: ${({ theme }) => theme.color['cream-60'].hex};
`;

const DatasetDescription = styled(Typography)`
    font-size: 0.85rem;
    color: ${({ theme }) => theme.color['cream-80'].hex};
    margin-top: ${({ theme }) => theme.spacing(0.5)};
`;
