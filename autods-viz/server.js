import express from 'express';
import { WebSocketServer } from 'ws';
import chokidar from 'chokidar';
import fs from 'fs/promises';
import path from 'path';
import http from 'http';

const resultsRoot = path.resolve('results');
const port = Number(process.env.PORT) || 3000;
const basePath = process.env.BASE_PATH || '';
const app = express();

app.use(express.json());

const nodes = new Map(); // key: id -> node data
let watcher = null;
let currentRun = null; // directory name under results/
let watchDir = null; // absolute path for the active run

function fileToMeta(filePath) {
  const name = path.basename(filePath);
  const match = name.match(/mcts_node_(\d+)_(\d+)\.json$/);
  if (!match) return null;
  return { level: Number(match[1]), index: Number(match[2]), filename: name };
}

async function readNodeFile(filePath) {
  try {
    const meta = fileToMeta(filePath);
    if (!meta) return null;
    const raw = await fs.readFile(filePath, 'utf-8');
    const data = JSON.parse(raw);
    return { ...data, ...meta };
  } catch (err) {
    console.error('Failed to read node file', filePath, err.message);
    return null;
  }
}

async function loadExisting(targetDir) {
  const entries = await fs.readdir(targetDir, { withFileTypes: true });
  for (const entry of entries) {
    if (!entry.isFile()) continue;
    const meta = fileToMeta(entry.name);
    if (!meta) continue;
    const fullPath = path.join(targetDir, entry.name);
    const node = await readNodeFile(fullPath);
    if (node) nodes.set(node.id, node);
  }
}

function broadcast(wss, payload) {
  const message = JSON.stringify(payload);
  wss.clients.forEach((client) => {
    if (client.readyState === 1) {
      client.send(message);
    }
  });
}

async function listRuns() {
  try {
    const entries = await fs.readdir(resultsRoot, { withFileTypes: true });
    return entries.filter((e) => e.isDirectory()).map((e) => e.name).sort();
  } catch (err) {
    console.error('Failed to list runs', err.message);
    return [];
  }
}

async function resolveInitialRun() {
  // Environment override: WATCH_DIR can be an absolute path or a run name under results/
  if (process.env.WATCH_DIR) {
    const envDir = path.isAbsolute(process.env.WATCH_DIR)
      ? process.env.WATCH_DIR
      : path.join(resultsRoot, process.env.WATCH_DIR);
    try {
      const stat = await fs.stat(envDir);
      if (stat.isDirectory()) {
        return { name: path.basename(envDir), dir: envDir };
      }
    } catch (err) {
      console.warn('WATCH_DIR is set but invalid, falling back to results/');
    }
  }

  const runs = await listRuns();
  if (runs.length) {
    const first = runs[0];
    return { name: first, dir: path.join(resultsRoot, first) };
  }

  // Fallback to resultsRoot itself if nothing else exists
  return { name: path.basename(resultsRoot), dir: resultsRoot };
}

async function setWatchDir(runName, wss, targetOverride) {
  const targetDir = targetOverride || path.join(resultsRoot, runName);
  const stat = await fs.stat(targetDir).catch(() => null);
  if (!stat || !stat.isDirectory()) {
    throw new Error(`Run "${runName}" does not exist under results/`);
  }

  if (watcher) {
    await watcher.close();
    watcher = null;
  }

  watchDir = targetDir;
  currentRun = path.basename(targetDir);
  nodes.clear();
  await loadExisting(watchDir);

  watcher = chokidar.watch(path.join(watchDir, 'mcts_node_*_*.json'), {
    ignoreInitial: true,
    awaitWriteFinish: { stabilityThreshold: 200, pollInterval: 50 },
  });

  watcher
    .on('add', (filePath) => upsertNode(wss, filePath))
    .on('change', (filePath) => upsertNode(wss, filePath))
    .on('unlink', (filePath) => removeNode(wss, filePath));

  broadcast(wss, { type: 'init', run: currentRun, nodes: Array.from(nodes.values()) });
  console.log(`Watching directory: ${watchDir}`);
}

async function upsertNode(wss, filePath) {
  const node = await readNodeFile(filePath);
  if (!node) return;
  nodes.set(node.id, node);
  broadcast(wss, { type: 'upsert', node });
}

async function removeNode(wss, filePath) {
  const meta = fileToMeta(filePath);
  if (!meta) return;
  const existing = Array.from(nodes.values()).find((n) => n.filename === meta.filename);
  if (existing) {
    nodes.delete(existing.id);
    broadcast(wss, { type: 'remove', id: existing.id });
  }
}

async function start() {
  await fs.mkdir(resultsRoot, { recursive: true });
  const { name: initialRun, dir: initialDir } = await resolveInitialRun();

  const server = http.createServer(app);
  const wss = new WebSocketServer({ server });

  wss.on('connection', (ws) => {
    ws.send(JSON.stringify({ type: 'init', run: currentRun, nodes: Array.from(nodes.values()) }));
  });

  await setWatchDir(initialRun, wss, initialDir);

  // Serve index.html with injected BASE_PATH
  app.get('/', async (req, res) => {
    const html = await fs.readFile('public/index.html', 'utf-8');
    const injected = html.replace(
      '</head>',
      `  <script>window.BASE_PATH = ${JSON.stringify(basePath)};</script>\n  </head>`
    );
    res.type('html').send(injected);
  });

  app.use(express.static('public'));

  app.get('/api/nodes', (_req, res) => {
    res.json({ run: currentRun, nodes: Array.from(nodes.values()) });
  });

  app.get('/api/health', (_req, res) => res.json({ ok: true, run: currentRun, count: nodes.size }));

  app.get('/api/runs', async (_req, res) => {
    const runs = await listRuns();
    res.json({ current: currentRun, runs });
  });

  app.post('/api/watch', async (req, res) => {
    const run = req.body?.run;
    if (!run) return res.status(400).json({ error: 'run is required' });
    try {
      await setWatchDir(run, wss);
      res.json({ ok: true, current: currentRun, nodes: Array.from(nodes.values()) });
    } catch (err) {
      res.status(400).json({ error: err.message });
    }
  });

  server.listen(port, () => {
    console.log(`Server running at http://localhost:${port}`);
    console.log(`Watching directory: ${watchDir}`);
    console.log('Open the browser to see the tree.');
  });
}

start().catch((err) => {
  console.error('Failed to start server', err);
  process.exit(1);
});
