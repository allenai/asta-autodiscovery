'use client';

import {
    createContext,
    PropsWithChildren,
    useCallback,
    useContext,
    useRef,
    useEffect,
} from 'react';
import { useRouter, usePathname, useSearchParams, ReadonlyURLSearchParams } from 'next/navigation';

interface URLSearchParamsContextValue {
    searchParams: ReadonlyURLSearchParams;
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
    const pendingChanges = useRef<Map<string, string>>(new Map());
    const pendingDeletions = useRef<Set<string>>(new Set());

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
            // Accumulate this change
            pendingChanges.current.set(key, value);
            pendingDeletions.current.delete(key); // Remove from deletions if it was marked

            // Debounce: Clear existing timeout
            if (updateTimeoutRef.current) {
                clearTimeout(updateTimeoutRef.current);
            }

            updateTimeoutRef.current = setTimeout(() => {
                // Start with current URL params
                const params = new URLSearchParams(window.location.search);

                // Apply all pending changes
                pendingChanges.current.forEach((val, k) => {
                    params.set(k, val);
                });

                // Apply all pending deletions
                pendingDeletions.current.forEach((k) => {
                    params.delete(k);
                });

                router.replace(`${pathname}?${params.toString()}`, { scroll: false });

                // Clear pending changes
                pendingChanges.current.clear();
                pendingDeletions.current.clear();
            }, 250);
        },
        [router, pathname]
    );

    const deleteSearchParam = useCallback(
        (key: string) => {
            // Accumulate this deletion
            pendingDeletions.current.add(key);
            pendingChanges.current.delete(key); // Remove from changes if it was set

            // Clear any pending timeout to apply changes immediately
            if (updateTimeoutRef.current) {
                clearTimeout(updateTimeoutRef.current);
            }

            // Apply immediately (no debounce for deletions - immediate feedback)
            const params = new URLSearchParams(window.location.search);

            // Apply all pending changes
            pendingChanges.current.forEach((val, k) => {
                params.set(k, val);
            });

            // Apply all pending deletions
            pendingDeletions.current.forEach((k) => {
                params.delete(k);
            });

            const queryString = params.toString();
            router.replace(queryString ? `${pathname}?${queryString}` : pathname, {
                scroll: false,
            });

            // Clear pending changes
            pendingChanges.current.clear();
            pendingDeletions.current.clear();
        },
        [router, pathname]
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
