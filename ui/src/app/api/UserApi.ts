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

/** A top-level directory in the viewer's read-only data library. */
export interface DatalibDirFromApi {
    name: string;
    /** Contents of the directory's README.md (possibly truncated), if it has one */
    description: string | null;
}

export interface GetViewerDatalibResponseBody {
    dirs: DatalibDirFromApi[];
}

export class UserApi extends BaseApi {
    async getViewer() {
        return this.request<GetViewerUserResponseBody>({
            url: `${USER_URL_PREFIX}/me`,
            method: 'GET',
        });
    }

    async getViewerCredits() {
        return this.request<GetViewerCreditsResponseBody>({
            url: `${USER_URL_PREFIX}/me/credits`,
            method: 'GET',
        });
    }

    /** List the viewer's data library directories, which can be mounted read-only into runs. */
    async getViewerDatalib() {
        return this.request<GetViewerDatalibResponseBody>({
            url: `${USER_URL_PREFIX}/me/datalib`,
            method: 'GET',
        });
    }
}

const api = new UserApi();
export const getUserApi = () => api;
