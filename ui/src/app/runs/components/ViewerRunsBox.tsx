import { Box, Button, CircularProgress, Typography, styled } from '@mui/material';
import ExpandLessOutlinedIcon from '@mui/icons-material/ExpandLessOutlined';
import ExpandMoreOutlinedIcon from '@mui/icons-material/ExpandMoreOutlined';
import { useMemo, useState } from 'react';

import { CreateRunButton } from '@/runs/components/CreateRunButton';
import { useRuns } from '@/contexts/RunsContext';
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
    const { viewerRuns, isViewerRunsLoading } = useRuns();

    // Group runs by status, sorted for display by STATUS_BUCKETS order
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

    const [expandedBuckets, setExpandedBuckets] = useState<Record<Bucket, boolean>>(() => ({
        [Bucket.NOT_STARTED]: true,
        [Bucket.RUNNING]: false,
        [Bucket.FINISHED]: false,
        [Bucket.ERROR]: false,
        [Bucket.CANCELLED]: false,
    }));

    const onClickToggleButton = (bucket: Bucket) => {
        setExpandedBuckets((prev) => ({
            ...prev,
            [bucket]: !prev[bucket],
        }));
    };

    return (
        <>
            <Header>
                <Headline>Your Sessions</Headline>
                <div>
                    <CreateRunButton />
                </div>
            </Header>
            {viewerRuns && viewerRuns.length > 0 && (
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
    fontFamily: '"PP Telegraf", Manrope, sans-serif',
    fontSize: 24,
    fontStyle: 'normal',
    fontWeight: 700,
    lineHeight: '115%',
}));

const RunsList = styled('div')(({ theme }) => ({
    paddingBottom: theme.spacing(2),
}));

const RunItem = styled('div')(({ theme }) => ({
    marginTop: theme.spacing(1),
}));
