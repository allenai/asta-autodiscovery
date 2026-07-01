'use client';

import {
    createContext,
    useCallback,
    useContext,
    useEffect,
    useMemo,
    useState,
    ReactNode,
} from 'react';

import { createAuth0Client } from '@/auth/Auth0Client';
import { setAuthBridge } from '@/auth/authBridge';
import { AuthConfig, decodeJwtPayload, fetchAuthConfig } from '@/auth/authConfig';
import LoginDialog from '@/components/LoginDialog';

export interface AuthUser {
    sub?: string;
    name?: string;
    email?: string;
    picture?: string;
    email_verified?: boolean;
}

export interface AuthContextType {
    isAuthenticated: boolean;
    isLoading: boolean;
    user: AuthUser | undefined;
    permissions: string[];
    hasPermission: (permission: string) => boolean;
    /** Provider-agnostic login. Auth0 redirects (creds ignored); password_file uses creds. */
    login: (creds?: { username: string; password: string }) => Promise<void>;
    /** Back-compat alias for Auth0 redirect login. */
    loginWithRedirect: () => Promise<void>;
    logout: () => void;
    getAccessToken: () => Promise<string>;
    hasRequiredPermission: boolean;
    canExploreWithAsta: boolean;
    authError: string | null;
    /** Which provider is active, once known. */
    provider: AuthConfig['provider'] | null;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const ASTA_PERMISSION = 'enroll:asta_integration';
const SESSION_STORAGE_KEY = 'ad_session_token';

// ---------------------------------------------------------------------------
// Top-level selector: fetch runtime config, then mount the matching provider.
// Exported as Auth0Provider to preserve the existing import in ClientProviders.
// ---------------------------------------------------------------------------
export function Auth0Provider({ children }: { children: ReactNode }) {
    const [config, setConfig] = useState<AuthConfig | null>(null);

    useEffect(() => {
        fetchAuthConfig().then(setConfig);
    }, []);

    if (!config) {
        return <LoadingAuthProvider>{children}</LoadingAuthProvider>;
    }
    switch (config.provider) {
        case 'none':
            return <NoneAuthProvider>{children}</NoneAuthProvider>;
        case 'password_file':
            return <PasswordFileAuthProvider config={config}>{children}</PasswordFileAuthProvider>;
        case 'auth0':
        default:
            return <Auth0AuthProvider config={config}>{children}</Auth0AuthProvider>;
    }
}

// While the runtime config is in flight, report loading so consumers wait.
function LoadingAuthProvider({ children }: { children: ReactNode }) {
    const value = useMemo<AuthContextType>(
        () => ({
            isAuthenticated: false,
            isLoading: true,
            user: undefined,
            permissions: [],
            hasPermission: () => false,
            login: async () => {},
            loginWithRedirect: async () => {},
            logout: () => {},
            getAccessToken: async () => '',
            hasRequiredPermission: false,
            canExploreWithAsta: false,
            authError: null,
            provider: null,
        }),
        []
    );
    return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// ---------------------------------------------------------------------------
// Auth0 provider (parity with the previous implementation).
// ---------------------------------------------------------------------------
function Auth0AuthProvider({ config, children }: { config: AuthConfig; children: ReactNode }) {
    const [client] = useState(() => createAuth0Client(config));

    const [isAuthenticated, setIsAuthenticated] = useState(false);
    const [isLoading, setIsLoading] = useState(true);
    const [user, setUser] = useState<AuthUser | undefined>(undefined);
    const [permissions, setPermissions] = useState<string[]>([]);
    const [authError, setAuthError] = useState<string | null>(null);

    useEffect(() => {
        const init = async () => {
            try {
                if (!client) {
                    setIsLoading(false);
                    return;
                }
                if (
                    window.location.search.includes('code=') &&
                    window.location.search.includes('state=')
                ) {
                    const result = await client.handleRedirectCallback();
                    const targetUrl = result.appState?.returnTo || window.location.pathname;
                    window.location.replace(targetUrl);
                }

                const authenticated = await client.isAuthenticated();
                setIsAuthenticated(authenticated);

                if (authenticated) {
                    setUser(await client.getUser());
                    try {
                        const token = await client.getTokenSilently();
                        const payload = decodeJwtPayload(token);
                        const perms: string[] = Array.isArray(payload?.permissions)
                            ? (payload!.permissions as string[])
                            : [];
                        setPermissions(perms);
                        if (
                            config.requiredPermission &&
                            !perms.includes(config.requiredPermission)
                        ) {
                            setAuthError(
                                `Access denied. Required permission: ${config.requiredPermission}`
                            );
                        }
                    } catch (error) {
                        console.error('Error checking permissions:', error);
                        setAuthError('Failed to verify user permissions');
                    }
                }
                setIsLoading(false);
            } catch (error) {
                console.error('Auth0 initialization error:', error);
                setIsLoading(false);
            }
        };
        init();
    }, [client, config.requiredPermission]);

    const loginWithRedirect = useCallback(async () => {
        if (client) {
            await client.loginWithRedirect({
                authorizationParams: { redirect_uri: window.location.origin },
                appState: { returnTo: window.location.pathname + window.location.search },
            });
        }
    }, [client]);

    const logout = useCallback(() => {
        client?.logout({ logoutParams: { returnTo: window.location.origin } });
    }, [client]);

    const getAccessToken = useCallback(async (): Promise<string> => {
        if (!client) {
            throw new Error('Auth0 client not initialized');
        }
        return client.getTokenSilently();
    }, [client]);

    // Wire the bridge so BaseApi can attach tokens without importing Auth0.
    useEffect(() => {
        setAuthBridge({
            getToken: async () => {
                if (!client) return null;
                const u = await client.getUser();
                if (!u) return null;
                return client.getTokenSilently().catch(() => null);
            },
            getUserId: async () => (client ? (await client.getUser())?.sub ?? null : null),
            onUnauthorized: () => {
                client?.getUser().then((u) => {
                    if (u) loginWithRedirect();
                });
            },
        });
    }, [client, loginWithRedirect]);

    const hasRequiredPermission = config.requiredPermission
        ? permissions.includes(config.requiredPermission)
        : true;

    const value = useAuthValue({
        isAuthenticated,
        isLoading,
        user,
        permissions,
        login: loginWithRedirect,
        loginWithRedirect,
        logout,
        getAccessToken,
        hasRequiredPermission,
        authError,
        provider: 'auth0',
    });
    return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// ---------------------------------------------------------------------------
// Password-file provider: login form -> /api/auth/login -> stored bearer token.
// ---------------------------------------------------------------------------
function PasswordFileAuthProvider({
    config,
    children,
}: {
    config: AuthConfig;
    children: ReactNode;
}) {
    const [token, setToken] = useState<string | null>(null);
    const [user, setUser] = useState<AuthUser | undefined>(undefined);
    const [permissions, setPermissions] = useState<string[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [authError, setAuthError] = useState<string | null>(null);
    const [showLogin, setShowLogin] = useState(false);

    const applyToken = useCallback((value: string | null) => {
        if (!value) {
            setToken(null);
            setUser(undefined);
            setPermissions([]);
            return;
        }
        const payload = decodeJwtPayload(value);
        const exp = typeof payload?.exp === 'number' ? (payload.exp as number) : 0;
        if (!payload || (exp && exp * 1000 < Date.now())) {
            window.localStorage.removeItem(SESSION_STORAGE_KEY);
            setToken(null);
            setUser(undefined);
            setPermissions([]);
            return;
        }
        setToken(value);
        setUser({
            sub: payload.sub as string | undefined,
            name: payload.name as string | undefined,
            email: payload.email as string | undefined,
        });
        setPermissions(Array.isArray(payload.permissions) ? (payload.permissions as string[]) : []);
    }, []);

    // Restore any existing session on mount.
    useEffect(() => {
        applyToken(window.localStorage.getItem(SESSION_STORAGE_KEY));
        setIsLoading(false);
    }, [applyToken]);

    const login = useCallback(
        async (creds?: { username: string; password: string }) => {
            if (!creds) {
                throw new Error('Username and password are required');
            }
            setAuthError(null);
            const resp = await fetch('/api/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(creds),
            });
            if (!resp.ok) {
                const message =
                    (await resp
                        .json()
                        .then((d) => d.error)
                        .catch(() => null)) || 'Login failed';
                setAuthError(message);
                throw new Error(message);
            }
            const data = await resp.json();
            window.localStorage.setItem(SESSION_STORAGE_KEY, data.token);
            applyToken(data.token);
        },
        [applyToken]
    );

    const logout = useCallback(() => {
        window.localStorage.removeItem(SESSION_STORAGE_KEY);
        applyToken(null);
    }, [applyToken]);

    // Interactive login trigger (used by AuthButton / IntroBox): open the form.
    const loginWithRedirect = useCallback(async () => {
        setAuthError(null);
        setShowLogin(true);
    }, []);

    const getAccessToken = useCallback(async (): Promise<string> => {
        if (!token) {
            throw new Error('Not authenticated');
        }
        return token;
    }, [token]);

    useEffect(() => {
        setAuthBridge({
            getToken: async () => token,
            getUserId: async () => user?.sub ?? null,
            onUnauthorized: () => logout(),
        });
    }, [token, user, logout]);

    const hasRequiredPermission = config.requiredPermission
        ? permissions.includes(config.requiredPermission)
        : true;

    const value = useAuthValue({
        isAuthenticated: !!token,
        isLoading,
        user,
        permissions,
        login,
        loginWithRedirect,
        logout,
        getAccessToken,
        hasRequiredPermission,
        authError,
        provider: 'password_file',
    });
    return (
        <AuthContext.Provider value={value}>
            {children}
            <LoginDialog
                open={showLogin}
                onClose={() => setShowLogin(false)}
                error={authError}
                onSubmit={async (creds) => {
                    await login(creds);
                    setShowLogin(false);
                }}
            />
        </AuthContext.Provider>
    );
}

// ---------------------------------------------------------------------------
// "none" provider: desktop mode — always authenticated as the local user.
// ---------------------------------------------------------------------------
const LOCAL_USER: AuthUser = {
    sub: 'local',
    name: 'Local User',
    email: 'local@localhost',
    email_verified: true,
};

function NoneAuthProvider({ children }: { children: ReactNode }) {
    useEffect(() => {
        setAuthBridge({
            getToken: async () => null,
            getUserId: async () => LOCAL_USER.sub ?? null,
            onUnauthorized: () => {},
        });
    }, []);

    const value = useMemo<AuthContextType>(
        () => ({
            isAuthenticated: true,
            isLoading: false,
            user: LOCAL_USER,
            permissions: [],
            hasPermission: () => true, // desktop mode unlocks everything
            login: async () => {},
            loginWithRedirect: async () => {},
            logout: () => {},
            getAccessToken: async () => '',
            hasRequiredPermission: true,
            canExploreWithAsta: true,
            authError: null,
            provider: 'none',
        }),
        []
    );
    return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// Shared assembly of the context value (memoized) for the auth0/password_file paths.
function useAuthValue(
    parts: Omit<AuthContextType, 'hasPermission' | 'canExploreWithAsta'>
): AuthContextType {
    const {
        isAuthenticated,
        isLoading,
        user,
        permissions,
        login,
        loginWithRedirect,
        logout,
        getAccessToken,
        hasRequiredPermission,
        authError,
        provider,
    } = parts;
    return useMemo<AuthContextType>(() => {
        const hasPermission = (permission: string) => permissions.includes(permission);
        return {
            isAuthenticated,
            isLoading,
            user,
            permissions,
            hasPermission,
            login,
            loginWithRedirect,
            logout,
            getAccessToken,
            hasRequiredPermission,
            canExploreWithAsta: hasPermission(ASTA_PERMISSION),
            authError,
            provider,
        };
    }, [
        isAuthenticated,
        isLoading,
        user,
        permissions,
        login,
        loginWithRedirect,
        logout,
        getAccessToken,
        hasRequiredPermission,
        authError,
        provider,
    ]);
}

export function useAuth0(): AuthContextType {
    const context = useContext(AuthContext);
    if (context === undefined) {
        throw new Error('useAuth0 must be used within an Auth0Provider');
    }
    return context;
}

/** Provider-agnostic alias preferred for new code. */
export const useAuth = useAuth0;
