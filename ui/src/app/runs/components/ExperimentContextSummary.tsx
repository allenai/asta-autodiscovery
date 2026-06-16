import { Box, styled, Typography } from '@mui/material';
import { Markdown } from '@allenai/varnish2/components';

import { Experiment, ExperimentStatus } from '@/types/Run';
import { getSurprisalDirection, escapeMarkdown } from '@/runs/utils/ExperimentUtils';
import { BeliefDistributionPlot } from '@/runs/components/BeliefDistributionPlot';

type ExperimentContextSummaryProps = {
    experiment: Experiment;
    surprisalWidth?: number | null;
};

/**
 * Renders the Belief Shift, Hypothesis, and Analysis sections for an experiment.
 * Shared between the experiment detail panel and the Continue with Asta modal so the
 * two stay visually in sync. Parent is expected to supply vertical spacing between the
 * rendered <Box> sections (e.g. a Stack with spacing).
 */
export function ExperimentContextSummary({
    experiment,
    surprisalWidth,
}: ExperimentContextSummaryProps) {
    // Mirror the table's threshold logic so the panel and the Surprisal column stay in sync.
    const isSurprising =
        experiment.status !== ExperimentStatus.SUCCEEDED
            ? false
            : surprisalWidth != null
              ? Math.abs(experiment.surprise ?? 0) >= surprisalWidth
              : experiment.isSurprising;

    return (
        <>
            {(experiment.surprise !== null ||
                experiment.priorBelief ||
                experiment.posteriorBelief) && (
                <Box>
                    <SectionHeader>
                        Belief Shift
                        {experiment.surprise !== null &&
                            (isSurprising ? (
                                <OrangeText>
                                    : {getSurprisalDirection(experiment.surprise)} (
                                    {experiment.surprise.toFixed(3)})
                                </OrangeText>
                            ) : (
                                <CreamText>
                                    : {getSurprisalDirection(experiment.surprise)} (
                                    {experiment.surprise.toFixed(3)})
                                </CreamText>
                            ))}
                    </SectionHeader>
                    {(experiment.priorBelief || experiment.posteriorBelief) && (
                        <BeliefDistributionPlot
                            prior={experiment.priorBelief}
                            posterior={experiment.posteriorBelief}
                            isSurprising={isSurprising}
                        />
                    )}
                </Box>
            )}

            {experiment.hypothesis && (
                <Box>
                    <SectionHeader>Hypothesis</SectionHeader>
                    <StyledMarkdown>{escapeMarkdown(experiment.hypothesis)}</StyledMarkdown>
                </Box>
            )}

            {experiment.analysis && (
                <Box>
                    <SectionHeader>Analysis</SectionHeader>
                    <StyledMarkdown>{escapeMarkdown(experiment.analysis)}</StyledMarkdown>
                </Box>
            )}
        </>
    );
}

export const SectionHeader = styled(Typography)`
    color: ${({ theme }) => theme.color['green-40'].rgba.toString()};
    font-weight: 700;
`;

export const OrangeText = styled('strong')`
    color: ${({ theme }) => theme.color['warning-orange-100'].hex};
`;

export const CreamText = styled('strong')`
    color: ${({ theme }) => theme.color['cream-100'].hex};
`;

export const StyledMarkdown = styled(Markdown)`
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

    /*
     * Varnish2's Markdown maps every <code> (inline or block) to a block-level
     * <pre>, which shows single-backtick inline code as a full-width dark block.
     * Inline code comes out as <p><pre>...</pre></p>; block code as
     * <span><pre>...</pre></span>. Reset <pre> to inline appearance and keep
     * block styling only when it's wrapped by varnish2's <span>.
     */
    & pre {
        display: inline;
        padding: 1px 6px;
        margin: 0 2px;
        max-height: none;
        max-width: fit-content;
        overflow: visible;
        font-size: 0.85em;
        line-height: inherit;
        vertical-align: baseline;
    }

    & span > pre {
        display: block;
        padding: ${({ theme }) => theme.spacing(2)};
        margin: ${({ theme }) => theme.spacing(1)} 0;
        max-width: 100%;
        overflow: auto;
        font-size: 0.8125rem;
        line-height: 1.4;
    }
`;
