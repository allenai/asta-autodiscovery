import { Box, Button, CircularProgress, Typography, styled } from '@mui/material';
import ExpandLessOutlinedIcon from '@mui/icons-material/ExpandLessOutlined';
import ExpandMoreOutlinedIcon from '@mui/icons-material/ExpandMoreOutlined';
import { useMemo, useState, useEffect } from 'react';

import { CreateRunButton } from '@/runs/components/CreateRunButton';
import { useViewerRuns } from '@/contexts/ViewerRunsContext';
import { RunSummary } from '@/runs/components/RunSummary';
import { Run, RunStatus } from '@/types/Run';

enum Bucket {
    NOT_STARTED = 'NOT_STARTED',
    RUNNING = 'RUNNING',
    FINISHED = 'FINISHED',
    ERROR = 'ERROR',
    CANCELLED = 'CANCELLED',
}

// Mapping of status value to bucket, ordered for display
const STATUS_BUCKETS: Record<RunStatus, Bucket> = {
    CREATED: Bucket.NOT_STARTED,
    QUEUED: Bucket.NOT_STARTED,
    PENDING: Bucket.NOT_STARTED,
    UNKNOWN: Bucket.NOT_STARTED,
    RUNNING: Bucket.RUNNING,
    COMPLETED: Bucket.FINISHED,
    SUCCEEDED: Bucket.FINISHED,
    FAILED: Bucket.ERROR,
    ERROR: Bucket.ERROR,
    CANCELLED: Bucket.CANCELLED,
};

const BUCKET_LABELS: Record<Bucket, string> = {
    [Bucket.NOT_STARTED]: 'Not Started',
    [Bucket.RUNNING]: 'Running',
    [Bucket.FINISHED]: 'Finished',
    [Bucket.ERROR]: 'Error',
    [Bucket.CANCELLED]: 'Cancelled',
};

export const ViewerRunsBox = () => {
    const { viewerRuns, isViewerRunsLoading } = useViewerRuns();

    // Group runs by status, sorted for display by STATUS_BUCKETS order
    const runsByBucket = useMemo(() => {
        const buckets: Record<string, Run[]> = {};
        if (viewerRuns) {
            Object.values(viewerRuns).forEach((run) => {
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

    const [expandedBuckets, setExpandedBuckets] = useState<Record<Bucket, boolean>>({
        [Bucket.NOT_STARTED]: false,
        [Bucket.RUNNING]: false,
        [Bucket.FINISHED]: false,
        [Bucket.ERROR]: false,
        [Bucket.CANCELLED]: false,
    });

    // Find the first non-empty bucket and expand it
    useEffect(() => {
        // Order buckets by priority for expansion
        const bucketPriority = [
            Bucket.RUNNING,
            Bucket.NOT_STARTED,
            Bucket.FINISHED,
            Bucket.ERROR,
            Bucket.CANCELLED,
        ];

        const firstNonEmptyBucket = bucketPriority.find(
            (bucket) => runsByBucket[bucket]?.length > 0
        );

        if (firstNonEmptyBucket) {
            setExpandedBuckets({
                [Bucket.NOT_STARTED]: firstNonEmptyBucket === Bucket.NOT_STARTED,
                [Bucket.RUNNING]: firstNonEmptyBucket === Bucket.RUNNING,
                [Bucket.FINISHED]: firstNonEmptyBucket === Bucket.FINISHED,
                [Bucket.ERROR]: firstNonEmptyBucket === Bucket.ERROR,
                [Bucket.CANCELLED]: firstNonEmptyBucket === Bucket.CANCELLED,
            });
        }
    }, [runsByBucket]);

    const onClickToggleButton = (bucket: Bucket) => {
        setExpandedBuckets((prev) => ({
            ...prev,
            [bucket]: !prev[bucket],
        }));
    };

    return (
        <>
            <Header>
                <Headline>Your sessions</Headline>
                <div>
                    <CreateRunButton />
                </div>
            </Header>
            {viewerRuns && Object.keys(viewerRuns).length > 0 && (
                <Wrapper>
                    {Object.entries(runsByBucket).map(([bucket, runs]) => {
                        if (runs.length === 0) return null;
                        const isExpanded = expandedBuckets[bucket as Bucket];
                        return (
                            <StatusGroup key={bucket}>
                                <StatusHeader onClick={() => onClickToggleButton(bucket as Bucket)}>
                                    <ToggleButton
                                        startIcon={
                                            isExpanded ? (
                                                <ExpandLessOutlinedIcon />
                                            ) : (
                                                <ExpandMoreOutlinedIcon />
                                            )
                                        }
                                    />
                                    <StatusLabel
                                        className={isExpanded ? 'is-expanded' : 'is-collapsed'}>
                                        {runs.length} {BUCKET_LABELS[bucket as Bucket]}
                                    </StatusLabel>
                                </StatusHeader>
                                {isExpanded && (
                                    <RunsList>
                                        {runs.map((run) => (
                                            <RunItem key={run.id}>
                                                <RunSummary run={run} />
                                            </RunItem>
                                        ))}
                                    </RunsList>
                                )}
                            </StatusGroup>
                        );
                    })}
                </Wrapper>
            )}
            {isViewerRunsLoading && (
                <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
                    <CircularProgress sx={(theme) => ({ color: theme.color['green-100'].hex })} />
                </Box>
            )}
        </>
    );
};

const StatusGroup = styled('div')(({ theme }) => ({
    marginBottom: theme.spacing(2),
    '&:last-child': {
        marginBottom: 0,
    },
    '&:last-child > div:last-child': {
        paddingBottom: 0,
    },
}));

const StatusHeader = styled('div')(({ theme }) => ({
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'start',
    gap: theme.spacing(1),
}));

const StatusLabel = styled(Typography)(({ theme }) => ({
    color: '#FAF2E9',
    fontFeatureSettings: "'liga' off, 'clig' off",
    fontFamily: '"PP Telegraf", Manrope, sans-serif',
    fontSize: '18px',
    fontStyle: 'normal',
    fontWeight: 700,
    lineHeight: '115%',
    cursor: 'pointer',
    transition: 'color 250ms ease-out',
    '&:hover': {
        color: theme.color['green-100'].hex,
    },
    '&.is-collapsed': {
        color: theme.color['green-20'].hex,
    },
    '&.is-collapsed:hover': {
        color: theme.color['green-100'].hex,
    },
}));

const ToggleButton = styled(Button)(({ theme }) => ({
    background: theme.color['teal-100'].hex,
    border: 'none',
    color: theme.color['green-100'].hex,
    cursor: 'pointer',
    width: '20px',
    height: '20px',
    minWidth: '20px',
    '& .MuiButton-startIcon': {
        margin: 0,
    },
}));

// eslint-disable-next-line @typescript-eslint/no-unused-vars
const Header = styled('div')(({ theme }) => ({
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',

    '@media (max-width: 600px)': {
        flexDirection: 'column',
        alignItems: 'flex-start',
        gap: theme.spacing(1),
    },
}));

const Wrapper = styled(Box)(({ theme }) => ({
    backgroundColor: '#162D31',
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

    '@media (max-width: 600px)': {
        marginTop: '36px',
    },
}));

const RunsList = styled('div')(({ theme }) => ({
    paddingBottom: theme.spacing(2),
}));

const RunItem = styled('div')(({ theme }) => ({
    marginTop: theme.spacing(1),
}));
