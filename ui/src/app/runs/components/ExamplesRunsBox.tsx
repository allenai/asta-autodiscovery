import { Box, CircularProgress, Typography, styled } from '@mui/material';

import { RunSummary } from '@/runs/components/RunSummary';
import { useExampleRuns } from '@/contexts/ExampleRunsContext';

export const ExamplesRunsBox = () => {
    const { exampleRuns, isExampleRunsLoading } = useExampleRuns();
    return (
        <>
            <Headline variant="h5">Example Sessions</Headline>
            {exampleRuns && exampleRuns.length > 0 && (
                <Wrapper>
                    {exampleRuns.map((run) => (
                        <RunItem key={run.id}>
                            <RunSummary run={run} />
                        </RunItem>
                    ))}
                </Wrapper>
            )}
            {isExampleRunsLoading && (
                <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
                    <CircularProgress sx={(theme) => ({ color: theme.color['green-100'].hex })} />
                </Box>
            )}
        </>
    );
};

const Wrapper = styled(Box)(({ theme }) => ({
    backgroundColor: theme.color['cream-4'].rgba.toString(),
    color: theme.color['cream-100'].hex,
    fontSize: '1.125rem',
    padding: theme.spacing(2),
    borderRadius: theme.spacing(1.5),
    marginTop: theme.spacing(1),
}));

// eslint-disable-next-line @typescript-eslint/no-unused-vars
const Headline = styled(Typography)(({ theme }) => ({
    color: '#0FCB8C',
    fontFamily: '"PP Telegraf", Manrope, sans-serif',
    fontSize: 24,
    fontStyle: 'normal',
    fontWeight: 700,
    lineHeight: '115%',
}));

const RunItem = styled('div')(({ theme }) => ({
    marginBottom: theme.spacing(2),
    '&:last-child': {
        marginBottom: 0,
    },
}));
