#!/usr/bin/env python3
"""Probe what a vLLM-served Qwen theorizer ACTUALLY returns for a theorizer-shaped
request, so we can see where generated tokens go (content vs reasoning_content vs
dropped).

Prints, per call: finish_reason, usage (completion/reasoning tokens), the tokenized
length of content, and head/tail of both content and reasoning_content RAW — so if
the model emits a <think>...</think> block it is visible verbatim.

Run this against a server started WITHOUT --reasoning-parser to see the untouched
raw generation (the parser can't have dropped anything), and/or WITH the parser to
see how it splits.

    python probe_reasoning.py --model Qwen/Qwen3.5-9B \
        --base_url http://localhost:8000/v1 [--structured]
"""
import argparse
import os

from openai import OpenAI

SYSTEM = (
    "You are an expert scientific hypothesis generator. Given a dataset, propose "
    "novel, testable hypotheses each with a concrete experiment plan. Respond ONLY "
    'with JSON of the form {"experiments": [{"hypothesis": str, "experiment_plan": '
    '{"objective": str, "steps": str}}, ...]}.'
)
USER = (
    "Dataset: a TCGA breast-cancer cohort with clinical variables (age, pathologic "
    "stage, ER/PR/HER2 status, survival) plus per-patient somatic mutation counts and "
    "gene-expression features. Generate exactly 2 new hypotheses with experiment plans."
)


def _content_tokens(text, model):
    try:
        from tokenizers import Tokenizer

        return len(Tokenizer.from_pretrained(model).encode(text).ids)
    except Exception as e:  # noqa: BLE001
        return f"n/a ({e})"


def _preview(s, n=400):
    s = s or ""
    return s if len(s) <= 2 * n else f"{s[:n]}\n   ...[{len(s) - 2 * n} chars elided]...\n{s[-n:]}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--base_url", default=None)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--temperature", type=float, default=1.0)
    ap.add_argument("--structured", action="store_true", help="send the ExperimentList response_format")
    args = ap.parse_args()

    key = os.getenv("OPENAI_API_KEY") or ("EMPTY" if args.base_url else None)
    client = OpenAI(base_url=args.base_url, api_key=key)

    kwargs = dict(
        model=args.model,
        messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": USER}],
        temperature=args.temperature,
        seed=args.seed,
    )
    if args.structured:
        try:
            from autodiscovery.structured_outputs import ExperimentList

            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "ExperimentList", "schema": ExperimentList.model_json_schema(), "strict": False},
            }
        except Exception as e:  # noqa: BLE001
            print(f"[warn] no schema ({e}); running unstructured")

    print(f"=== probe: model={args.model} structured={args.structured} base_url={args.base_url} ===")
    resp = client.chat.completions.create(**kwargs)
    choice = resp.choices[0]
    msg = choice.message
    content = msg.content or ""
    reasoning = getattr(msg, "reasoning_content", None) or ""
    u = resp.usage
    try:
        rt = u.completion_tokens_details.reasoning_tokens
    except Exception:  # noqa: BLE001
        rt = getattr(u, "reasoning_tokens", None)

    print(f"finish_reason = {choice.finish_reason}")
    print(f"usage: prompt={u.prompt_tokens} completion={u.completion_tokens} provider_reasoning_tokens={rt}")
    print(f"content_len_chars={len(content)}  content_tokens={_content_tokens(content, args.model)}")
    print(f"reasoning_content_len_chars={len(reasoning)}")
    print(f"has '<think>' in content: {'<think>' in content}   has '</think>' in content: {'</think>' in content}")
    print("\n----- RAW content (head/tail) -----")
    print(_preview(content))
    print("\n----- RAW reasoning_content (head/tail) -----")
    print(_preview(reasoning) if reasoning else "(empty)")


if __name__ == "__main__":
    main()
