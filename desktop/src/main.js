const http = require('node:http');
const os = require('node:os');
const path = require('node:path');
const { spawn } = require('node:child_process');
const { app, BrowserWindow, Menu, shell, utilityProcess } = require('electron');

const { bootstrapRuntime } = require('./bootstrap');
const { API_ORIGIN, API_PORT, UI_ORIGIN, UI_PORT, defaultDataRoot, serviceEnvironment } = require('./runtime');
const { prepareDataRoot } = require('./storage');

let loadingWindow;
let mainWindow;
let children = [];

function resourceRoot() {
  return app.isPackaged ? path.join(process.resourcesPath, 'app') : path.resolve(__dirname, '..', '..');
}

function status(message, level = 'info') {
  if (loadingWindow && !loadingWindow.isDestroyed()) loadingWindow.webContents.send('bootstrap-status', { message, level });
}

function waitForUrl(url, child, timeoutMs = 120000) {
  const deadline = Date.now() + timeoutMs;
  return new Promise((resolve, reject) => {
    const check = () => {
      if (child.exitCode !== null) return reject(new Error(`Service exited before becoming ready: ${child.exitCode}`));
      const request = http.get(url, (response) => {
        response.resume();
        if (response.statusCode < 500) resolve(); else retry();
      });
      request.on('error', retry);
      request.setTimeout(1000, () => { request.destroy(); retry(); });
    };
    const retry = () => Date.now() >= deadline ? reject(new Error(`Timed out waiting for ${url}`)) : setTimeout(check, 150);
    check();
  });
}

function track(child) {
  child.exitCode = null;
  child.on('exit', (code) => { child.exitCode = code; });
  children.push(child);
  return child;
}

function spawnService(command, args, options) {
  const child = track(spawn(command, args, { ...options, detached: true, stdio: ['ignore', 'pipe', 'pipe'] }));
  child.stdout.on('data', (chunk) => process.stdout.write(chunk));
  child.stderr.on('data', (chunk) => process.stderr.write(chunk));
  return child;
}

function spawnUi(options) {
  const child = track(utilityProcess.fork(path.join(__dirname, 'ui-runner.js'), [], { cwd: options.cwd, env: options.env, serviceName: 'AutoDiscovery UI', stdio: 'pipe' }));
  child.autodiscoveryUtility = true;
  child.stdout?.on('data', (chunk) => process.stdout.write(chunk));
  child.stderr?.on('data', (chunk) => process.stderr.write(chunk));
  return child;
}

function stopServices() {
  for (const child of children.splice(0)) {
    if (child.exitCode === null && child.pid) {
      try { child.autodiscoveryUtility ? child.kill() : process.kill(-child.pid, 'SIGTERM'); } catch {}
    }
  }
}

async function startServices(root, runtime, dataRoot) {
  const env = serviceEnvironment({ root, runtime, dataRoot, userDataRoot: app.getPath('userData') });
  status('Starting the local API...');
  const api = spawnService(runtime.pythonPath, ['-m', 'gunicorn', '--workers', '1', '--threads', '4', '--timeout', '0', '--bind', `127.0.0.1:${API_PORT}`, 'app:create_app()'], { cwd: path.join(root, 'api'), env });
  await waitForUrl(`${API_ORIGIN}/api`, api);
  status('Starting the application...');
  const uiRoot = app.isPackaged ? path.join(root, 'ui') : path.join(root, 'ui', '.next', 'standalone');
  const ui = spawnUi({ cwd: uiRoot, env: { ...env, AUTODISCOVERY_UI_SERVER: path.join(uiRoot, 'server.js'), HOSTNAME: '127.0.0.1', NODE_PATH: path.join(uiRoot, 'runtime_modules'), PORT: String(UI_PORT) } });
  await waitForUrl(UI_ORIGIN, ui);
}

function secureWindowOptions() {
  return { backgroundColor: '#102d2f', webPreferences: { contextIsolation: true, nodeIntegration: false, sandbox: true, preload: path.join(__dirname, 'preload.js') } };
}

function createLoadingWindow() {
  loadingWindow = new BrowserWindow({ ...secureWindowOptions(), titleBarStyle: 'hiddenInset', width: 640, height: 420, resizable: false, show: false });
  loadingWindow.loadFile(path.join(__dirname, 'loading.html'));
  loadingWindow.once('ready-to-show', () => loadingWindow.show());
}

async function createMainWindow() {
  mainWindow = new BrowserWindow({ ...secureWindowOptions(), titleBarStyle: 'hiddenInset', width: 1440, height: 960, minWidth: 1024, minHeight: 720, show: false, title: 'AutoDiscovery' });
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith('https://')) shell.openExternal(url);
    return { action: 'deny' };
  });
  mainWindow.webContents.on('will-navigate', (event, url) => {
    if (!url.startsWith(UI_ORIGIN)) { event.preventDefault(); if (url.startsWith('https://')) shell.openExternal(url); }
  });
  await Promise.all([mainWindow.loadURL(UI_ORIGIN), new Promise((resolve) => mainWindow.once('ready-to-show', resolve))]);
  mainWindow.show();
  loadingWindow?.close();
}

async function boot() {
  createLoadingWindow();
  try {
    const root = resourceRoot();
    const dataRoot = prepareDataRoot(process.env.AUTODISCOVERY_DATA_ROOT || defaultDataRoot(os.homedir()));
    const runtime = await bootstrapRuntime({ runtimeRoot: path.join(app.getPath('userData'), 'runtime'), resourceRoot: root, appVersion: app.getVersion(), status });
    await startServices(root, runtime, dataRoot);
    await createMainWindow();
  } catch (error) {
    console.error(error);
    status(error instanceof Error ? error.message : String(error), 'error');
  }
}

if (!app.requestSingleInstanceLock()) app.quit();
else {
  app.on('second-instance', () => { if (mainWindow) { if (mainWindow.isMinimized()) mainWindow.restore(); mainWindow.focus(); } });
  app.whenReady().then(() => { Menu.setApplicationMenu(null); return boot(); });
  app.on('before-quit', stopServices);
  app.on('window-all-closed', () => app.quit());
}

module.exports = { API_ORIGIN, UI_ORIGIN, serviceEnvironment, waitForUrl };