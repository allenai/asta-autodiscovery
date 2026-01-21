'use client';

import { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import { User } from '@auth0/auth0-spa-js';
import { auth0Client, auth0Config } from '@/auth/Auth0Client';

export interface Auth0ContextType {
    isAuthenticated: boolean;
    isLoading: boolean;
    user: User | undefined;
    loginWithRedirect: () => Promise<void>;
    logout: () => void;
    getAccessToken: () => Promise<string>;
    hasRequiredPermission: boolean;
    authError: string | null;
}

const Auth0Context = createContext<Auth0ContextType | undefined>(undefined);

interface Auth0ProviderProps {
    children: ReactNode;
}

export function Auth0Provider({ children }: Auth0ProviderProps) {
    const [isAuthenticated, setIsAuthenticated] = useState(false);
    const [isLoading, setIsLoading] = useState(true);
    const [user, setUser] = useState<User | undefined>(undefined);
    const [hasRequiredPermission, setHasRequiredPermission] = useState(false);
    const [authError, setAuthError] = useState<string | null>(null);

    useEffect(() => {
        const initAuth0 = async () => {
            try {
                if (!auth0Client) {
                    setIsLoading(false);
                    return;
                }

                // Handle redirect callback
                if (
                    window.location.search.includes('code=') &&
                    window.location.search.includes('state=')
                ) {
                    await auth0Client.handleRedirectCallback();
                    window.history.replaceState({}, document.title, window.location.pathname);
                }

                // Check if user is authenticated
                const authenticated = await auth0Client.isAuthenticated();
                setIsAuthenticated(authenticated);

                if (authenticated) {
                    const userProfile = await auth0Client.getUser();
                    setUser(userProfile);

                    // Check for required permission if specified
                    if (auth0Config.requiredPermission) {
                        try {
                            const token = await auth0Client.getTokenSilently();

                            // Decode the access token to get permissions
                            // Note: This is a simple decode, not validation (validation happens on backend)
                            const tokenParts = token.split('.');
                            const payload = JSON.parse(atob(tokenParts[1]));

                            // Permissions are typically in the "permissions" claim
                            const permissions = payload.permissions || [];

                            const hasPermission =
                                Array.isArray(permissions) &&
                                permissions.includes(auth0Config.requiredPermission);
                            setHasRequiredPermission(hasPermission);

                            if (!hasPermission) {
                                setAuthError(
                                    `Access denied. Required permission: ${auth0Config.requiredPermission}`
                                );
                                // Don't auto-logout - let the dialog handle user action
                            }
                        } catch (error) {
                            console.error('Error checking permissions:', error);
                            setAuthError('Failed to verify user permissions');
                        }
                    } else {
                        setHasRequiredPermission(true);
                    }
                }

                setIsLoading(false);
            } catch (error) {
                console.error('Auth0 initialization error:', error);
                setIsLoading(false);
            }
        };

        initAuth0();
    }, [auth0Client]);

    const loginWithRedirect = async () => {
        if (auth0Client) {
            await auth0Client.loginWithRedirect({
                authorizationParams: {
                    redirect_uri: window.location.origin,
                },
            });
        }
    };

    const logout = () => {
        if (auth0Client) {
            auth0Client.logout({
                logoutParams: {
                    returnTo: window.location.origin,
                },
            });
        }
    };

    const getAccessToken = async (): Promise<string> => {
        if (!auth0Client) {
            throw new Error('Auth0 client not initialized');
        }
        return await auth0Client.getTokenSilently();
    };

    return (
        <Auth0Context.Provider
            value={{
                isAuthenticated,
                isLoading,
                user,
                loginWithRedirect,
                logout,
                getAccessToken,
                hasRequiredPermission,
                authError,
            }}>
            {children}
        </Auth0Context.Provider>
    );
}

export function useAuth0(): Auth0ContextType {
    const context = useContext(Auth0Context);
    if (context === undefined) {
        throw new Error('useAuth0 must be used within an Auth0Provider');
    }
    return context;
}
