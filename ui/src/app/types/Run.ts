import {
    RunDetailsFromApi,
    ExperimentSummaryFromApi,
    ExperimentDetailedFromApi,
    RunResponseBody,
} from '@/api/RunsApi';

export type Run = {
    id: string;
    name: string;
    path: string;
    details: RunDetails | null;
    executionStatus?: Record<string, unknown> | null;
};

export type RunDetails = {
    executionId: string | null;
    createdAt: string;
    status: string;
    statusCheckedAt: string | null;
};

export type ExperimentSummary = {
    experimentId: string;
    parentId: string | null;
    childIds: string[] | null;
    status: string;
    isSurprising: boolean;
};

export type ExperimentDetailed = {
    experimentId: string;
    parentId: string | null;
    childIds: string[] | null;
    creationIdx: number;
    status: string;
    isSurprising: boolean;
    runtimeMs: number | null;
    hypothesis: string | null;
    experimentPlan: Record<string, any> | null;
    review: string | null;
};

export const getRunFromApi = (responseBody: RunResponseBody): Run => {
    return {
        id: responseBody.runid,
        name: '', // TODO: Populate name when available from API
        path: responseBody.path || '',
        details: getRunDetailsFromApi(responseBody.run_details),
        executionStatus: responseBody.execution_status || null,
    };
};

export const getRunDetailsFromApi = (detailsFromApi?: RunDetailsFromApi): RunDetails | null => {
    if (!detailsFromApi) {
        return null;
    }
    return {
        executionId: detailsFromApi.execution_id,
        createdAt: detailsFromApi.created_at,
        status: detailsFromApi.status,
        statusCheckedAt: detailsFromApi.status_checked_at,
    };
};

export const getExperimentSummaryFromApi = (
    experimentFromApi: ExperimentSummaryFromApi
): ExperimentSummary => {
    return {
        experimentId: experimentFromApi.experiment_id,
        parentId: experimentFromApi.parent_id,
        childIds: experimentFromApi.child_ids,
        status: experimentFromApi.status,
        isSurprising: experimentFromApi.is_surprising,
    };
};

export const getExperimentDetailedFromApi = (
    experimentFromApi: ExperimentDetailedFromApi
): ExperimentDetailed => {
    return {
        experimentId: experimentFromApi.experiment_id,
        parentId: experimentFromApi.parent_id,
        childIds: experimentFromApi.child_ids,
        creationIdx: experimentFromApi.creation_idx,
        status: experimentFromApi.status,
        isSurprising: experimentFromApi.is_surprising,
        runtimeMs: experimentFromApi.runtime_ms,
        hypothesis: experimentFromApi.hypothesis,
        experimentPlan: experimentFromApi.experiment_plan,
        review: experimentFromApi.review,
    };
};
