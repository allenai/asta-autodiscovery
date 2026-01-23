import { styled } from '@mui/material';
import NewReleasesOutlinedIcon from '@mui/icons-material/NewReleasesOutlined';
import ScienceOutlinedIcon from '@mui/icons-material/ScienceOutlined';
import HourglassTopOutlinedIcon from '@mui/icons-material/HourglassTopOutlined';
import { ReactNode } from 'react';

import { Run } from '@/types/Run';

export const RunPills = ({ run }: { run: Run }) => {
    const { stats } = run;
    if (!stats) {
        return null;
    }

    const { numSurprisingExperiments, completedExperiments, pendingExperiments } = stats;
    const children = [];
    if (numSurprisingExperiments > 0) {
        children.push(<SurprisalsPill key="surprisals" numSurprisals={numSurprisingExperiments} />);
    }
    if (completedExperiments > 0) {
        children.push(<ExperimentsRunPill key="completed" numRuns={completedExperiments} />);
    }
    if (pendingExperiments > 0) {
        children.push(<ExperimentsPendingPill key="pending" numPending={pendingExperiments} />);
    }

    if (children.length === 0) {
        return null;
    }
    return <PillsWrapper>{children}</PillsWrapper>;
};

export const SurprisalsPill = ({ numSurprisals }: { numSurprisals: number }) => {
    return (
        <Pill icon={<SurprisalsIcon />} label={`${numSurprisals.toLocaleString()} Surprisals`} />
    );
};

export const ExperimentsRunPill = ({ numRuns }: { numRuns: number }) => {
    return (
        <Pill icon={<ExperimentsRunIcon />} label={`${numRuns.toLocaleString()} Experiments Run`} />
    );
};

export const ExperimentsPendingPill = ({ numPending }: { numPending: number }) => {
    return (
        <Pill
            icon={<ExperimentsPendingIcon />}
            label={`${numPending.toLocaleString()} Experiments Pending`}
        />
    );
};

const PillsWrapper = styled('div')(({ theme }) => ({
    display: 'flex',
    gap: theme.spacing(1),
    alignItems: 'center',
}));

const Pill = ({ icon, label }: { icon: ReactNode; label: ReactNode }) => {
    return (
        <PillContainer>
            <PillIcon>{icon}</PillIcon>
            <PillLabel>{label}</PillLabel>
        </PillContainer>
    );
};

const PillContainer = styled('div')(({ theme }) => ({
    display: 'inline-flex',
    alignItems: 'center',
    padding: theme.spacing(0.5, 1),
    borderRadius: theme.spacing(2),
    border: `1px solid ${theme.color['cream-100'].hex}30`,
    color: theme.color['cream-100'].hex,
    lineHeight: 1,
}));

const PillIcon = styled('div')(({ theme }) => ({
    marginRight: theme.spacing(0.5),
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
}));

const PillLabel = styled('div')(({ theme }) => ({
    fontSize: 14,
    fontWeight: 400,
    color: `${theme.color['cream-100'].hex}CD`,
}));

const SurprisalsIcon = styled(NewReleasesOutlinedIcon)(({ theme }) => ({
    height: '16px',
    width: '16px',
    color: theme.color['cream-100'].hex,
}));

const ExperimentsRunIcon = styled(ScienceOutlinedIcon)(({ theme }) => ({
    height: '16px',
    width: '16px',
    color: theme.color['cream-100'].hex,
}));

const ExperimentsPendingIcon = styled(HourglassTopOutlinedIcon)(({ theme }) => ({
    height: '16px',
    width: '16px',
    color: theme.color['cream-100'].hex,
}));
