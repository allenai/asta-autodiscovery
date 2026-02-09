import { BaseApi } from '@/api/BaseApi';

const RUNS_URL_PREFIX = '/api/runs';

export interface RunDetailsFromApi {
    execution_id: string | null;
    created_at: string;
    finished_at: string | null;
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
        content_type: string | null;
        file_size_bytes: number | null;
    }[];
    // Job configuration parameters
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
    status: string;
    name: string;
    userid: string;
    path?: string;
    description?: string;
    run_details?: RunDetailsFromApi;
    run_stats?: RunStatsFromApi;
    execution_status?: Record<string, unknown>;
    run_metadata?: RunMetadataFromApi;
}

export interface UploadDatasetResponseBody {
    path: string;
    filename: string;
    message: string;
}

export interface GenerateUploadUrlResponseBody {
    upload_url: string;
    gcs_path: string;
    filename: string;
    expires_at_unix: number;
}

export interface RunResponseBody extends RunFromApi {}

export interface GetViewerRunsResponseBody {
    runs: RunFromApi[];
}

export interface ExperimentFromApi {
    experiment_id: string;
    parent_id: string | null;
    child_ids: string[] | null;
    creation_idx: number;
    id_in_run: number;
    status: string;
    is_surprising: boolean;
    surprise: number | null;
    prior: number | null;
    posterior: number | null;
    prior_belief?: Record<string, any> | null;
    posterior_belief?: Record<string, any> | null;
    runtime_ms: number | null;
    hypothesis: string | null;
    analysis: string | null;
    experiment_plan: Record<string, any> | null;
    review: string | null;
    code: string | null;
    code_output?: string | null;
    rich_outputs?: Record<string, string>[] | null;
    created_at?: string | null;
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
    content_type: string | null;
    file_size_bytes: number | null;
}

export interface MetadataFromApi {
    name: string;
    description: string | null;
    domain: string | null;
    intent: string | null;
    datasets: MetadataDatasetFromApi[];
    // Job configuration parameters
    n_experiments: number | null;
    exploration_weight: number | null;
    mcts_selection: string | null;
    surprisal_width: number | null;
    evidence_weight: number | null;
    warmstart_experiments: string | null;
    n_warmstart: number | null;
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

    async listRuns({ userid, limit }: { userid?: string; limit?: number } = {}) {
        const effectiveUserid = userid ?? (await this.getUserId());

        const query: Record<string, string> = {};
        if (limit) {
            query.limit = limit.toString();
        }
        return this.request<GetViewerRunsResponseBody>({
            url: `${RUNS_URL_PREFIX}/${encodeURIComponent(effectiveUserid!)}/list`,
            method: 'GET',
            query,
        });
    }

    async getRunMetadata({ userid, runid }: { userid?: string; runid: string }) {
        const effectiveUserid = userid ?? (await this.getUserId());

        return this.request<GetRunMetadataResponseBody>({
            url: `${RUNS_URL_PREFIX}/${encodeURIComponent(effectiveUserid!)}/${encodeURIComponent(runid)}/metadata`,
            method: 'GET',
        });
    }

    async getRunExperiments({
        userid,
        runid,
        afterExperimentId,
    }: {
        userid?: string;
        runid: string;
        afterExperimentId?: string;
    }) {
        const effectiveUserid = userid ?? (await this.getUserId());

        const query: Record<string, string> = {};
        if (afterExperimentId) {
            query.after_experiment_id = afterExperimentId;
        }

        return this.request<GetRunExperimentsResponseBody>({
            url: `${RUNS_URL_PREFIX}/${encodeURIComponent(effectiveUserid!)}/${encodeURIComponent(runid)}/experiments`,
            method: 'GET',
            query,
        });
    }

    async getRunExperimentDetails({
        userid,
        runid,
        experimentId,
    }: {
        userid?: string;
        runid: string;
        experimentId: string;
    }) {
        const effectiveUserid = userid ?? (await this.getUserId());

        return this.request<GetRunExperimentDetailsResponseBody>({
            url: `${RUNS_URL_PREFIX}/${encodeURIComponent(effectiveUserid!)}/${encodeURIComponent(runid)}/experiments/${encodeURIComponent(
                experimentId
            )}`,
            method: 'GET',
        });
    }

    async getRun({ userid, runId }: { userid?: string; runId: string }) {
        const effectiveUserid = userid ?? (await this.getUserId());

        return this.request<RunResponseBody>({
            url: `${RUNS_URL_PREFIX}/${encodeURIComponent(effectiveUserid!)}/${encodeURIComponent(runId)}`,
            method: 'GET',
        });
    }

    async getRunStatus({ userid, runId }: { userid?: string; runId: string }) {
        const effectiveUserid = userid ?? (await this.getUserId());

        return this.request<RunResponseBody>({
            url: `${RUNS_URL_PREFIX}/${encodeURIComponent(effectiveUserid!)}/${encodeURIComponent(runId)}/status`,
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

    async generateUploadUrl({
        runid,
        filename,
        contentType,
        fileSizeBytes,
    }: {
        runid: string;
        filename: string;
        contentType: string;
        fileSizeBytes: number;
    }) {
        return this.request<GenerateUploadUrlResponseBody>({
            url: `${RUNS_URL_PREFIX}/${encodeURIComponent(runid)}/generate-upload-url`,
            method: 'POST',
            body: {
                filename,
                content_type: contentType,
                file_size_bytes: fileSizeBytes,
            },
        });
    }

    async submitRun(runId: string) {
        return this.request<RunResponseBody>({
            url: `${RUNS_URL_PREFIX}/submit`,
            method: 'POST',
            body: { runid: runId },
        });
    }

    async deleteRun(runId: string) {
        return this.request<{ message: string }>({
            url: `${RUNS_URL_PREFIX}/${encodeURIComponent(runId)}`,
            method: 'DELETE',
        });
    }
}
const api = new RunsApi();
export const getRunsApi = () => api;
