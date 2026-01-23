import { Box, CircularProgress, Typography, styled } from '@mui/material';
import { useMemo } from 'react';

import { CreateRunButton } from '@/runs/components/CreateRunButton';
import { useRuns } from '@/contexts/RunsContext';
import { RunSummary } from '@/runs/components/RunSummary';
import { Run, RunStatus } from '@/types/Run';

const STATUS_LABELS = {
    CREATED: 'Not Started',
    QUEUED: 'Queued',
    PENDING: 'Pending',
    RUNNING: 'Running',
    SUCCEEDED: 'Finished',
    FAILED: 'Error',
};

export const ViewerRunsBox = () => {
    const { viewerRuns, isViewerRunsLoading } = useRuns();

    // Group runs by status
    const runsByStatus: Record<RunStatus, Run[]> = useMemo(() => {
        const buckets: Record<string, Run[]> = {};
        if (viewerRuns) {
            viewerRuns.forEach((run) => {
                const status = run.details?.status ?? 'unknown';
                if (!buckets[status]) {
                    buckets[status] = [];
                }
                buckets[status].push(run);
            });
        }
        // Order the statuses for display
        return {
            CREATED: buckets.CREATED || [],
            QUEUED: buckets.QUEUED || [],
            PENDING: buckets.PENDING || [],
            RUNNING: buckets.RUNNING || [],
            SUCCEEDED: buckets.SUCCEEDED || [],
            FAILED: buckets.FAILED || [],
        };
    }, [viewerRuns]);

    console.log({ runsByStatus });

    return (
        <>
            <Header>
                <Headline variant="h5">Your Sessions</Headline>
                <div>
                    <CreateRunButton />
                </div>
            </Header>
            {viewerRuns && viewerRuns.length > 0 && (
                <Wrapper>
                    {Object.entries(runsByStatus).map(([status, runs]) => {
                        if (runs.length === 0) return null;
                        return (
                            <StatusGroup key={status}>
                                <StatusLabel>{STATUS_LABELS[status as RunStatus]}</StatusLabel>
                                {runs.map((run) => (
                                    <RunItem key={run.id}>
                                        <RunSummary run={run} />
                                    </RunItem>
                                ))}
                            </StatusGroup>
                        );
                    })}
                </Wrapper>
            )}
            {isViewerRunsLoading && (
                <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
                    <CircularProgress />
                </Box>
            )}
        </>
    );
};

const StatusGroup = styled('div')(({ theme }) => ({
    marginBottom: theme.spacing(4),
}));

const StatusLabel = styled(Typography)(({ theme }) => ({
    variant: 'h5',
    color: theme.color['cream-100'].hex,
    fontSize: 16,
    fontStyle: 'normal',
    fontWeight: 700,
    lineHeight: '115%',
}));

// eslint-disable-next-line @typescript-eslint/no-unused-vars
const Header = styled('div')(({ theme }) => ({
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
}));

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
    fontSize: 24,
    fontStyle: 'normal',
    fontWeight: 700,
    lineHeight: '115%',
}));

const RunItem = styled('div')(({ theme }) => ({
    marginTop: theme.spacing(2),
}));
