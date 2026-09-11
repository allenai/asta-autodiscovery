#!/usr/bin/env python3
"""Analyze AutoDiscovery rollout reward hacking and hypothesis repetition.

The input directory contains one subdirectory per run, each with a
``rollout_records_fmt3_w_verdict.jsonl`` reward dump.  The script embeds every
deduplicated training hypothesis with all-MiniLM-L6-v2 and writes aggregate
metrics/examples as JSON for the standalone investigation report.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np
from sentence_transformers import SentenceTransformer


RUNS = {
    "g16": {
        "label": "Main reward · g16",
        "family": "group sweep",
        "group_size": 16,
        "expected_steps": 10,
        "experiment_id": "01M0RQFD4QVN3BS85PYDPC0MNX",
        "status": "complete",
    },
    "g32": {
        "label": "Main reward · g32",
        "family": "group sweep",
        "group_size": 32,
        "expected_steps": 10,
        "experiment_id": "01M115W5YND6WFMHTW59SAMTER",
        "status": "complete",
    },
    "g64": {
        "label": "Main reward · g64",
        "family": "group sweep",
        "group_size": 64,
        "expected_steps": 10,
        "experiment_id": "01M115W6MXGAT470P72WTK6ACR",
        "status": "OOM before rollout",
    },
    "g128": {
        "label": "Main reward · g128",
        "family": "group sweep",
        "group_size": 128,
        "expected_steps": 10,
        "experiment_id": "01M115W7FSZ8CWY2S6R1WK2Z65",
        "status": "partial · 1/10 steps · OOM",
    },
    "g256": {
        "label": "Main reward · g256",
        "family": "group sweep",
        "group_size": 256,
        "expected_steps": 10,
        "experiment_id": "01M0RQFDKMHE1GVKJ67EZF9042",
        "status": "complete",
    },
    "zero": {
        "label": "Always zero · g4",
        "family": "pseudo reward",
        "group_size": 4,
        "expected_steps": 10,
        "experiment_id": "01M0EJWDSXKNT3VEAHZZSX7ETE",
        "status": "complete",
    },
    "one": {
        "label": "Always one · g4",
        "family": "pseudo reward",
        "group_size": 4,
        "expected_steps": 10,
        "experiment_id": "01M0EJWE5NZ4FT12SDMD2004TX",
        "status": "complete",
    },
    "coin": {
        "label": "Coin flip · g4",
        "family": "pseudo reward",
        "group_size": 4,
        "expected_steps": 10,
        "experiment_id": "01M0EJWEJ3JMYVEH5DT0GEMHG2",
        "status": "complete",
    },
    "kw-g256": {
        "label": "Keyword: pottery form · g256",
        "family": "keyword reward",
        "group_size": 256,
        "expected_steps": 10,
        "experiment_id": "01M0K7MXZAS8C8NAPBA546SRSP",
        "status": "partial/retried · 3/10 saved steps",
    },
    "kw-pc-g16": {
        "label": "Keyword: pottery form + copper · g16",
        "family": "keyword reward",
        "group_size": 16,
        "expected_steps": 10,
        "experiment_id": "01M0K7MXAHFMNXR343PBSBVCQT",
        "status": "partial/retried · 1/10 steps",
    },
    "kw-pc-g256": {
        "label": "Keyword: pottery form + copper · g256",
        "family": "keyword reward",
        "group_size": 256,
        "expected_steps": 10,
        "experiment_id": "01M0K7MYKCR20S3MKFR73638FB",
        "status": "partial · 9 saved + partial step 9",
    },
    "kw-pcn-g256": {
        "label": "Keyword: pottery form + copper + negative · g256",
        "family": "keyword reward",
        "group_size": 256,
        "expected_steps": 10,
        "experiment_id": "01M0K7MZ646QW8V7X2GHZ67DQZ",
        "status": "failed · no rollout records",
    },
}

END_MARKER_RE = re.compile(r"\s*<\|im_end\|>\s*$", re.IGNORECASE)
TOKEN_RE = re.compile(r"[a-z0-9_]+")
SPACE_RE = re.compile(r"\s+")


def clean_hypothesis(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    value = END_MARKER_RE.sub("", value).strip()
    return SPACE_RE.sub(" ", value)


def normalized_exact(value: str) -> str:
    return " ".join(TOKEN_RE.findall(value.lower()))


def finite_number(value: float | np.floating[Any] | None) -> float | None:
    if value is None:
        return None
    value = float(value)
    return round(value, 6) if math.isfinite(value) else None


def quantile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    return finite_number(np.quantile(np.asarray(values, dtype=np.float32), q))


def mean(values: list[float]) -> float | None:
    return finite_number(statistics.fmean(values)) if values else None


def load_records(path: Path, group_size: int) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Keep the last record per training index and remove ambiguous eval index 0.

    Eval rollouts in this campaign reuse index 0.  Retry arms can also append
    repeated training indices.  Last-write deduplication selects the final retry;
    dropping index 0 removes the eval ambiguity at a cost of one training sample.
    """
    by_index: dict[int, dict[str, Any]] = {}
    raw_count = 0
    duplicate_count = 0
    with path.open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle):
            if not line.strip():
                continue
            raw_count += 1
            record = json.loads(line)
            index = record.get("index")
            if not isinstance(index, int):
                continue
            if index in by_index:
                duplicate_count += 1
            record["_line_no"] = line_no
            by_index[index] = record

    removed_index_zero = int(0 in by_index)
    by_index.pop(0, None)
    records = []
    for index, record in sorted(by_index.items()):
        record["step"] = index // group_size
        record["hypothesis_clean"] = clean_hypothesis(record.get("hypothesis"))
        record["hypothesis_words"] = len(TOKEN_RE.findall(record["hypothesis_clean"]))
        record["reasoning_words"] = len(TOKEN_RE.findall(record.get("reasoning") or ""))
        records.append(record)
    audit = {
        "raw_records": raw_count,
        "retry_or_eval_duplicates": duplicate_count,
        "removed_ambiguous_index_zero": removed_index_zero,
        "deduplicated_training_records": len(records),
    }
    return records, audit


def encode_all(model: SentenceTransformer, run_records: dict[str, list[dict[str, Any]]]) -> None:
    texts: list[str] = []
    refs: list[tuple[str, int]] = []
    for run_id, records in run_records.items():
        for i, record in enumerate(records):
            if record["hypothesis_clean"]:
                texts.append(record["hypothesis_clean"])
                refs.append((run_id, i))
    embeddings = model.encode(
        texts,
        batch_size=128,
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=True,
    ).astype(np.float32)
    for embedding, (run_id, i) in zip(embeddings, refs, strict=True):
        run_records[run_id][i]["_embedding"] = embedding


def nearest_neighbor_similarity(matrix: np.ndarray, block_size: int = 512) -> tuple[np.ndarray, np.ndarray]:
    n = matrix.shape[0]
    if n < 2:
        return np.full(n, np.nan, dtype=np.float32), np.full(n, -1, dtype=np.int32)
    best = np.full(n, -np.inf, dtype=np.float32)
    best_idx = np.full(n, -1, dtype=np.int32)
    for start in range(0, n, block_size):
        stop = min(start + block_size, n)
        scores = matrix[start:stop] @ matrix.T
        rows = np.arange(stop - start)
        scores[rows, np.arange(start, stop)] = -np.inf
        local_idx = np.argmax(scores, axis=1)
        best[start:stop] = scores[rows, local_idx]
        best_idx[start:stop] = local_idx
    return best, best_idx


def top_pairs(
    records: list[dict[str, Any]], matrix: np.ndarray, nearest: np.ndarray, nearest_idx: np.ndarray, limit: int = 8
) -> list[dict[str, Any]]:
    candidates = []
    seen: set[tuple[int, int]] = set()
    for i, j in enumerate(nearest_idx.tolist()):
        if j < 0:
            continue
        pair = (min(i, j), max(i, j))
        if pair in seen:
            continue
        seen.add(pair)
        candidates.append((float(nearest[i]), pair[0], pair[1]))
    candidates.sort(reverse=True)
    out = []
    for similarity, i, j in candidates[:limit]:
        left = records[i]
        right = records[j]
        out.append(
            {
                "similarity": finite_number(similarity),
                "left": {
                    "index": left["index"],
                    "step": left["step"],
                    "reward": left.get("reward"),
                    "text": left["hypothesis_clean"][:800],
                },
                "right": {
                    "index": right["index"],
                    "step": right["step"],
                    "reward": right.get("reward"),
                    "text": right["hypothesis_clean"][:800],
                },
            }
        )
    return out


def common_ngrams(records: list[dict[str, Any]], rewarded_only: bool, limit: int = 8) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    n_docs = 0
    stop = {
        "the", "and", "for", "with", "that", "this", "from", "are", "was", "were", "when", "where",
        "among", "events", "defined", "sustained", "year", "years", "mean", "increase", "increases",
        "change", "changes", "positive", "associated", "significantly", "greater", "higher", "lower",
    }
    for record in records:
        if rewarded_only and float(record.get("reward") or 0) <= 0:
            continue
        tokens = [t for t in TOKEN_RE.findall(record["hypothesis_clean"].lower()) if t not in stop and len(t) > 2]
        if not tokens:
            continue
        n_docs += 1
        doc_ngrams = set()
        for width in (2, 3, 4):
            doc_ngrams.update(" ".join(tokens[i : i + width]) for i in range(len(tokens) - width + 1))
        counts.update(doc_ngrams)
    if not n_docs:
        return []
    return [
        {"phrase": phrase, "document_count": count, "document_rate": finite_number(count / n_docs)}
        for phrase, count in counts.most_common(limit)
    ]


def analyze_run(records: list[dict[str, Any]], meta: dict[str, Any], audit: dict[str, int]) -> dict[str, Any]:
    embedded_records = [record for record in records if "_embedding" in record]
    matrix = (
        np.stack([record["_embedding"] for record in embedded_records])
        if embedded_records
        else np.empty((0, 384), dtype=np.float32)
    )
    nearest, nearest_idx = nearest_neighbor_similarity(matrix)
    for record, value in zip(embedded_records, nearest.tolist(), strict=True):
        record["_nearest_similarity"] = value

    exact_values = [normalized_exact(record["hypothesis_clean"]) for record in embedded_records]
    unique_exact = len(set(exact_values))
    rewards = [float(record.get("reward") or 0.0) for record in records]
    hypothesis_words = [float(record["hypothesis_words"]) for record in embedded_records]
    rewarded_records = [record for record in embedded_records if float(record.get("reward") or 0.0) > 0]
    rewarded_matrix = (
        np.stack([record["_embedding"] for record in rewarded_records])
        if rewarded_records
        else np.empty((0, matrix.shape[1] if matrix.size else 384), dtype=np.float32)
    )
    rewarded_nearest, _ = nearest_neighbor_similarity(rewarded_matrix)
    rewarded_nn_values = [float(value) for value in rewarded_nearest if math.isfinite(float(value))]

    step_results = []
    by_step: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_step[record["step"]].append(record)

    prior_embeddings: list[np.ndarray] = []
    for step in sorted(by_step):
        step_records = by_step[step]
        step_embedded = [record for record in step_records if "_embedding" in record]
        step_matrix = (
            np.stack([record["_embedding"] for record in step_embedded])
            if step_embedded
            else np.empty((0, matrix.shape[1] if matrix.size else 384), dtype=np.float32)
        )
        pair_values: list[float] = []
        if len(step_embedded) > 1:
            similarity = step_matrix @ step_matrix.T
            upper = similarity[np.triu_indices(similarity.shape[0], 1)]
            pair_values = upper.astype(float).tolist()
        earlier_max: list[float] = []
        if prior_embeddings and len(step_embedded):
            prior_matrix = np.concatenate(prior_embeddings, axis=0)
            earlier_max = (step_matrix @ prior_matrix.T).max(axis=1).astype(float).tolist()
        if len(step_embedded):
            prior_embeddings.append(step_matrix)

        step_rewards = [float(record.get("reward") or 0.0) for record in step_records]
        step_exact = [normalized_exact(record["hypothesis_clean"]) for record in step_embedded]
        keyword_flags = [bool(record.get("keyword_matched")) for record in step_records if "keyword_matched" in record]
        oversized_flags = [record["hypothesis_words"] >= 500 for record in step_records]
        trace_as_hypothesis_flags = [
            bool(
                record["hypothesis_clean"].lower().startswith(("thinking process", "we need", "we need answer"))
                and record["reasoning_words"] == 0
            )
            for record in step_records
        ]
        step_results.append(
            {
                "step": step,
                "n": len(step_records),
                "hypothesis_coverage": finite_number(len(step_embedded) / len(step_records)) if step_records else None,
                "reward_mean": mean(step_rewards),
                "reward_positive_rate": mean([float(value > 0) for value in step_rewards]),
                "keyword_match_rate": mean([float(value) for value in keyword_flags]),
                "truncation_rate": mean(
                    [float(record.get("error") == "truncated_response") for record in step_records]
                ),
                "failure_rate": mean([float(bool(record.get("error"))) for record in step_records]),
                "hypothesis_words_median": quantile(
                    [float(record["hypothesis_words"]) for record in step_embedded], 0.5
                ),
                "reasoning_words_median": quantile(
                    [float(record["reasoning_words"]) for record in step_records], 0.5
                ),
                "oversized_hypothesis_rate_500w": mean([float(value) for value in oversized_flags]),
                "trace_as_hypothesis_rate": mean([float(value) for value in trace_as_hypothesis_flags]),
                "exact_duplicate_rate": finite_number(1 - len(set(step_exact)) / len(step_exact)) if step_exact else None,
                "pairwise_similarity_median": quantile(pair_values, 0.5),
                "pairwise_similarity_p90": quantile(pair_values, 0.9),
                "prior_step_max_similarity_median": quantile(earlier_max, 0.5),
                "prior_step_max_similarity_p90": quantile(earlier_max, 0.9),
                "prior_step_repetition_rate_090": mean([float(value >= 0.90) for value in earlier_max]),
            }
        )

    nn_values = [float(value) for value in nearest if math.isfinite(float(value))]
    rewarded_examples = []
    for step in sorted(by_step):
        candidates = [record for record in by_step[step] if float(record.get("reward") or 0.0) > 0]
        if not candidates:
            continue
        record = candidates[0]
        text = record["hypothesis_clean"]
        rewarded_examples.append(
            {
                "step": step,
                "index": record["index"],
                "reward": record.get("reward"),
                "hypothesis_words": record["hypothesis_words"],
                "trace_as_hypothesis": bool(
                    text.lower().startswith(("thinking process", "we need", "we need answer"))
                    and record["reasoning_words"] == 0
                ),
                "text_start": text[:900],
                "text_end": text[-240:] if len(text) > 240 else text,
            }
        )
    return {
        **meta,
        "audit": audit,
        "n_training_records": len(records),
        "n_hypotheses": len(embedded_records),
        "steps_observed": len(by_step),
        "reward_mean": mean(rewards),
        "reward_positive_rate": mean([float(value > 0) for value in rewards]),
        "truncation_rate": mean([float(record.get("error") == "truncated_response") for record in records]),
        "failure_rate": mean([float(bool(record.get("error"))) for record in records]),
        "hypothesis_coverage": finite_number(len(embedded_records) / len(records)) if records else None,
        "hypothesis_words_median": quantile(hypothesis_words, 0.5),
        "hypothesis_words_p90": quantile(hypothesis_words, 0.9),
        "exact_duplicate_rate": finite_number(1 - unique_exact / len(exact_values)) if exact_values else None,
        "nearest_similarity_median": quantile(nn_values, 0.5),
        "nearest_similarity_p90": quantile(nn_values, 0.9),
        "nearest_repetition_rate_090": mean([float(value >= 0.90) for value in nn_values]),
        "nearest_repetition_rate_095": mean([float(value >= 0.95) for value in nn_values]),
        "rewarded_nearest_similarity_median": quantile(rewarded_nn_values, 0.5),
        "rewarded_nearest_repetition_rate_090": mean([float(value >= 0.90) for value in rewarded_nn_values]),
        "oversized_hypothesis_rate_500w": mean(
            [float(record["hypothesis_words"] >= 500) for record in records]
        ),
        "trace_as_hypothesis_rate": mean(
            [
                float(
                    record["hypothesis_clean"].lower().startswith(("thinking process", "we need", "we need answer"))
                    and record["reasoning_words"] == 0
                )
                for record in records
            ]
        ),
        "steps": step_results,
        "rewarded_examples": rewarded_examples,
        "top_similar_pairs": top_pairs(embedded_records, matrix, nearest, nearest_idx),
        "common_rewarded_ngrams": common_ngrams(records, rewarded_only=True),
        "common_all_ngrams": common_ngrams(records, rewarded_only=False),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    args = parser.parse_args()

    run_records: dict[str, list[dict[str, Any]]] = {}
    audits: dict[str, dict[str, int]] = {}
    for run_id, meta in RUNS.items():
        path = args.input_root / run_id / "rollout_records_fmt3_w_verdict.jsonl"
        if not path.exists():
            run_records[run_id] = []
            audits[run_id] = {
                "raw_records": 0,
                "retry_or_eval_duplicates": 0,
                "removed_ambiguous_index_zero": 0,
                "deduplicated_training_records": 0,
            }
            continue
        run_records[run_id], audits[run_id] = load_records(path, meta["group_size"])

    model = SentenceTransformer(str(args.model), device="cpu")
    encode_all(model, run_records)

    runs = {
        run_id: analyze_run(run_records[run_id], meta, audits[run_id])
        if run_records[run_id]
        else {**meta, "audit": audits[run_id], "n_training_records": 0, "n_hypotheses": 0, "steps_observed": 0}
        for run_id, meta in RUNS.items()
    }

    centroids: dict[str, np.ndarray] = {}
    for run_id, records in run_records.items():
        vectors = [record["_embedding"] for record in records if "_embedding" in record]
        if vectors:
            centroid = np.stack(vectors).mean(axis=0)
            norm = np.linalg.norm(centroid)
            centroids[run_id] = centroid / norm if norm else centroid
    centroid_similarity = []
    ids = [run_id for run_id in RUNS if run_id in centroids]
    for left in ids:
        centroid_similarity.append(
            {
                "run": left,
                "values": [finite_number(float(centroids[left] @ centroids[right])) for right in ids],
            }
        )

    result = {
        "method": {
            "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
            "embedding_dimension": 384,
            "deduplication": "last reward record per sample index; index 0 excluded because eval reused it",
            "semantic_repetition_threshold": 0.90,
            "scope": "all non-empty deduplicated training hypotheses in each available reward dump",
        },
        "run_order": list(RUNS),
        "runs": runs,
        "centroid_order": ids,
        "centroid_similarity": centroid_similarity,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
