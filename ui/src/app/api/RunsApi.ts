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

export interface RunMetadataFromApi {
    name: string;
    description: string | null;
    domain: string | null;
    intent: string | null;
    datasets: {
        name: string;
        description: string | null;
    }[];
}

export interface RunArgsFromApi {
    n_experiments: number | null;
    exploration_weight: number | null;
    mcts_selection: string | null;
    surprisal_width: number | null;
    evidence_weight: number | null;
    warmstart_experiments: string | null;
    n_warmstart: number | null;
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
    run_metadata?: RunMetadataFromApi;
    run_args?: RunArgsFromApi;
}

interface UploadDatasetResponseBody {
    path: string;
    filename: string;
    message: string;
}

interface GenerateUploadUrlRequest {
    filename: string;
    content_type: string;
    file_size_bytes: number;
}

interface GenerateUploadUrlResponse {
    upload_url: string;
    filename: string;
    expires_at_unix: number;
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
    prior: number | null;
    posterior: number | null;
    runtime_ms: number | null;
    hypothesis: string | null;
    analysis: string | null;
    experiment_plan: Record<string, any> | null;
    review: string | null;
    code: string | null;
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

export interface MetadataDatasetFromApi {
    name: string;
    description: string | null;
}

export interface MetadataFromApi {
    name: string;
    description: string | null;
    domain: string | null;
    intent: string | null;
    datasets: MetadataDatasetFromApi[];
}

export interface GetRunMetadataResponseBody {
    runid: string;
    metadata: MetadataFromApi;
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

    async getRunMetadata(runid: string) {
        return this.request<GetRunMetadataResponseBody>({
            url: `${RUNS_URL_PREFIX}/${encodeURIComponent(runid)}/metadata`,
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

    async saveMetadata(runId: string, metadata: RunMetadataFromApi) {
        return this.request<{ path: string; message: string }>({
            url: `${RUNS_URL_PREFIX}/${encodeURIComponent(runId)}/metadata`,
            method: 'POST',
            body: { metadata },
        });
    }

    async saveJobArgs(runId: string, args: Record<string, unknown>) {
        return this.request<{ path: string; message: string }>({
            url: `${RUNS_URL_PREFIX}/${encodeURIComponent(runId)}/args`,
            method: 'POST',
            body: { args },
        });
    }

    async uploadDataset(runId: string, file: File) {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('runid', runId);

        return this.request<UploadDatasetResponseBody>({
            url: `${RUNS_URL_PREFIX}/upload-dataset`,
            method: 'POST',
            body: formData,
        });
    }

    async generateUploadUrl(runId: string, params: GenerateUploadUrlRequest) {
        return this.request<GenerateUploadUrlResponse>({
            url: `${RUNS_URL_PREFIX}/${encodeURIComponent(runId)}/generate-upload-url`,
            method: 'POST',
            body: params,
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
