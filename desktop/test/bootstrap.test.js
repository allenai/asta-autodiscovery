const assert = require('node:assert/strict');
const test = require('node:test');

const { GUEST_PACKAGES, TOOL_MANIFEST, UNIX_PATH_MAX, VM_IMAGE, VM_RUNTIME_SCHEMA, assertSupportedPlatform, buildVmConfig, calculateVmResources, defaultLimaHome, packageSources } = require('../src/bootstrap');

test('bootstrap pins verified Apple Silicon artifacts', () => {
  for (const name of ['uv', 'copilot', 'lima']) {
    assert.equal(TOOL_MANIFEST[name].sha256.length, 64);
    assert.match(TOOL_MANIFEST[name].url, /darwin|Darwin/);
  }
  assert.equal(VM_IMAGE.sha256.length, 64);
  assert.match(VM_IMAGE.url, /ubuntu-24\.04-minimal-cloudimg-arm64/);
});

test('VM configuration preserves host capacity and disables guest networking services', () => {
  const gibibyte = 1024 ** 3;
  assert.deepEqual(calculateVmResources({ logicalCpus: 8, totalMemoryBytes: 16 * gibibyte, freeDiskBytes: 200 * gibibyte }), { cpus: 6, memoryGiB: 10, diskGiB: 100 });
  const config = buildVmConfig({ resources: { cpus: 6, memoryGiB: 10, diskGiB: 40 } });
  assert.match(config, /mounts: \[\]/);
  assert.match(config, /containerd:\n  system: false\n  user: false/);
  assert.match(config, /hostResolver:\n  enabled: false/);
  assert.match(config, new RegExp(VM_IMAGE.sha256));
});

test('platform support is limited to Apple Silicon macOS', () => {
  assert.doesNotThrow(() => assertSupportedPlatform('darwin', 'arm64'));
  assert.throws(() => assertSupportedPlatform('darwin', 'x64'), /Apple Silicon/);
});

test('Lima home leaves room for its Unix socket name', () => {
  const limaHome = defaultLimaHome('/test-home');
  const socketPath = `${limaHome}/ad/ssh.sock.1234567890123456`;
  assert.equal(limaHome, '/test-home/Library/Caches/org.allenai.autodiscovery/lima');
  assert.ok(socketPath.length < UNIX_PATH_MAX);
});

test('VM runtime schema changes when its provisioned contract changes', () => {
  assert.equal(VM_RUNTIME_SCHEMA, 2);
});

test('host environment installs the Copilot provider extra without embedding a payload', () => {
  const sources = packageSources('/application');
  assert.ok(sources.includes('/application/packages/autodiscovery[copilot]'));
  assert.ok(!sources.some((source) => source.includes('payload') || source.includes('offline')));
});

test('VM bootstrap installs its scientific stack without a missing requirements artifact', () => {
  assert.ok(GUEST_PACKAGES.includes('ipython==9.15.0'));
  assert.ok(GUEST_PACKAGES.includes('numpy==2.4.6'));
  assert.ok(GUEST_PACKAGES.includes('scikit-learn==1.9.0'));
  assert.ok(GUEST_PACKAGES.includes('umap-learn==0.5.12'));
  assert.ok(GUEST_PACKAGES.every((packageName) => packageName.includes('==')));
  assert.ok(!GUEST_PACKAGES.some((packageName) => packageName.includes('guest-requirements')));
});