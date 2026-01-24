import { styled } from '@mui/material';
import IconHub from '@mui/icons-material/HubOutlined';
import IconError from '@mui/icons-material/Error';
import Link from 'next/link';
import { useState } from 'react';

import { Run, RunStatus } from '@/types/Run';
import { RunPills } from '@/runs/components/RunPills';

export type RunSummaryProps = {
    run: Run;
    startExpanded?: boolean;
};

export const RunSummary = ({ run, startExpanded }: RunSummaryProps) => {
    const { id, name } = run;
    const status = run.details?.status ?? RunStatus.UNKNOWN;

    const [isExpanded, setIsExpanded] = useState(startExpanded ?? false);

    return (
        <Layout>
            <LayoutIcon>
                <IconWrapper onClick={() => setIsExpanded(!isExpanded)}>
                    <RunIcon status={status} />
                </IconWrapper>
            </LayoutIcon>
            <LayoutContent>
                <TitleLink href={`/runs/${id}`} passHref>
                    <Title>{name}</Title>
                </TitleLink>
                {isExpanded && <>EXPANDED</>}
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
    cursor: 'pointer',
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
