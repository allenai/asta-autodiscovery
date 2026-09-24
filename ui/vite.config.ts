import { fileURLToPath } from 'node:url';

import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
    plugins: [react()],
    resolve: {
        alias: { '@': fileURLToPath(new URL('./src/app', import.meta.url)) },
    },
    server: {
        host: true,
        port: 3000,
        // Behind the local nginx proxy the browser reaches HMR on :8080, not :3000.
        hmr: process.env.VITE_HMR_CLIENT_PORT
            ? { clientPort: Number(process.env.VITE_HMR_CLIENT_PORT) }
            : undefined,
    },
    preview: { host: true, port: 3000 },
});
