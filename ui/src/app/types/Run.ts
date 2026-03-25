import { ExperimentFromApi, MetadataFromApi, RunDetailsFromApi, RunFromApi } from '@/api/RunsApi';

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
    maxFileSize?: string | null;
    /** ID of the parent run this was forked from, if any */
    parentRunId?: string | null;
    /** Name of the parent run (for display without an extra fetch) */
    parentRunName?: string | null;
    /** ISO date when the dataset will be deleted (typically 7 days after run creation) */
    datasetExpiresAt?: string | null;
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
    finishedAt: string | null;
    status: RunStatus;
    statusCheckedAt: string | null;
};

export type BeliefDistribution = {
    _type?: string | null;
    prior_params?: number[] | null;
    n?: number | null;
    definitely_true?: number | null;
    maybe_true?: number | null;
    uncertain?: number | null;
    maybe_false?: number | null;
    definitely_false?: number | null;
    _empirical_mean?: number | null;
    mean?: number | null;
};

export type Experiment = {
    experimentId: string;
    parentId: string | null;
    childIds: string[] | null;
    creationIdx: number;
    idInRun: number;
    status: string;
    isSurprising: boolean;
    surprise: number | null;
    prior: number | null;
    posterior: number | null;
    priorBelief: BeliefDistribution | null;
    posteriorBelief: BeliefDistribution | null;
    runtimeMs: number | null;
    hypothesis: string | null;
    analysis: string | null;
    experimentPlan: Record<string, any> | null;
    review: string | null;
    code: string | null;
    codeOutput: string | null;
    richOutputs: RichOutputBundle[] | null;
    createdAt?: string | null;
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
    // Sharing
    isShared: boolean;
    // Bookmarking
    isBookmarked: boolean;
    bookmarkedExperimentIds: string[];
    // Job configuration parameters
    nExperiments?: number | null;
    explorationWeight?: number | null;
    mctsSelection?: string | null;
    surprisalWidth?: number | null;
    evidenceWeight?: number | null;
    warmstartExperiments?: string | null;
    nWarmstart?: number | null;
};

export const getRunFromApi = (runFromApi: RunFromApi): Run => {
    return {
        id: runFromApi.runid,
        userid: runFromApi.userid,
        name: runFromApi.name,
        description: runFromApi.description || '',
        path: runFromApi.path || '',
        details: getRunDetailsFromApi(runFromApi.run_details),
        stats: getRunStatsFromApi(runFromApi.run_stats),
        executionStatus: runFromApi.execution_status || null,
        metadata: getMetadataFromApi(runFromApi.run_metadata) || null,
        maxFileSize: runFromApi.max_file_size || null,
        parentRunId: runFromApi.parent_run_id ?? null,
        parentRunName: runFromApi.parent_run_name ?? null,
        datasetExpiresAt: runFromApi.dataset_expires_at ?? null,
    };
};

export const getRunDetailsFromApi = (detailsFromApi?: RunDetailsFromApi): RunDetails | null => {
    if (!detailsFromApi) {
        return null;
    }
    return {
        executionId: detailsFromApi.execution_id,
        createdAt: detailsFromApi.created_at,
        finishedAt: detailsFromApi.finished_at,
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
        idInRun: experimentFromApi.id_in_run,
        status: experimentFromApi.status,
        isSurprising: experimentFromApi.is_surprising,
        surprise: experimentFromApi.surprise,
        prior: experimentFromApi.prior,
        posterior: experimentFromApi.posterior,
        priorBelief: experimentFromApi.prior_belief ?? null,
        posteriorBelief: experimentFromApi.posterior_belief ?? null,
        runtimeMs: experimentFromApi.runtime_ms,
        hypothesis: experimentFromApi.hypothesis,
        analysis: experimentFromApi.analysis,
        experimentPlan: experimentFromApi.experiment_plan,
        review: experimentFromApi.review,
        code: experimentFromApi.code,
        codeOutput: experimentFromApi.code_output ?? null,
        richOutputs: experimentFromApi.rich_outputs ?? null,
        createdAt: experimentFromApi.created_at ?? null,
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
        isShared: !!metadataFromApi.is_shared,
        isBookmarked: !!metadataFromApi.is_bookmarked,
        bookmarkedExperimentIds: metadataFromApi.bookmarked_experiment_ids ?? [],
        // Job configuration parameters
        nExperiments: metadataFromApi.n_experiments,
        explorationWeight: metadataFromApi.exploration_weight,
        mctsSelection: metadataFromApi.mcts_selection,
        surprisalWidth: metadataFromApi.surprisal_width,
        evidenceWeight: metadataFromApi.evidence_weight,
        warmstartExperiments: metadataFromApi.warmstart_experiments,
        nWarmstart: metadataFromApi.n_warmstart,
    };
};
