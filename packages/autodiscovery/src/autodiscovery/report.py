"""Generate a static HTML report directory for AutoDiscovery results.

The report is written as a directory of assets rather than a single
self-contained HTML file: ``index.html`` carries markup + CSS + JS,
``data.js`` defines the embedded run data as global JS constants, and
``figures/`` holds per-experiment images as separate files. Only the
fields actually rendered by the UI are emitted — internal MCTS state
(messages, untried/tried experiments, visits/value, full belief
distributions, etc.) is dropped.
"""

from __future__ import annotations

import base64
import binascii
import json
import os
import shutil

# MIME types we know how to render, in priority order (best first).
_IMAGE_MIME_EXT = {
    "image/svg+xml": "svg",
    "image/png": "png",
    "image/jpeg": "jpg",
}
_RICH_OUTPUT_PRIORITY = ("image/svg+xml", "image/png", "image/jpeg", "text/plain")


def _load_nodes(out_dir: str) -> list[dict]:
    """Load MCTS nodes from the output directory."""
    nodes_path = os.path.join(out_dir, "mcts_nodes.json")
    if os.path.exists(nodes_path):
        with open(nodes_path) as f:
            return json.load(f)
    # Fallback: gather individual node files
    nodes = []
    for fname in sorted(os.listdir(out_dir)):
        if fname.startswith("mcts_node_") and fname.endswith(".json"):
            with open(os.path.join(out_dir, fname)) as f:
                nodes.append(json.load(f))
    return nodes


def _load_rich_outputs(out_dir: str) -> dict[str, list]:
    """Load rich outputs keyed by node id."""
    ro_dir = os.path.join(out_dir, "rich_outputs")
    outputs: dict[str, list] = {}
    if not os.path.isdir(ro_dir):
        return outputs
    for fname in os.listdir(ro_dir):
        if not fname.endswith(".json"):
            continue
        node_key = fname.replace("ro_", "node_").replace(".json", "")
        with open(os.path.join(ro_dir, fname)) as f:
            data = json.load(f)
        if data:
            outputs[node_key] = data
    return outputs


def _load_args(out_dir: str) -> dict:
    args_path = os.path.join(out_dir, "args.json")
    if os.path.exists(args_path):
        with open(args_path) as f:
            return json.load(f)
    return {}


def _load_metadata(out_dir: str) -> dict:
    run_args = _load_args(out_dir)
    meta_path = run_args.get("dataset_metadata", "")
    if meta_path and os.path.exists(meta_path):
        with open(meta_path) as f:
            return json.load(f)
    return {}


def _belief_mean(b: object) -> float | None:
    if isinstance(b, dict):
        m = b.get("mean")
        if isinstance(m, (int, float)):
            return float(m)
    return None


def _trim_plan(plan: object) -> dict | None:
    if not isinstance(plan, dict):
        return None
    kept = {k: plan.get(k) for k in ("objective", "steps", "deliverables") if plan.get(k)}
    return kept or None


def _write_rich_outputs(
    bundles: list,
    node_id: str,
    figures_dir: str,
) -> list[dict]:
    """Write image bundles to disk; return list of UI-ready figure descriptors."""
    figs: list[dict] = []
    for idx, bundle in enumerate(bundles):
        if not isinstance(bundle, dict):
            continue
        chosen = next((m for m in _RICH_OUTPUT_PRIORITY if bundle.get(m)), None)
        if chosen is None:
            continue
        payload = bundle[chosen]
        if chosen == "text/plain":
            figs.append({"kind": "text", "text": str(payload)})
            continue
        ext = _IMAGE_MIME_EXT[chosen]
        fname = f"{node_id}_{idx}.{ext}"
        fpath = os.path.join(figures_dir, fname)
        try:
            if chosen == "image/svg+xml":
                trimmed = payload.strip() if isinstance(payload, str) else ""
                if trimmed.startswith("<"):
                    with open(fpath, "w", encoding="utf-8") as f:
                        f.write(trimmed)
                else:
                    with open(fpath, "wb") as f:
                        f.write(base64.b64decode(payload))
            else:
                with open(fpath, "wb") as f:
                    f.write(base64.b64decode(payload))
        except (binascii.Error, ValueError, TypeError):
            continue
        figs.append({"kind": "image", "src": f"figures/{fname}"})
    return figs


def _trim_node(node: dict, figures: list[dict]) -> dict:
    return {
        "id": node.get("id"),
        "parent_id": node.get("parent_id"),
        "creation_idx": node.get("creation_idx"),
        "success": bool(node.get("success")),
        "surprising": bool(node.get("surprising")),
        "belief_change": node.get("belief_change"),
        "prior_mean": _belief_mean(node.get("prior")),
        "posterior_mean": _belief_mean(node.get("posterior")),
        "hypothesis": node.get("hypothesis") or "",
        "experiment_plan": _trim_plan(node.get("experiment_plan")),
        "code": node.get("code") or "",
        "code_output": node.get("code_output") or "",
        "analysis": node.get("analysis") or "",
        "review": node.get("review") or "",
        "rich_outputs": figures,
    }


def _escape_json_for_script(obj: object) -> str:
    """Serialize to JSON safe for embedding inside a <script> tag."""
    return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")


def generate_report(out_dir: str) -> str:
    """Generate a static HTML report directory under *out_dir*/report.

    Returns the path to the generated ``index.html``.
    """
    raw_nodes = _load_nodes(out_dir)
    rich_outputs = _load_rich_outputs(out_dir)
    run_args = _load_args(out_dir)
    metadata = _load_metadata(out_dir)

    report_dir = os.path.join(out_dir, "report")
    figures_dir = os.path.join(report_dir, "figures")
    if os.path.isdir(figures_dir):
        shutil.rmtree(figures_dir)
    os.makedirs(figures_dir, exist_ok=True)

    nodes: list[dict] = []
    for node in raw_nodes:
        nid = node.get("id") or ""
        bundles = rich_outputs.get(nid, [])
        figures = _write_rich_outputs(bundles, nid, figures_dir) if bundles else []
        nodes.append(_trim_node(node, figures))

    trimmed_args = {"dataset_metadata": run_args.get("dataset_metadata", "")}
    trimmed_metadata = {
        "name": metadata.get("name", ""),
        "description": metadata.get("description", ""),
    }

    data_js = (
        f"const NODES = {_escape_json_for_script(nodes)};\n"
        f"const RUN_ARGS = {_escape_json_for_script(trimmed_args)};\n"
        f"const METADATA = {_escape_json_for_script(trimmed_metadata)};\n"
    )
    with open(os.path.join(report_dir, "data.js"), "w", encoding="utf-8") as f:
        f.write(data_js)

    index_path = os.path.join(report_dir, "index.html")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(_INDEX_HTML)
    return index_path


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

_INDEX_HTML = (
    """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>AutoDiscovery Report</title>
<script src="https://d3js.org/d3.v7.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<style>
"""
    # The CSS body is concatenated rather than f-string interpolated so that
    # the `{` / `}` characters inside the stylesheet don't need to be escaped.
    + r"""
* { margin: 0; padding: 0; box-sizing: border-box; }

:root {
  --bg-dark: #0D2529;
  --bg-panel: #163638;
  --bg-panel-alt: #163638f9;
  --cream: #FAF2E9;
  --cream-dim: rgba(250,242,233,0.6);
  --cream-border: rgba(250,242,233,0.18);
  --green: #0FCB8C;
  --green-dim: rgba(15,203,140,0.4);
  --orange: #FFA31C;
  --pink: #E86CB5;
  --node-base: #384849;
  --error-red: #F44336;
  --font: 'Segoe UI', system-ui, -apple-system, sans-serif;
  --mono: 'SF Mono', 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
}

html, body { height: 100%; background: var(--bg-dark); color: var(--cream); font-family: var(--font); font-size: 14px; overflow: hidden; }

#app { display: flex; height: 100vh; }

/* --- Graph panel (left) --- */
#graph-panel { flex: 0 0 35%; min-width: 280px; position: relative; background: var(--bg-dark); overflow: hidden; }
#graph-panel svg { width: 100%; height: 100%; }

/* --- Run panel (center) --- */
#run-panel { flex: 1 1 auto; min-width: 320px; background: var(--bg-panel); border-left: 1px solid var(--cream-border); border-right: 1px solid var(--cream-border); overflow-y: auto; padding: 20px 24px; }

/* --- Detail panel (right) --- */
#detail-panel { flex: 0 0 38%; max-width: 520px; background: var(--bg-panel-alt); border-left: 1px solid var(--cream-border); overflow-y: auto; padding: 20px 24px; }
#detail-panel.hidden { display: none; }

/* --- Run header --- */
#run-header h1 { font-size: 20px; font-weight: 600; margin-bottom: 4px; }
#run-header .meta { font-size: 12px; color: var(--cream-dim); margin-bottom: 16px; }
#run-header .stats { display: flex; gap: 16px; margin-bottom: 16px; flex-wrap: wrap; }
#run-header .stat { background: rgba(250,242,233,0.06); border: 1px solid var(--cream-border); border-radius: 8px; padding: 8px 14px; }
#run-header .stat .label { font-size: 11px; color: var(--cream-dim); text-transform: uppercase; letter-spacing: 0.5px; }
#run-header .stat .value { font-size: 18px; font-weight: 600; }

/* --- Top surprisals --- */
#top-surprisals { margin-bottom: 20px; }
#top-surprisals h3 { font-size: 14px; color: var(--green); margin-bottom: 8px; }
.surprisal-item { background: rgba(250,242,233,0.05); border: 1px solid var(--cream-border); border-radius: 8px; padding: 12px 14px; margin-bottom: 8px; cursor: pointer; border-left: 4px solid transparent; transition: border-color 0.15s; }
.surprisal-item:hover { border-left-color: var(--green); }
.surprisal-item.selected { border-left-color: var(--green); }
.surprisal-item .belief-label { font-size: 11px; color: var(--orange); font-weight: 600; text-transform: uppercase; margin-bottom: 4px; }
.surprisal-item .hyp { font-size: 13px; line-height: 1.4; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.surprisal-item .view-link { font-size: 12px; color: var(--green); margin-top: 6px; display: inline-block; }

/* --- Table --- */
#experiments-table h3 { font-size: 14px; color: var(--green); margin-bottom: 8px; }
.exp-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.exp-table thead th { text-align: left; padding: 8px 10px; border-bottom: 2px solid var(--cream-border); color: var(--cream-dim); font-weight: 600; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; cursor: pointer; user-select: none; white-space: nowrap; }
.exp-table thead th:hover { color: var(--cream); }
.exp-table thead th .sort-arrow { margin-left: 4px; font-size: 10px; }
.exp-table tbody tr { cursor: pointer; border-bottom: 1px solid var(--cream-border); transition: background 0.1s; }
.exp-table tbody tr:nth-child(even) { background: rgba(250,242,233,0.03); }
.exp-table tbody tr:hover { background: rgba(15,203,140,0.08); }
.exp-table tbody tr.selected { background: rgba(15,203,140,0.12); border-left: 4px solid var(--green); }
.exp-table td { padding: 10px 10px; vertical-align: top; }
.exp-table .col-id { width: 40px; text-align: center; font-weight: 600; }
.exp-table .col-hyp { max-width: 300px; line-height: 1.4; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
.exp-table .col-surprisal { width: 80px; text-align: center; }
.exp-table .col-belief { width: 90px; text-align: center; font-size: 12px; }
.exp-table .col-dir { width: 80px; text-align: center; font-size: 12px; }
.surprising { color: var(--orange); font-weight: 700; }
.dir-positive { color: var(--green); }
.dir-negative { color: var(--pink); }
.dir-neutral { color: var(--cream-dim); }

/* --- Detail panel --- */
#detail-content .detail-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
#detail-content .detail-header h2 { font-size: 16px; font-weight: 600; }
.close-btn { background: none; border: 1px solid var(--cream-border); color: var(--cream); border-radius: 6px; padding: 4px 12px; cursor: pointer; font-size: 13px; }
.close-btn:hover { background: rgba(250,242,233,0.1); }

.detail-section { margin-bottom: 20px; }
.detail-section h4 { font-size: 12px; color: var(--green); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px; font-weight: 600; }

/* Belief shift */
.belief-shift { background: rgba(250,242,233,0.05); border-radius: 8px; padding: 14px; margin-bottom: 16px; }
.belief-shift .shift-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.belief-shift .direction { font-weight: 600; font-size: 14px; }
.belief-shift .surprisal-val { font-size: 13px; }
.belief-bar { position: relative; height: 40px; background: rgba(250,242,233,0.08); border-radius: 20px; margin: 8px 0; overflow: visible; }
.belief-bar .axis-labels { display: flex; justify-content: space-between; font-size: 10px; color: var(--cream-dim); margin-top: 4px; }
.belief-dot { position: absolute; top: 50%; transform: translate(-50%, -50%); width: 14px; height: 14px; border-radius: 50%; z-index: 2; }
.belief-dot.prior { background: var(--pink); }
.belief-dot.posterior { background: var(--green); }
.belief-arrow { position: absolute; top: 50%; height: 3px; transform: translateY(-50%); z-index: 1; border-radius: 2px; }
.belief-legend { display: flex; gap: 16px; font-size: 11px; margin-top: 8px; }
.belief-legend span::before { content: ''; display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 4px; vertical-align: middle; }
.belief-legend .legend-prior::before { background: var(--pink); }
.belief-legend .legend-post::before { background: var(--green); }

/* Markdown content */
.md-content { font-size: 13px; line-height: 1.6; }
.md-content p { margin-bottom: 8px; }
.md-content ul, .md-content ol { margin-left: 20px; margin-bottom: 8px; }
.md-content strong { color: var(--cream); }
.md-content code { background: rgba(250,242,233,0.1); padding: 1px 5px; border-radius: 3px; font-family: var(--mono); font-size: 12px; }
.md-content pre { background: rgba(0,0,0,0.3); padding: 12px; border-radius: 6px; overflow-x: auto; margin-bottom: 8px; }
.md-content pre code { background: none; padding: 0; font-size: 12px; }

/* Code blocks */
.code-block { position: relative; background: rgba(0,0,0,0.35); border-radius: 8px; margin-bottom: 12px; overflow: hidden; }
.code-block .code-header { display: flex; justify-content: space-between; align-items: center; padding: 6px 12px; background: rgba(0,0,0,0.2); font-size: 11px; color: var(--cream-dim); }
.code-block pre { padding: 12px; overflow-x: auto; max-height: 300px; overflow-y: auto; margin: 0; }
.code-block code { font-family: var(--mono); font-size: 12px; line-height: 1.5; color: var(--cream); }
.code-toggle { background: none; border: 1px solid var(--cream-border); color: var(--cream-dim); border-radius: 4px; padding: 2px 8px; cursor: pointer; font-size: 11px; }
.code-toggle:hover { color: var(--cream); }

/* Rich outputs / figures */
.figures-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 12px; }
.figure-card { background: rgba(255,255,255,0.05); border-radius: 8px; overflow: hidden; cursor: pointer; border: 1px solid var(--cream-border); transition: border-color 0.15s; }
.figure-card:hover { border-color: var(--green); }
.figure-card img { width: 100%; height: auto; display: block; }
.figure-card pre { padding: 8px; font-size: 11px; max-height: 200px; overflow: auto; }
.figure-card .fig-label { padding: 6px 10px; font-size: 11px; color: var(--cream-dim); }

/* Status chip */
.status-chip { display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: 11px; font-weight: 600; text-transform: uppercase; }
.status-chip.succeeded { background: rgba(15,203,140,0.2); color: var(--green); }
.status-chip.failed { background: rgba(244,67,54,0.2); color: var(--error-red); }

/* Fullscreen overlay for figures */
.overlay { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.85); z-index: 1000; display: flex; align-items: center; justify-content: center; cursor: pointer; }
.overlay img { max-width: 90%; max-height: 90%; }

/* D3 tree styles */
.node circle { stroke-width: 2; cursor: pointer; }
.node text { font-size: 11px; fill: var(--cream); pointer-events: none; text-anchor: middle; dominant-baseline: central; font-weight: 600; }
.link { fill: none; stroke: #334155; stroke-width: 1.2; }
.link.selected { stroke: var(--green); stroke-width: 2.5; }
.graph-legend { position: absolute; bottom: 12px; right: 12px; background: rgba(13,37,41,0.85); border: 1px solid var(--cream-border); border-radius: 8px; padding: 10px 14px; font-size: 11px; }
.graph-legend .legend-row { display: flex; align-items: center; gap: 6px; margin-bottom: 4px; }
.graph-legend .legend-row:last-child { margin-bottom: 0; }
.graph-legend .swatch { width: 12px; height: 12px; border-radius: 50%; }

/* Responsive */
@media (max-width: 900px) {
  #app { flex-direction: column; }
  #graph-panel { flex: 0 0 250px; }
  #detail-panel { max-width: 100%; }
}

/* Scrollbar */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(250,242,233,0.15); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: rgba(250,242,233,0.25); }
"""
    + """
</style>
</head>
<body>
<div id="app">
  <div id="graph-panel"></div>
  <div id="run-panel">
    <div id="run-header"></div>
    <div id="top-surprisals"></div>
    <div id="experiments-table"></div>
  </div>
  <div id="detail-panel" class="hidden">
    <div id="detail-content"></div>
  </div>
</div>
<script src="data.js"></script>
<script>
"""
    + r"""
// ---- Helpers ----
function beliefLabel(val) {
  if (val == null) return '—';
  if (val < 0.2) return 'Likely False';
  if (val < 0.4) return 'Maybe False';
  if (val < 0.6) return 'Uncertain';
  if (val < 0.8) return 'Maybe True';
  return 'Likely True';
}

function beliefDirection(node) {
  const pr = node.prior_mean;
  const po = node.posterior_mean;
  if (pr == null || po == null) return 'neutral';
  const d = po - pr;
  if (Math.abs(d) < 0.005) return 'neutral';
  return d > 0 ? 'positive' : 'negative';
}

function escapeHtml(s) {
  if (!s) return '';
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

function renderMarkdown(s) {
  if (!s) return '';
  try { return marked.parse(s); } catch { return '<p>' + escapeHtml(s) + '</p>'; }
}

function nodeNumber(n) {
  if (!n || !n.id) return '';
  return n.id.startsWith('node_') ? n.id.slice(5) : n.id;
}

function nodeNumberSortKey(n) {
  const num = nodeNumber(n);
  const parts = String(num).split('_').map(p => {
    const v = parseInt(p, 10);
    return Number.isFinite(v) ? v : p;
  });
  return parts;
}

function compareSortKey(a, b) {
  const la = Math.max(a.length, b.length);
  for (let i = 0; i < la; i++) {
    const va = a[i], vb = b[i];
    if (va === undefined) return -1;
    if (vb === undefined) return 1;
    if (va < vb) return -1;
    if (va > vb) return 1;
  }
  return 0;
}

// ---- Filter experiment nodes (skip root/data-loading) ----
const experimentNodes = NODES.filter(n => n.hypothesis);
const allNodesById = {};
NODES.forEach(n => { allNodesById[n.id] = n; });

// ---- State ----
let selectedNodeId = null;
let sortCol = 'creation_idx';
let sortAsc = true;

// ---- Run Header ----
function renderRunHeader() {
  const el = document.getElementById('run-header');
  const name = METADATA.name || RUN_ARGS.dataset_metadata || 'AutoDiscovery Run';
  const desc = METADATA.description || '';
  const nTotal = experimentNodes.length;
  const nSurprising = experimentNodes.filter(n => n.surprising).length;
  const nSucceeded = experimentNodes.filter(n => n.success).length;

  el.innerHTML = `
    <h1>${escapeHtml(name)}</h1>
    ${desc ? '<div class="meta">' + escapeHtml(desc) + '</div>' : ''}
    <div class="stats">
      <div class="stat"><div class="label">Experiments</div><div class="value">${nTotal}</div></div>
      <div class="stat"><div class="label">Succeeded</div><div class="value">${nSucceeded}</div></div>
      <div class="stat"><div class="label">Surprising</div><div class="value surprising">${nSurprising}</div></div>
    </div>
  `;
}

// ---- Top Surprisals ----
function renderTopSurprisals() {
  const el = document.getElementById('top-surprisals');
  const surprising = experimentNodes
    .filter(n => n.surprising)
    .sort((a, b) => Math.abs(b.belief_change || 0) - Math.abs(a.belief_change || 0));

  if (surprising.length === 0) {
    el.innerHTML = '';
    return;
  }

  const items = surprising.slice(0, 5);
  el.innerHTML = `
    <h3>Top Findings</h3>
    ${items.map(n => {
      const postMean = n.posterior_mean;
      const label = postMean != null ? ("It's " + beliefLabel(postMean) + ' that:') : '';
      return `
        <div class="surprisal-item ${selectedNodeId === n.id ? 'selected' : ''}" data-id="${n.id}">
          <div class="belief-label">${escapeHtml(label)}</div>
          <div class="hyp">${escapeHtml(n.hypothesis)}</div>
          <div class="view-link">View details &rarr;</div>
        </div>
      `;
    }).join('')}
  `;

  el.querySelectorAll('.surprisal-item').forEach(item => {
    item.addEventListener('click', () => selectNode(item.dataset.id));
  });
}

// ---- Experiments Table ----
function renderTable() {
  const el = document.getElementById('experiments-table');
  const sorted = [...experimentNodes].sort((a, b) => {
    if (sortCol === 'creation_idx') {
      const cmp = compareSortKey(nodeNumberSortKey(a), nodeNumberSortKey(b));
      return sortAsc ? cmp : -cmp;
    }
    let va, vb;
    switch (sortCol) {
      case 'hypothesis': va = (a.hypothesis || '').toLowerCase(); vb = (b.hypothesis || '').toLowerCase(); break;
      case 'surprisal': va = Math.abs(a.belief_change || 0); vb = Math.abs(b.belief_change || 0); break;
      case 'prior': va = a.prior_mean ?? -1; vb = b.prior_mean ?? -1; break;
      case 'posterior': va = a.posterior_mean ?? -1; vb = b.posterior_mean ?? -1; break;
      default: va = a.creation_idx; vb = b.creation_idx;
    }
    if (va < vb) return sortAsc ? -1 : 1;
    if (va > vb) return sortAsc ? 1 : -1;
    return 0;
  });

  function thArrow(col) {
    if (sortCol !== col) return '';
    return `<span class="sort-arrow">${sortAsc ? '&#9650;' : '&#9660;'}</span>`;
  }

  el.innerHTML = `
    <h3>Experiments</h3>
    <table class="exp-table">
      <thead><tr>
        <th class="col-id" data-col="creation_idx"># ${thArrow('creation_idx')}</th>
        <th data-col="hypothesis">Hypothesis ${thArrow('hypothesis')}</th>
        <th class="col-surprisal" data-col="surprisal">Surprisal ${thArrow('surprisal')}</th>
        <th class="col-belief" data-col="prior">Before ${thArrow('prior')}</th>
        <th class="col-belief" data-col="posterior">After ${thArrow('posterior')}</th>
        <th class="col-dir">Direction</th>
      </tr></thead>
      <tbody>
        ${sorted.map(n => {
          const bc = n.belief_change != null ? Math.abs(n.belief_change).toFixed(3) : '—';
          const dir = beliefDirection(n);
          const priorLabel = beliefLabel(n.prior_mean);
          const postLabel = beliefLabel(n.posterior_mean);
          const dirLabel = dir.charAt(0).toUpperCase() + dir.slice(1);
          return `<tr class="${selectedNodeId === n.id ? 'selected' : ''}" data-id="${n.id}">
            <td class="col-id">${escapeHtml(nodeNumber(n))}</td>
            <td class="col-hyp">${escapeHtml(n.hypothesis)}</td>
            <td class="col-surprisal ${n.surprising ? 'surprising' : ''}">${bc}</td>
            <td class="col-belief">${priorLabel}</td>
            <td class="col-belief">${postLabel}</td>
            <td class="col-dir dir-${dir}">${dirLabel}</td>
          </tr>`;
        }).join('')}
      </tbody>
    </table>
  `;

  el.querySelectorAll('thead th[data-col]').forEach(th => {
    th.addEventListener('click', () => {
      const col = th.dataset.col;
      if (sortCol === col) { sortAsc = !sortAsc; } else { sortCol = col; sortAsc = true; }
      renderTable();
    });
  });

  el.querySelectorAll('tbody tr').forEach(tr => {
    tr.addEventListener('click', () => selectNode(tr.dataset.id));
  });
}

// ---- Detail Panel ----
function renderDetail() {
  const panel = document.getElementById('detail-panel');
  const content = document.getElementById('detail-content');

  if (!selectedNodeId) {
    panel.classList.add('hidden');
    return;
  }
  panel.classList.remove('hidden');
  const n = allNodesById[selectedNodeId];
  if (!n) return;

  const dir = beliefDirection(n);
  const dirLabel = dir.charAt(0).toUpperCase() + dir.slice(1);
  const bc = n.belief_change != null ? Math.abs(n.belief_change).toFixed(3) : null;
  const priorMean = n.prior_mean;
  const postMean = n.posterior_mean;

  let beliefHtml = '';
  if (priorMean != null && postMean != null) {
    const arrowColor = n.surprising ? 'var(--orange)' : 'var(--cream-dim)';
    const left = Math.min(priorMean, postMean) * 100;
    const width = Math.abs(postMean - priorMean) * 100;
    beliefHtml = `
      <div class="belief-shift">
        <div class="shift-header">
          <span class="direction dir-${dir}">${dirLabel}</span>
          ${bc != null ? `<span class="surprisal-val ${n.surprising ? 'surprising' : ''}">Surprisal: ${bc}</span>` : ''}
        </div>
        <div class="belief-bar">
          <div class="belief-arrow" style="left:${left}%;width:${width}%;background:${arrowColor}"></div>
          <div class="belief-dot prior" style="left:${priorMean * 100}%" title="Prior: ${priorMean.toFixed(3)}"></div>
          <div class="belief-dot posterior" style="left:${postMean * 100}%" title="Posterior: ${postMean.toFixed(3)}"></div>
        </div>
        <div class="belief-bar">
          <div class="axis-labels"><span>Likely False</span><span>Uncertain</span><span>Likely True</span></div>
        </div>
        <div class="belief-legend">
          <span class="legend-prior">Before (${priorMean.toFixed(3)})</span>
          <span class="legend-post">After (${postMean.toFixed(3)})</span>
        </div>
      </div>
    `;
  }

  const plan = n.experiment_plan || {};
  let planHtml = '';
  if (plan.objective || plan.steps || plan.deliverables) {
    planHtml = `
      <div class="detail-section">
        <h4>Experiment Plan</h4>
        ${plan.objective ? '<div class="md-content">' + renderMarkdown('**Objective:** ' + plan.objective) + '</div>' : ''}
        ${plan.steps ? '<div class="md-content">' + renderMarkdown(plan.steps) + '</div>' : ''}
        ${plan.deliverables ? '<div class="md-content">' + renderMarkdown('**Deliverables:** ' + plan.deliverables) + '</div>' : ''}
      </div>
    `;
  }

  let codeHtml = '';
  if (n.code) {
    const lines = n.code.split('\n');
    const collapsed = lines.length > 15;
    codeHtml = `
      <div class="detail-section">
        <h4>Code</h4>
        <div class="code-block">
          <div class="code-header">
            <span>Python &middot; ${lines.length} lines</span>
            ${collapsed ? '<button class="code-toggle" onclick="toggleCode(this)">Show all</button>' : ''}
          </div>
          <pre style="${collapsed ? 'max-height:220px' : ''}"><code>${escapeHtml(n.code)}</code></pre>
        </div>
      </div>
    `;
  }

  let outputHtml = '';
  if (n.code_output) {
    const isError = n.code_output.startsWith('exitcode: 1') || n.code_output.includes('Error');
    outputHtml = `
      <div class="detail-section">
        <h4>Code Output</h4>
        <div class="code-block">
          <div class="code-header"><span>${n.success ? 'Succeeded' : 'Failed'}</span></div>
          <pre style="max-height:300px"><code style="${isError ? 'color:var(--error-red)' : ''}">${escapeHtml(n.code_output)}</code></pre>
        </div>
      </div>
    `;
  }

  // Rich outputs (figures)
  let figuresHtml = '';
  const ro = n.rich_outputs || [];
  if (ro.length > 0) {
    const figs = ro.map((item, i) => {
      let inner = '';
      if (item.kind === 'image' && item.src) {
        inner = `<img src="${item.src}" alt="Figure ${i+1}" loading="lazy"/>`;
      } else if (item.kind === 'text' && item.text) {
        inner = `<pre>${escapeHtml(item.text)}</pre>`;
      }
      if (!inner) return '';
      return `<div class="figure-card" onclick="openOverlay(this)"><div class="fig-content">${inner}</div><div class="fig-label">Figure ${i+1}</div></div>`;
    }).filter(Boolean).join('');

    if (figs) {
      figuresHtml = `<div class="detail-section"><h4>Figures</h4><div class="figures-grid">${figs}</div></div>`;
    }
  }

  const statusChip = n.success
    ? '<span class="status-chip succeeded">Succeeded</span>'
    : '<span class="status-chip failed">Failed</span>';

  content.innerHTML = `
    <div class="detail-header">
      <h2>Experiment ${escapeHtml(nodeNumber(n))} ${statusChip}</h2>
      <button class="close-btn" onclick="selectNode(null)">&times; Close</button>
    </div>
    ${beliefHtml}
    ${n.hypothesis ? `<div class="detail-section"><h4>Hypothesis</h4><div class="md-content">${renderMarkdown(n.hypothesis)}</div></div>` : ''}
    ${n.analysis ? `<div class="detail-section"><h4>Analysis</h4><div class="md-content">${renderMarkdown(n.analysis)}</div></div>` : ''}
    ${planHtml}
    ${codeHtml}
    ${outputHtml}
    ${figuresHtml}
    ${n.review && n.review !== 'N/A' ? `<div class="detail-section"><h4>Review</h4><div class="md-content">${renderMarkdown(n.review)}</div></div>` : ''}
  `;
}

function toggleCode(btn) {
  const pre = btn.closest('.code-block').querySelector('pre');
  if (pre.style.maxHeight) {
    pre.style.maxHeight = '';
    btn.textContent = 'Collapse';
  } else {
    pre.style.maxHeight = '220px';
    btn.textContent = 'Show all';
  }
}

function openOverlay(card) {
  const content = card.querySelector('.fig-content').innerHTML;
  const overlay = document.createElement('div');
  overlay.className = 'overlay';
  overlay.innerHTML = content;
  overlay.addEventListener('click', () => overlay.remove());
  document.body.appendChild(overlay);
}

// ---- Selection ----
function selectNode(id) {
  selectedNodeId = id;
  renderTable();
  renderTopSurprisals();
  renderDetail();
  highlightGraphNode(id);
}

// ---- D3 Radial Tree ----
function renderGraph() {
  const container = document.getElementById('graph-panel');
  const width = container.clientWidth || 500;
  const height = container.clientHeight || 500;

  const nodeMap = {};
  NODES.forEach(n => { nodeMap[n.id] = { ...n, children: [] }; });

  let rootId = null;
  NODES.forEach(n => {
    if (n.parent_id && nodeMap[n.parent_id]) {
      nodeMap[n.parent_id].children.push(nodeMap[n.id]);
    } else if (!rootId) {
      rootId = n.id;
    }
  });
  if (!rootId && NODES.length > 0) rootId = NODES[0].id;
  if (!rootId) return;

  const treeRoot = d3.hierarchy(nodeMap[rootId], d => d.children);

  const radius = Math.min(width, height) / 2 - 60;
  const treeLayout = d3.tree()
    .size([2 * Math.PI, radius])
    .separation((a, b) => (a.parent === b.parent ? 1 : 2) / a.depth || 1);

  treeLayout(treeRoot);

  const svg = d3.select(container).append('svg')
    .attr('width', width)
    .attr('height', height);

  const g = svg.append('g')
    .attr('transform', `translate(${width/2},${height/2})`);

  const zoom = d3.zoom()
    .scaleExtent([0.3, 3])
    .on('zoom', (event) => g.attr('transform', `translate(${width/2 + event.transform.x},${height/2 + event.transform.y}) scale(${event.transform.k})`));
  svg.call(zoom);

  g.selectAll('.link')
    .data(treeRoot.links())
    .join('path')
    .attr('class', 'link')
    .attr('d', d3.linkRadial().angle(d => d.x).radius(d => d.y));

  const nodeG = g.selectAll('.node')
    .data(treeRoot.descendants())
    .join('g')
    .attr('class', 'node')
    .attr('transform', d => `rotate(${d.x * 180 / Math.PI - 90}) translate(${d.y},0)`)
    .style('cursor', 'pointer')
    .on('click', (event, d) => selectNode(d.data.id));

  nodeG.append('circle')
    .attr('r', 16)
    .attr('fill', d => {
      const n = d.data;
      if (!n.surprising && !n.belief_change) return 'var(--node-base)';
      const intensity = Math.min(Math.abs(n.belief_change || 0) / 0.7, 1);
      if (n.surprising) {
        return d3.interpolateRgb('#384849', '#FFA31C')(intensity);
      }
      return d3.interpolateRgb('#384849', '#FAF2E9')(intensity);
    })
    .attr('stroke', d => d.data.id === selectedNodeId ? 'var(--green)' : 'rgba(250,242,233,0.2)')
    .attr('stroke-width', d => d.data.id === selectedNodeId ? 3 : 1.5);

  nodeG.append('text')
    .text(d => nodeNumber(d.data))
    .attr('transform', d => `rotate(${-(d.x * 180 / Math.PI - 90)})`);

  container.insertAdjacentHTML('beforeend', `
    <div class="graph-legend">
      <div class="legend-row"><div class="swatch" style="background:var(--node-base)"></div> Low surprisal</div>
      <div class="legend-row"><div class="swatch" style="background:var(--orange)"></div> High surprisal</div>
      <div class="legend-row"><div class="swatch" style="background:var(--green)"></div> Selected</div>
    </div>
  `);
}

function highlightGraphNode(id) {
  d3.selectAll('.node circle')
    .attr('stroke', d => d.data.id === id ? 'var(--green)' : 'rgba(250,242,233,0.2)')
    .attr('stroke-width', d => d.data.id === id ? 3 : 1.5);

  const ancestors = new Set();
  if (id) {
    let cur = id;
    while (cur && allNodesById[cur]) {
      ancestors.add(cur);
      cur = allNodesById[cur].parent_id;
    }
  }

  d3.selectAll('.link')
    .attr('stroke', d => ancestors.has(d.target.data.id) ? 'var(--green)' : '#334155')
    .attr('stroke-width', d => ancestors.has(d.target.data.id) ? 2.5 : 1.2);
}

renderRunHeader();
renderTopSurprisals();
renderTable();
renderGraph();
"""
    + """
</script>
</body>
</html>
"""
)
