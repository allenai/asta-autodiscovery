#!/usr/bin/env python3
"""L1 seed-determinism benchmark for the AutoDiscovery theorizer.

Sends the SAME experiment-generation request N times with a FIXED seed and
checks whether the model returns identical outputs. Mirrors the real theorizer
request shape (temperature, seed, reasoning_effort, and optionally the
ExperimentList structured-output schema) so the result reflects the actual
generation path.

Works against a vLLM-served theorizer (--base_url http://localhost:PORT/v1) or
the default OpenAI endpoint. Also reports per-call token usage (incl.
reasoning_tokens) and whether reasoning_content is returned, so it doubles as a
check that the vLLM reasoning parser is active.

Exit code 0 if all N outputs are identical, 1 otherwise.

Example:
    python benchmark_seed.py --model Qwen/Qwen3.5-9B \
        --base_url http://localhost:8000/v1 --seed 42 --n 3
"""
import argparse
import hashlib
import json
import os
import sys

from openai import OpenAI

DEFAULT_SYSTEM = (
    "You are an expert scientific hypothesis generator. Given a dataset, propose "
    "novel, testable hypotheses each with a concrete experiment plan. Respond ONLY "
    'with JSON of the form {"experiments": [{"hypothesis": str, "experiment_plan": '
    '{"objective": str, "steps": str}}, ...]}.'
)
DEFAULT_USER = (
    "Dataset: a TCGA breast-cancer cohort with clinical variables (age, pathologic "
    "stage, ER/PR/HER2 status, survival time and vital status) plus per-patient "
    "somatic mutation counts and gene-expression features. Generate exactly 4 new "
    "hypotheses with their experiment plans."
)


def _load_experiment_schema():
    """Return the ExperimentList JSON schema, or None if unavailable."""
    try:
        from autodiscovery.structured_outputs import ExperimentList

        return ExperimentList.model_json_schema()
    except Exception as e:  # noqa: BLE001 - diagnostic tool, never hard-fail
        print(f"[warn] could not load ExperimentList schema ({e}); running unstructured")
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--base_url", default=None, help="vLLM endpoint; omit for OpenAI")
    ap.add_argument("--api_key", default=None)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--n", type=int, default=3, help="number of repeated calls")
    ap.add_argument("--temperature", type=float, default=1.0)
    ap.add_argument("--reasoning_effort", default="medium")
    ap.add_argument("--max_tokens", type=int, default=None)
    ap.add_argument(
        "--structured",
        action="store_true",
        default=True,
        help="use the ExperimentList response_format (default: on)",
    )
    ap.add_argument("--no-structured", dest="structured", action="store_false")
    args = ap.parse_args()

    key = args.api_key or os.getenv("OPENAI_API_KEY") or ("EMPTY" if args.base_url else None)
    client = OpenAI(base_url=args.base_url, api_key=key)

    response_format = None
    if args.structured:
        schema = _load_experiment_schema()
        if schema is not None:
            response_format = {
                "type": "json_schema",
                "json_schema": {"name": "ExperimentList", "schema": schema, "strict": False},
            }

    messages = [
        {"role": "system", "content": DEFAULT_SYSTEM},
        {"role": "user", "content": DEFAULT_USER},
    ]

    print(
        f"=== seed benchmark: model={args.model} base_url={args.base_url or 'OpenAI'} "
        f"seed={args.seed} n={args.n} temperature={args.temperature} "
        f"reasoning_effort={args.reasoning_effort} structured={response_format is not None} ==="
    )

    contents, reasonings = [], []
    for i in range(args.n):
        kwargs = dict(
            model=args.model,
            messages=messages,
            temperature=args.temperature,
            seed=args.seed,
        )
        if args.max_tokens is not None:
            kwargs["max_tokens"] = args.max_tokens
        if response_format is not None:
            kwargs["response_format"] = response_format
        extra = {"reasoning_effort": args.reasoning_effort} if args.reasoning_effort else {}
        try:
            resp = client.chat.completions.create(extra_body=extra, **kwargs)
        except Exception as e:  # noqa: BLE001
            print(f"[warn] call {i + 1} with reasoning_effort failed ({e}); retrying without it")
            resp = client.chat.completions.create(**kwargs)

        msg = resp.choices[0].message
        content = msg.content or ""
        reasoning = getattr(msg, "reasoning_content", None)
        contents.append(content)
        reasonings.append(reasoning or "")

        u = resp.usage
        ct = getattr(u, "completion_tokens", None) if u else None
        rt = None
        try:
            rt = u.completion_tokens_details.reasoning_tokens
        except Exception:  # noqa: BLE001
            rt = getattr(u, "reasoning_tokens", None) if u else None
        chash = hashlib.sha256(content.encode()).hexdigest()[:12]
        rhash = hashlib.sha256((reasoning or "").encode()).hexdigest()[:12]
        print(
            f"call {i + 1}: content_len={len(content)} content_sha={chash} "
            f"reasoning_len={len(reasoning or '')} reasoning_sha={rhash} "
            f"completion_tokens={ct} reasoning_tokens={rt}"
        )

    uniq_content = set(contents)
    uniq_reason = set(reasonings)
    identical = len(uniq_content) == 1
    print(
        f"\n=== RESULT (seed={args.seed}): {len(uniq_content)} unique content(s), "
        f"{len(uniq_reason)} unique reasoning trace(s) across {args.n} calls ==="
    )
    print("CONTENT DETERMINISTIC: identical across all calls" if identical else "CONTENT NON-DETERMINISTIC: outputs differ")

    if not identical:
        base = contents[0]
        for i in range(1, len(contents)):
            if contents[i] != base:
                a, b = base, contents[i]
                j = 0
                while j < min(len(a), len(b)) and a[j] == b[j]:
                    j += 1
                print(f"first divergence (call 1 vs call {i + 1}) at char {j}:")
                print("  call1  :", repr(a[max(0, j - 20) : j + 40]))
                print(f"  call{i + 1}  :", repr(b[max(0, j - 20) : j + 40]))
                break

    for i, o in enumerate(contents):
        try:
            n = len(json.loads(o).get("experiments", []))
        except Exception:  # noqa: BLE001
            n = "UNPARSEABLE"
        print(f"  call{i + 1} parsed experiments={n}")

    sys.exit(0 if identical else 1)


if __name__ == "__main__":
    main()
