import { Box, CircularProgress, Typography, styled } from '@mui/material';
import { useMemo } from 'react';

import { CreateRunButton } from '@/runs/components/CreateRunButton';
import { useRuns } from '@/contexts/RunsContext';
import { RunSummary } from '@/runs/components/RunSummary';
import { Run, RunStatus } from '@/types/Run';

enum Bucket {
    NotStarted = 'NotStarted',
    Running = 'Running',
    Finished = 'Finished',
    Error = 'Error',
    Cancelled = 'Cancelled',
}

// Mapping of status value to bucket
const STATUS_BUCKETS: Record<RunStatus, Bucket> = {
    CANCELLED: Bucket.Cancelled,
    FAILED: Bucket.Error,
    ERROR: Bucket.Error,
    CREATED: Bucket.NotStarted,
    QUEUED: Bucket.NotStarted,
    PENDING: Bucket.NotStarted,
    RUNNING: Bucket.Running,
    COMPLETED: Bucket.Finished,
    SUCCEEDED: Bucket.Finished,
    UNKNOWN: Bucket.NotStarted,
};

// Ordered in which they are displayed
const BUCKET_LABELS: Record<Bucket, string> = {
    [Bucket.NotStarted]: 'Not Started',
    [Bucket.Running]: 'Running',
    [Bucket.Finished]: 'Finished',
    [Bucket.Error]: 'Error',
    [Bucket.Cancelled]: 'Cancelled',
};

export const ViewerRunsBox = () => {
    const { viewerRuns, isViewerRunsLoading } = useRuns();

    // Group runs by status, sorted for display by STATUS_LABELS order
    const runsByBucket = useMemo(() => {
        const buckets: Record<string, Run[]> = {};
        if (viewerRuns) {
            viewerRuns.forEach((run) => {
                const status = run.details?.status ?? RunStatus.UNKNOWN;
                if (!buckets[status]) {
                    buckets[status] = [];
                }
                buckets[status].push(run);
            });
        }
        const orderedBuckets = Object.entries(STATUS_BUCKETS).reduce(
            (acc, [status, bucket]) => {
                if (!acc[bucket]) {
                    acc[bucket] = [];
                }
                acc[bucket].push(...(buckets[status] || []));
                return acc;
            },
            {} as Record<Bucket, Run[]>
        );
        return orderedBuckets;
    }, [viewerRuns]);

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
                    {Object.entries(runsByBucket).map(([bucket, runs]) => {
                        if (runs.length === 0) return null;
                        return (
                            <StatusGroup key={bucket}>
                                <StatusLabel>{BUCKET_LABELS[bucket as Bucket]}</StatusLabel>
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
