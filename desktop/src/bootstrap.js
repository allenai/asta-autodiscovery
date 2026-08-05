const crypto = require('node:crypto');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { Readable } = require('node:stream');
const { pipeline } = require('node:stream/promises');
const { spawn } = require('node:child_process');

const TOOL_MANIFEST = {
  uv: { version: '0.9.25', url: 'https://github.com/astral-sh/uv/releases/download/0.9.25/uv-aarch64-apple-darwin.tar.gz', sha256: '606b3c6949d971709f2526fa0d9f0fd23ccf60e09f117999b406b424af18a6a6', executable: 'uv-aarch64-apple-darwin/uv' },
  copilot: { version: '1.0.75', url: 'https://github.com/github/copilot-cli/releases/download/v1.0.75/copilot-darwin-arm64.tar.gz', sha256: 'a5ede0d96dbb6cfff8bed0f6872ac3eb05bf0a4ed342d44a0a6548cb242713c2', executable: 'copilot' },
  lima: { version: '2.2.0', url: 'https://github.com/lima-vm/lima/releases/download/v2.2.0/lima-2.2.0-Darwin-arm64.tar.gz', sha256: 'bbdef91774885a0d05f7b048c4eb89ae2bcf3a0c252ae7ca7934e63df76d93c3', executable: 'bin/limactl' },
};
const PYTHON_VERSION = '3.13.1';
const VM_INSTANCE_NAME = 'ad';
const VM_RUNTIME_SCHEMA = 2;
const UNIX_PATH_MAX = 104;
const VM_IMAGE = { url: 'https://cloud-images.ubuntu.com/minimal/releases/noble/release-20260716/ubuntu-24.04-minimal-cloudimg-arm64.img', sha256: '7e938df669e3b1923595eeda97aa28569350c5283e05a835cc912a2486a54934' };
const GUEST_UV = { version: '0.9.25', url: 'https://github.com/astral-sh/uv/releases/download/0.9.25/uv-aarch64-unknown-linux-gnu.tar.gz', sha256: 'a8f1d71a42c4470251a880348b2d28d530018693324175084fa1749d267c98c6' };
const GUEST_PACKAGES = [
  'ipython==9.15.0',
  'numpy==2.4.6',
  'pandas==3.0.5',
  'matplotlib==3.11.1',
  'matplotlib-inline==0.2.2',
  'seaborn==0.13.2',
  'scikit-learn==1.9.0',
  'scipy==1.18.0',
  'statsmodels==0.14.6',
  'openpyxl==3.1.5',
  'umap-learn==0.5.12',
];

function assertSupportedPlatform(platform = process.platform, arch = process.arch) {
  if (platform !== 'darwin' || arch !== 'arm64') throw new Error('This AutoDiscovery build requires Apple Silicon macOS.');
}

function calculateVmResources({ logicalCpus, totalMemoryBytes, freeDiskBytes }) {
  const gibibyte = 1024 ** 3;
  const totalMemoryGiB = Math.floor(totalMemoryBytes / gibibyte);
  return { cpus: Math.max(2, logicalCpus - 2), memoryGiB: Math.max(4, totalMemoryGiB - Math.max(6, Math.ceil(totalMemoryGiB * 0.25))), diskGiB: Math.max(20, Math.min(100, Math.floor(freeDiskBytes / gibibyte * 0.5))) };
}

function defaultLimaHome(homeDirectory = os.homedir()) {
  return path.join(homeDirectory, 'Library', 'Caches', 'org.allenai.autodiscovery', 'lima');
}

function shellQuote(value) {
  return `'${String(value).replaceAll("'", `"'"'`)}'`;
}

function buildVmConfig({ resources }) {
  const provision = [
    '#!/bin/bash', 'set -eux -o pipefail', 'if [ -f /opt/.autodiscovery-base-ready ]; then exit 0; fi', 'export DEBIAN_FRONTEND=noninteractive', 'apt-get update', 'apt-get install -y --no-install-recommends ca-certificates curl', 'mkdir -p /opt/uv', `curl --fail --location --silent --show-error ${shellQuote(GUEST_UV.url)} -o /tmp/uv.tar.gz`, `echo ${shellQuote(`${GUEST_UV.sha256}  /tmp/uv.tar.gz`)} | sha256sum --check --status`, 'tar -xzf /tmp/uv.tar.gz -C /opt/uv --strip-components=1', `/opt/uv/uv python install ${PYTHON_VERSION} --install-dir /opt/autodiscovery-python --no-progress`, `/opt/uv/uv venv /opt/autodiscovery-venv --python /opt/autodiscovery-python/cpython-${PYTHON_VERSION}-linux-aarch64-gnu/bin/python3.13 --seed`, 'chmod -R a+rX /opt/uv /opt/autodiscovery-python /opt/autodiscovery-venv', 'rm -rf /tmp/uv.tar.gz /root/.cache/uv /var/lib/apt/lists/*', 'touch /opt/.autodiscovery-base-ready',
  ];
  return ['vmType: vz', 'arch: aarch64', 'images:', `- location: ${JSON.stringify(VM_IMAGE.url)}`, '  arch: aarch64', `  digest: ${JSON.stringify(`sha256:${VM_IMAGE.sha256}`)}`, '  variant: minimal', `cpus: ${resources.cpus}`, `memory: ${resources.memoryGiB}GiB`, `disk: ${resources.diskGiB}GiB`, 'mountType: virtiofs', 'mounts: []', 'containerd:', '  system: false', '  user: false', 'hostResolver:', '  enabled: false', 'provision:', '- mode: system', '  script: |', ...provision.map((line) => `    ${line}`), ''].join('\n');
}

function run(command, args, options = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, { ...options, env: options.env || process.env, stdio: ['ignore', 'pipe', 'pipe'] });
    let stdout = '';
    let stderr = '';
    child.stdout.on('data', (chunk) => { stdout += chunk; options.onOutput?.(chunk.toString()); });
    child.stderr.on('data', (chunk) => { stderr += chunk; options.onOutput?.(chunk.toString()); });
    child.on('error', reject);
    child.on('exit', (code) => code === 0 ? resolve({ stdout, stderr }) : reject(new Error(`${path.basename(command)} exited ${code}: ${stderr || stdout}`)));
  });
}

async function sha256File(filePath) {
  const hash = crypto.createHash('sha256');
  await pipeline(fs.createReadStream(filePath), hash);
  return hash.digest('hex');
}

async function downloadFile(url, destination) {
  const response = await fetch(url, { redirect: 'follow' });
  if (!response.ok || !response.body) throw new Error(`Download failed (${response.status}): ${url}`);
  fs.mkdirSync(path.dirname(destination), { recursive: true });
  const partial = `${destination}.partial`;
  await pipeline(Readable.fromWeb(response.body), fs.createWriteStream(partial, { mode: 0o600 }));
  fs.renameSync(partial, destination);
}

async function ensureTool(name, runtimeRoot, status) {
  const manifest = TOOL_MANIFEST[name];
  const toolRoot = path.join(runtimeRoot, 'tools', `${name}-${manifest.version}`);
  const executable = path.join(toolRoot, manifest.executable);
  if (fs.existsSync(executable)) return executable;
  const archive = path.join(runtimeRoot, 'downloads', `${name}-${manifest.version}.tar.gz`);
  status(`Downloading ${name}...`);
  await downloadFile(manifest.url, archive);
  if (await sha256File(archive) !== manifest.sha256) throw new Error(`Integrity check failed for ${name}`);
  const temporary = `${toolRoot}.installing`;
  fs.rmSync(temporary, { recursive: true, force: true });
  fs.mkdirSync(temporary, { recursive: true });
  await run('/usr/bin/tar', ['-xzf', archive, '-C', temporary]);
  fs.rmSync(toolRoot, { recursive: true, force: true });
  fs.renameSync(temporary, toolRoot);
  fs.chmodSync(executable, 0o755);
  fs.rmSync(archive, { force: true });
  return executable;
}

function packageSources(resourceRoot) {
  const names = ['agents', 'autodiscovery_jobs', 'autodiscovery_modal', 'code_execution'];
  return [...names.map((name) => path.join(resourceRoot, 'packages', name)), `${path.join(resourceRoot, 'packages', 'autodiscovery')}[copilot]`];
}

async function ensurePythonEnvironment({ uvPath, runtimeRoot, resourceRoot, appVersion, status }) {
  const environmentRoot = path.join(runtimeRoot, 'python-environment');
  const pythonPath = path.join(environmentRoot, 'bin', 'python');
  const markerPath = path.join(environmentRoot, '.autodiscovery-runtime.json');
  const expectedMarker = { appVersion, python: PYTHON_VERSION, uv: TOOL_MANIFEST.uv.version };
  try { if (JSON.stringify(JSON.parse(fs.readFileSync(markerPath, 'utf8'))) === JSON.stringify(expectedMarker) && fs.existsSync(pythonPath)) return pythonPath; } catch {}
  const environment = { ...process.env, UV_CACHE_DIR: path.join(runtimeRoot, 'uv-cache'), UV_PYTHON_INSTALL_DIR: path.join(runtimeRoot, 'python'), UV_MANAGED_PYTHON: '1' };
  status('Installing Python...');
  await run(uvPath, ['python', 'install', PYTHON_VERSION, '--managed-python', '--no-progress'], { env: environment });
  status('Creating the application environment...');
  await run(uvPath, ['venv', environmentRoot, '--python', PYTHON_VERSION, '--managed-python', '--seed', '--clear'], { env: environment });
  status('Installing AutoDiscovery...');
  await run(uvPath, ['pip', 'install', '--python', pythonPath, '--no-progress', '--requirement', path.join(resourceRoot, 'api', 'requirements.txt'), ...packageSources(resourceRoot)], { env: environment });
  fs.rmSync(environment.UV_CACHE_DIR, { recursive: true, force: true });
  fs.writeFileSync(markerPath, JSON.stringify(expectedMarker, null, 2), { mode: 0o600 });
  return pythonPath;
}

async function ensureVmEnvironment({ uvPath, limaPath, runtimeRoot, resourceRoot, appVersion, status }) {
  const limaHome = defaultLimaHome();
  const markerPath = path.join(limaHome, '.autodiscovery-runtime.json');
  const expectedMarker = { runtimeSchema: VM_RUNTIME_SCHEMA, appVersion, lima: TOOL_MANIFEST.lima.version, image: VM_IMAGE.sha256, guestUv: GUEST_UV.version, python: PYTHON_VERSION };
  const environment = { ...process.env, LIMA_HOME: limaHome };
  try { if (JSON.stringify(JSON.parse(fs.readFileSync(markerPath, 'utf8'))) === JSON.stringify(expectedMarker) && fs.existsSync(path.join(limaHome, VM_INSTANCE_NAME, 'lima.yaml'))) return { limaHome, limaPath }; } catch {}
  status('Preparing the secure analysis VM...');
  await run(limaPath, ['stop', VM_INSTANCE_NAME], { env: environment }).catch(() => {});
  await run(limaPath, ['delete', '--force', VM_INSTANCE_NAME], { env: environment }).catch(() => {});
  fs.mkdirSync(limaHome, { recursive: true });
  const configPath = path.join(runtimeRoot, 'autodiscovery-vm.yaml');
  const disk = fs.statfsSync(runtimeRoot);
  const resources = calculateVmResources({ logicalCpus: os.cpus().length, totalMemoryBytes: os.totalmem(), freeDiskBytes: disk.bavail * disk.bsize });
  fs.writeFileSync(configPath, buildVmConfig({ resources }), { mode: 0o600 });
  await run(limaPath, ['create', `--name=${VM_INSTANCE_NAME}`, '--tty=false', configPath], { env: environment });
  status('Starting the secure analysis VM...');
  await run(limaPath, ['start', VM_INSTANCE_NAME, '--timeout=20m', '--progress'], { env: environment });
  status('Installing scientific analysis tools...');
  const artifacts = path.join(runtimeRoot, 'guest-artifacts');
  fs.rmSync(artifacts, { recursive: true, force: true });
  fs.mkdirSync(artifacts, { recursive: true });
  const codeExecutionPath = path.join(resourceRoot, 'packages', 'code_execution');
  await run(uvPath, ['build', '--wheel', codeExecutionPath, '--out-dir', artifacts], { env: { ...process.env, UV_CACHE_DIR: path.join(runtimeRoot, 'uv-cache') } });
  const wheelName = fs.readdirSync(artifacts).find((name) => name.endsWith('.whl'));
  if (!wheelName) throw new Error('Failed to build the secure VM execution package.');
  await run(limaPath, ['copy', '--backend=scp', path.join(artifacts, wheelName), `${VM_INSTANCE_NAME}:/tmp/`], { env: environment });
  await run(limaPath, ['shell', VM_INSTANCE_NAME, '--', 'sudo', '/opt/uv/uv', 'pip', 'install', '--python', '/opt/autodiscovery-venv/bin/python', ...GUEST_PACKAGES], { env: environment });
  await run(limaPath, ['shell', VM_INSTANCE_NAME, '--', 'sudo', '/opt/uv/uv', 'pip', 'install', '--python', '/opt/autodiscovery-venv/bin/python', '--no-deps', `/tmp/${wheelName}`], { env: environment });
  await run(limaPath, ['shell', VM_INSTANCE_NAME, '--', 'sudo', 'chmod', '-R', 'a+rX', '/opt/autodiscovery-venv'], { env: environment });
  await run(limaPath, ['shell', VM_INSTANCE_NAME, '--', '/opt/autodiscovery-venv/bin/python', '-c', 'import code_execution, numpy, pandas, scipy, sklearn'], { env: environment });
  await run(limaPath, ['stop', VM_INSTANCE_NAME], { env: environment });
  fs.writeFileSync(markerPath, JSON.stringify(expectedMarker, null, 2), { mode: 0o600 });
  return { limaHome, limaPath };
}

async function bootstrapRuntime({ runtimeRoot, resourceRoot, appVersion, status = () => {} }) {
  assertSupportedPlatform();
  fs.mkdirSync(runtimeRoot, { recursive: true });
  const uvPath = await ensureTool('uv', runtimeRoot, status);
  const copilotPath = await ensureTool('copilot', runtimeRoot, status);
  const limaPath = await ensureTool('lima', runtimeRoot, status);
  const pythonPath = await ensurePythonEnvironment({ uvPath, runtimeRoot, resourceRoot, appVersion, status });
  return { uvPath, copilotPath, pythonPath, ...await ensureVmEnvironment({ uvPath, limaPath, runtimeRoot, resourceRoot, appVersion, status }) };
}

module.exports = { GUEST_PACKAGES, GUEST_UV, PYTHON_VERSION, TOOL_MANIFEST, UNIX_PATH_MAX, VM_IMAGE, VM_RUNTIME_SCHEMA, assertSupportedPlatform, bootstrapRuntime, buildVmConfig, calculateVmResources, defaultLimaHome, packageSources, sha256File };