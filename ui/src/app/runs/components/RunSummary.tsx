import { styled, Typography } from '@mui/material';
import IconHub from '@mui/icons-material/HubOutlined';
import IconError from '@mui/icons-material/Error';
import Link from 'next/link';

import { Run, RunStatus } from '@/types/Run';
import { RunPills } from '@/runs/components/RunPills';
import { useAuth0 } from '@/contexts/Auth0Context';

export type RunSummaryProps = {
    run: Run;
};

export const RunSummary = ({ run }: RunSummaryProps) => {
    const { user: authUser } = useAuth0();
    const { id, userid, name, description } = run;
    const status = run.details?.status ?? RunStatus.UNKNOWN;
    const shortDescription = description?.includes('.')
        ? description.split('.')[0] + '.'
        : description;


    // If the run belongs to a different user, use the /shared route
    const isSharedRun = authUser?.sub !== userid;
    const href = isSharedRun ? `/shared/${userid}/${id}` : `/runs/${id}`;

    return (
        <LayoutLink href={href} passHref>
            <Layout>
                <LayoutIcon>
                    <IconWrapper>
                        <RunIcon status={status} />
                    </IconWrapper>
                </LayoutIcon>
                <LayoutContent>
                    <Title className="run-title">{name}</Title>
                    {description && <Description>{shortDescription}</Description>}
                    {run.stats &&
                        (run.stats.numSurprisingExperiments > 0 ||
                            run.stats.completedExperiments > 0 ||
                            run.stats.pendingExperiments > 0) && (
                            <LayoutPills>
                                <RunPills run={run} />
                            </LayoutPills>
                        )}
                </LayoutContent>
            </Layout>
        </LayoutLink>
    );
};

const LayoutLink = styled(Link)(() => ({
    textDecoration: 'none',
    cursor: 'pointer',
}));

const Layout = styled('div')(({ theme }) => ({
    border: `1px solid ${theme.color['cream-10'].rgba.toString()}`,
    borderRadius: '4px',
    padding: theme.spacing(2),
    display: 'grid',
    gridTemplateColumns: 'auto 1fr',
    gap: theme.spacing(1),
    cursor: 'pointer',
    transition: 'border 250ms ease-out, background-color 250ms ease-out',
    '&:hover': {
        border: '1px solid rgba(255, 255, 255, 0.4)',
        backgroundColor: theme.color['cream-4'].rgba.toString(),
    },
    '&:hover .run-title': {
        color: theme.color['green-100'].hex,
    },
}));

// eslint-disable-next-line @typescript-eslint/no-unused-vars
const LayoutIcon = styled('div')(({ theme }) => ({}));

// eslint-disable-next-line @typescript-eslint/no-unused-vars
const LayoutContent = styled('div')(({ theme }) => ({}));

const LayoutPills = styled('div')(({ theme }) => ({
    marginTop: theme.spacing(1),
}));

const Description = styled(Typography)(({ theme }) => ({
    overflowWrap: 'anywhere',
    margin: 0,
    fontSize: '1rem',
    color: theme.color['cream-100'].hex,
    display: '-webkit-box',
    WebkitLineClamp: 3,
    WebkitBoxOrient: 'vertical',
    overflow: 'hidden',
}));

// eslint-disable-next-line @typescript-eslint/no-unused-vars
const Title = styled('h3')(({ theme }) => ({
    overflowWrap: 'anywhere',
    color: theme.color['cream-100'].hex,
    margin: 0,
    fontSize: '1.25rem',
    lineHeight: 1.5,
    fontWeight: 600,
    marginTop: '-.25em',
    transition: 'color 250ms ease-out',
}));

// eslint-disable-next-line @typescript-eslint/no-unused-vars
const IconWrapper = styled('div')(({ theme }) => ({
    width: '20px',
    height: '20px',
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
}));

const RunIcon = ({ status }: { status: RunStatus }) => {
    const sharedProps = {
        sx: {
            height: '20px',
            width: '20px',
        },
    };
    switch (status) {
        case RunStatus.CREATED:
        case RunStatus.CANCELLED:
        case RunStatus.PENDING:
        case RunStatus.QUEUED:
            return <IconHub {...sharedProps} htmlColor="#FAF2E980" />;
        case RunStatus.ERROR:
        case RunStatus.FAILED:
            return <IconError {...sharedProps} color="error" />;
        default:
            return <IconHub {...sharedProps} color="secondary" />;
    }
};
