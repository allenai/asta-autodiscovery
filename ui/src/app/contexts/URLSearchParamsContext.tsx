'use client';

import {
    createContext,
    PropsWithChildren,
    useCallback,
    useContext,
    useRef,
    useEffect,
} from 'react';
import { useRouter, usePathname, useSearchParams } from 'next/navigation';

interface URLSearchParamsContextValue {
    searchParams: URLSearchParams;
    setSearchParam: (key: string, value: string) => void;
    deleteSearchParam: (key: string) => void;
    getSearchParam: (key: string) => string | null;
}

const URLSearchParamsContext = createContext<URLSearchParamsContextValue | null>(null);

export function useURLSearchParams(): URLSearchParamsContextValue {
    const context = useContext(URLSearchParamsContext);
    if (!context) {
        throw new Error('useURLSearchParams must be used within a URLSearchParamsProvider');
    }
    return context;
}

export function useSearchValue(key: string): string | null {
    const { getSearchParam } = useURLSearchParams();
    return getSearchParam(key);
}

export function URLSearchParamsProvider({ children }: PropsWithChildren) {
    const router = useRouter();
    const pathname = usePathname();
    const searchParams = useSearchParams();
    const updateTimeoutRef = useRef<NodeJS.Timeout | null>(null);

    // Clean up timeout on unmount
    useEffect(() => {
        return () => {
            if (updateTimeoutRef.current) {
                clearTimeout(updateTimeoutRef.current);
            }
        };
    }, []);

    const setSearchParam = useCallback(
        (key: string, value: string) => {
            // Debounce: Clear existing timeout
            if (updateTimeoutRef.current) {
                clearTimeout(updateTimeoutRef.current);
            }

            updateTimeoutRef.current = setTimeout(() => {
                // Read from window.location to avoid recreating callback on every URL change
                const params = new URLSearchParams(window.location.search);
                params.set(key, value);
                router.replace(`${window.location.pathname}?${params.toString()}`, { scroll: false });
            }, 250);
        },
        [router]
    );

    const deleteSearchParam = useCallback(
        (key: string) => {
            // Clear any pending setSearchParam operations to prevent race condition
            if (updateTimeoutRef.current) {
                clearTimeout(updateTimeoutRef.current);
            }

            // No debounce for deletion - immediate feedback
            // Read from window.location to avoid recreating callback on every URL change
            const params = new URLSearchParams(window.location.search);
            params.delete(key);
            const queryString = params.toString();
            router.replace(queryString ? `${window.location.pathname}?${queryString}` : window.location.pathname, {
                scroll: false,
            });
        },
        [router]
    );

    const getSearchParam = useCallback(
        (key: string) => {
            return searchParams.get(key);
        },
        [searchParams]
    );

    return (
        <URLSearchParamsContext.Provider
            value={{ searchParams, setSearchParam, deleteSearchParam, getSearchParam }}>
            {children}
        </URLSearchParamsContext.Provider>
    );
}
