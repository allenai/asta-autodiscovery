/// <reference types="vite/client" />

interface ImportMetaEnv {
    readonly VITE_AUTH_PROVIDER?: string;
    readonly VITE_AUTH0_DOMAIN?: string;
    readonly VITE_AUTH0_CLIENT_ID?: string;
    readonly VITE_AUTH0_AUDIENCE?: string;
    readonly VITE_HEAP_PROJECT_ID?: string;
    readonly VITE_ENABLE_ASTA_MARKETING?: string;
}
