import { styled, Typography, Box, Stack, Dialog, DialogContent, IconButton } from '@mui/material';
import LightbulbOutlinedIcon from '@mui/icons-material/LightbulbOutlined';
import ScienceOutlinedIcon from '@mui/icons-material/ScienceOutlined';
import CloseIcon from '@mui/icons-material/Close';
import { useMemo, useState } from 'react';

import { Experiment, RichOutputBundle } from '@/types/Run';
import { CodeBlock } from '@/components/CodeBlock';
import { getPriorAndPosteriorLabel, getSurprisalDirection } from '@/runs/utils/ExperimentUtils';
import { useRunExperiments } from '@/contexts/RunExperimentsContext';
import { StatusChip } from '@/runs/components/StatusChip';

type ExperimentDetailsProps = {
    experiment: Experiment;
};

type RichOutputMime = 'image/svg+xml' | 'image/png' | 'image/jpeg' | 'text/plain';

type RichOutputPreview =
    | {
          kind: 'image';
          mime: Exclude<RichOutputMime, 'text/plain'>;
          src: string;
      }
    | {
          kind: 'text';
          mime: 'text/plain';
          text: string;
      }
    | null;

const RICH_OUTPUT_PRIORITY: RichOutputMime[] = [
    'image/svg+xml',
    'image/png',
    'image/jpeg',
    'text/plain',
];

const buildSvgDataUri = (payload: string) => {
    const trimmed = payload.trim();
    const isXml = trimmed.startsWith('<') || trimmed.startsWith('<?xml');
    return isXml
        ? `data:image/svg+xml;utf8,${encodeURIComponent(trimmed)}`
        : `data:image/svg+xml;base64,${trimmed}`;
};

const getPreferredRichOutput = (bundle: RichOutputBundle): RichOutputPreview => {
    for (const mime of RICH_OUTPUT_PRIORITY) {
        const payload = bundle[mime];
        if (!payload) {
            continue;
        }
        if (mime === 'text/plain') {
            return { kind: 'text', mime, text: payload };
        }
        const src =
            mime === 'image/svg+xml' ? buildSvgDataUri(payload) : `data:${mime};base64,${payload}`;
        return { kind: 'image', mime, src };
    }
    return null;
};

const extractPlotAnalyses = (codeOutput: string | null) => {
    if (!codeOutput) {
        return [];
    }
    const analyses: string[] = [];
    const pattern = /=== Plot Analysis \(figure (\d+)\) ===\s*([\s\S]*?)(?:\n=+|\r\n=+|$)/g;
    let match = pattern.exec(codeOutput);
    while (match) {
        const index = Number(match[1]);
        const analysis = match[2]?.trim();
        if (!Number.isNaN(index) && analysis) {
            analyses[index - 1] = analysis;
        }
        match = pattern.exec(codeOutput);
    }
    return analyses;
};

export function ExperimentDetails({ experiment }: ExperimentDetailsProps) {
    const { isLoadingSelectedExperiment, selectedExperimentError } = useRunExperiments();
    const richOutputs = experiment.richOutputs ?? [];
    const hasRichOutputs = richOutputs.length > 0;

    return (
        <DetailsWrapper spacing={2}>
            <ExperimentName>{experiment.experimentId}</ExperimentName>

            <Box>
                <SectionHeader>Status</SectionHeader>
                <Box sx={{ mt: 0.5 }}>
                    <StatusChip
                        label={experiment.status}
                        size="small"
                        $status={experiment.status}
                    />
                </Box>
            </Box>

            {experiment.hypothesis && (
                <Box>
                    <SectionHeader>Hypothesis</SectionHeader>
                    <Typography variant="body2" sx={{ mt: 0.5 }}>
                        {experiment.hypothesis}
                    </Typography>
                    <BeliefChip>
                        <ScienceOutlinedIcon />
                        Belief before experiment:{' '}
                        <strong>
                            {getPriorAndPosteriorLabel(experiment.prior)} (
                            {experiment.prior?.toFixed(3)})
                        </strong>
                    </BeliefChip>
                </Box>
            )}

            {experiment.analysis && (
                <Box>
                    <SectionHeader>Analysis</SectionHeader>
                    <Typography variant="body2" sx={{ mt: 0.5 }}>
                        {experiment.analysis}
                    </Typography>
                    <BeliefChip>
                        <ScienceOutlinedIcon />
                        Belief after experiment:{' '}
                        <strong>
                            {getPriorAndPosteriorLabel(experiment.posterior)} (
                            {experiment.posterior?.toFixed(3)})
                        </strong>
                    </BeliefChip>
                </Box>
            )}

            {experiment.surprise !== null && (
                <Box>
                    <SectionHeader>Surprise</SectionHeader>
                    <BeliefChip>
                        <LightbulbOutlinedIcon />
                        {getSurprisalDirection(experiment.surprise)}{' '}
                        <strong>({experiment.surprise.toFixed(3)})</strong>
                    </BeliefChip>
                </Box>
            )}

            {experiment.experimentPlan && (
                <>
                    <Box>
                        <SectionHeader>Experiment Plan</SectionHeader>
                        <Typography variant="body2" sx={{ mt: 0.5 }}>
                            Objective: {experiment.experimentPlan.objective}
                        </Typography>
                    </Box>
                    <Box>
                        <SectionHeader>Steps</SectionHeader>
                        <Typography variant="body2" sx={{ mt: 0.5 }}>
                            {experiment.experimentPlan.steps}
                        </Typography>
                    </Box>
                    <Box>
                        <SectionHeader>Deliverables</SectionHeader>
                        <Typography variant="body2" sx={{ mt: 0.5 }}>
                            {experiment.experimentPlan.deliverables}
                        </Typography>
                    </Box>

                    {experiment.code && (
                        <Box>
                            <SectionHeader>Code</SectionHeader>
                            <CodeBlock code={experiment.code} />
                        </Box>
                    )}

                    {(hasRichOutputs || isLoadingSelectedExperiment || selectedExperimentError) && (
                        <RichOutputsSection
                            richOutputs={richOutputs}
                            codeOutput={experiment.codeOutput}
                            isLoading={isLoadingSelectedExperiment}
                            error={selectedExperimentError}
                        />
                    )}
                </>
            )}

            {experiment.review && (
                <Box>
                    <SectionHeader>Review</SectionHeader>
                    <Typography variant="body2" sx={{ mt: 0.5 }}>
                        Objective: {experiment.review}
                    </Typography>
                </Box>
            )}
        </DetailsWrapper>
    );
}

type RichOutputsSectionProps = {
    richOutputs: RichOutputBundle[];
    codeOutput: string | null;
    isLoading: boolean;
    error: string | null;
};

function RichOutputsSection({
    richOutputs,
    codeOutput,
    isLoading,
    error,
}: RichOutputsSectionProps) {
    const [activeImage, setActiveImage] = useState<{
        index: number;
        src: string;
        analysis: string | null;
    } | null>(null);
    const plotAnalyses = useMemo(() => extractPlotAnalyses(codeOutput), [codeOutput]);

    return (
        <Box>
            <SectionHeader>Figures</SectionHeader>
            {isLoading && (
                <Typography variant="caption" sx={{ mt: 0.5 }}>
                    Loading figures...
                </Typography>
            )}
            {error && (
                <Typography
                    variant="caption"
                    sx={(theme) => ({
                        mt: 0.5,
                        color: theme.color['error-red-80'].hex,
                    })}>
                    {error}
                </Typography>
            )}
            {richOutputs.length > 0 && (
                <RichOutputsGrid>
                    {richOutputs.map((bundle, idx) => {
                        const preview = getPreferredRichOutput(bundle);
                        if (!preview) {
                            return (
                                <RichOutputCard key={`rich-output-${idx}`}>
                                    <Typography variant="body2">
                                        Unsupported rich output.
                                    </Typography>
                                </RichOutputCard>
                            );
                        }
                        if (preview.kind === 'text') {
                            return (
                                <RichOutputCard key={`rich-output-${idx}`}>
                                    <Typography variant="caption" sx={{ mb: 0.5 }}>
                                        Output {idx + 1}
                                    </Typography>
                                    <CodeBlock code={preview.text} />
                                </RichOutputCard>
                            );
                        }
                        return (
                            <RichOutputCard key={`rich-output-${idx}`}>
                                <RichOutputClickableArea
                                    onClick={() =>
                                        setActiveImage({
                                            index: idx,
                                            src: preview.src,
                                            analysis: plotAnalyses[idx] ?? null,
                                        })
                                    }>
                                    <RichOutputTitle
                                        variant="caption"
                                        className="rich-output-title">
                                        Figure {idx + 1}
                                    </RichOutputTitle>
                                    <RichOutputImage
                                        src={preview.src}
                                        alt={`Figure ${idx + 1}`}
                                        loading="lazy"
                                    />
                                </RichOutputClickableArea>
                            </RichOutputCard>
                        );
                    })}
                </RichOutputsGrid>
            )}
            <Dialog
                open={Boolean(activeImage)}
                onClose={() => setActiveImage(null)}
                maxWidth={false}
                PaperProps={{
                    sx: {
                        width: 'calc(100vw - 120px)',
                        height: 'calc(100vh - 120px)',
                        maxWidth: 'calc(100vw - 120px)',
                        maxHeight: 'calc(100vh - 120px)',
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
                <FullscreenHeader>
                    <Typography
                        variant="h6"
                        sx={(theme) => ({
                            fontWeight: 'bold',
                            fontSize: '18px',
                            color: theme.color['green-40'].hex,
                        })}>
                        {activeImage ? `Figure ${activeImage.index + 1}` : ''}
                    </Typography>
                    <IconButton
                        onClick={() => setActiveImage(null)}
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
                </FullscreenHeader>
                <DialogContent sx={{ p: 0 }}>
                    {activeImage && (
                        <FullscreenBody>
                            <FullscreenImage
                                src={activeImage.src}
                                alt={`Figure ${activeImage.index + 1}`}
                            />
                            {activeImage.analysis && (
                                <FullscreenAnalysis>
                                    <SectionHeader>Plot Analysis</SectionHeader>
                                    <AnalysisText>{activeImage.analysis}</AnalysisText>
                                </FullscreenAnalysis>
                            )}
                        </FullscreenBody>
                    )}
                </DialogContent>
            </Dialog>
        </Box>
    );
}

const DetailsWrapper = styled(Stack)`
    color: ${({ theme }) => theme.color['cream-100'].hex};
`;

const ExperimentName = styled(Typography)`
    color: ${({ theme }) => theme.color['warning-orange-100'].hex};
    font-weight: 700;
`;

const SectionHeader = styled(Typography)`
    color: ${({ theme }) => theme.color['green-40'].rgba.toString()};
    font-weight: 700;
`;

const BeliefChip = styled(Box)`
    align-items: center;
    backgroundcolor: transparent;
    border: 1px solid ${({ theme }) => theme.color['green-40'].rgba.toString()};
    border-radius: 40px;
    color: ${({ theme }) => theme.color['cream-100'].hex};
    display: flex;
    gap: ${({ theme }) => theme.spacing(0.5)};
    font-size: 0.875rem;
    margin-top: ${({ theme }) => theme.spacing(1)};
    padding: ${({ theme }) => theme.spacing(0.5, 1)};
    width: fit-content;

    .MuiSvgIcon-root {
        color: ${({ theme }) => theme.color['green-100'].hex};
        font-size: 1rem;
    }
`;

const RichOutputsGrid = styled(Box)`
    display: grid;
    gap: ${({ theme }) => theme.spacing(2)};
    margin-top: ${({ theme }) => theme.spacing(1)};
`;

const RichOutputCard = styled(Box)`
    background-color: ${({ theme }) => theme.color['dark-teal-100'].hex};
    border: 1px solid ${({ theme }) => theme.color['cream-4'].rgba.toString()};
    border-radius: ${({ theme }) => theme.shape.borderRadius}px;
`;

const RichOutputClickableArea = styled('div')`
    cursor: pointer;

    &:hover .rich-output-title {
        color: ${({ theme }) => theme.color['green-100'].hex};
    }
`;

const RichOutputTitle = styled(Typography)`
    display: block;
    margin-bottom: 8px;
    transition: color 250ms ease-out;
` as typeof Typography & { className?: string };

const RichOutputImage = styled('img')`
    border-radius: ${({ theme }) => theme.shape.borderRadius}px;
    display: block;
    max-width: 100%;
    object-fit: contain;
    width: 100%;
`;

const FullscreenHeader = styled(Box)`
    align-items: center;
    background-color: ${({ theme }) => theme.color['extra-dark-teal-100'].hex};
    color: ${({ theme }) => theme.color['cream-100'].hex};
    display: flex;
    justify-content: space-between;
    padding: 12px 24px;
    border-bottom: 1px solid ${({ theme }) => theme.color['cream-10'].rgba.toString()};
`;

const FullscreenBody = styled(Box)`
    background-color: ${({ theme }) => theme.color['extra-dark-teal-100'].hex};
    color: ${({ theme }) => theme.color['cream-100'].hex};
    display: grid;
    gap: ${({ theme }) => theme.spacing(3)};
    min-height: 100%;
    padding: ${({ theme }) => theme.spacing(3)};
`;

const FullscreenImage = styled('img')`
    border-radius: ${({ theme }) => theme.shape.borderRadius}px;
    max-height: 70vh;
    object-fit: contain;
    width: 100%;
`;

const FullscreenAnalysis = styled(Box)`
    background-color: ${({ theme }) => theme.color['dark-teal-100'].hex};
    border-radius: ${({ theme }) => theme.shape.borderRadius}px;
    padding: ${({ theme }) => theme.spacing(2)};
`;

const AnalysisText = styled('pre')`
    font-family: inherit;
    font-size: 0.9rem;
    margin: ${({ theme }) => theme.spacing(1, 0, 0, 0)};
    white-space: pre-wrap;
`;
