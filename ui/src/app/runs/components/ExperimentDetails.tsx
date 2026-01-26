import { styled, Typography, Box, Chip, Stack } from '@mui/material';

import { Experiment } from '@/types/Run';
import { CodeBlock } from '@/components/CodeBlock';

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
                </Box>
            )}

            {experiment.analysis && (
                <Box>
                    <SectionHeader>Analysis</SectionHeader>
                    <Typography variant="body2" sx={{ mt: 0.5 }}>
                        {experiment.analysis}
                    </Typography>
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
