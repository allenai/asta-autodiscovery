#!/usr/bin/env python3
"""Profile the 29 AutoDiscovery benchmark tasks and render a self-contained report.

The report separates measurable data complexity (volume, width, missingness,
multi-table structure, and type mix) from statistical risk.  It also measures
the exact Qwen3.5 chat-template length of the task1 prompts used by the g256
sweep, because Slime filters prompts that exceed --rollout-max-prompt-len.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import math
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from transformers import AutoTokenizer


PROMPT_LIMIT = 8192
TABULAR_SUFFIXES = {".csv", ".dta"}
TEMPORAL_NAME = re.compile(
    r"(^|[^a-z])(date|time|year|month|day|week|ce|bce|calbp|period|wave|quarter)([^a-z]|$)",
    re.IGNORECASE,
)
@dataclass
class FileProfile:
    name: str
    kind: str
    bytes: int
    rows: int | None = None
    columns: int | None = None
    missing_pct: float | None = None
    numeric_columns: int | None = None
    categorical_columns: int | None = None
    temporal_columns: int | None = None


@dataclass
class TaskProfile:
    task: str
    dataset_id: str
    source: str
    domain: str
    workflow_tags: str
    source_files: int
    tabular_tables: int
    auxiliary_files: int
    total_bytes: int
    total_rows: int
    max_rows: int
    declared_columns: int
    actual_columns: int
    max_columns: int
    total_cells: int
    missing_pct: float
    numeric_pct: float
    categorical_pct: float
    temporal_columns: int
    low_cardinality_numeric_columns: int
    high_cardinality_text_columns: int
    constant_columns: int
    duplicate_row_pct: float
    cross_table_shared_columns: int
    rows_per_column: float
    schema_tokens: int
    full_prompt_tokens_median: int
    full_prompt_tokens_max: int
    prompt_rows: int
    prompt_limit_status: str
    prompt_headroom: int
    files: list[FileProfile] = field(default_factory=list)
    scale_score: float = 0.0
    schema_score: float = 0.0
    structure_score: float = 0.0
    quality_score: float = 0.0
    shape_score: float = 0.0
    type_mix_score: float = 0.0
    complexity_score: float = 0.0
    complexity_tier: str = ""
    statistical_risk: str = ""
    flags: list[str] = field(default_factory=list)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=Path("/private/tmp/autods_dataset_complexity"),
    )
    parser.add_argument(
        "--tokenizer",
        type=Path,
        required=True,
        help="Local Qwen3.5 tokenizer snapshot.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
    )
    return parser.parse_args()


def read_csv_robust(path: Path) -> pd.DataFrame:
    first_line = path.open("r", encoding="utf-8", errors="replace").readline()
    delimiter = "\t" if first_line.count("\t") > first_line.count(",") else ","
    try:
        return pd.read_csv(path, sep=delimiter, low_memory=False)
    except (UnicodeDecodeError, pd.errors.ParserError):
        return pd.read_csv(path, sep=delimiter, low_memory=False, encoding="latin-1", engine="python")


def read_table(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".dta":
        return pd.read_stata(path, convert_categoricals=False)
    return read_csv_robust(path)


def metadata_entries(metadata: dict[str, Any], source: str) -> list[dict[str, Any]]:
    if source == "blade":
        return [{"name": "data.csv", "columns": metadata.get("data_desc", {}).get("fields", [])}]
    return metadata.get("datasets", [])


def declared_column_count(entry: dict[str, Any], source: str) -> int:
    if source == "blade":
        return len(entry.get("columns", []))
    return len(entry.get("columns", {}).get("raw", []))


def task_raw_dir(data_root: Path, metadata_path: Path, dataset_id: str, source: str) -> Path:
    if source == "blade":
        return data_root / "blade" / dataset_id
    dirname = metadata_path.parent.name
    candidates = sorted((data_root / "discoverybench").glob(f"*/{dirname}"))
    if len(candidates) != 1:
        raise FileNotFoundError(f"Expected one raw-data directory for {dataset_id}; found {candidates}")
    return candidates[0]


def find_prompt_path(prompt_root: Path, dataset_id: str) -> Path:
    if dataset_id == "archaeology":
        return prompt_root / "arch64_fmt3" / "fmt3_pairs_related_train.parquet"
    return prompt_root / f"task1_{dataset_id}" / "fmt3_pairs_related_train.parquet"


def token_count(tokenizer: Any, text: str) -> int:
    return len(tokenizer(text, add_special_tokens=False)["input_ids"])


def prompt_metrics(prompt_path: Path, tokenizer: Any) -> tuple[int, int, int, int]:
    frame = pd.read_parquet(prompt_path)
    full_counts: list[int] = []
    schema_counts: list[int] = []
    for row in frame.itertuples(index=False):
        messages = [dict(message) for message in row.messages]
        rendered = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        full_counts.append(token_count(tokenizer, rendered))
        user_text = messages[-1]["content"]
        description = user_text.split("Description:", 1)[-1].split("\nResearch intent:", 1)[0]
        schema_counts.append(token_count(tokenizer, description))
    return (
        int(round(float(np.median(schema_counts)))),
        int(round(float(np.median(full_counts)))),
        max(full_counts),
        len(frame),
    )


def profile_task(
    dataset_id: str,
    source: str,
    metadata_path: Path,
    data_root: Path,
    prompt_root: Path,
    tokenizer: Any,
) -> TaskProfile:
    metadata = json.loads(metadata_path.read_text())
    entries = metadata_entries(metadata, source)
    raw_dir = task_raw_dir(data_root, metadata_path, dataset_id, source)
    file_profiles: list[FileProfile] = []
    frames: list[pd.DataFrame] = []
    column_sets: list[set[str]] = []
    total_missing = 0
    total_cells = 0
    numeric_columns = 0
    categorical_columns = 0
    temporal_columns = 0
    low_cardinality_numeric = 0
    high_cardinality_text = 0
    constant_columns = 0
    duplicate_rows = 0
    total_rows_for_duplicates = 0

    for entry in entries:
        name = entry.get("name", "data.csv")
        path = raw_dir / name
        if not path.exists() and source == "blade":
            path = raw_dir / "data.csv"
        if not path.exists():
            raise FileNotFoundError(f"Missing raw file for {dataset_id}: {path}")
        if path.suffix.lower() not in TABULAR_SUFFIXES:
            file_profiles.append(FileProfile(name=name, kind="auxiliary", bytes=path.stat().st_size))
            continue

        frame = read_table(path)
        frames.append(frame)
        rows, columns = frame.shape
        cells = rows * columns
        missing = int(frame.isna().sum().sum())
        numeric = list(frame.select_dtypes(include=[np.number, "bool"]).columns)
        categorical = [column for column in frame.columns if column not in numeric]
        temporal = [column for column in frame.columns if TEMPORAL_NAME.search(str(column))]
        low_cardinality_numeric += sum(
            frame[column].nunique(dropna=True) <= max(20, int(rows * 0.01)) for column in numeric
        )
        high_cardinality_text += sum(
            rows > 0 and frame[column].nunique(dropna=True) / rows >= 0.5 for column in categorical
        )
        constant_columns += sum(frame[column].nunique(dropna=True) <= 1 for column in frame.columns)
        duplicate_rows += int(frame.duplicated().sum())
        total_rows_for_duplicates += rows
        total_missing += missing
        total_cells += cells
        numeric_columns += len(numeric)
        categorical_columns += len(categorical)
        temporal_columns += len(temporal)
        column_sets.append({str(column).strip().lower() for column in frame.columns})
        file_profiles.append(
            FileProfile(
                name=name,
                kind="tabular",
                bytes=path.stat().st_size,
                rows=rows,
                columns=columns,
                missing_pct=(100.0 * missing / cells) if cells else 0.0,
                numeric_columns=len(numeric),
                categorical_columns=len(categorical),
                temporal_columns=len(temporal),
            )
        )

    shared_columns: set[str] = set()
    for i, left in enumerate(column_sets):
        for right in column_sets[i + 1 :]:
            shared_columns.update(left & right)

    declared_columns = sum(declared_column_count(entry, source) for entry in entries)
    actual_columns = sum(len(frame.columns) for frame in frames)
    total_rows = sum(len(frame) for frame in frames)
    max_rows = max((len(frame) for frame in frames), default=0)
    max_columns = max((len(frame.columns) for frame in frames), default=0)
    schema_tokens, prompt_median, prompt_max, prompt_rows = prompt_metrics(
        find_prompt_path(prompt_root, dataset_id), tokenizer
    )
    if prompt_max > PROMPT_LIMIT:
        prompt_status = "filtered"
    elif prompt_max >= int(PROMPT_LIMIT * 0.9):
        prompt_status = "near-cap"
    else:
        prompt_status = "safe"

    domain = metadata.get("domain", source)
    workflow_tags = str(metadata.get("workflow_tags", ""))
    if source == "blade":
        domain = "blade"
    total_columns_typed = numeric_columns + categorical_columns
    profile = TaskProfile(
        task=dataset_id.replace("_", "-"),
        dataset_id=dataset_id,
        source=source,
        domain=domain,
        workflow_tags=workflow_tags,
        source_files=len(entries),
        tabular_tables=len(frames),
        auxiliary_files=len(entries) - len(frames),
        total_bytes=sum(item.bytes for item in file_profiles),
        total_rows=total_rows,
        max_rows=max_rows,
        declared_columns=declared_columns,
        actual_columns=actual_columns,
        max_columns=max_columns,
        total_cells=total_cells,
        missing_pct=(100.0 * total_missing / total_cells) if total_cells else 0.0,
        numeric_pct=(100.0 * numeric_columns / total_columns_typed) if total_columns_typed else 0.0,
        categorical_pct=(100.0 * categorical_columns / total_columns_typed) if total_columns_typed else 0.0,
        temporal_columns=temporal_columns,
        low_cardinality_numeric_columns=low_cardinality_numeric,
        high_cardinality_text_columns=high_cardinality_text,
        constant_columns=constant_columns,
        duplicate_row_pct=(100.0 * duplicate_rows / total_rows_for_duplicates) if total_rows_for_duplicates else 0.0,
        cross_table_shared_columns=len(shared_columns),
        rows_per_column=(total_rows / actual_columns) if actual_columns else math.inf,
        schema_tokens=schema_tokens,
        full_prompt_tokens_median=prompt_median,
        full_prompt_tokens_max=prompt_max,
        prompt_rows=prompt_rows,
        prompt_limit_status=prompt_status,
        prompt_headroom=PROMPT_LIMIT - prompt_max,
        files=file_profiles,
    )
    return profile


def percentile_ranks(values: list[float]) -> list[float]:
    return (pd.Series(values).rank(method="average", pct=True) * 100.0).tolist()


def add_scores(profiles: list[TaskProfile]) -> None:
    scale = percentile_ranks([math.log1p(profile.total_cells) for profile in profiles])
    width = percentile_ranks([math.log1p(profile.actual_columns) for profile in profiles])
    schema = percentile_ranks([math.log1p(profile.schema_tokens) for profile in profiles])

    for profile, scale_rank, width_rank, schema_rank in zip(profiles, scale, width, schema, strict=True):
        profile.scale_score = scale_rank
        profile.schema_score = 0.55 * schema_rank + 0.45 * width_rank
        profile.structure_score = min(100.0, 24.0 * max(0, profile.source_files - 1))
        if profile.cross_table_shared_columns:
            profile.structure_score = min(100.0, profile.structure_score + 8.0)
        profile.quality_score = min(100.0, profile.missing_pct / 35.0 * 100.0)
        profile.shape_score = min(100.0, (profile.actual_columns / max(profile.total_rows, 1)) / 0.25 * 100.0)
        dominant_type = max(profile.numeric_pct, profile.categorical_pct) / 100.0
        profile.type_mix_score = 100.0 * (1.0 - abs(dominant_type - 0.5) * 2.0)
        profile.complexity_score = (
            0.23 * profile.scale_score
            + 0.23 * profile.schema_score
            + 0.18 * profile.structure_score
            + 0.14 * profile.quality_score
            + 0.12 * profile.shape_score
            + 0.10 * profile.type_mix_score
        )

        if profile.total_rows < 100 or profile.rows_per_column < 3:
            profile.statistical_risk = "high"
        elif profile.total_rows < 300 or profile.rows_per_column < 10:
            profile.statistical_risk = "moderate"
        else:
            profile.statistical_risk = "lower"

        flags: list[str] = []
        if profile.prompt_limit_status == "filtered":
            flags.append("prompt filtered at 8,192")
        elif profile.prompt_limit_status == "near-cap":
            flags.append("prompt near 8,192 cap")
        if profile.source_files > 1:
            flags.append(f"{profile.source_files} source files")
        if profile.actual_columns >= 50:
            flags.append("wide schema")
        if profile.total_rows >= 10_000:
            flags.append("large-n")
        if profile.missing_pct >= 20:
            flags.append("missing-heavy")
        if profile.total_rows < 100:
            flags.append("small-n")
        if profile.rows_per_column < 3:
            flags.append("p≈n or p>n")
        if profile.temporal_columns:
            flags.append("temporal fields")
        if profile.actual_columns != profile.declared_columns - profile.auxiliary_files:
            flags.append("raw/schema width mismatch")
        profile.flags = flags

    ordered_scores = sorted(profile.complexity_score for profile in profiles)
    q50, q75, q90 = np.quantile(ordered_scores, [0.50, 0.75, 0.90])
    for profile in profiles:
        if profile.complexity_score >= q90:
            profile.complexity_tier = "very high"
        elif profile.complexity_score >= q75:
            profile.complexity_tier = "high"
        elif profile.complexity_score >= q50:
            profile.complexity_tier = "medium"
        else:
            profile.complexity_tier = "low"


def human_bytes(size: int) -> str:
    if size >= 1024**2:
        return f"{size / 1024**2:.1f} MiB"
    if size >= 1024:
        return f"{size / 1024:.1f} KiB"
    return f"{size} B"


def human_int(value: int) -> str:
    return f"{value:,}"


def csv_rows(profiles: list[TaskProfile]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for rank, profile in enumerate(sorted(profiles, key=lambda p: p.complexity_score, reverse=True), start=1):
        row = {"rank": rank, **asdict(profile)}
        row.pop("files")
        row["flags"] = "; ".join(profile.flags)
        rows.append(row)
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def task_rows_html(profiles: list[TaskProfile]) -> str:
    ranked = sorted(profiles, key=lambda profile: profile.complexity_score, reverse=True)
    rows: list[str] = []
    for rank, profile in enumerate(ranked, start=1):
        flags = "".join(f'<span class="chip">{esc(flag)}</span>' for flag in profile.flags)
        rows.append(
            f"""
            <tr data-search="{esc(profile.task + ' ' + profile.source + ' ' + ' '.join(profile.flags))}">
              <td data-sort="{rank}">{rank}</td>
              <td class="task"><strong>{esc(profile.task)}</strong><span>{esc(profile.source)} · {esc(profile.domain)}</span></td>
              <td data-sort="{profile.complexity_score:.4f}"><span class="score">{profile.complexity_score:.1f}</span><span class="tier tier-{profile.complexity_tier.replace(' ', '-')}">{esc(profile.complexity_tier)}</span></td>
              <td data-sort="{profile.source_files}">{profile.source_files}</td>
              <td data-sort="{profile.total_rows}">{human_int(profile.total_rows)}</td>
              <td data-sort="{profile.actual_columns}">{profile.actual_columns}</td>
              <td data-sort="{profile.total_cells}">{human_int(profile.total_cells)}</td>
              <td data-sort="{profile.total_bytes}">{human_bytes(profile.total_bytes)}</td>
              <td data-sort="{profile.missing_pct:.5f}">{profile.missing_pct:.1f}%</td>
              <td data-sort="{profile.schema_tokens}">{human_int(profile.schema_tokens)}</td>
              <td class="prompt-{profile.prompt_limit_status}" data-sort="{profile.full_prompt_tokens_max}">{human_int(profile.full_prompt_tokens_max)}</td>
              <td data-sort="{profile.rows_per_column:.5f}">{profile.rows_per_column:.1f}</td>
              <td><span class="risk risk-{profile.statistical_risk}">{profile.statistical_risk}</span></td>
              <td class="flags">{flags or '<span class="muted">—</span>'}</td>
            </tr>
            """
        )
    return "\n".join(rows)


def file_details_html(profiles: list[TaskProfile]) -> str:
    sections: list[str] = []
    for profile in sorted(profiles, key=lambda p: p.complexity_score, reverse=True):
        file_rows: list[str] = []
        for item in profile.files:
            file_rows.append(
                "<tr>"
                f"<td>{esc(item.name)}</td><td>{item.kind}</td><td>{human_bytes(item.bytes)}</td>"
                f"<td>{human_int(item.rows) if item.rows is not None else '—'}</td>"
                f"<td>{item.columns if item.columns is not None else '—'}</td>"
                f"<td>{f'{item.missing_pct:.1f}%' if item.missing_pct is not None else '—'}</td>"
                "</tr>"
            )
        sections.append(
            f"""
            <details>
              <summary>{esc(profile.task)} <span>{profile.source_files} file(s), {human_int(profile.total_rows)} rows, {profile.actual_columns} raw columns</span></summary>
              <table class="mini"><thead><tr><th>File</th><th>Kind</th><th>Bytes</th><th>Rows</th><th>Columns</th><th>Missing</th></tr></thead>
              <tbody>{''.join(file_rows)}</tbody></table>
            </details>
            """
        )
    return "\n".join(sections)


def score_bars_html(profile: TaskProfile) -> str:
    components = [
        ("Data scale", profile.scale_score, 23),
        ("Schema/search", profile.schema_score, 23),
        ("Multi-file structure", profile.structure_score, 18),
        ("Missingness", profile.quality_score, 14),
        ("p/n shape", profile.shape_score, 12),
        ("Type mix", profile.type_mix_score, 10),
    ]
    return "".join(
        f'<div class="component"><span>{esc(label)} <small>{weight}%</small></span><i><b style="width:{score:.1f}%"></b></i><em>{score:.0f}</em></div>'
        for label, score, weight in components
    )


def render_html(profiles: list[TaskProfile]) -> str:
    ranked = sorted(profiles, key=lambda p: p.complexity_score, reverse=True)
    total_bytes = sum(profile.total_bytes for profile in profiles)
    filtered = [profile for profile in profiles if profile.prompt_limit_status == "filtered"]
    near_cap = [profile for profile in profiles if profile.prompt_limit_status == "near-cap"]
    highest = ranked[:5]
    top_cards = "".join(
        f'<article><span>#{idx}</span><h3>{esc(profile.task)}</h3><strong>{profile.complexity_score:.1f}</strong><p>{esc(", ".join(profile.flags[:3]) or "single-table profile")}</p></article>'
        for idx, profile in enumerate(highest, start=1)
    )
    notable = {profile.dataset_id: profile for profile in profiles}
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AutoDiscovery · 29-task dataset complexity</title>
<style>
:root{{--ink:#17233a;--muted:#687386;--paper:#f5f6f8;--card:#fff;--line:#dfe3e8;--blue:#275dad;--teal:#16867a;--amber:#bd6c00;--red:#b42318}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--paper);color:var(--ink);font:14px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif}}
main{{max-width:1500px;margin:0 auto;padding:40px 28px 80px}} h1{{font-size:31px;letter-spacing:-.035em;margin:0 0 8px}} h2{{font-size:20px;margin:0 0 14px}} h3{{margin:0}} p{{margin:7px 0}} .lede{{max-width:900px;color:var(--muted);font-size:16px}}
.meta{{margin-top:12px;color:var(--muted);font-size:12px}} .grid{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:26px 0}}
.metric,.panel,.top article{{background:var(--card);border:1px solid var(--line);border-radius:12px;box-shadow:0 1px 2px #17233a0a}} .metric{{padding:18px}} .metric span{{display:block;color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.06em}} .metric strong{{font-size:27px;display:block;margin-top:5px}} .metric p{{color:var(--muted);font-size:12px}}
.warning{{border-left:5px solid var(--red);background:#fff6f5;padding:17px 20px;margin:18px 0;border-radius:8px}} .warning strong{{color:var(--red)}}
.panel{{padding:22px;margin:18px 0}} .top{{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px}} .top article{{padding:16px;position:relative}} .top article>span{{color:var(--muted);font-size:11px}} .top article strong{{font-size:25px;color:var(--blue)}} .top article p{{font-size:12px;color:var(--muted)}}
.split{{display:grid;grid-template-columns:1.1fr .9fr;gap:18px}} .component{{display:grid;grid-template-columns:170px 1fr 35px;gap:10px;align-items:center;margin:9px 0}} .component span{{font-size:12px}} .component small{{color:var(--muted)}} .component i{{height:8px;background:#e8ebef;border-radius:9px;overflow:hidden}} .component b{{display:block;height:100%;background:linear-gradient(90deg,var(--teal),var(--blue))}} .component em{{font-style:normal;text-align:right;color:var(--muted)}}
.controls{{display:flex;gap:10px;align-items:center;margin:0 0 12px}} input{{min-width:300px;padding:9px 11px;border:1px solid var(--line);border-radius:7px;font:inherit}} .table-wrap{{overflow:auto;border:1px solid var(--line);border-radius:9px}} table{{width:100%;border-collapse:collapse;background:#fff}} th{{position:sticky;top:0;background:#26364f;color:#fff;text-align:center;font-size:11px;letter-spacing:.035em;padding:10px 8px;white-space:nowrap;cursor:pointer}} td{{border-bottom:1px solid #ebedf0;padding:9px 8px;text-align:right;white-space:nowrap}} td.task,td.flags{{text-align:left}} td.task span{{display:block;color:var(--muted);font-size:11px}} tbody tr:hover{{background:#f5f9ff}} .score{{font-weight:700;font-size:16px;display:block}} .tier,.risk,.chip{{display:inline-block;border-radius:999px;padding:2px 7px;font-size:10px}} .tier{{background:#e9eef6;color:#31496d}} .tier-very-high{{background:#fde7e5;color:#8f2018}} .tier-high{{background:#fff0d8;color:#8a5000}} .tier-medium{{background:#e5f1fb;color:#245a8c}} .risk-high{{background:#fde7e5;color:#8f2018}} .risk-moderate{{background:#fff0d8;color:#8a5000}} .risk-lower{{background:#e3f5ed;color:#17663d}} .chip{{margin:1px 3px 1px 0;background:#edf0f4;color:#526075}} .prompt-filtered{{background:#fff0ef;color:var(--red);font-weight:700}} .prompt-near-cap{{background:#fff6e8;color:#8a5000;font-weight:700}} .muted{{color:var(--muted)}}
details{{background:#fff;border:1px solid var(--line);border-radius:8px;margin:8px 0}} summary{{cursor:pointer;padding:12px 14px;font-weight:600}} summary span{{font-weight:400;color:var(--muted);margin-left:8px}} .mini{{border-top:1px solid var(--line)}} .mini th{{position:static;background:#eef1f5;color:var(--ink);cursor:default}} .mini td{{font-size:12px}}
.notes li{{margin:7px 0}} code{{background:#edf0f4;padding:2px 5px;border-radius:4px}} footer{{color:var(--muted);font-size:12px;margin-top:24px}} @media(max-width:900px){{.grid,.top,.split{{grid-template-columns:1fr 1fr}}}} @media(max-width:600px){{main{{padding:24px 14px}}.grid,.top,.split{{grid-template-columns:1fr}}input{{min-width:0;width:100%}}}}
</style>
</head>
<body><main>
<h1>AutoDiscovery dataset complexity · 29 tasks</h1>
<p class="lede">A raw-data audit of the exact DiscoveryBench + BLADE bundle behind the group-size sweep. Complexity here is operational: how much data the reward-side analyst must load and reason over, how broad the hypothesis search space is, and how much cleaning/joining is implied. It is not a claim that one scientific domain is intrinsically harder than another.</p>
<p class="meta">Generated {now} · Qwen3.5-9B tokenizer · sweep prompt cap {PROMPT_LIMIT:,} tokens · raw source snapshot s3://ai2-asta-workspaces/autods/datasets</p>

<section class="grid">
  <div class="metric"><span>Tasks</span><strong>{len(profiles)}</strong><p>14 DiscoveryBench + 15 BLADE</p></div>
  <div class="metric"><span>Raw data</span><strong>{human_bytes(total_bytes)}</strong><p>Referenced analysis files only</p></div>
  <div class="metric"><span>Largest table</span><strong>{human_int(max(p.max_rows for p in profiles))}</strong><p>soccer rows</p></div>
  <div class="metric"><span>Widest schema</span><strong>{max(p.declared_columns for p in profiles)}</strong><p>worldbank indicators, across 6 tables</p></div>
</section>

<div class="warning"><strong>One task is silently excluded by the current prompt cap.</strong> <code>worldbank-education-gdp-indicators</code> renders to {notable['worldbank_education_gdp_indicators'].full_prompt_tokens_max:,} tokens—{abs(notable['worldbank_education_gdp_indicators'].prompt_headroom):,} over the 8,192-token limit. Slime’s dataset loader filters over-length prompts instead of truncating them, leaving this one-row task empty. <code>requirements-engineering-for-ML-enabled-systems</code> is near the cap at {notable['requirements_engineering_for_ML_enabled_systems'].full_prompt_tokens_max:,} tokens.</div>

<section class="panel"><h2>Highest operational complexity</h2><div class="top">{top_cards}</div></section>

<section class="split">
  <div class="panel"><h2>How the index is composed</h2>{score_bars_html(ranked[0])}<p class="meta">Bars show component percentiles/severity for the top-ranked task ({esc(ranked[0].task)}). Weights: data scale 23%, schema/search breadth 23%, multi-file structure 18%, missingness 14%, p/n shape 12%, type mix 10%.</p></div>
  <div class="panel notes"><h2>Interpretation for g256</h2><ul>
    <li><strong>Keep g256 for reward sparsity/diversity, not because tables are large.</strong> Sampling cost is fixed by group size; raw-data complexity mainly changes reward-evaluation latency and failure risk.</li>
    <li><strong>Do not treat all 29 tasks as equivalent.</strong> The top cluster combines very wide schemas, multiple files, large n, or heavy missingness; the bottom cluster consists mostly of compact single tables.</li>
    <li><strong>Separate power risk from operational complexity.</strong> Tiny or p≈n datasets can be statistically fragile even when cheap to load. That can make binary surprise noisier.</li>
  </ul></div>
</section>

<section class="panel"><h2>Ranked task table</h2><div class="controls"><input id="search" type="search" placeholder="Filter task or flag…"><span class="meta">Click any header to sort.</span></div><div class="table-wrap"><table id="tasks"><thead><tr>
<th>Rank</th><th>Task</th><th>Index</th><th>Files</th><th>Rows Σ</th><th>Cols Σ</th><th>Cells</th><th>Bytes</th><th>Missing</th><th>Schema tok.</th><th>Prompt max</th><th>Rows/col</th><th>Stat. risk</th><th>Flags</th>
</tr></thead><tbody>{task_rows_html(profiles)}</tbody></table></div>
<p class="meta">Rows Σ and columns Σ are summed across referenced tabular files; cells is the sum of rows × columns per table. Rows/col is a simple dimensionality diagnostic, not degrees of freedom. Prompt max includes the Qwen chat template and lineage history.</p></section>

<section class="panel"><h2>File-level audit</h2>{file_details_html(profiles)}</section>

<section class="panel notes"><h2>Method and limitations</h2><ul>
  <li>Raw CSV/DTA tables were read directly. Tab-delimited files with a <code>.csv</code> suffix were detected from their header. The phylogenetic tree is counted as an auxiliary source, not forced into a table.</li>
  <li>The relative complexity index is intentionally transparent, but its weights are judgment calls. Use the component columns and flags for scheduling decisions rather than treating a one-point score difference as meaningful.</li>
  <li>Missingness is cell-weighted. Type mix uses parsed storage types; numeric-coded categories are separately counted in the machine-readable export but do not change the headline index.</li>
  <li><code>nls-raw</code> and <code>nls-bmi-raw</code> reference the same 12,686 × 61 raw NLS table. They remain separate because they are separate benchmark tasks and prompt histories.</li>
  <li>Prompt measurements reproduce Slime’s filter path: apply the Qwen3.5 chat template, tokenize the rendered string with <code>add_special_tokens=False</code>, then compare with <code>--rollout-max-prompt-len</code>.</li>
</ul></section>
<footer>Companion CSV and JSON contain the exact metrics and per-file profiles.</footer>
</main>
<script>
const table=document.getElementById('tasks'), body=table.tBodies[0], search=document.getElementById('search');
search.addEventListener('input',()=>{{const q=search.value.toLowerCase();[...body.rows].forEach(r=>r.hidden=!r.dataset.search.toLowerCase().includes(q));}});
[...table.tHead.rows[0].cells].forEach((th,i)=>{{let asc=true;th.addEventListener('click',()=>{{const rows=[...body.rows];rows.sort((a,b)=>{{const av=a.cells[i].dataset.sort??a.cells[i].innerText.toLowerCase(),bv=b.cells[i].dataset.sort??b.cells[i].innerText.toLowerCase();const an=Number(av),bn=Number(bv);const cmp=Number.isFinite(an)&&Number.isFinite(bn)?an-bn:String(av).localeCompare(String(bv));return asc?cmp:-cmp;}});rows.forEach(r=>body.appendChild(r));asc=!asc;}});}});
</script></body></html>"""


def main() -> None:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    output_dir = (args.output_dir or repo_root / "output" / "autods-dataset-complexity-29").resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    config_path = repo_root / "examples" / "autodiscovery_rl" / "datasets_dbench_blade.json"
    config = json.loads(config_path.read_text())["datasets"]
    tokenizer = AutoTokenizer.from_pretrained(args.tokenizer, local_files_only=True, trust_remote_code=True)
    profiles: list[TaskProfile] = []
    for entry in config:
        metadata_path = (config_path.parent / entry["metadata_path"]).resolve()
        profiles.append(
            profile_task(
                dataset_id=entry["dataset_id"],
                source=entry["dataset_metadata_type"],
                metadata_path=metadata_path,
                data_root=args.data_root.resolve(),
                prompt_root=(args.data_root / "prompts").resolve(),
                tokenizer=tokenizer,
            )
        )

    if len(profiles) != 29:
        raise RuntimeError(f"Expected 29 tasks, got {len(profiles)}")
    add_scores(profiles)
    rows = csv_rows(profiles)
    csv_path = output_dir / "autods-dataset-complexity-29.csv"
    json_path = output_dir / "autods-dataset-complexity-29.json"
    html_path = output_dir / "autods-dataset-complexity-29.html"
    write_csv(csv_path, rows)
    json_path.write_text(json.dumps([asdict(profile) for profile in profiles], indent=2) + "\n")
    html_path.write_text(render_html(profiles))

    print(f"wrote {html_path}")
    print(f"wrote {csv_path}")
    print(f"wrote {json_path}")
    print("\nTop 10 by relative operational complexity:")
    for rank, profile in enumerate(sorted(profiles, key=lambda p: p.complexity_score, reverse=True)[:10], 1):
        print(
            f"{rank:2d}. {profile.task:55s} {profile.complexity_score:5.1f}  "
            f"rows={profile.total_rows:7,d} cols={profile.actual_columns:3d} "
            f"miss={profile.missing_pct:5.1f}% prompt={profile.full_prompt_tokens_max:4d}"
        )


if __name__ == "__main__":
    main()
