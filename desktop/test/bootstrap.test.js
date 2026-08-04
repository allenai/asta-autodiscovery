const assert = require('node:assert/strict');
const test = require('node:test');

const { TOOL_MANIFEST, UNIX_PATH_MAX, VM_IMAGE, assertSupportedPlatform, buildVmConfig, calculateVmResources, defaultLimaHome, packageSources } = require('../src/bootstrap');

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
  const limaHome = defaultLimaHome('/Users/zachary.reitz');
  const socketPath = `${limaHome}/ad/ssh.sock.1234567890123456`;
  assert.equal(limaHome, '/Users/zachary.reitz/Library/Caches/org.allenai.autodiscovery/lima');
  assert.ok(socketPath.length < UNIX_PATH_MAX);
});

test('host environment installs the Copilot provider extra without embedding a payload', () => {
  const sources = packageSources('/application');
  assert.ok(sources.includes('/application/packages/autodiscovery[copilot]'));
  assert.ok(!sources.some((source) => source.includes('payload') || source.includes('offline')));
});