import { styled, Typography, Box, Stack } from '@mui/material';
import { Markdown } from '@allenai/varnish2/components';

import { Experiment } from '@/types/Run';
import { CodeBlock } from '@/components/CodeBlock';
import {
    getPriorAndPosteriorLabel,
    getSurprisalDirection,
    escapeMarkdown,
} from '@/runs/utils/ExperimentUtils';
import { useRunExperiments } from '@/contexts/RunExperimentsContext';
import { StatusChip } from '@/runs/components/StatusChip';
import { RichOutputsSection } from '@/runs/components/RichOutputsSection';
import { BeliefDistributionPlot } from '@/runs/components/BeliefDistributionPlot';
import { ExperimentBookmarkControl } from './ExperimentBookmarkControl';

type ExperimentDetailsProps = {
    experiment: Experiment;
};

export function ExperimentDetails({ experiment }: ExperimentDetailsProps) {
    const { isLoadingSelectedExperiment, selectedExperimentError } = useRunExperiments();
    const richOutputs = experiment.richOutputs ?? [];
    const hasRichOutputs = richOutputs.length > 0;

    return (
        <DetailsWrapper spacing={0}>
            <TitleWrapper>
                <ExperimentName>Experiment ID: {experiment.idInRun}</ExperimentName>
                <Bookmark>
                    <ExperimentBookmarkControl experiment={experiment} />
                </Bookmark>
            </TitleWrapper>
            <ContentWrapper spacing={2}>
                {experiment.status !== 'SUCCEEDED' && (
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
                )}

                {experiment.surprise !== null && (
                    <Box>
                        <SectionHeader>Surprisal</SectionHeader>
                        <BeliefChip>
                            {getSurprisalDirection(experiment.surprise)}{' '}
                            {experiment.isSurprising ? (
                                <OrangeText>({experiment.surprise.toFixed(3)})</OrangeText>
                            ) : (
                                <strong>({experiment.surprise.toFixed(3)})</strong>
                            )}
                        </BeliefChip>
                    </Box>
                )}

                {(experiment.priorBelief || experiment.posteriorBelief) && (
                    <Box>
                        <SectionHeader>Belief Shift</SectionHeader>
                        <BeliefDistributionPlot
                            prior={experiment.priorBelief}
                            posterior={experiment.posteriorBelief}
                            isSurprising={experiment.isSurprising}
                        />
                    </Box>
                )}

                {experiment.hypothesis && (
                    <Box>
                        <SectionHeader>Hypothesis</SectionHeader>
                        <BeliefChip>
                            Belief before experiment:{' '}
                            <PinkText>
                                {getPriorAndPosteriorLabel(experiment.prior)} (
                                {experiment.prior?.toFixed(3)})
                            </PinkText>
                        </BeliefChip>
                        <StyledMarkdown>{escapeMarkdown(experiment.hypothesis)}</StyledMarkdown>
                    </Box>
                )}

                {experiment.analysis && (
                    <Box>
                        <SectionHeader>Analysis</SectionHeader>
                        <BeliefChip>
                            Belief after experiment:{' '}
                            <GreenText>
                                {getPriorAndPosteriorLabel(experiment.posterior)} (
                                {experiment.posterior?.toFixed(3)})
                            </GreenText>
                        </BeliefChip>
                        <StyledMarkdown>{escapeMarkdown(experiment.analysis)}</StyledMarkdown>
                    </Box>
                )}

                {experiment.experimentPlan && (
                    <>
                        <Box>
                            <SectionHeader>Experiment Plan</SectionHeader>
                            <StyledMarkdown>
                                {escapeMarkdown(
                                    `Objective: ${experiment.experimentPlan.objective}`
                                )}
                            </StyledMarkdown>
                        </Box>
                        <Box>
                            <SectionHeader>Steps</SectionHeader>
                            <StyledMarkdown>
                                {escapeMarkdown(experiment.experimentPlan.steps)}
                            </StyledMarkdown>
                        </Box>
                        <Box>
                            <SectionHeader>Deliverables</SectionHeader>
                            <StyledMarkdown>
                                {escapeMarkdown(experiment.experimentPlan.deliverables)}
                            </StyledMarkdown>
                        </Box>

                        {experiment.code && (
                            <Box>
                                <SectionHeader>Code</SectionHeader>
                                <CodeBlock code={experiment.code} />
                            </Box>
                        )}

                        {experiment.codeOutput && (
                            <Box>
                                <SectionHeader>Code Output</SectionHeader>
                                <CodeBlock code={experiment.codeOutput} />
                            </Box>
                        )}

                        {(hasRichOutputs ||
                            isLoadingSelectedExperiment ||
                            selectedExperimentError) && (
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
                        <StyledMarkdown>{escapeMarkdown(experiment.review)}</StyledMarkdown>
                    </Box>
                )}
            </ContentWrapper>
        </DetailsWrapper>
    );
}

const DetailsWrapper = styled(Stack)`
    color: ${({ theme }) => theme.color['cream-100'].hex};
`;

const TitleWrapper = styled('div')`
    padding: ${({ theme }) => theme.spacing(3)};
    border-bottom: 1px solid ${({ theme }) => theme.color['cream-10'].rgba.toString()};
`;

const ContentWrapper = styled(Stack)`
    padding: ${({ theme }) => theme.spacing(3)};
`;

const ExperimentName = styled('h2')`
    color: ${({ theme }) => theme.color['cream-100'].hex};
    display: inline-block;
    font-family: 'PP Telegraf', Manrope, sans-serif;
    font-weight: 700;
    font-size: 20px;
    line-height: 24px;
    margin: 0;
    vertical-align: middle;
`;

const Bookmark = styled('div')`
    display: inline-block;
    vertical-align: middle;
`;

const SectionHeader = styled(Typography)`
    color: ${({ theme }) => theme.color['green-40'].rgba.toString()};
    font-weight: 700;
`;

const BeliefChip = styled(Box)`
    align-items: center;
    background-color: ${({ theme }) => theme.color['extra-dark-teal-100'].hex};
    border-radius: 40px;
    color: ${({ theme }) => theme.color['cream-100'].hex};
    display: flex;
    gap: ${({ theme }) => theme.spacing(0.5)};
    font-size: 0.875rem;
    margin: ${({ theme }) => theme.spacing(1)} 0;
    padding: ${({ theme }) => theme.spacing(0.5, 1)};
    width: fit-content;
`;

const PinkText = styled('strong')`
    color: ${({ theme }) => theme.color['pink-100'].hex};
`;

const GreenText = styled('strong')`
    color: ${({ theme }) => theme.color['green-100'].hex};
`;

const OrangeText = styled('strong')`
    color: ${({ theme }) => theme.color['warning-orange-100'].hex};
`;

const StyledMarkdown = styled(Markdown)`
    margin-top: ${({ theme }) => theme.spacing(0.5)};

    &,
    & * {
        font-size: 0.875rem !important;
        margin: 0;
    }

    & ol,
    & ul {
        padding-left: 1.5em;
        margin: 0.25em 0;
    }

    & li {
        margin: 0.125em 0;
    }

    & p {
        margin: 0.25em 0;
    }

    & p:first-of-type {
        margin-top: 0;
    }
`;
