import { fileURLToPath } from 'node:url';

import { defineConfig, mergeConfig, type Plugin } from 'vite';
import { viteSingleFile } from 'vite-plugin-singlefile';

import baseConfig from './vite.config';

// Builds the run view as the standalone HTML report that every AutoDiscovery run
// writes beside its results (see autodiscovery/report.py). The output is package
// data of the asta-autodiscovery Python package, so the job image and the PyPI
// build run this first; `make report-viewer` does it for a source checkout.
//
// Everything is inlined into one index.html: the report is usually opened from
// disk, and browsers refuse module scripts and fonts loaded from file:// URLs.
// The run's own data stays outside, in data.js and figures/ beside the page.
const outDir = fileURLToPath(
    new URL('../packages/autodiscovery/src/autodiscovery/report_viewer', import.meta.url)
);

// The entry is report.html, so the webapp's index.html stays the app's; the
// report ships it under the name a browser opens by default.
const renameToIndexHtml = (): Plugin => ({
    name: 'report-viewer-index-html',
    enforce: 'post',
    generateBundle(_options, bundle) {
        const page = bundle['report.html'];
        if (page) {
            page.fileName = 'index.html';
        }
    },
});

export default mergeConfig(
    baseConfig,
    defineConfig({
        // Nothing from public/ is referenced by the run view.
        publicDir: false,
        plugins: [viteSingleFile({ removeViteModuleLoader: true }), renameToIndexHtml()],
        build: {
            outDir,
            emptyOutDir: true,
            rollupOptions: { input: fileURLToPath(new URL('./report.html', import.meta.url)) },
        },
    })
);
