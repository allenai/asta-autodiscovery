const assert = require('node:assert/strict');
const path = require('node:path');
const test = require('node:test');

const { API_ORIGIN, UI_ORIGIN, defaultDataRoot, serviceEnvironment } = require('../src/runtime');

test('desktop services use the local job and Lima execution backends', () => {
  const environment = serviceEnvironment({
    root: '/application',
    runtime: {
      copilotPath: '/runtime/copilot',
      limaHome: '/runtime/lima-home',
      limaPath: '/runtime/limactl',
      uvPath: '/runtime/uv',
    },
    dataRoot: '/test-home/AutoDiscovery',
    userDataRoot: '/test-home/Library/Application Support/AutoDiscovery',
  });

  assert.equal(environment.API_ORIGIN, API_ORIGIN);
  assert.equal(environment.AUTH_PROVIDER, 'none');
  assert.equal(environment.AUTODISCOVERY_LOCAL_ROOT, '/test-home/AutoDiscovery');
  assert.equal(environment.AUTODISCOVERY_COPILOT_HOME, '/test-home/Library/Application Support/AutoDiscovery/copilot');
  assert.equal(environment.AUTODISCOVERY_LIMA_HOME, '/runtime/lima-home');
  assert.equal(environment.AUTODISCOVERY_LIMA_PATH, '/runtime/limactl');
  assert.equal(environment.CODE_EXECUTION_BACKEND, 'lima');
  assert.equal(environment.JOB_BACKEND, 'local');
  assert.equal(environment.AUTODISCOVERY_DEPLOYMENT_MODE, undefined);
  assert.equal(environment.AUTODISCOVERY_EXECUTION_BACKEND, undefined);
  assert.equal(
    environment.PYTHONPATH,
    [
      '/application/api',
      '/application/packages/agents/src',
      '/application/packages/autodiscovery/src',
      '/application/packages/autodiscovery_jobs/src',
      '/application/packages/autodiscovery_modal/src',
      '/application/packages/code_execution/src',
    ].join(path.delimiter),
  );
});

test('desktop defaults keep user datasets in the visible AutoDiscovery directory', () => {
  assert.equal(defaultDataRoot('/test-home'), '/test-home/AutoDiscovery');
  assert.equal(UI_ORIGIN, 'http://127.0.0.1:61552');
});