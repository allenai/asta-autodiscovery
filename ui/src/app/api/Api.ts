import { BaseApi } from '@/api/BaseApi';
import { CreateRunResponseBody, GetAllRunsResponseBody } from '@/api/ApiResponse';

const RUNS_URL_PREFIX = '/api/runs';

export class Api extends BaseApi {
    async createRun() {
        return this.request<CreateRunResponseBody>({
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
const api = new Api();
export const getApi = () => api;
