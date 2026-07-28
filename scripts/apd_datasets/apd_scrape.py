#!/usr/bin/env python3
"""Scrape datasets from awesomedata/awesome-public-datasets into a GCS bucket.

Pipeline (each stage reads the previous stage's jsonl, so you can inspect/edit
between stages):

    catalog   parse README.rst  -> catalog.jsonl   {category,name,description,url,meta_url,icon}
    classify  probe each URL     -> plan.jsonl      + handler {direct|github|kaggle|landing} + candidate files/size
    fetch     download + upload  -> manifest.jsonl  (dry-run by default; --execute to actually pull)

Only `direct` and `github` handlers actually download without extra credentials.
`kaggle` needs the Kaggle API; `landing` pages are cataloged but flagged manual
(unless --discover found data-file links on the page).

Downloads stream to a temp file, then `gcloud storage cp` to
  gs://<bucket>/<prefix>/<Category>/<dataset-slug>/<filename>
Auth/quota use your active `gcloud` login and project.

Examples:
    python apd_scrape.py catalog --rst apd.rst \
        --categories Biology Chemistry Healthcare Neuroscience --out catalog.jsonl
    python apd_scrape.py classify --in catalog.jsonl --out plan.jsonl --discover --workers 16
    python apd_scrape.py fetch --in plan.jsonl \
        --gcs gs://sijia-adv-exp/datasets/awesome-public-datasets \
        --handlers direct github --max-bytes 2000000000 --execute
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request

UA = "Mozilla/5.0 (apd-scrape; +https://github.com/awesomedata/awesome-public-datasets)"
# Strong = unambiguous dataset files, trusted even when discovered on a page.
STRONG_EXTS = (
    ".csv", ".tsv", ".zip", ".gz", ".tgz", ".tar", ".parquet", ".jsonl",
    ".xlsx", ".xls", ".h5", ".hdf5", ".nc", ".rar", ".7z",
    ".sqlite", ".db", ".feather", ".arrow", ".mat", ".npz",
)
# Weak = trusted only when the catalog URL itself ends this way (not via
# discovery), since pages are full of incidental .json/.txt files.
WEAK_EXTS = (".json", ".txt", ".dat", ".data", ".npy")
DATA_EXTS = STRONG_EXTS + WEAK_EXTS
# Incidental site files that are never the dataset, even with a data extension.
DENY_BASENAMES = {
    "manifest.json", "humans.txt", "robots.txt", "package.json", "package-lock.json",
    "composer.json", "sitemap.txt", "favicon.json", "tsconfig.json", "asset-manifest.json",
    "page-data.json", "app-data.json", "config.json", "settings.json",
}
_DENY_SUBSTR = ("page-data", "rst.txt", "sitemap", "manifest", "/humans.txt")
# One entry: * |OK_ICON| `Name - Description [...] <URL>`_ [`Meta <meta_url>`_]
_ENTRY = re.compile(
    r"^\*\s+(?:\|(?P<icon>\w+?)_ICON\|\s+)?`(?P<body>.+?)\s+<(?P<url>[^>]+)>`_"
    r"(?:\s*\[`Meta\s+<(?P<meta>[^>]+)>`_\])?\s*$"
)
_HREF = re.compile(r"""href\s*=\s*["']([^"']+)["']""", re.I)


def _slug(text: str) -> str:
    s = re.sub(r"[^0-9A-Za-z._-]+", "-", text).strip("-")
    return s[:80] or "dataset"


# -- stage 1: catalog ---------------------------------------------------------


def _section_bounds(lines: list[str], name: str) -> tuple[int, int] | None:
    """Return [start, end) line indices of a `Name\\n----` RST section body."""
    for i in range(len(lines) - 1):
        if lines[i].strip() == name and set(lines[i + 1].strip()) == {"-"} and lines[i + 1].strip():
            start = i + 2
            for j in range(start, len(lines) - 1):
                # Next section header: a title line followed by an underline of ---- .
                nxt = lines[j + 1].strip()
                if lines[j].strip() and nxt and set(nxt) == {"-"} and len(nxt) >= 3:
                    return start, j
            return start, len(lines)
    return None


def cmd_catalog(args) -> None:
    lines = open(args.rst, encoding="utf-8").read().splitlines()
    rows = []
    for category in args.categories:
        bounds = _section_bounds(lines, category)
        if bounds is None:
            print(f"[warn] section not found: {category}", file=sys.stderr)
            continue
        start, end = bounds
        for line in lines[start:end]:
            m = _ENTRY.match(line.strip())
            if not m:
                continue
            body = m.group("body")
            name, _, desc = body.partition(" - ")
            desc = re.sub(r"\s*\[\.\.\.\]\s*$", "", desc).strip()
            rows.append(
                {
                    "category": category,
                    "name": name.strip(),
                    "description": desc,
                    "url": m.group("url").strip(),
                    "meta_url": (m.group("meta") or "").strip() or None,
                    "icon": (m.group("icon") or "").upper() or None,
                }
            )
    with open(args.out, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    by_cat: dict[str, int] = {}
    for r in rows:
        by_cat[r["category"]] = by_cat.get(r["category"], 0) + 1
    print(f"[catalog] {len(rows)} entries -> {args.out}")
    for c, n in by_cat.items():
        print(f"    {c}: {n}")


# -- stage 2: classify --------------------------------------------------------


def _head(url: str, timeout: int = 20):
    """Return (final_url, status, content_type, content_length) or (url, None, ...)."""
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.url, r.status, r.headers.get("Content-Type", ""), r.headers.get("Content-Length")
    except Exception:
        return url, None, "", None


def _get_text(url: str, limit: int = 400_000, timeout: int = 20) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            ctype = r.headers.get("Content-Type", "")
            if "html" not in ctype and "text" not in ctype and "xml" not in ctype:
                return ""
            return r.read(limit).decode("utf-8", "replace")
    except Exception:
        return ""


def _looks_direct(url: str) -> bool:
    """Catalog URL itself is a data file (strong or weak ext)."""
    path = urllib.parse.urlparse(url).path.lower()
    return path.endswith(DATA_EXTS)


def _is_real_data_link(url: str) -> bool:
    """A *discovered* link worth downloading: strong ext, not an incidental file."""
    path = urllib.parse.urlparse(url).path.lower()
    base = os.path.basename(path)
    if base in DENY_BASENAMES or any(s in path for s in _DENY_SUBSTR):
        return False
    return path.endswith(STRONG_EXTS)


def _classify_one(entry: dict, discover: bool) -> dict:
    url = entry["url"]
    host = urllib.parse.urlparse(url).netloc.lower()
    out = dict(entry, handler="landing", candidates=[], size_hint=None, note=None)

    if _looks_direct(url):
        _, _, _, clen = _head(url)
        out["handler"] = "direct"
        out["candidates"] = [url]
        out["size_hint"] = int(clen) if clen and clen.isdigit() else None
        return out

    if "github.com" in host:
        parts = [p for p in urllib.parse.urlparse(url).path.split("/") if p]
        if len(parts) >= 2 and parts[0] not in ("awesomedata",):
            owner, repo = parts[0], parts[1].removesuffix(".git")
            out["handler"] = "github"
            out["candidates"] = [f"https://codeload.github.com/{owner}/{repo}/tar.gz/HEAD"]
            out["note"] = f"{owner}/{repo} default-branch tarball"
            return out

    if "kaggle.com" in host:
        out["handler"] = "kaggle"
        out["note"] = "needs Kaggle API credentials"
        return out

    # Unknown landing page: sniff headers, optionally scan for data-file links.
    final, status, ctype, clen = _head(url)
    if status and ("html" not in ctype.lower()) and any(
        t in ctype.lower() for t in ("csv", "zip", "octet-stream", "parquet", "json", "excel")
    ):
        out["handler"] = "direct"
        out["candidates"] = [final]
        out["size_hint"] = int(clen) if clen and clen.isdigit() else None
        return out

    if discover:
        html = _get_text(url)
        found = []
        for href in _HREF.findall(html):
            absu = urllib.parse.urljoin(final if status else url, href)
            if _is_real_data_link(absu) and absu not in found:
                found.append(absu)
            if len(found) >= 20:
                break
        if found:
            out["handler"] = "direct"
            out["candidates"] = found
            out["note"] = f"{len(found)} data link(s) discovered on page"
    out["note"] = out["note"] or ("dead/unreachable" if status is None else "no direct data link")
    return out


def cmd_classify(args) -> None:
    entries = [json.loads(l) for l in open(args.__dict__["in"], encoding="utf-8")]
    results: list[dict] = [None] * len(entries)
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(_classify_one, e, args.discover): i for i, e in enumerate(entries)}
        for done, fut in enumerate(concurrent.futures.as_completed(futs), 1):
            i = futs[fut]
            results[i] = fut.result()
            if done % 10 == 0 or done == len(entries):
                print(f"    classified {done}/{len(entries)}", file=sys.stderr)
    with open(args.out, "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    tally: dict[str, int] = {}
    for r in results:
        tally[r["handler"]] = tally.get(r["handler"], 0) + 1
    print(f"[classify] {len(results)} entries -> {args.out}")
    for h, n in sorted(tally.items(), key=lambda kv: -kv[1]):
        print(f"    {h}: {n}")


# -- stage 3: fetch -----------------------------------------------------------


def _download(url: str, dest: str, max_bytes: int) -> int:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    total = 0
    with urllib.request.urlopen(req, timeout=60) as r, open(dest, "wb") as f:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise ValueError(f"exceeds max-bytes ({max_bytes})")
            f.write(chunk)
    return total


def _gcs_cp(local: str, gcs_uri: str) -> None:
    subprocess.run(["gcloud", "storage", "cp", local, gcs_uri], check=True, capture_output=True)


def cmd_fetch(args) -> None:
    entries = [json.loads(l) for l in open(args.__dict__["in"], encoding="utf-8")]
    handlers = set(args.handlers)
    manifest = []
    planned = downloaded = skipped = failed = 0
    for e in entries:
        if e["handler"] not in handlers or not e["candidates"]:
            skipped += 1
            continue
        if args.categories and e["category"] not in args.categories:
            skipped += 1
            continue
        slug = _slug(e["name"])
        for url in e["candidates"]:
            fname = os.path.basename(urllib.parse.urlparse(url).path) or "download"
            if e["handler"] == "github":
                fname = f"{slug}.tar.gz"
            gcs_uri = f"{args.gcs.rstrip('/')}/{e['category']}/{slug}/{fname}"
            planned += 1
            if not args.execute:
                sz = f"~{e['size_hint']}B" if e.get("size_hint") else "size?"
                print(f"[plan] {e['category']}/{slug}: {url} ({sz}) -> {gcs_uri}")
                continue
            tmp = tempfile.NamedTemporaryFile(delete=False, dir=args.tmp_dir)
            tmp.close()
            try:
                n = _download(url, tmp.name, args.max_bytes)
                sha = hashlib.sha256(open(tmp.name, "rb").read()).hexdigest()
                _gcs_cp(tmp.name, gcs_uri)
                manifest.append(
                    {"category": e["category"], "name": e["name"], "source_url": url,
                     "gcs_uri": gcs_uri, "bytes": n, "sha256": sha}
                )
                downloaded += 1
                print(f"[ok] {gcs_uri} ({n} B)")
            except Exception as ex:  # noqa: BLE001 - report and continue
                failed += 1
                print(f"[fail] {e['name']} <{url}>: {type(ex).__name__}: {ex}", file=sys.stderr)
            finally:
                os.path.exists(tmp.name) and os.unlink(tmp.name)
    if args.execute and args.manifest:
        with open(args.manifest, "w", encoding="utf-8") as f:
            for m in manifest:
                f.write(json.dumps(m, ensure_ascii=False) + "\n")
    print(f"[fetch] planned={planned} downloaded={downloaded} failed={failed} skipped={skipped}"
          + (f" -> {args.manifest}" if args.execute and args.manifest else ""))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("catalog")
    c.add_argument("--rst", required=True)
    c.add_argument("--categories", nargs="+", required=True)
    c.add_argument("--out", default="catalog.jsonl")
    c.set_defaults(func=cmd_catalog)

    cl = sub.add_parser("classify")
    cl.add_argument("--in", required=True)
    cl.add_argument("--out", default="plan.jsonl")
    cl.add_argument("--discover", action="store_true", help="scan landing pages for data-file links")
    cl.add_argument("--workers", type=int, default=16)
    cl.set_defaults(func=cmd_classify)

    fp = sub.add_parser("fetch")
    fp.add_argument("--in", required=True)
    fp.add_argument("--gcs", required=True, help="gs://bucket/prefix")
    fp.add_argument("--handlers", nargs="+", default=["direct", "github"])
    fp.add_argument("--categories", nargs="*", default=None, help="restrict to these categories")
    fp.add_argument("--max-bytes", type=int, default=2_000_000_000)
    fp.add_argument("--tmp-dir", default=None)
    fp.add_argument("--manifest", default="manifest.jsonl")
    fp.add_argument("--execute", action="store_true", help="actually download+upload (default: dry-run plan)")
    fp.set_defaults(func=cmd_fetch)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
