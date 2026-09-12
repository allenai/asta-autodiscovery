#!/usr/bin/env python3
"""Rebuild index.html and README.md for analysis/autodiscovery_rl from its registries.

  registry/claude-artifacts.json
      the claude.ai artifact pages; offline copies live under pages/
  registry/key-artifacts.json
      the reports, summaries, figures, launch specs, patches and code in this folder
  registry/source-workspace-registry.json
      Codex's full source-workspace inventory (read for its summary counts)

A claude.ai page links to its copy under pages/ when that file exists here, otherwise to its
live URL. Standard library only. Run from anywhere:

    python analysis/autodiscovery_rl/scripts/build_artifact_index.py
"""

import html
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
E = html.escape
CODE = re.compile(r"`([^`]+)`")


def htext(s):
    """HTML-escaped text with `code` spans rendered as <code>."""
    out, i = [], 0
    for m in CODE.finditer(s):
        out += [E(s[i : m.start()]), f"<code>{E(m.group(1))}</code>"]
        i = m.end()
    return "".join(out) + E(s[i:])


def mtext(s):
    """Markdown-safe text for tables.

    < and > are escaped outside `code` spans (GitHub strips unknown tags), | is escaped, and
    newlines become spaces.
    """
    out, i = [], 0
    for m in CODE.finditer(s):
        out += [s[i : m.start()].replace("<", "&lt;").replace(">", "&gt;"), f"`{m.group(1)}`"]
        i = m.end()
    out.append(s[i:].replace("<", "&lt;").replace(">", "&gt;"))
    return "".join(out).replace("|", "\\|").replace("\n", " ")


def plain(s, n):
    """First ~n characters without code markup, cut at a word boundary."""
    s = s.replace("`", "")
    return s if len(s) <= n else s[:n].rsplit(" ", 1)[0] + "…"


TOPICS = [
    (
        "pipeline-and-reward-server",
        "How the pipeline works",
        "One training step end to end: trainer, reward sidecar, sandboxed experiments, "
        "belief scoring, and where it fails.",
    ),
    (
        "sanity-checks-and-controls",
        "Sanity checks and controls",
        "One-prompt runs with 0/1/coin/codex/keyword rewards that test whether the RL loop "
        "learns at all.",
    ),
    (
        "reward-signal-robustness-and-hacking",
        "Reward signal: robustness and hacking",
        "Whether the surprise reward measures what it should: grounding, re-scoring noise, "
        "belief shift, and exploitation.",
    ),
    ("group-size", "Group size", "The archaeology g16 → g256 sweep and its diagnostics."),
    (
        "belief-models",
        "Belief models",
        "gpt-5-mini vs gemini-3.8-flash vs gpt-5.6-luna as the judge that scores belief shift.",
    ),
    (
        "datasets-tasks-and-prompts",
        "Datasets, tasks and prompts",
        "What the policy sees, which tasks are worth training on, and how complex each dataset is.",
    ),
    (
        "training-runs-and-dashboards",
        "Training runs and dashboards",
        "Where to find every run, its reward curve, and the early dashboards.",
    ),
    (
        "hypotheses-rollouts-and-logs",
        "Hypotheses, rollouts and logs",
        "The raw material: every generated hypothesis, rollout and experiment log, by run.",
    ),
    (
        "provenance-registries-and-code",
        "Registries, provenance and code",
        "Machine-readable inventories, the analysis code that produced the reports, and "
        "preserved patches.",
    ),
]
TOPIC_KEYS = [t[0] for t in TOPICS]
START_HERE = [
    "ee9f104f",
    "5f517052",
    "395f82b0",
    "reports/reward-hacking-similarity-investigation.html",
]


def load(name):
    with open(os.path.join(ROOT, "registry", name)) as f:
        return json.load(f)


claude = load("claude-artifacts.json")
key = load("key-artifacts.json")
source = load("source-workspace-registry.json")["summary"]
pages = claude["pages"]
by_id8 = {p["id"][:8]: p for p in pages}
items = key["items"]
by_path = {k["path"]: k for k in items}


def here(path):
    return os.path.exists(os.path.join(ROOT, path))


def page_href(p):
    return p["bundle_path"] if here(p["bundle_path"]) else p["url"]


def fsize(n):
    if n >= 1e6:
        return f"{n / 1e6:.1f} MB"
    return f"{max(1, round(n / 1e3)):d} KB"


def page_bytes(p):
    """Size of the copy in this folder when there is one, else of the live page as exported."""
    return (
        os.path.getsize(os.path.join(ROOT, p["bundle_path"]))
        if here(p["bundle_path"])
        else p["size_bytes"]
    )


saved = [p for p in pages if here(p["bundle_path"])]
saved_job = [p for p in saved if p["job_specific"]]
job = [p for p in pages if p["job_specific"]]
job_bytes = sum(p["size_bytes"] for p in job)
saved_bytes = sum(page_bytes(p) for p in saved)
rewritten = [p for p in saved if p.get("links_rewritten")]
ig = [p for p in pages if p["group"] == "Information-graph pages"]
perrun = sorted(
    [p for p in pages if p["group"] == "Per-run hypotheses & belief shift"],
    key=lambda p: (p["label"], p["id"]),
)


def topic_entries(t):
    """Pages and key artifacts for one topic.

    Excludes the information-graph chips and per-run rows, which are rendered separately.
    """
    out = [
        ("page", p)
        for p in pages
        if p["topic"] == t
        and p["group"] not in ("Information-graph pages", "Per-run hypotheses & belief shift")
    ]
    out += [("key", k) for k in items if k["topic"] == t]
    return out


def ig_name(p):
    return (
        p["title"]
        .replace(" · Information Graph POC", "")
        .replace(" Information Graph POC", "")
        .strip()
    )


def where_sentence():
    if len(saved_job) == len(job):
        return "Every entry links to its copy in this folder."
    n_live = len(job) - len(saved_job)
    live_size = fsize(sum(p["size_bytes"] for p in job if not here(p["bundle_path"])))
    return (
        f"Entries link to their copy in this folder, except the {n_live} job-specific claude.ai "
        "pages (hypotheses browsers, rollout and log dumps, per-run pages; "
        f"{live_size} together), which are not copied and link to their live page instead."
    )


def opening_notes(code, bold):
    """How the folder behaves for someone who only has a clone of the repo."""
    return (
        f"Opened from a clone, every {code('.html')} page here renders straight from disk: the "
        "data is embedded, nothing is fetched at load time, and the only external resource is a "
        "web font. Links out to claude.ai, wandb and Beaker open their live pages, which need an "
        f"account on those services; entries and related links marked {bold('live')} or "
        f"{bold('live only')} are claude.ai pages that are not saved here. Some linked files are "
        f"not web pages: {code('.csv')}, {code('.tsv')} and {code('.yaml')} may download instead "
        f"of opening, and {code('.md')} files open as raw text. The saved pages do not link back "
        f"here, so start from {code('index.html')}."
    )


def claude_provenance():
    s = (
        "claude.ai pages: exported 2026-09-11 from the artifact registry ({}). Found through the "
        "artifact listing plus a scan of 1,707 local Claude Code session transcripts, each page "
        "opened to confirm it exists and saved as served, with links between saved pages pointing "
        "at each other's local copies.".format(claude["registry_page"])
    )
    if rewritten:
        titles = ", ".join(p["title"] for p in rewritten)
        s += (
            f" In {len(rewritten)} saved pages ({titles}), links to pages not saved here were "
            "rewritten to their live claude.ai URLs, so those files differ from the served page "
            "only in those links."
        )
    return s


# ---------------------------------------------------------------- index.html
CSS = """
:root{color-scheme:light;--bg:#f6f7f9;--panel:#fff;--ink:#141a21;--muted:#5c6773;--line:#e3e7ec;--chip:#eef1f5;
 --run:#2563eb;--codex:#0f766e;--warn:#9a5b12;--warnbg:#fbf3e6;
 --mono:ui-monospace,Menlo,Consolas,monospace;--sans:"Inter",system-ui,-apple-system,sans-serif}
@media(prefers-color-scheme:dark){:root:not([data-theme=light]){color-scheme:dark;--bg:#0e1319;--panel:#161d26;--ink:#e7edf4;
 --muted:#8a97a6;--line:#232c38;--chip:#1c2530;--run:#5b9bff;--codex:#3ec6b0;--warn:#e0a860;--warnbg:#241c10}}
:root[data-theme=dark]{color-scheme:dark;--bg:#0e1319;--panel:#161d26;--ink:#e7edf4;--muted:#8a97a6;--line:#232c38;
 --chip:#1c2530;--run:#5b9bff;--codex:#3ec6b0;--warn:#e0a860;--warnbg:#241c10}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--sans);line-height:1.55}
.wrap{max-width:960px;margin:0 auto;padding:30px 20px 80px;display:flex;\
flex-direction:column;gap:30px}
a{color:var(--run);text-decoration:none}a:hover{text-decoration:underline}
a:focus-visible{outline:2px solid var(--run);outline-offset:2px;border-radius:3px}
.eyebrow{font-family:var(--mono);font-size:11.5px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
h1{font-size:clamp(24px,4vw,32px);margin:6px 0 10px;letter-spacing:-.015em;text-wrap:balance}
h2{font-size:17px;margin:0;text-wrap:balance}
h3{font-size:14px;margin:0;text-wrap:balance}
.lede{color:var(--muted);font-size:14.5px;max-width:72ch;margin:0}
.tally{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:10px}
.tally div{background:var(--panel);border:1px solid var(--line);border-radius:10px;\
padding:12px 14px}
.tally b{display:block;font-size:22px;font-variant-numeric:tabular-nums;letter-spacing:-.01em}
.tally span{font-family:var(--mono);font-size:11.5px;color:var(--muted)}
.nav{display:flex;flex-wrap:wrap;gap:6px}
.nav a{font-family:var(--mono);font-size:12px;background:var(--panel);\
border:1px solid var(--line);border-radius:20px;padding:3px 10px}
.start{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px}
.start a{display:flex;flex-direction:column;gap:3px;background:var(--panel);\
border:1px solid var(--line);border-radius:10px;padding:12px 14px;color:var(--ink)}
.start a:hover{border-color:var(--run);text-decoration:none}
.start b{font-size:14px}.start span{font-size:12.5px;color:var(--muted)}
.topic{display:flex;flex-direction:column;gap:10px;scroll-margin-top:12px}
.topic>.lede{font-size:13.5px}
.list{background:var(--panel);border:1px solid var(--line);border-radius:12px;overflow:hidden}
.item{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:3px 16px;padding:12px 16px;\
border-top:1px solid var(--line)}
.item:first-child{border-top:0}
.item .t{font-weight:600;font-size:14.5px}
.item .m{font-family:var(--mono);font-size:11.5px;color:var(--muted);text-align:right;\
white-space:nowrap;font-variant-numeric:tabular-nums}
.item .d{grid-column:1/-1;font-size:13px;color:var(--muted);max-width:80ch}
.item .x{grid-column:1/-1;font-family:var(--mono);font-size:11.5px;color:var(--muted);\
display:flex;flex-wrap:wrap;gap:4px 12px}
.src{font-family:var(--mono);font-size:10.5px;font-weight:500;padding:1px 7px;\
border-radius:20px;margin-left:6px;white-space:nowrap;
 border:1px solid currentColor;vertical-align:1px}
.src.page{color:var(--run)}.src.key{color:var(--codex)}
.note{font-family:var(--mono);font-size:10.5px;background:var(--chip);color:var(--muted);\
padding:1px 7px;border-radius:20px;margin-left:6px;font-weight:400}
.caution{grid-column:1/-1;font-size:12.5px;color:var(--warn);background:var(--warnbg);\
border-radius:6px;padding:5px 9px}
.chips{display:flex;flex-wrap:wrap;gap:6px}
.chips a{max-width:100%;overflow-wrap:anywhere;font-family:var(--mono);font-size:12px;\
background:var(--panel);border:1px solid var(--line);border-radius:20px;padding:3px 10px}
.tablewrap{background:var(--panel);border:1px solid var(--line);border-radius:12px;overflow-x:auto}
.runs{border-collapse:collapse;width:100%;font-size:13px}
.runs th,.runs td{padding:8px 12px;border-top:1px solid var(--line);text-align:right;\
white-space:nowrap;font-variant-numeric:tabular-nums}
.runs th{border-top:0;font-family:var(--mono);font-size:10.5px;font-weight:500;\
letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}
.runs th:first-child,.runs td:first-child{text-align:left}
.runs td{font-family:var(--mono);font-size:12px;color:var(--muted)}
.runs td:first-child{font-family:var(--sans);font-size:13.5px;color:var(--ink);\
white-space:normal;min-width:15em}
.runs td:first-child a{font-weight:600}
.runs .pid,.runs .dup{display:block;font-family:var(--mono);font-size:11px;color:var(--muted)}
.runs .dup{color:var(--warn)}
.runs tbody tr:hover td{background:var(--chip)}
.prose{display:flex;flex-direction:column;gap:8px;font-size:14px;max-width:76ch}
.prose p,.prose ul{margin:0}.prose li{margin:3px 0}
code{font-family:var(--mono);font-size:12px}
footer{font-family:var(--mono);font-size:11.5px;color:var(--muted);\
border-top:1px solid var(--line);padding-top:14px}
@media(max-width:560px){.item{grid-template-columns:minmax(0,1fr)}.item .m{text-align:left}}
"""


def page_item(p):
    href = page_href(p)
    live = "" if href == p["url"] else ' · <a href="{}">live ↗</a>'.format(E(p["url"]))
    where = "" if here(p["bundle_path"]) else " · live only"
    note = ('<span class="note">{}</span>'.format(htext(p["note"]))) if p["note"] else ""
    meta = " · ".join(x for x in (p["date"], fsize(page_bytes(p))) if x)
    return (
        '<div class="item"><div class="t"><a href="{}">{}</a>'
        '<span class="src page">claude.ai page</span>{}</div>'
        '<div class="m">{}{}{}</div><div class="d">{}</div></div>'.format(
            E(href), E(p["title"]), note, E(meta), where, live, htext(p["what_it_shows"])
        )
    )


def key_item(k):
    extras = [f'<a href="{E(q)}">{E(os.path.basename(q))}</a>' for q in k["extra_paths"] if here(q)]
    rel = [
        '<a href="{}">{}</a>{}'.format(
            E(page_href(by_id8[i])),
            E(by_id8[i]["title"]),
            "" if here(by_id8[i]["bundle_path"]) else " (live)",
        )
        for i in k["related_claude_pages"]
        if i in by_id8
    ]
    x = ""
    if extras:
        x += "<span>also: {}</span>".format(", ".join(extras))
    if rel:
        x += "<span>related pages: {}</span>".format(", ".join(rel))
    meta = " · ".join(
        v for v in (k["date"], fsize(os.path.getsize(os.path.join(ROOT, k["path"])))) if v
    )
    caution = ('<div class="caution">{}</div>'.format(htext(k["caution"]))) if k["caution"] else ""
    return (
        '<div class="item"><div class="t"><a href="{}">{}</a><span class="src key">{}</span>'
        '</div><div class="m">{}</div><div class="d">{}</div>{}{}</div>'.format(
            E(k["path"]),
            E(k["title"]),
            E(k["kind"]),
            E(meta),
            htext(k["what_it_shows"]),
            (f'<div class="x">{x}</div>') if x else "",
            caution,
        )
    )


def start_card(ref):
    if ref in by_id8:
        p = by_id8[ref]
        return '<a href="{}"><b>{}</b><span>{}</span></a>'.format(
            E(page_href(p)), E(p["title"]), E(plain(p["what_it_shows"], 120))
        )
    k = by_path[ref]
    return '<a href="{}"><b>{}</b><span>{}</span></a>'.format(
        E(k["path"]), E(k["title"]), E(plain(k["what_it_shows"], 120))
    )


def render_index():
    o = []
    w = o.append
    w("<title>AutoDiscovery RL artifacts</title>")
    w('<meta name="viewport" content="width=device-width, initial-scale=1">')
    w(
        '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap">'
    )
    w(f"<style>{CSS}</style>")
    w(
        '<div class="wrap"><header><div class="eyebrow">autodiscovery RL · '
        "allenai/asta-autodiscovery · analysis/autodiscovery_rl · exported Sep 11 2026</div>"
    )
    w("<h1>AutoDiscovery RL artifacts</h1>")
    w(
        '<p class="lede">Everything kept from the AutoDiscovery RL work, in one place and '
        "organized by what was studied. Two sources are merged here: the "
        '<span style="color:var(--run)">claude.ai pages</span> written during the project '
        "(dashboards, analyses, explainers, hypothesis browsers), and the "
        '<span style="color:var(--codex)">reports, summaries, figures and code</span> exported '
        f"from the Codex workspace. {htext(where_sentence())}</p></header>"
    )
    n_experiments = source["external_experiments"]
    w(
        f'<div class="tally"><div><b>{len(pages)}</b><span>claude.ai pages · {len(saved)} '
        "saved here</span></div>"
        f"<div><b>{len(items)}</b><span>reports, summaries, figures, specs &amp; code</span></div>"
        f"<div><b>{n_experiments:d}</b><span>Beaker experiments in the source registry</span></div>"
        "<div><b>146</b><span>runs of rollout dumps on weka · 24 GB</span></div></div>"
    )
    w(
        '<section class="topic"><h2>Start here</h2><div class="start">{}</div></section>'.format(
            "".join(start_card(r) for r in START_HERE)
        )
    )
    w(
        '<nav class="nav" aria-label="Topics">{}</nav>'.format(
            "".join(f'<a href="#{k}">{E(t)}</a>' for k, t, _ in TOPICS)
        )
    )
    for k, t, blurb in TOPICS:
        w(f'<section class="topic" id="{k}"><h2>{E(t)}</h2><p class="lede">{E(blurb)}</p>')
        ents = topic_entries(k)
        if ents:
            w(
                '<div class="list">{}</div>'.format(
                    "".join(page_item(x) if kind == "page" else key_item(x) for kind, x in ents)
                )
            )
        if k == "datasets-tasks-and-prompts" and ig:
            chips = "".join(f'<a href="{E(page_href(p))}">{E(ig_name(p))}</a>' for p in ig)
            w(
                f"<h3>Information-graph pages · {len(ig)}</h3>"
                '<p class="lede" style="font-size:13px">One per AutoDiscovery benchmark dataset '
                "(Aug 20–21), all linked from the 29-Task Sweep.</p>"
                f'<div class="chips">{chips}</div>'
            )
        if k == "hypotheses-rollouts-and-logs" and perrun:
            linked_here = sum(here(p["bundle_path"]) for p in perrun)
            copies = (
                "Offline copies are in this folder."
                if linked_here == len(perrun)
                else (
                    "These link to their live pages; offline copies are in the full handoff bundle."
                )
            )
            w(
                f"<h3>Per-run hypotheses &amp; belief shift · {len(perrun)}</h3>"
                '<p class="lede" style="font-size:13px">Pages made Aug 4–5, one per training '
                "run: every hypothesis with its reward and prior→posterior belief shift. "
                f"{copies} Rows marked “same file as” are byte-identical pages shown under "
                "different page ids.</p>"
            )
            w(
                '<div class="tablewrap"><table class="runs"><thead><tr>'
                '<th scope="col">Run</th><th scope="col">Hypotheses</th>'
                '<th scope="col">Steps</th><th scope="col">Datasets</th>'
                '<th scope="col">Batch mean reward</th><th scope="col">Failed reviewer</th>'
                '<th scope="col">Size</th></tr></thead><tbody>'
            )
            for p in perrun:
                dup = ('<span class="dup">{}</span>'.format(E(p["note"]))) if p["note"] else ""
                w(
                    '<tr><td><a href="{}">{}</a><span class="pid">{}</span>{}</td><td>{}</td>'
                    "<td>{:d}</td><td>{:d}</td><td>{:.3f}</td><td>{}%</td><td>{}</td></tr>".format(
                        E(page_href(p)),
                        E(p["label"]),
                        p["id"][:8],
                        dup,
                        format(p["hypotheses"], ","),
                        p["steps"],
                        p["datasets"],
                        p["mean_reward"],
                        p["failed_reviewer_pct"],
                        fsize(p["size_bytes"]),
                    )
                )
            w("</tbody></table></div>")
        w("</section>")
    notes = htext(opening_notes(lambda t: f"`{t}`", lambda t: t))
    storage = f"<p>{notes}</p>" + "".join(f"<p>{s}</p>" for s in storage_paragraphs(html_mode=True))
    w(
        '<section class="prose" id="storage"><h2>What is in Git, and what is not</h2>'
        f"{storage}</section>"
    )
    codex_items = "".join(f"<li>{htext(line)}</li>" for line in key["codex_provenance"])
    w(
        '<section class="prose" id="provenance"><h2>Provenance</h2>'
        f"<p>{htext(claude_provenance())}</p><p><b>Codex workspace export.</b></p>"
        f"<ul>{codex_items}</ul></section>"
    )
    w(
        "<footer>Generated by <code>scripts/build_artifact_index.py</code> from "
        "<code>registry/claude-artifacts.json</code>, <code>registry/key-artifacts.json</code> "
        "and <code>registry/source-workspace-registry.json</code>.</footer></div>"
    )
    return "\n".join(o)


def storage_paragraphs(html_mode):
    code = (lambda s: f"<code>{E(s)}</code>") if html_mode else (lambda s: f"`{s}`")
    bold = (lambda s: f"<b>{E(s)}</b>") if html_mode else (lambda s: f"**{s}**")
    job_line = (
        (
            f"The {len(job)} job-specific pages (hypotheses browsers, rollout and log dumps, "
            f"per-run pages, {fsize(job_bytes)}) are saved here too."
        )
        if len(saved_job) == len(job)
        else (
            "The {} job-specific claude.ai pages (hypotheses browsers, rollout and log dumps, "
            "per-run pages) total {}, with single files up to {}, so they stay out of Git and "
            "link to their live pages; the full offline bundle with all {} pages is {}, kept "
            "outside the repo.".format(
                len(job),
                fsize(job_bytes),
                fsize(max(p["size_bytes"] for p in job)),
                len(pages),
                code("autodiscovery-rl-handoff/"),
            )
        )
    )
    return [
        "In Git: {} of claude.ai pages under {} ({} files), plus the reports, summaries, "
        "figures, launch specs, analysis code, patch and registries exported from the Codex "
        "workspace. {}".format(bold(fsize(saved_bytes)), code("pages/"), len(saved), job_line),
        "Not in Git: raw rollout tensors, JSONL records, reward-server logs, model and optimizer "
        "checkpoints, the Codex rollout dashboard (its source, generated build and data under "
        "dashboard-reproduction/ in the slime workspace, which the source registry records) and "
        "dependency caches. Rollout dumps for 146 runs (24 GB) are on weka at {}, and the Codex "
        "workspace's collected training logs (194 files, 5.8 GiB) at {}. The Codex source "
        "workspace ({:d} files, {:.1f} GiB) and the {:d} Beaker experiments and {:d} "
        "result-dataset IDs it tracked, as of the Sep 11 export, are recorded in {}; local "
        "paths in that file refer to the original slime checkout, and the runs index and "
        "launch specs cite a few later runs that it does not list.".format(
            code(
                "/weka/nora-default/sijial/training-data/rollout_pt_dumps/<experiment-name>-<id6>/"
            ),
            code("/weka/nora-default/sijial/training-logs/autodiscovery-rl-2026-09-11"),
            source["inventory_files"],
            source["inventory_bytes"] / 2**30,
            source["external_experiments"],
            source["result_datasets"],
            code("registry/source-workspace-registry.json"),
        ),
        "Every page embeds its own data, so a saved {} opens offline. Live claude.ai links need "
        "the owner's account unless the page is shared by link.".format(code(".html")),
    ]


# ---------------------------------------------------------------- README.md
def md_cell(s):
    return mtext(s)


def md_page(p):
    href = page_href(p)
    link = "[{}]({})".format(md_cell(p["title"]), href.replace(" ", "%20"))
    if href != p["url"]:
        link += " · [live]({})".format(p["url"])
    return link


def render_readme():
    m = []
    w = m.append
    w("# AutoDiscovery RL artifacts")
    w("")
    w(
        "Everything kept from the AutoDiscovery RL work, organized by what was studied. Two "
        "sources are merged here: the **claude.ai pages** written during the project "
        "(dashboards, analyses, explainers, hypothesis browsers) and the **reports, summaries, "
        "figures and code** exported from the Codex workspace."
    )
    w("")
    w(
        "Open [`index.html`](index.html) in a browser to browse. GitHub shows `.html` files as "
        "source, so clone the repo or download this folder and open them locally. "
        "`registry/claude-artifacts.json` (or `.csv`) and `registry/key-artifacts.json` list "
        "every entry, and `registry/source-workspace-registry.json` holds the full Codex "
        "inventory with Beaker IDs. Rebuild this README and the index with "
        "`python analysis/autodiscovery_rl/scripts/build_artifact_index.py`."
    )
    w("")
    w(
        mtext(where_sentence())
        + " Dates give the period a page covers, or the day it was made for single-job dumps."
    )
    w("")
    w(mtext(opening_notes(lambda t: f"`{t}`", lambda t: f"**{t}**")))
    w("")
    w("## Start here")
    w("")
    for ref in START_HERE:
        if ref in by_id8:
            p = by_id8[ref]
            w("- {} — {}".format(md_page(p), mtext(p["what_it_shows"])))
        else:
            k = by_path[ref]
            w("- [{}]({}) — {}".format(k["title"], k["path"], mtext(k["what_it_shows"])))
    w("")
    w("## Folder layout")
    w("")
    w("| Folder | Contents |")
    w("|---|---|")
    for folder, what in (
        (
            "pages/",
            f"Offline copies of the claude.ai pages ({len(saved)} files), each saved as served "
            "with its data embedded",
        ),
        (
            "reports/",
            "Reward-hacking similarity report, g256 hypothesis rollouts, and the 29-task "
            "dataset-complexity report package",
        ),
        ("figures/", "Reward-versus-rollout PNG and PDF"),
        (
            "summaries/",
            "Group-size and belief-model comparisons, g64 diagnostics, g128 summary, collection "
            "manifest, August outcome table",
        ),
        (
            "launch-specs/",
            "Recovered specs for 206 slime RL experiments, the four-task g256 launch, and the "
            "verified Weka training-log transfer",
        ),
        (
            "scripts/",
            "Analysis, report-rendering, plotting and summary code, plus the registry and index "
            "generators",
        ),
        ("catalog/", "Historical 200-experiment dashboard catalog"),
        (
            "patches/",
            "The uncommitted slime keyword truncation-penalty change, preserved as a patch",
        ),
        (
            "registry/",
            "claude.ai page registry (JSON, CSV), key-artifact registry, and the Codex "
            "source-workspace registry (JSON, HTML, Markdown)",
        ),
    ):
        if here(folder):
            w(f"| [`{folder}`]({folder}) | {what} |")
    for k, t, blurb in TOPICS:
        w("")
        w(f"## {t}")
        w("")
        w(blurb)
        ents = topic_entries(k)
        if ents:
            w("")
            w("| Artifact | Source | What it shows |")
            w("|---|---|---|")
            for kind, x in ents:
                if kind == "page":
                    note = (" *({})*".format(md_cell(x["note"]))) if x["note"] else ""
                    src = (
                        "claude.ai page"
                        + (", {}".format(x["date"]) if x["date"] else "")
                        + f", {fsize(page_bytes(x))}"
                        + ("" if here(x["bundle_path"]) else ", live only")
                    )
                    w(
                        "| {} | {} | {}{} |".format(
                            md_page(x), src, md_cell(x["what_it_shows"]), note
                        )
                    )
                else:
                    extras = ", ".join(
                        f"[{os.path.basename(q)}]({q})" for q in x["extra_paths"] if here(q)
                    )
                    link = "[{}]({})".format(md_cell(x["title"]), x["path"]) + (
                        (f" ({extras})") if extras else ""
                    )
                    src = x["kind"] + (", {}".format(x["date"]) if x["date"] else "")
                    rel = ", ".join(
                        md_page(by_id8[i]) + ("" if here(by_id8[i]["bundle_path"]) else " (live)")
                        for i in x["related_claude_pages"]
                        if i in by_id8
                    )
                    extra = (f" Related: {rel}.") if rel else ""
                    caution = (
                        (" **Note:** {}".format(md_cell(x["caution"]))) if x["caution"] else ""
                    )
                    w(
                        "| {} | {} | {}{}{} |".format(
                            link, src, md_cell(x["what_it_shows"]), extra, caution
                        )
                    )
        if k == "datasets-tasks-and-prompts" and ig:
            w("")
            links = ", ".join(f"[{ig_name(p)}]({page_href(p)})" for p in ig)
            w(
                f"**Information-graph pages ({len(ig)})**, one per benchmark dataset, "
                f"Aug 20–21: {links}"
            )
        if k == "hypotheses-rollouts-and-logs" and perrun:
            w("")
            w(
                "<details><summary>Per-run hypotheses &amp; belief shift "
                f"({len(perrun)} pages, made Aug 4–5)</summary>"
            )
            w("")
            w('Rows marked "same file as" are byte-identical pages shown under different page ids.')
            w("")
            w(
                "| Run | Hypotheses | Steps | Datasets "
                "| Batch mean reward | Failed reviewer | Size |"
            )
            w("|---|---:|---:|---:|---:|---:|---:|")
            for p in perrun:
                dup = (" *({})*".format(p["note"])) if p["note"] else ""
                w(
                    "| [{} ({})]({}){} | {} | {:d} | {:d} | {:.3f} | {}% | {} |".format(
                        md_cell(p["label"]),
                        p["id"][:8],
                        page_href(p),
                        dup,
                        format(p["hypotheses"], ","),
                        p["steps"],
                        p["datasets"],
                        p["mean_reward"],
                        p["failed_reviewer_pct"],
                        fsize(p["size_bytes"]),
                    )
                )
            w("")
            w("</details>")
    w("")
    w("## What is in Git, and what is not")
    w("")
    for s in storage_paragraphs(html_mode=False):
        w("- " + s)
    w("")
    w("## Provenance")
    w("")
    w(mtext(claude_provenance()))
    w("")
    w("**Codex workspace export.**")
    w("")
    for line in key["codex_provenance"]:
        w("- " + line)
    return "\n".join(m) + "\n"


# ---------------------------------------------------------------- write
missing = [k["path"] for k in items if not here(k["path"])]
assert not missing, f"key-artifacts.json lists missing files: {missing}"
assert all(k["topic"] in TOPIC_KEYS for k in items), "unknown topic in key-artifacts.json"
assert all(p["topic"] in TOPIC_KEYS for p in pages), "unknown topic in claude-artifacts.json"
with open(os.path.join(ROOT, "index.html"), "w") as f:
    f.write(
        '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">\n'
        + render_index().replace('<div class="wrap">', '</head><body>\n<div class="wrap">', 1)
        + "\n</body></html>\n"
    )
with open(os.path.join(ROOT, "README.md"), "w") as f:
    f.write(render_readme())
print(
    f"index.html and README.md rebuilt: {len(pages)} claude.ai pages ({len(saved)} saved here), "
    f"{len(items)} key artifacts"
)
