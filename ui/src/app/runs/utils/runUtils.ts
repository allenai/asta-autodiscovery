import { Experiment, RunDetails } from '@/types/Run';

export const getRunStatusString = (runDetails: RunDetails, experiments: Experiment[]): string => {
    const finishedTime = runDetails.finishedAt ?? runDetails.statusCheckedAt;

    if (runDetails.status === 'SUCCEEDED') {
        if (finishedTime) {
            const duration = formatDuration(new Date(runDetails.createdAt), new Date(finishedTime));
            return `Finished ${createDateTimeString(new Date(finishedTime))} (${duration})`;
        }

        return `Started ${createDateTimeString(new Date(runDetails.createdAt))}`;
    }

    if (runDetails.status === 'FAILED' && runDetails.statusCheckedAt) {
        return `Failed ${createDateTimeString(new Date(runDetails.statusCheckedAt))}`;
    }

    const latestExperimentCreatedAt = experiments.at(-1)?.createdAt;
    if (latestExperimentCreatedAt) {
        return `Last updated ${createDateTimeString(new Date(latestExperimentCreatedAt))}`;
    }

    return `Started ${createDateTimeString(new Date(runDetails.createdAt))}`;
};

export const createDateTimeString = (date: Date | string): string => {
    const dateFormat: Intl.DateTimeFormatOptions = {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
    };
    return new Date(date).toLocaleString('en-US', dateFormat);
};

export const formatDuration = (startDate: Date, endDate: Date): string => {
    const durationMs = endDate.getTime() - startDate.getTime();
    const seconds = Math.floor(durationMs / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);

    if (days > 0) {
        const remainingHours = hours % 24;
        return remainingHours > 0 ? `${days}d ${remainingHours}h` : `${days}d`;
    }
    if (hours > 0) {
        const remainingMinutes = minutes % 60;
        return remainingMinutes > 0 ? `${hours}h ${remainingMinutes}m` : `${hours}h`;
    }
    if (minutes > 0) {
        const remainingSeconds = seconds % 60;
        return remainingSeconds > 0 ? `${minutes}m ${remainingSeconds}s` : `${minutes}m`;
    }
    return `${seconds}s`;
};
