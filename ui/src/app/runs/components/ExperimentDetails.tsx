import { styled, Typography, Box, Chip, Stack } from '@mui/material';

import { Experiment } from '@/types/Run';

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
                    <Typography variant="caption">Hypothesis</Typography>
                    <Typography variant="body2" sx={{ mt: 0.5 }}>
                        {experiment.hypothesis}
                    </Typography>
                </Box>
            )}

            <Box>
                <Typography variant="caption">Surprising</Typography>
                <Box sx={{ mt: 0.5 }}>{experiment.isSurprising ? 'Yes' : 'No'}</Box>
            </Box>

            <Box>
                <Typography variant="caption">Creation Index</Typography>
                <Typography variant="body2" sx={{ mt: 0.5 }}>
                    {experiment.creationIdx}
                </Typography>
            </Box>

            {experiment.runtimeMs && (
                <Box>
                    <Typography variant="caption">Runtime</Typography>
                    <Typography variant="body2" sx={{ mt: 0.5 }}>
                        {experiment.runtimeMs} ms
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
