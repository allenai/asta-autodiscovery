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
    credits: ViewerCreditsFromApi | null; // null when credit tracking is disabled
}

/**
 * Which data library a directory belongs to: `global` directories are shared with
 * all users, `user` directories are the viewer's own. A global and a user directory
 * may have the same name.
 */
export type DatalibScope = 'global' | 'user';

/** A top-level directory in the viewer's read-only data library. */
export interface DatalibDirFromApi {
    name: string;
    /** Contents of the directory's README.md (possibly truncated), if it has one */
    description: string | null;
    /** Absent from older API responses, which only listed user directories */
    scope?: DatalibScope;
    /**
     * Files by extension (lowercase, no dot; `""` for none), most common first. Counts
     * cover at most a capped number of files; see `file_count_capped`.
     */
    file_types?: { ext: string; count: number }[];
    /** Number of files counted (excluding the top-level README.md) */
    file_count?: number;
    /** True when the directory holds more files than were counted */
    file_count_capped?: boolean;
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

    /**
     * List the data library directories the viewer can mount read-only into runs:
     * global (shared) directories first, then the viewer's own.
     */
    async getViewerDatalib() {
        return this.request<GetViewerDatalibResponseBody>({
            url: `${USER_URL_PREFIX}/me/datalib`,
            method: 'GET',
        });
    }
}

const api = new UserApi();
export const getUserApi = () => api;
