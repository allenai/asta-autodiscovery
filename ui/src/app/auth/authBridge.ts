/**
 * Decouples non-React modules (e.g. BaseApi) from any specific auth provider.
 *
 * The active provider populates these functions when it mounts; callers read
 * through the bridge without knowing which provider is in use. Defaults are
 * safe no-ops so public/anonymous flows work before a provider initializes.
 */
export interface AuthBridge {
    /** Current access token, or null when none (anonymous / "none" provider). */
    getToken: () => Promise<string | null>;
    /** Current user id (sub), or null when not authenticated. */
    getUserId: () => Promise<string | null>;
    /** Invoked when the API returns 401 (e.g. redirect to login / clear session). */
    onUnauthorized: () => void;
}

export const authBridge: AuthBridge = {
    getToken: async () => null,
    getUserId: async () => null,
    onUnauthorized: () => {},
};

/** Called by the active provider to wire its implementation into the bridge. */
export function setAuthBridge(impl: Partial<AuthBridge>): void {
    Object.assign(authBridge, impl);
}
