import { authBridge } from '@/auth/authBridge';

const DEFAULT_HEADERS = {
    'Content-Type': 'application/json',
} as const;

export class BaseApi {
    /**
     * Get the current authenticated user's ID from the active auth provider.
     * Returns null if not authenticated or if user data is not available.
     */
    protected getUserId = async (): Promise<string | null> => {
        try {
            return await authBridge.getUserId();
        } catch (error) {
            console.error('Error getting user ID:', error);
            return null;
        }
    };

    protected createDefaultHeaders = async (): Promise<{
        'Content-Type': string;
        Authorization?: string;
    }> => {
        // No token means anonymous (public pages) or the "none" desktop provider —
        // send no Authorization header and let the backend decide.
        const token = await authBridge.getToken().catch((error: unknown) => {
            console.error('Error getting access token: ', error);
            return null;
        });

        return {
            ...DEFAULT_HEADERS,
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
        };
    };

    async request<T>({
        url,
        method,
        headers = {},
        query = {},
        body = '',
        shouldThrowOnServerError = true,
        ...options
    }: {
        url: string;
        method: string;
        headers?: Record<string, string>;
        query?: Record<string, string>;
        body?: any;
        shouldThrowOnServerError?: boolean;
        options?: RequestInit;
    }): Promise<{
        response: Response;
        data: T;
    }> {
        let bodyToSend: null | string | FormData = null;
        const isFormData = body instanceof FormData;

        switch (method.toUpperCase()) {
            case 'GET':
            case 'HEAD':
                break;
            default:
                if (isFormData) {
                    bodyToSend = body;
                } else {
                    bodyToSend = typeof body === 'string' ? body : JSON.stringify(body || {});
                }
                break;
        }

        const defaultHeaders = await this.createDefaultHeaders();

        const init: Record<string, any> = {
            method,
            headers: {
                // For FormData, don't include Content-Type header (browser will set it with boundary)
                ...(isFormData ? { Authorization: defaultHeaders.Authorization } : defaultHeaders),
                ...headers,
            },
            body: bodyToSend,
            ...options,
        };

        if (Object.keys(query).length > 0) {
            url += '?' + new URLSearchParams(query).toString();
        }

        const resp = await fetch(url, init);

        // A 401 means the server rejected our credentials. Let the active provider
        // decide how to recover (Auth0 re-login redirect, clear stored session, etc.).
        // Anonymous visitors browsing public pages never get a 401, so they are
        // unaffected.
        if (resp.status === 401) {
            authBridge.onUnauthorized();
        }

        if (!resp.ok) {
            const errorMsg: string | null = await resp
                .json()
                .then((result) => result.error)
                .catch(() => resp.text())
                .catch(() => null);
            if (shouldThrowOnServerError) {
                throw new Error(
                    `Request failed with status ${resp.status}${errorMsg ? `: ${errorMsg}` : ''}`
                );
            }
        }
        const data = await resp.json();
        return {
            response: resp,
            data,
        };
    }
}
