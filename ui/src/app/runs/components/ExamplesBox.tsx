import { Box, Typography, styled } from '@mui/material';
import { RunSummary } from './RunSummary';

// import { Run } from '@/types/Run';

export type Run = {
    id: string;
    name: string;
    path: string;
    details: RunDetails | null;
    executionStatus?: Record<string, unknown> | null;
};

export type RunDetails = {
    executionId: string | null;
    createdAt: string;
    status: string;
    statusCheckedAt: string | null;
};

const EXAMPLE_RUNS: Run[] = [
    {
        id: 'run-1',
        name: 'Melanoma',
        path: '/path/to/run-1',
        details: {
            executionId: 'exec-1',
            createdAt: '2024-01-01T12:00:00Z',
            status: 'completed',
            statusCheckedAt: '2024-01-01T14:00:00Z',
        },
        executionStatus: {
            accuracy: 0.95,
            loss: 0.05,
        },
    },
    {
        id: 'run-2',
        name: 'Breast Cancer',
        path: '/path/to/run-2',
        details: {
            executionId: 'exec-2',
            createdAt: '2024-01-02T12:00:00Z',
            status: 'completed',
            statusCheckedAt: '2024-01-02T14:00:00Z',
        },
        executionStatus: {
            accuracy: 0.9,
            loss: 0.1,
        },
    },
    {
        id: 'run-3',
        name: 'Reef Notes',
        path: '/path/to/run-3',
        details: {
            executionId: 'exec-3',
            createdAt: '2024-01-03T12:00:00Z',
            status: 'completed',
            statusCheckedAt: '2024-01-03T14:00:00Z',
        },
        executionStatus: {
            accuracy: 0.85,
            loss: 0.15,
        },
    },
];

export const ExamplesBox = () => {
    return (
        <>
            <Headline variant="h5">Example Sessions</Headline>
            <Wrapper>
                {EXAMPLE_RUNS.map((run) => (
                    <RunItem key={run.id}>
                        <RunSummary run={run} startExpanded />
                    </RunItem>
                ))}
            </Wrapper>
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

const Headline = styled(Typography)(({ theme }) => ({
    color: '#0FCB8C',
    fontSize: 24,
    fontStyle: 'normal',
    fontWeight: 700,
    lineHeight: '115%',
}));

const RunItem = styled('div')(({ theme }) => ({
    marginBottom: theme.spacing(2),
}));
