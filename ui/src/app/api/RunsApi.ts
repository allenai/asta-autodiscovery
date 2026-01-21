import { BaseApi } from '@/api/BaseApi';

const RUNS_URL_PREFIX = '/api/runs';

export interface RunDetailsFromApi {
    execution_id: string | null;
    created_at: string;
    status: string;
    status_checked_at: string | null;
}

export type PostCreateRunResponseBody = {
    runid: string;
    path: string;
    message: string;
    run_details?: RunDetailsFromApi;
};

export type GetAllRunsResponseBody = {
    runs: string[];
};

export class RunsApi extends BaseApi {
    async createRun() {
        return this.request<PostCreateRunResponseBody>({
            url: `${RUNS_URL_PREFIX}/create`,
            method: 'POST',
        });
    }

    async listRuns() {
        return this.request<GetAllRunsResponseBody>({
            url: `${RUNS_URL_PREFIX}/list`,
            method: 'GET',
        });
    }
}

const api = new RunsApi();
export const getRunsApi = () => api;
