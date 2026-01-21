import {
    RunDetailsFromApi,
    PostCreateRunResponseBody,
    GetAllRunsResponseBody,
} from '@/api/RunsApi';

export type Run = {
    id: string;
    name: string;
    path: string;
    details: RunDetails | null;
};

export type RunDetails = {
    executionId: string | null;
    createdAt: string;
    status: string;
    statusCheckedAt: string | null;
};

export const getRunFromApi = (responseBody: PostCreateRunResponseBody): Run => {
    return {
        id: responseBody.runid,
        name: '', // TODO: Populate name when available from API
        path: responseBody.path || '',
        details: getRunDetailsFromApi(responseBody.run_details),
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
