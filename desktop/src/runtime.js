const os = require('node:os');
const path = require('node:path');

const API_PORT = 61551;
const UI_PORT = 61552;
const API_ORIGIN = `http://127.0.0.1:${API_PORT}`;
const UI_ORIGIN = `http://127.0.0.1:${UI_PORT}`;

function serviceEnvironment({ root, runtime, dataRoot, userDataRoot }) {
  const packageNames = [
    'agents',
    'autodiscovery',
    'autodiscovery_jobs',
    'autodiscovery_modal',
    'code_execution',
  ];
  return {
    ...process.env,
    API_ORIGIN,
    AUTH_PROVIDER: 'none',
    AUTODISCOVERY_COPILOT_HOME: path.join(userDataRoot, 'copilot'),
    AUTODISCOVERY_LIMA_HOME: runtime.limaHome,
    AUTODISCOVERY_LIMA_PATH: runtime.limaPath,
    AUTODISCOVERY_LOCAL_ROOT: dataRoot,
    CODE_EXECUTION_BACKEND: 'lima',
    COPILOT_CLI_PATH: runtime.copilotPath,
    JOB_BACKEND: 'local',
    PATH: `${path.dirname(runtime.uvPath)}:${path.dirname(runtime.copilotPath)}:${process.env.PATH || ''}`,
    PYTHONPATH: [
      path.join(root, 'api'),
      ...packageNames.map((name) => path.join(root, 'packages', name, 'src')),
    ].join(path.delimiter),
    PYTHONUNBUFFERED: '1',
    UV_CACHE_DIR: path.join(userDataRoot, 'uv-cache'),
  };
}

function defaultDataRoot(homeDirectory = os.homedir()) {
  return path.join(homeDirectory, 'AutoDiscovery');
}

module.exports = { API_ORIGIN, API_PORT, UI_ORIGIN, UI_PORT, defaultDataRoot, serviceEnvironment };