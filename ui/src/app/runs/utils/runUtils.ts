import { Experiment, RunDetails } from '@/types/Run';

export const getRunStatusString = (runDetails: RunDetails, experiments: Experiment[]): string => {
    const dateFormat: Intl.DateTimeFormatOptions = {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
    };
    const finishedTime = runDetails.finishedAt ?? runDetails.statusCheckedAt;

    if (runDetails.status === 'SUCCEEDED' && finishedTime) {
        return `Finished ${new Date(finishedTime).toLocaleString('en-US', dateFormat)}`;
    }

    if (runDetails.status === 'FAILED' && runDetails.statusCheckedAt) {
        return `Failed ${new Date(runDetails.statusCheckedAt).toLocaleString('en-US', dateFormat)}`;
    }

    const latestExperimentCreatedAt = experiments.at(-1)?.createdAt;
    if (latestExperimentCreatedAt) {
        return `Last updated ${new Date(latestExperimentCreatedAt).toLocaleString('en-US', dateFormat)}`;
    }

    return `Started ${new Date(runDetails.createdAt).toLocaleString('en-US', dateFormat)}`;
};
