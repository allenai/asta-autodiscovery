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
        url?: string | null;
        is_preloaded?: boolean;
    }[];
    // Sharing
    is_shared?: boolean | null;
    // Bookmarking
    is_bookmarked?: boolean | null;
    bookmarked_experiment_ids?: string[] | null;
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
    max_file_size?: string;
    parent_run_id?: string | null;
    parent_run_name?: string | null;
    dataset_expires_at?: string | null;
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

export interface RunResponseBody extends RunFromApi {
    can_view_datasets: boolean;
}

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
    url?: string | null;
    is_preloaded?: boolean;
}

export interface MetadataFromApi {
    name: string;
    description: string | null;
    domain: string | null;
    intent: string | null;
    datasets: MetadataDatasetFromApi[];
    // Sharing
    is_shared?: boolean | null;
    // Bookmarking
    is_bookmarked?: boolean | null;
    bookmarked_experiment_ids?: string[] | null;
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

export interface ShareRunResponseBody {
    runid: string;
    is_shared: boolean;
}

export interface BookmarkRunResponseBody {
    runid: string;
    is_bookmarked: boolean;
}

export interface BookmarkExperimentResponseBody {
    experiment_id: string;
    is_bookmarked: boolean;
}

export interface GetSharedRunOwnerResponseBody {
    runid: string;
    userid: string;
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
        knownExperimentIds,
    }: {
        userid?: string;
        runid: string;
        knownExperimentIds: string[];
    }) {
        const effectiveUserid = userid ?? (await this.getUserId());

        return this.request<GetRunExperimentsResponseBody>({
            url: `${RUNS_URL_PREFIX}/${encodeURIComponent(effectiveUserid!)}/${encodeURIComponent(runid)}/experiments`,
            method: 'POST',
            body: { known_experiment_ids: knownExperimentIds },
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
        const userid = await this.getUserId();
        return this.request<void>({
            url: `${RUNS_URL_PREFIX}/${encodeURIComponent(userid!)}/${encodeURIComponent(runId)}/cancel`,
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

    async shareRun({ runId, isShared }: { runId: string; isShared: boolean }) {
        const userid = await this.getUserId();
        return this.request<ShareRunResponseBody>({
            url: `${RUNS_URL_PREFIX}/${encodeURIComponent(userid!)}/${encodeURIComponent(runId)}/share`,
            method: 'POST',
            body: { is_shared: isShared },
        });
    }

    async getSharedRunOwner({ runId }: { runId: string }) {
        return this.request<GetSharedRunOwnerResponseBody>({
            url: `${RUNS_URL_PREFIX}/shared/${encodeURIComponent(runId)}/owner`,
            method: 'GET',
        });
    }

    async bookmarkRun({ runId, isBookmarked }: { runId: string; isBookmarked: boolean }) {
        const userid = await this.getUserId();
        return this.request<BookmarkRunResponseBody>({
            url: `${RUNS_URL_PREFIX}/${encodeURIComponent(userid!)}/${encodeURIComponent(runId)}/bookmark`,
            method: 'POST',
            body: { is_bookmarked: isBookmarked },
        });
    }

    async bookmarkExperiment({
        runId,
        experimentId,
        isBookmarked,
    }: {
        runId: string;
        experimentId: string;
        isBookmarked: boolean;
    }) {
        const userid = await this.getUserId();
        return this.request<BookmarkExperimentResponseBody>({
            url: `${RUNS_URL_PREFIX}/${encodeURIComponent(userid!)}/${encodeURIComponent(runId)}/experiments/${encodeURIComponent(experimentId)}/bookmark`,
            method: 'POST',
            body: { is_bookmarked: isBookmarked },
        });
    }
}
const api = new RunsApi();
export const getRunsApi = () => api;
