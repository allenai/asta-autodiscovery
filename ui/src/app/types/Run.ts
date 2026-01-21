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

export type RunFromApi = {
    runid: string;
    title?: string;
    path?: string;
    run_details?: RunDetailsFromApi;
};

export type RunDetailsFromApi = {
    execution_id: string | null;
    created_at: string;
    status: string;
    status_checked_at: string | null;
};

export const getRunFromApi = (runFromApi: RunFromApi): Run => {
    return {
        id: runFromApi.runid,
        name: runFromApi.title || '',
        path: runFromApi.path || '',
        details: getRunDetailsFromApi(runFromApi.run_details),
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
