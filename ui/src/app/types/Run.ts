import { ExperimentFromApi, RunDetailsFromApi, RunFromApi } from '@/api/RunsApi';

// Maps to values from _get_execution_phase() in cloudrun.py
export enum RunStatus {
    CANCELLED = 'CANCELLED',
    FAILED = 'FAILED',
    ERROR = 'ERROR',
    CREATED = 'CREATED',
    PENDING = 'PENDING',
    QUEUED = 'QUEUED',
    RUNNING = 'RUNNING',
    COMPLETED = 'COMPLETED',
    SUCCEEDED = 'SUCCEEDED',
    UNKNOWN = 'UNKNOWN',
}

export type Run = {
    id: string;
    name: string;
    description: string | null;
    path: string;
    details: RunDetails | null;
    stats: RunStats | null;
    executionStatus?: Record<string, unknown> | null;
};

export type RunStats = {
    requestedExperiments: number;
    completedExperiments: number;
    pendingExperiments: number;
    numSurprisingExperiments: number;
};

export type RunDetails = {
    executionId: string | null;
    createdAt: string;
    status: RunStatus;
    statusCheckedAt: string | null;
};

export type Experiment = {
    experimentId: string;
    parentId: string | null;
    childIds: string[] | null;
    creationIdx: number;
    status: string;
    isSurprising: boolean;
    surprise: number | null;
    prior: number | null;
    posterior: number | null;
    runtimeMs: number | null;
    hypothesis: string | null;
    experimentPlan: Record<string, any> | null;
    review: string | null;
    code: string | null;
};

export type MetadataDataset = {
    name: string;
    description: string | null;
};

export type Metadata = {
    title: string;
    description: string | null;
    datasets: MetadataDataset[];
};

export const getRunFromApi = (runFromApi: RunFromApi): Run => {
    return {
        id: runFromApi.runid,
        name: runFromApi.name || `Run ${runFromApi.runid}`,
        description: runFromApi.description || '',
        path: runFromApi.path || '',
        details: getRunDetailsFromApi(runFromApi.run_details),
        stats: getRunStatsFromApi(runFromApi.run_stats),
        executionStatus: runFromApi.execution_status || null,
    };
};

export const getRunDetailsFromApi = (detailsFromApi?: RunDetailsFromApi): RunDetails | null => {
    if (!detailsFromApi) {
        return null;
    }
    return {
        executionId: detailsFromApi.execution_id,
        createdAt: detailsFromApi.created_at,
        status: detailsFromApi.status as RunStatus,
        statusCheckedAt: detailsFromApi.status_checked_at,
    };
};

export const getRunStatsFromApi = (runFromApi: any): RunStats | null => {
    if (!runFromApi) {
        return null;
    }
    return {
        requestedExperiments: runFromApi.requested_experiments,
        completedExperiments: runFromApi.completed_experiments,
        pendingExperiments: runFromApi.pending_experiments,
        numSurprisingExperiments: runFromApi.num_surprising_experiments,
    };
};

export const getExperimentFromApi = (experimentFromApi: ExperimentFromApi): Experiment => {
    return {
        experimentId: experimentFromApi.experiment_id,
        parentId: experimentFromApi.parent_id,
        childIds: experimentFromApi.child_ids,
        creationIdx: experimentFromApi.creation_idx,
        status: experimentFromApi.status,
        isSurprising: experimentFromApi.is_surprising,
        surprise: experimentFromApi.surprise,
        prior: experimentFromApi.prior,
        posterior: experimentFromApi.posterior,
        runtimeMs: experimentFromApi.runtime_ms,
        hypothesis: experimentFromApi.hypothesis,
        experimentPlan: experimentFromApi.experiment_plan,
        review: experimentFromApi.review,
        code: experimentFromApi.code,
    };
};

export const getMetadataDatasetFromApi = (datasetFromApi: any): MetadataDataset => {
    return {
        name: datasetFromApi.name,
        description: datasetFromApi.description,
    };
};

export const getMetadataFromApi = (metadataFromApi: any): Metadata => {
    return {
        title: metadataFromApi.title,
        description: metadataFromApi.description,
        datasets: metadataFromApi.datasets.map(getMetadataDatasetFromApi),
    };
};
