"""Generate the static HTML report for an AutoDiscovery run.

The report is the web UI's run view: the same React components, built by
``ui/vite.report.config.ts`` into one self-contained page that ships with this
package as ``report_viewer/index.html``. This module copies that page into
*out_dir*/report and writes the run's data beside it:

- ``data.js`` sets ``window.AUTODISCOVERY_REPORT`` to the run and its experiments
  in the shapes the API serves them (``RunFromApi`` and ``ExperimentFromApi`` in
  ``ui/src/app/api/RunsApi.ts``), so the page maps them with the web UI's own code;
- ``figures/`` holds each experiment's images as files, which data.js references
  by relative URL rather than embedding.

Internal MCTS state (messages, untried/tried experiments, visits/value, etc.) is
left out, as it is from the API's responses.

A run writes its report when it starts and again as each experiment finishes
(see autodiscovery/run.py), so the report can be read, and refreshed, while the
run is still going.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path

# The built run view. A source checkout builds it with `make report-viewer`; the
# job image and the published wheel build it before packaging.
VIEWER_HTML = Path(__file__).with_name("report_viewer") / "index.html"

# Bundle key for a figure saved as a file; mirrors RICH_OUTPUT_URL_KEY in
# ui/src/app/types/Run.ts.
_FIGURE_URL_KEY = "x-report-figure-url"

# MIME types we know how to render, in priority order (best first).
_IMAGE_MIME_EXT = {
    "image/svg+xml": "svg",
    "image/png": "png",
    "image/jpeg": "jpg",
}
_RICH_OUTPUT_PRIORITY = ("image/svg+xml", "image/png", "image/jpeg", "text/plain")

# The run's first node loads the data and is not an experiment. The API leaves it
# out of a run's experiments (ROOT_NODE_FILENAME in autodiscovery_jobs.persistence),
# and the UI draws a placeholder root in its place.
_ROOT_NODE_ID = "node_1_0"


def _load_nodes(out_dir: str, prefer_aggregate: bool) -> list[dict]:
    """Load MCTS nodes from the output directory.

    The aggregate mcts_nodes.json is written once a run finishes, so it is only
    read for a finished run; during one it may be a stale copy, e.g. from the run
    a ``--continue_from_dir`` run copied its files from.
    """
    nodes_path = os.path.join(out_dir, "mcts_nodes.json")
    if prefer_aggregate and os.path.exists(nodes_path):
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


def _load_metadata(run_args: dict) -> dict:
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


def _write_rich_outputs(
    bundles: list,
    node_id: str,
    figures_dir: str,
) -> list[dict]:
    """Write image bundles to disk; return the bundles data.js carries for them.

    Positions are kept, so "Figure N" and the code output's per-figure analyses
    line up as they do in the web UI; a bundle with nothing renderable becomes
    an empty one, which the page shows as unsupported. Files are named by their
    content, so the report's updates during a run skip figures already written.
    """
    out: list[dict] = []
    for idx, bundle in enumerate(bundles):
        chosen = (
            next((m for m in _RICH_OUTPUT_PRIORITY if bundle.get(m)), None)
            if isinstance(bundle, dict)
            else None
        )
        if chosen is None:
            out.append({})
            continue
        payload = bundle[chosen]
        if chosen == "text/plain":
            out.append({"text/plain": str(payload)})
            continue
        ext = _IMAGE_MIME_EXT[chosen]
        digest = hashlib.sha256(str(payload).encode()).hexdigest()[:12]
        fname = f"{node_id}_{idx}_{digest}.{ext}"
        fpath = os.path.join(figures_dir, fname)
        if os.path.exists(fpath):
            out.append({_FIGURE_URL_KEY: f"figures/{fname}"})
            continue
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
            out.append({})
            continue
        out.append({_FIGURE_URL_KEY: f"figures/{fname}"})
    return out


def _experiments(nodes: list[dict], rich_outputs: dict[str, list]) -> list[dict]:
    """Shape nodes as the API's experiment details (api/utils/experiments.py)."""
    nodes = [n for n in nodes if n.get("id") != _ROOT_NODE_ID]
    children: dict[str | None, list[dict]] = {}
    for node in nodes:
        children.setdefault(node.get("parent_id"), []).append(node)

    experiments = []
    for node in sorted(nodes, key=lambda n: n.get("creation_idx", 0)):
        nid = node.get("id") or ""
        creation_idx = node.get("creation_idx", 0)
        success = node.get("success")
        prior = node.get("prior")
        posterior = node.get("posterior")
        time_elapsed = node.get("time_elapsed")
        kids = sorted(children.get(nid, []), key=lambda n: n.get("creation_idx", 0))
        experiments.append(
            {
                "experiment_id": nid,
                "parent_id": node.get("parent_id"),
                "child_ids": [kid.get("id") for kid in kids],
                "creation_idx": creation_idx,
                "id_in_run": creation_idx - 1,
                "status": "PENDING" if success is None else "SUCCEEDED" if success else "FAILED",
                "is_surprising": node.get("surprising"),
                "surprise": node.get("normalized_surprisal"),
                "prior": _belief_mean(prior),
                "posterior": _belief_mean(posterior),
                "prior_belief": prior if isinstance(prior, dict) else None,
                "posterior_belief": posterior if isinstance(posterior, dict) else None,
                "runtime_ms": time_elapsed * 1000.0 if time_elapsed is not None else None,
                "hypothesis": node.get("hypothesis"),
                "analysis": node.get("analysis"),
                "experiment_plan": node.get("experiment_plan"),
                "review": node.get("review"),
                "code": node.get("code"),
                "code_output": node.get("code_output"),
                "rich_outputs": rich_outputs.get(nid, []),
                "created_at": node.get("created_at"),
            }
        )
    return experiments


def _run(
    out_dir: str, run_args: dict, metadata: dict, experiments: list[dict], status: str
) -> dict:
    """Shape the run as the API serves one (``RunFromApi``).

    Run parameters come from args.json, which records what actually ran. Name,
    description and datasets come from the dataset metadata: the user's own file
    for a CLI run, or the run's metadata.json for one launched from the web UI.
    """
    now = datetime.now(UTC).isoformat()
    created_at = min((e["created_at"] for e in experiments if e["created_at"]), default=None)
    hypotheses = [e for e in experiments if e["hypothesis"]]
    requested = run_args.get("n_experiments") or len(hypotheses)
    completed = sum(e["status"] != "PENDING" for e in hypotheses)
    datalib_dirs = metadata.get("datalib_dirs")
    if datalib_dirs is None:
        datalib_dirs = [os.path.basename(p.rstrip("/")) for p in run_args.get("datalib_dir") or []]
    return {
        # Opaque but stable per output directory: the page keys its remembered
        # panel widths and visited rows by it.
        "runid": str(uuid.uuid5(uuid.NAMESPACE_URL, os.path.abspath(out_dir))),
        "status": status,
        "name": metadata.get("name") or "AutoDiscovery run",
        "userid": "",
        "description": metadata.get("description") or "",
        "run_details": {
            "execution_id": None,
            "created_at": created_at or now,
            "finished_at": now if status in ("SUCCEEDED", "FAILED") else None,
            "status": status,
            "status_checked_at": now if status == "FAILED" else None,
        },
        "run_stats": {
            "requested_experiments": requested,
            "completed_experiments": completed,
            "pending_experiments": max(requested - completed, 0) if status == "RUNNING" else 0,
            "num_surprising_experiments": sum(bool(e["is_surprising"]) for e in hypotheses),
        },
        "run_metadata": {
            "name": metadata.get("name") or "",
            "description": metadata.get("description"),
            "domain": metadata.get("domain") or None,
            "intent": metadata.get("intent") or None,
            "datasets": [
                {
                    "name": d.get("name"),
                    "description": d.get("description"),
                    "content_type": d.get("content_type"),
                    "file_size_bytes": d.get("file_size_bytes"),
                }
                for d in metadata.get("datasets") or []
                if isinstance(d, dict)
            ],
            "datalib_dirs": datalib_dirs,
            "global_datalib_dirs": metadata.get("global_datalib_dirs") or [],
            "n_experiments": run_args.get("n_experiments"),
            "exploration_weight": run_args.get("exploration_weight"),
            "mcts_selection": run_args.get("mcts_selection"),
            "surprisal_width": run_args.get("surprisal_width"),
            "evidence_weight": run_args.get("evidence_weight"),
            "warmstart_experiments": run_args.get("warmstart_experiments"),
            "n_warmstart": run_args.get("n_warmstart"),
        },
    }


def _replace(path: str, data: bytes) -> None:
    """Write *path* via a temporary file, so a reader never sees half of it."""
    tmp = f"{path}.tmp"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, path)


def generate_report(out_dir: str, status: str = "SUCCEEDED") -> str:
    """Generate a static HTML report directory under *out_dir*/report.

    *status* is the run's, as the web UI names them: ``RUNNING`` while it runs,
    then ``SUCCEEDED`` or ``FAILED``; ``UNKNOWN`` when that cannot be told.

    Returns the path to the generated ``index.html``.
    """
    raw_nodes = _load_nodes(out_dir, prefer_aggregate=status == "SUCCEEDED")
    raw_rich_outputs = _load_rich_outputs(out_dir)
    run_args = _load_args(out_dir)
    metadata = _load_metadata(run_args)

    report_dir = os.path.join(out_dir, "report")
    figures_dir = os.path.join(report_dir, "figures")
    os.makedirs(figures_dir, exist_ok=True)

    rich_outputs = {
        nid: _write_rich_outputs(bundles, nid, figures_dir)
        for nid, bundles in raw_rich_outputs.items()
        if nid != _ROOT_NODE_ID
    }
    experiments = _experiments(raw_nodes, rich_outputs)
    data = {
        "run": _run(out_dir, run_args, metadata, experiments, status),
        "experiments": experiments,
    }
    data_js = f"window.AUTODISCOVERY_REPORT = {json.dumps(data, ensure_ascii=False)};\n"
    _replace(os.path.join(report_dir, "data.js"), data_js.encode())

    if not VIEWER_HTML.is_file():
        raise FileNotFoundError(
            f"the report viewer is not built ({VIEWER_HTML}); the run's data is in "
            f"{report_dir}/data.js. From a source checkout, build the viewer with "
            "`make report-viewer` (needs Node.js and Yarn) and rerun "
            "`python -m autodiscovery.report <out_dir>`."
        )
    index_path = os.path.join(report_dir, "index.html")
    _replace(index_path, VIEWER_HTML.read_bytes())
    return index_path


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        sys.exit("usage: python -m autodiscovery.report <out_dir>")
    # A finished run leaves the aggregate node file; without it the run may still
    # be going, or have stopped early, and the report cannot tell which.
    finished = os.path.exists(os.path.join(sys.argv[1], "mcts_nodes.json"))
    print(generate_report(sys.argv[1], "SUCCEEDED" if finished else "UNKNOWN"))
