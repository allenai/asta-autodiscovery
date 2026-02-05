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
                const params = new URLSearchParams(searchParams);
                params.set(key, value);
                router.replace(`${pathname}?${params.toString()}`, { scroll: false });
            }, 250);
        },
        [router, pathname, searchParams]
    );

    const deleteSearchParam = useCallback(
        (key: string) => {
            // No debounce for deletion - immediate feedback
            const params = new URLSearchParams(searchParams);
            params.delete(key);
            const queryString = params.toString();
            router.replace(queryString ? `${pathname}?${queryString}` : pathname, {
                scroll: false,
            });
        },
        [router, pathname, searchParams]
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
