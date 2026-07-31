'use client';

import { createContext, PropsWithChildren, useContext, useEffect, useMemo, useState } from 'react';

import { getRunsApi, RuntimeConfigResponseBody } from '@/api/RunsApi';

interface RuntimeConfigState {
    config: RuntimeConfigResponseBody | null;
    isLoading: boolean;
    isLocal: boolean;
}

const RuntimeConfigContext = createContext<RuntimeConfigState>({
    config: null,
    isLoading: true,
    isLocal: false,
});

export function RuntimeConfigProvider({ children }: PropsWithChildren) {
    const [config, setConfig] = useState<RuntimeConfigResponseBody | null>(null);
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        getRunsApi()
            .getRuntimeConfig()
            .then(({ data }) => setConfig(data))
            .catch(() => setConfig(null))
            .finally(() => setIsLoading(false));
    }, []);

    const value = useMemo(
        () => ({
            config,
            isLoading,
            isLocal: config?.deployment_mode === 'local',
        }),
        [config, isLoading]
    );

    return <RuntimeConfigContext.Provider value={value}>{children}</RuntimeConfigContext.Provider>;
}

export function useRuntimeConfig(): RuntimeConfigState {
    return useContext(RuntimeConfigContext);
}
