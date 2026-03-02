import { auth0Client } from '@/auth/Auth0Client';

const DEFAULT_HEADERS = {
    'Content-Type': 'application/json',
} as const;

export class BaseApi {
    /**
     * Get the current authenticated user's ID from Auth0.
     * Returns null if not authenticated or if user data is not available.
     */
    protected getUserId = async (): Promise<string | null> => {
        if (!auth0Client) {
            return null;
        }

        try {
            const user = await auth0Client.getUser();
            return user?.sub ?? null;
        } catch (error) {
            console.error('Error getting user ID:', error);
            return null;
        }
    };

    protected createDefaultHeaders = async (): Promise<{
        'Content-Type': string;
        Authorization?: string;
    }> => {
        if (!auth0Client) {
            return DEFAULT_HEADERS;
        }

        const client = auth0Client;
        const token = await client.getTokenSilently().catch((error: unknown) => {
            console.error('Error getting token: ', error);
            // Session is unrecoverable — send the user back through login, preserving their
            // current location so they land back where they were after re-authenticating.
            const message = error instanceof Error ? error.message : String(error);
            if (
                message.includes('Missing Refresh Token') ||
                message.includes('login_required') ||
                message.includes('consent_required')
            ) {
                client.loginWithRedirect({
                    appState: { returnTo: window.location.pathname + window.location.search },
                });
            }
            return undefined;
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
