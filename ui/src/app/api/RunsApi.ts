import { BaseApi } from '@/api/BaseApi';

const RUNS_URL_PREFIX = '/api/runs';

export interface RunDetailsFromApi {
    execution_id: string | null;
    created_at: string;
    status: string;
    status_checked_at: string | null;
}

export interface RunStatsFromApi {
    requested_experiments: number;
    completed_experiments: number;
    pending_experiments: number;
    num_surprising_experiments: number;
}

export interface RunFromApi {
    runid: string;
    path?: string;
    status: string;
    name?: string;
    description?: string;
    run_details?: RunDetailsFromApi;
    run_stats?: RunStatsFromApi;
    execution_status?: Record<string, unknown>;
}

interface UploadDatasetResponseBody {
    path: string;
    filename: string;
    message: string;
}

export interface RunResponseBody extends RunFromApi {}

export interface GetAllRunsResponseBody {
    runs: string[];
}

export interface GetViewerRunsResponseBody {
    runs: RunFromApi[];
}

export interface GetExampleRunsResponseBody extends GetViewerRunsResponseBody {}

export interface ExperimentFromApi {
    experiment_id: string;
    parent_id: string | null;
    child_ids: string[] | null;
    creation_idx: number;
    status: string;
    is_surprising: boolean;
    surprise: number | null;
    runtime_ms: number | null;
    hypothesis: string | null;
    experiment_plan: Record<string, any> | null;
    review: string | null;
}

export interface GetRunExperimentsResponseBody {
    runid: string;
    after_experiment_id: string | null;
    has_job_completed: boolean;
    experiments: ExperimentFromApi[];
}

export interface GetRunExperimentDetailsResponseBody {
    runid: string | null;
    experiment_id: string;
    experiment: ExperimentFromApi;
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

    async listViewerRuns() {
        return this.request<GetViewerRunsResponseBody>({
            url: `${RUNS_URL_PREFIX}/list/me`,
            method: 'GET',
        });
    }

    async listExampleRuns() {
        return this.request<GetExampleRunsResponseBody>({
            url: `${RUNS_URL_PREFIX}/list/examples`,
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

    async saveMetadata(runId: string, metadata: Record<string, unknown>) {
        return this.request<RunResponseBody>({
            url: `${RUNS_URL_PREFIX}/metadata`,
            method: 'POST',
            body: { runid: runId, metadata },
        });
    }

    async uploadDataset(runId: string, file: File) {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('runid', runId);
        console.log('here in api upload dataset', file, runId);

        return this.request<UploadDatasetResponseBody>({
            url: `${RUNS_URL_PREFIX}/upload-dataset`,
            method: 'POST',
            body: formData,
        });
    }

    async submitRun(runId: string, config: Record<string, unknown>) {
        return this.request<RunResponseBody>({
            url: `${RUNS_URL_PREFIX}/submit`,
            method: 'POST',
            body: { runid: runId, ...config },
        });
    }
}
const api = new RunsApi();
export const getRunsApi = () => api;
