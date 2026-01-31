'use client';

import {
    Dialog,
    DialogTitle,
    DialogContent,
    IconButton,
    Typography,
    Box,
    Divider,
    styled,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import prettyBytes from 'pretty-bytes';

import { Metadata } from '@/types/Run';
import { MCTS_SELECTION } from '@/runs/hooks/useRunSetup';

interface RunParametersModalProps {
    open: boolean;
    onClose: () => void;
    metadata: Metadata | null | undefined;
}

/**
 * Modal displaying run parameters in read-only format.
 * Shows metadata (name, description, datasets, domain, intent) and
 * run arguments (experiments, exploration weight, etc.) - all from metadata.
 */
export function RunParametersModal({ open, onClose, metadata }: RunParametersModalProps) {
    const getMctsSelectionLabel = (value: string | null) => {
        if (!value) return 'Not set';
        const option = Object.values(MCTS_SELECTION).find((opt) => opt.value === value);
        return option?.label ?? value;
    };

    return (
        <Dialog
            open={open}
            onClose={onClose}
            maxWidth={false}
            PaperProps={{
                sx: {
                    width: '90%',
                    maxWidth: '600px',
                    borderRadius: '24px',
                },
            }}
            slotProps={{
                backdrop: {
                    sx: {
                        backgroundColor: 'rgba(0, 0, 0, 0.8)',
                    },
                },
            }}>
            <StyledDialogTitle>
                <TitleText>Run Parameters</TitleText>
                <IconButton
                    onClick={onClose}
                    aria-label="close"
                    sx={(theme) => ({
                        color: theme.color['cream-100'].hex,
                        cursor: 'pointer',
                        transition: 'color 250ms ease-out',
                        '&:hover': {
                            color: theme.color['green-100'].hex,
                        },
                    })}>
                    <CloseIcon />
                </IconButton>
            </StyledDialogTitle>
            <StyledDialogContent>
                {/* Metadata Section */}
                <Section>
                    <SectionTitle>Session info</SectionTitle>

                    <FieldRow>
                        <FieldLabel>Discovery session name</FieldLabel>
                        <FieldValue>{metadata?.name || 'Untitled'}</FieldValue>
                    </FieldRow>

                    {metadata?.description && (
                        <FieldRow>
                            <FieldLabel>Dataset context</FieldLabel>
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
                                        {(dataset.fileSizeBytes || dataset.contentType) && (
                                            <DatasetSize>
                                                {[
                                                    dataset.contentType,
                                                    dataset.fileSizeBytes
                                                        ? prettyBytes(dataset.fileSizeBytes)
                                                        : null,
                                                ]
                                                    .filter(Boolean)
                                                    .join(' · ')}
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
                    <SectionTitle>Session settings</SectionTitle>

                    <FieldRow>
                        <FieldLabel>Experiment Budget</FieldLabel>
                        <FieldValue>
                            {metadata?.nExperiments != null
                                ? `${metadata.nExperiments} experiments`
                                : 'Not set'}
                        </FieldValue>
                    </FieldRow>

                    <FieldRow>
                        <FieldLabel>Exploration weight</FieldLabel>
                        <FieldValue>{metadata?.explorationWeight ?? 'Default'}</FieldValue>
                    </FieldRow>

                    <FieldRow>
                        <FieldLabel>Search strategy</FieldLabel>
                        <FieldValue>
                            {getMctsSelectionLabel(metadata?.mctsSelection ?? null)}
                        </FieldValue>
                    </FieldRow>

                    <FieldRow>
                        <FieldLabel>Surprise threshold</FieldLabel>
                        <FieldValue>{metadata?.surprisalWidth ?? 'Default'}</FieldValue>
                    </FieldRow>

                    <FieldRow>
                        <FieldLabel>Evidence weight</FieldLabel>
                        <FieldValue>{metadata?.evidenceWeight ?? 'Default'}</FieldValue>
                    </FieldRow>

                    {metadata?.warmstartExperiments && (
                        <FieldRow>
                            <FieldLabel>Warmstart experiments</FieldLabel>
                            <FieldValue>{metadata.warmstartExperiments}</FieldValue>
                        </FieldRow>
                    )}

                    {metadata?.nWarmstart != null && (
                        <FieldRow>
                            <FieldLabel>Warmstart count</FieldLabel>
                            <FieldValue>{metadata.nWarmstart}</FieldValue>
                        </FieldRow>
                    )}
                </Section>
            </StyledDialogContent>
        </Dialog>
    );
}

const StyledDialogTitle = styled(DialogTitle)`
    align-items: center;
    background-color: ${({ theme }) => theme.color['extra-dark-teal-100'].hex};
    color: ${({ theme }) => theme.color['cream-100'].hex};
    display: flex;
    justify-content: space-between;
    padding: 12px 24px;
    border-bottom: 1px solid ${({ theme }) => theme.color['cream-10'].rgba.toString()};
`;

const TitleText = styled(Typography)`
    font-family: 'PP Telegraf', Manrope, sans-serif;
    font-weight: 700;
    font-size: 18px;
    color: ${({ theme }) => theme.color['green-40'].hex};
`;

const StyledDialogContent = styled(DialogContent)`
    background-color: ${({ theme }) => theme.color['extra-dark-teal-100'].hex};
    color: ${({ theme }) => theme.color['cream-100'].hex};
    padding: ${({ theme }) => theme.spacing(3)} !important;
`;

const Section = styled(Box)`
    display: flex;
    flex-direction: column;
    gap: ${({ theme }) => theme.spacing(1.5)};
`;

const SectionTitle = styled(Typography)`
    font-family: 'PP Telegraf', Manrope, sans-serif;
    font-size: 18px;
    font-weight: 700;
    color: ${({ theme }) => theme.color['green-100'].hex};
    margin-bottom: ${({ theme }) => theme.spacing(1)};
`;

const FieldRow = styled(Box)`
    display: flex;
    flex-direction: column;
    gap: ${({ theme }) => theme.spacing(0.5)};
`;

const FieldLabel = styled(Typography)`
    font-size: 14px;
    font-weight: 700;
    color: rgb(159, 234, 209);
    text-transform: none;
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
