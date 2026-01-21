import { BaseApi } from '@/api/BaseApi';

const RUNS_URL_PREFIX = '/api/runs';

export interface RunDetailsFromApi {
    execution_id: string | null;
    created_at: string;
    status: string;
    status_checked_at: string | null;
}

export interface RunResponseBody {
    runid: string;
    path: string;
    message: string;
    run_details?: RunDetailsFromApi;
    execution_status?: Record<string, unknown>;
}

export interface GetAllRunsResponseBody {
    runs: string[];
}

export interface ExperimentSummaryFromApi {
    experiment_id: string;
    parent_id: string | null;
    child_ids: string[] | null;
    status: string;
    is_surprising: boolean;
}
export interface GetRunExperimentsResponseBody {
    runid: string;
    after_experiment_id: string | null;
    experiments: ExperimentSummaryFromApi[];
}

export interface ExperimentDetailedFromApi {
    experiment_id: string;
    parent_id: string | null;
    child_ids: string[] | null;
    creation_idx: number;
    status: string;
    is_surprising: boolean;
    runtime_ms: number | null;
    hypothesis: string | null;
    experiment_plan: Record<string, any> | null;
    review: string | null;
}

export interface GetRunExperimentDetailsResponseBody {
    runid: string | null;
    experiment_id: string;
    experiment: ExperimentDetailedFromApi;
}
export interface GetRunStatusResponseBody {
    runid: string;
    run_details: RunDetailsFromApi;
    execution_status?: Record<string, unknown>; // TODO: Type this properly
}

export class RunsApi extends BaseApi {
    async createRun() {
        return this.request<RunResponseBody>({
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

    async getRunExperiments({
        runid,
        afterExperimentId,
    }: {
        runid: string;
        afterExperimentId?: string;
    }) {
        const query: Record<string, string> = {};
        if (afterExperimentId) {
            query.after_experiment_id = afterExperimentId;
        }

        return this.request<GetRunExperimentsResponseBody>({
            url: `${RUNS_URL_PREFIX}/${encodeURIComponent(runid)}/experiments`,
            method: 'GET',
            query,
        });
    }

    async getRunExperimentDetails({
        runid,
        experimentId,
    }: {
        runid: string;
        experimentId: string;
    }) {
        return this.request<GetRunExperimentDetailsResponseBody>({
            url: `${RUNS_URL_PREFIX}/${encodeURIComponent(runid)}/experiments/${encodeURIComponent(
                experimentId
            )}`,
            method: 'GET',
        });
    }

    async getRun(runId: string) {
        return this.request<RunResponseBody>({
            url: `${RUNS_URL_PREFIX}/${runId}`,
            method: 'GET',
        });
    }

    async getRunStatus(runId: string) {
        return this.request<RunResponseBody>({
            url: `${RUNS_URL_PREFIX}/${runId}/status`,
            method: 'GET',
        });
    }

    async cancelRun(runId: string) {
        return this.request<void>({
            url: `${RUNS_URL_PREFIX}/${runId}/cancel`,
            method: 'POST',
        });
    }
}
const api = new RunsApi();
export const getRunsApi = () => api;
