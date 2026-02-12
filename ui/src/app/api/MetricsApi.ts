import { BaseApi } from '@/api/BaseApi';
import type {
    AggregatedUsageResponse,
    CacheStatusResponse,
    OverviewMetrics,
    RunMetrics,
    UserDetailMetrics,
    UsersListResponse,
} from '@/types/Metrics';

const METRICS_URL_PREFIX = '/api/metrics';

export class MetricsApi extends BaseApi {
    async getOverview(params?: { startDate?: string; endDate?: string }) {
        const query: Record<string, string> = {};
        if (params?.startDate) query.start_date = params.startDate;
        if (params?.endDate) query.end_date = params.endDate;

        return this.request<OverviewMetrics>({
            url: `${METRICS_URL_PREFIX}/overview`,
            method: 'GET',
            query,
        });
    }

    async getUsers(params?: { startDate?: string; endDate?: string }) {
        const query: Record<string, string> = {};
        if (params?.startDate) query.start_date = params.startDate;
        if (params?.endDate) query.end_date = params.endDate;

        return this.request<UsersListResponse>({
            url: `${METRICS_URL_PREFIX}/users`,
            method: 'GET',
            query,
        });
    }

    async getUserDetail(userid: string) {
        return this.request<UserDetailMetrics>({
            url: `${METRICS_URL_PREFIX}/users/${encodeURIComponent(userid)}`,
            method: 'GET',
        });
    }

    async getRunMetrics(userid: string, runid: string) {
        return this.request<RunMetrics>({
            url: `${METRICS_URL_PREFIX}/runs/${encodeURIComponent(userid)}/${encodeURIComponent(runid)}`,
            method: 'GET',
        });
    }

    async getAggregatedUsage(params?: { startDate?: string; endDate?: string }) {
        const query: Record<string, string> = {};
        if (params?.startDate) query.start_date = params.startDate;
        if (params?.endDate) query.end_date = params.endDate;

        return this.request<AggregatedUsageResponse>({
            url: `${METRICS_URL_PREFIX}/usage/aggregated`,
            method: 'GET',
            query,
        });
    }

    async getCacheStatus() {
        return this.request<CacheStatusResponse>({
            url: `${METRICS_URL_PREFIX}/cache/status`,
            method: 'GET',
        });
    }

    async refreshCache() {
        return this.request<{ status: string }>({
            url: `${METRICS_URL_PREFIX}/cache/refresh`,
            method: 'POST',
        });
    }
}

const api = new MetricsApi();
export const getMetricsApi = () => api;
