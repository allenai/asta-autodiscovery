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

    // If the run belongs to a different user, use the /shared route
    const isSharedRun = authUser?.sub !== userid;
    const href = isSharedRun ? `/shared/${userid}/${id}` : `/runs/${id}`;

    return (
        <Layout>
            <LayoutIcon>
                <IconWrapper>
                    <RunIcon status={status} />
                </IconWrapper>
            </LayoutIcon>
            <LayoutContent>
                <TitleLink href={href} passHref>
                    <Title>{name}</Title>
                </TitleLink>
                {description && <Description>{description}</Description>}
                <LayoutPills>
                    <RunPills run={run} />
                </LayoutPills>
            </LayoutContent>
        </Layout>
    );
};

const Layout = styled('div')(({ theme }) => ({
    border: `1px solid ${theme.palette.divider}`,
    borderRadius: theme.spacing(1),
    padding: theme.spacing(2),
    display: 'grid',
    gridTemplateColumns: 'auto 1fr',
    gap: theme.spacing(1),
}));

// eslint-disable-next-line @typescript-eslint/no-unused-vars
const LayoutIcon = styled('div')(({ theme }) => ({}));

// eslint-disable-next-line @typescript-eslint/no-unused-vars
const LayoutContent = styled('div')(({ theme }) => ({}));

const LayoutPills = styled('div')(({ theme }) => ({
    marginTop: theme.spacing(1),
}));

const Description = styled(Typography)(({ theme }) => ({
    margin: 0,
    fontSize: '1rem',
    color: theme.color['cream-100'].hex,
}));

// eslint-disable-next-line @typescript-eslint/no-unused-vars
const TitleLink = styled(Link)(({ theme }) => ({
    textDecoration: 'none',
    cursor: 'pointer',
    '&:hover': {
        textDecoration: 'underline',
        opacity: 0.8,
    },
}));

// eslint-disable-next-line @typescript-eslint/no-unused-vars
const Title = styled('h3')(({ theme }) => ({
    color: '#9FEAD1',
    margin: 0,
    fontSize: '1.25rem',
    lineHeight: 1.5,
    fontWeight: 600,
    marginTop: '-.25em',
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
