'use client';

import React, { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import { Auth0Client, User } from '@auth0/auth0-spa-js';

interface Auth0ContextType {
    isAuthenticated: boolean;
    isLoading: boolean;
    user: User | undefined;
    loginWithRedirect: () => Promise<void>;
    logout: () => void;
    getAccessToken: () => Promise<string>;
}

const Auth0Context = createContext<Auth0ContextType | undefined>(undefined);

interface Auth0ProviderProps {
    children: ReactNode;
    domain: string;
    clientId: string;
    audience: string;
    redirectUri?: string;
}

export function Auth0Provider({
    children,
    domain,
    clientId,
    audience,
    redirectUri
}: Auth0ProviderProps) {
    const [auth0Client, setAuth0Client] = useState<Auth0Client | null>(null);
    const [isAuthenticated, setIsAuthenticated] = useState(false);
    const [isLoading, setIsLoading] = useState(true);
    const [user, setUser] = useState<User | undefined>(undefined);

    useEffect(() => {
        const initAuth0 = async () => {
            try {
                const client = new Auth0Client({
                    domain,
                    clientId,
                    cacheLocation: 'localstorage',
                    useRefreshTokens: true,
                    authorizationParams: {
                        redirect_uri: redirectUri || window.location.origin,
                        audience,
                        scope: 'openid profile email offline_access',
                    }
                });

                setAuth0Client(client);

                // Handle redirect callback
                if (window.location.search.includes('code=') && window.location.search.includes('state=')) {
                    await client.handleRedirectCallback();
                    window.history.replaceState({}, document.title, window.location.pathname);
                }

                // Check if user is authenticated
                const authenticated = await client.isAuthenticated();
                setIsAuthenticated(authenticated);

                if (authenticated) {
                    const userProfile = await client.getUser();
                    setUser(userProfile);
                }

                setIsLoading(false);
            } catch (error) {
                console.error('Auth0 initialization error:', error);
                setIsLoading(false);
            }
        };

        initAuth0();
    }, [domain, clientId, audience, redirectUri]);

    const loginWithRedirect = async () => {
        if (auth0Client) {
            await auth0Client.loginWithRedirect();
        }
    };

    const logout = () => {
        if (auth0Client) {
            auth0Client.logout({
                logoutParams: {
                    returnTo: window.location.origin
                }
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
                getAccessToken
            }}
        >
            {children}
        </Auth0Context.Provider>
    );
}

export function useAuth0() {
    const context = useContext(Auth0Context);
    if (context === undefined) {
        throw new Error('useAuth0 must be used within an Auth0Provider');
    }
    return context;
}
