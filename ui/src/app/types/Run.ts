import {
    ExperimentFromApi,
    MetadataFromApi,
    RunArgsFromApi,
    RunDetailsFromApi,
    RunFromApi,
} from '@/api/RunsApi';

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
    userid: string;
    name: string;
    description: string | null;
    path: string;
    details: RunDetails | null;
    stats: RunStats | null;
    executionStatus?: Record<string, unknown> | null;
    metadata?: Metadata | null;
    args?: RunArgs | null;
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
    analysis: string | null;
    experimentPlan: Record<string, any> | null;
    review: string | null;
    code: string | null;
    codeOutput: string | null;
    richOutputs: RichOutputBundle[] | null;
};

export type RichOutputBundle = Record<string, string>;

export type MetadataDataset = {
    name: string;
    description: string | null;
    contentType: string | null;
    fileSizeBytes: number | null;
};

export type Metadata = {
    name: string;
    description: string | null;
    datasets: MetadataDataset[];
    domain?: string;
    intent?: string;
};

export type RunArgs = {
    nExperiments: number | null;
    explorationWeight: number | null;
    mctsSelection: string | null;
    surprisalWidth: number | null;
    evidenceWeight: number | null;
    warmstartExperiments: string | null;
    nWarmstart: number | null;
};

export const getRunFromApi = (runFromApi: RunFromApi): Run => {
    return {
        id: runFromApi.runid,
        userid: runFromApi.userid,
        name: runFromApi.name || `Run ${runFromApi.runid}`,
        description: runFromApi.description || '',
        path: runFromApi.path || '',
        details: getRunDetailsFromApi(runFromApi.run_details),
        stats: getRunStatsFromApi(runFromApi.run_stats),
        executionStatus: runFromApi.execution_status || null,
        metadata: getMetadataFromApi(runFromApi.run_metadata) || null,
        args: getRunArgsFromApi(runFromApi.run_args) || null,
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
        analysis: experimentFromApi.analysis,
        experimentPlan: experimentFromApi.experiment_plan,
        review: experimentFromApi.review,
        code: experimentFromApi.code,
        codeOutput: experimentFromApi.code_output ?? null,
        richOutputs: experimentFromApi.rich_outputs ?? null,
    };
};

export const getMetadataDatasetFromApi = (datasetFromApi: any): MetadataDataset => {
    return {
        name: datasetFromApi.name,
        description: datasetFromApi.description,
        contentType: datasetFromApi.content_type || null,
        fileSizeBytes: datasetFromApi.file_size_bytes || null,
    };
};

export const getMetadataFromApi = (metadataFromApi?: MetadataFromApi): Metadata | null => {
    if (!metadataFromApi) {
        return null;
    }

    return {
        name: metadataFromApi.name,
        description: metadataFromApi.description,
        domain: metadataFromApi.domain || undefined,
        intent: metadataFromApi.intent || undefined,
        datasets: metadataFromApi.datasets.map(getMetadataDatasetFromApi),
    };
};

export const getRunArgsFromApi = (argsFromApi?: RunArgsFromApi): RunArgs | null => {
    if (!argsFromApi) {
        return null;
    }

    return {
        nExperiments: argsFromApi.n_experiments,
        explorationWeight: argsFromApi.exploration_weight,
        mctsSelection: argsFromApi.mcts_selection,
        surprisalWidth: argsFromApi.surprisal_width,
        evidenceWeight: argsFromApi.evidence_weight,
        warmstartExperiments: argsFromApi.warmstart_experiments,
        nWarmstart: argsFromApi.n_warmstart,
    };
};
