import { styled, Typography, Box, Chip, Stack } from '@mui/material';
import LightbulbOutlinedIcon from '@mui/icons-material/LightbulbOutlined';
import ScienceOutlinedIcon from '@mui/icons-material/ScienceOutlined';

import { Experiment } from '@/types/Run';
import { CodeBlock } from '@/components/CodeBlock';
import { getPriorAndPosteriorLabel } from '../utils/ExperimentUtils';

type ExperimentDetailsProps = {
    experiment: Experiment;
};

export function ExperimentDetails({ experiment }: ExperimentDetailsProps) {
    return (
        <DetailsWrapper spacing={2}>
            <ExperimentName>{experiment.experimentId}</ExperimentName>

            <Box>
                <Typography variant="caption">Status</Typography>
                <Box sx={{ mt: 0.5 }}>
                    <Chip label={experiment.status} size="small" color="primary" />
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

            {experiment.surprise && (
                <Box>
                    <SectionHeader>Surprise</SectionHeader>
                    <BeliefChip>
                        <LightbulbOutlinedIcon />
                        {experiment.surprise > 0 ? 'Positive' : 'Negative'}{' '}
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
