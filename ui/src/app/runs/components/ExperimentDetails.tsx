import { memo, ReactNode, useEffect, useRef, useState } from 'react';
import { styled, Typography, Box, Stack, Button } from '@mui/material';

import { Experiment, ExperimentStatus } from '@/types/Run';
import { CodeBlock } from '@/components/CodeBlock';
import { escapeMarkdown } from '@/runs/utils/ExperimentUtils';
import { useAuth0 } from '@/contexts/Auth0Context';
import { useRunExperiments } from '@/contexts/RunExperimentsContext';
import { StatusChip } from '@/runs/components/StatusChip';
import { RichOutputsSection } from '@/runs/components/RichOutputsSection';
import {
    ExperimentContextSummary,
    SectionHeader,
    StyledMarkdown,
} from '@/runs/components/ExperimentContextSummary';
import { ExperimentBookmarkControl } from './ExperimentBookmarkControl';
import { ContinueWithAstaModal } from './ContinueWithAstaModal';

type ExperimentDetailsProps = {
    experiment: Experiment;
    runId: string;
    actions?: ReactNode;
    surprisalWidth?: number | null;
    datasetExpired?: boolean;
};

export const ExperimentDetails = memo(function ExperimentDetails({
    experiment,
    runId,
    actions,
    surprisalWidth,
    datasetExpired,
}: ExperimentDetailsProps) {
    const { canExploreWithAsta } = useAuth0();
    const { isLoadingSelectedExperiment, selectedExperimentError } = useRunExperiments();
    const richOutputs = experiment.richOutputs ?? [];
    const hasRichOutputs = richOutputs.length > 0;
    const [hasScrolled, setHasScrolled] = useState(false);
    const [isContinueModalOpen, setIsContinueModalOpen] = useState(false);
    const wrapperRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        // Walk up to the nearest scrollable ancestor (the ExperimentPanel)
        let scrollParent = wrapperRef.current?.parentElement;
        while (scrollParent) {
            const { overflowY } = getComputedStyle(scrollParent);
            if (overflowY === 'auto' || overflowY === 'scroll') break;
            scrollParent = scrollParent.parentElement;
        }
        if (!scrollParent) return;
        const el = scrollParent;

        let timer: ReturnType<typeof setTimeout>;
        const handler = () => {
            if (el.scrollTop > 0 && !timer) {
                timer = setTimeout(() => setHasScrolled(true), 1000);
            }
        };
        el.addEventListener('scroll', handler, { passive: true });
        return () => {
            el.removeEventListener('scroll', handler);
            clearTimeout(timer);
        };
    }, []);

    return (
        <DetailsWrapper ref={wrapperRef} spacing={0}>
            <TitleWrapper>
                <Bookmark>
                    <ExperimentBookmarkControl experiment={experiment} />
                </Bookmark>
                <ExperimentName>Experiment ID: {experiment.idInRun}</ExperimentName>
                {actions && <TitleActions>{actions}</TitleActions>}
            </TitleWrapper>
            <ContentWrapper spacing={2}>
                {experiment.status !== ExperimentStatus.SUCCEEDED && (
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

                <ExperimentContextSummary experiment={experiment} surprisalWidth={surprisalWidth} />

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
            {canExploreWithAsta &&
                (datasetExpired ? (
                    <ExpiredNotice>
                        This dataset has expired and is no longer available for exploration here.
                        You can continue your analysis with{' '}
                        <a href="https://asta.allen.ai" target="_blank" rel="noopener noreferrer">
                            Asta
                        </a>{' '}
                        by uploading the dataset there.
                    </ExpiredNotice>
                ) : (
                    <>
                        <BottomBar $visible={hasScrolled}>
                            <ContinueExploringButton
                                variant="outlined"
                                onClick={() => setIsContinueModalOpen(true)}>
                                Continue exploring with Asta
                            </ContinueExploringButton>
                        </BottomBar>
                        <ContinueWithAstaModal
                            open={isContinueModalOpen}
                            onClose={() => setIsContinueModalOpen(false)}
                            runId={runId}
                            experiment={experiment}
                            surprisalWidth={surprisalWidth}
                        />
                    </>
                ))}
        </DetailsWrapper>
    );
});

const DetailsWrapper = styled(Stack)`
    color: ${({ theme }) => theme.color['cream-100'].hex};
`;

const TitleWrapper = styled('div')`
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    row-gap: 12px;
    padding: 24px;
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

const TitleActions = styled('div')`
    display: flex;
    align-items: center;
    gap: ${({ theme }) => theme.spacing(1)};
    margin-left: auto;
`;

const Bookmark = styled('div')`
    display: inline-block;
    vertical-align: middle;
    margin-left: -12px;

    .MuiIconButton-root {
        padding: 0px 8px 1px 8px;
    }
`;

const BottomBar = styled('div')<{ $visible: boolean }>`
    position: sticky;
    bottom: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    margin: 0 8px 8px;
    padding: ${({ theme }) => theme.spacing(1.5, 3)};
    background-color: ${({ theme }) => theme.color['extra-dark-teal-100'].hex};
    border: 1px solid ${({ theme }) => theme.color['cream-10'].rgba.toString()};
    border-radius: 4px;
    box-shadow: 0 -4px 12px rgba(0, 0, 0, 0.3);
    transform: translateY(${({ $visible }) => ($visible ? '0' : 'calc(100% + 8px)')});
    transition: transform 250ms ease-out;
`;

const ExpiredNotice = styled(Typography)`
    margin: 0 8px 8px;
    padding: ${({ theme }) => theme.spacing(1.5, 3)};
    background-color: ${({ theme }) => theme.color['extra-dark-teal-100'].hex};
    border: 1px solid ${({ theme }) => theme.color['cream-10'].rgba.toString()};
    border-radius: 4px;
    box-shadow: 0 -4px 12px rgba(0, 0, 0, 0.3);
    text-align: center;
    color: ${({ theme }) => theme.color['cream-100'].hex};
    font-size: 0.875rem;

    a {
        color: ${({ theme }) => theme.color['green-40'].rgba.toString()};
        text-decoration: underline;

        &:hover {
            color: ${({ theme }) => theme.color['green-100'].hex};
        }
    }
`;

const ContinueExploringButton = styled(Button)`
    &.MuiButton-root {
        color: ${({ theme }) => theme.color['cream-100'].hex};
        padding: ${({ theme }) => theme.spacing(0, 2)};
        height: 32px;
        white-space: nowrap;
    }

    &.MuiButton-outlined {
        border: 1px solid ${({ theme }) => theme.color['green-40'].rgba.toString()};

        &:hover {
            color: ${({ theme }) => theme.color['green-100'].hex};
            border: 1px solid ${({ theme }) => theme.color['green-100'].hex};
        }
    }
`;
