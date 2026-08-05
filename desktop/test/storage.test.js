const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');

const { prepareDataRoot } = require('../src/storage');

test('prepares the visible AutoDiscovery data directory without hidden migration state', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'autodiscovery-desktop-'));
  const dataRoot = path.join(root, 'AutoDiscovery');

  assert.equal(prepareDataRoot(dataRoot), dataRoot);
  assert.equal(fs.existsSync(path.join(dataRoot, 'data')), true);
  assert.equal(fs.existsSync(path.join(root, '.autodiscovery')), false);

  fs.rmSync(root, { recursive: true, force: true });
});