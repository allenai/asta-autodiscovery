import { BaseApi } from '@/api/BaseApi';

const USER_URL_PREFIX = '/api/user';

export interface UserFromApi {
    sub: string;
    name: string;
    email: string;
    picture: string;
    email_verified: boolean;
}

export interface GetViewerUserResponseBody {
    user: UserFromApi;
}

export interface ViewerCreditsFromApi {
    granted: number; // Total credits granted to the user
    consumed: number; // Credits consumed on completed jobs
    pending: number; // Credits in started jobs which have yet to complete
    available: number; // Credits available for new jobs, assuming pending jobs are cancelled
}

export interface GetViewerCreditsResponseBody {
    credits: ViewerCreditsFromApi;
}

export interface GetViewerEnrollmentResponseBody {
    enrolled: boolean;
    enrollment_date: string | null;
    status: string | null;
    experiments_count: number | null;
    user_id: string | null;
}

export class UserApi extends BaseApi {
    async getViewer() {
        return this.request<GetViewerUserResponseBody>({
            url: `${USER_URL_PREFIX}/me`,
            method: 'GET',
        });
    }

    async getViewerEnrollmentStatus() {
        return this.request<GetViewerEnrollmentResponseBody>({
            url: `${USER_URL_PREFIX}/me/enrollment-status`,
            method: 'GET',
        });
    }

    async getViewerCredits() {
        return this.request<GetViewerCreditsResponseBody>({
            url: `${USER_URL_PREFIX}/me/credits`,
            method: 'GET',
        });
    }
}

const api = new UserApi();
export const getUserApi = () => api;
