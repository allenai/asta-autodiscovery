import express from 'express';
import { WebSocketServer } from 'ws';
import chokidar from 'chokidar';
import fs from 'fs/promises';
import path from 'path';
import http from 'http';

const watchDir = process.env.WATCH_DIR || path.resolve('reef');
const port = Number(process.env.PORT) || 3000;
const app = express();

const nodes = new Map(); // key: id -> node data

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

async function loadExisting() {
  const entries = await fs.readdir(watchDir, { withFileTypes: true });
  for (const entry of entries) {
    if (!entry.isFile()) continue;
    const meta = fileToMeta(entry.name);
    if (!meta) continue;
    const fullPath = path.join(watchDir, entry.name);
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
  await loadExisting();
  const server = http.createServer(app);
  const wss = new WebSocketServer({ server });

  wss.on('connection', (ws) => {
    ws.send(JSON.stringify({ type: 'init', nodes: Array.from(nodes.values()) }));
  });

  const watcher = chokidar.watch(path.join(watchDir, 'mcts_node_*_*.json'), {
    ignoreInitial: true,
    awaitWriteFinish: { stabilityThreshold: 200, pollInterval: 50 },
  });

  watcher
    .on('add', (filePath) => upsertNode(wss, filePath))
    .on('change', (filePath) => upsertNode(wss, filePath))
    .on('unlink', (filePath) => removeNode(wss, filePath));

  app.use(express.static('public'));
  app.get('/api/nodes', (_req, res) => {
    res.json({ nodes: Array.from(nodes.values()) });
  });

  app.get('/api/health', (_req, res) => res.json({ ok: true, count: nodes.size }));

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
