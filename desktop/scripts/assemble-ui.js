const fs = require('node:fs');
const path = require('node:path');

const uiRoot = path.resolve(__dirname, '..', '..', 'ui');
const standalone = path.join(uiRoot, '.next', 'standalone');

if (!fs.existsSync(path.join(standalone, 'server.js'))) throw new Error('Next standalone server was not generated');
fs.rmSync(path.join(standalone, '.next', 'static'), { recursive: true, force: true });
fs.cpSync(path.join(uiRoot, '.next', 'static'), path.join(standalone, '.next', 'static'), { recursive: true });
fs.rmSync(path.join(standalone, 'public'), { recursive: true, force: true });
fs.cpSync(path.join(uiRoot, 'public'), path.join(standalone, 'public'), { recursive: true });
const nodeModules = path.join(standalone, 'node_modules');
const runtimeModules = path.join(standalone, 'runtime_modules');
if (fs.existsSync(nodeModules)) {
  fs.rmSync(runtimeModules, { recursive: true, force: true });
  fs.renameSync(nodeModules, runtimeModules);
} else if (!fs.existsSync(runtimeModules)) throw new Error('Next standalone runtime dependencies were not generated');