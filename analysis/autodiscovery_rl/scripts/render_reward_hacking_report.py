#!/usr/bin/env python3
"""Render the standalone AutoDiscovery reward-hacking investigation report."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


TEMPLATE = r'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AutoDiscovery reward-hacking and repetition investigation</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #081019;
      --panel: #111c28;
      --panel-2: #162536;
      --ink: #eef6f7;
      --muted: #9fb2ba;
      --line: #294051;
      --cyan: #5ad7d0;
      --blue: #72aaff;
      --amber: #ffc16b;
      --red: #ff7e7e;
      --green: #77dfa5;
      --violet: #bf9cff;
      --shadow: 0 18px 48px rgb(0 0 0 / 26%);
    }
    * { box-sizing: border-box; }
    html { scroll-behavior: smooth; }
    body {
      margin: 0;
      background:
        radial-gradient(circle at 8% 0%, rgb(90 215 208 / 11%), transparent 31rem),
        radial-gradient(circle at 94% 6%, rgb(191 156 255 / 10%), transparent 28rem),
        var(--bg);
      color: var(--ink);
      font: 15px/1.55 ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    a { color: var(--cyan); }
    code { font: .9em ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
    .shell { width: min(1240px, calc(100% - 32px)); margin: 0 auto; padding: 46px 0 80px; }
    header { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 28px; align-items: end; margin-bottom: 25px; }
    .eyebrow { color: var(--cyan); font-size: 12px; font-weight: 700; letter-spacing: .15em; text-transform: uppercase; }
    h1 { max-width: 900px; margin: 8px 0 12px; font-size: clamp(34px, 5.5vw, 66px); line-height: 1; letter-spacing: -.045em; }
    h2 { margin: 0; font-size: 24px; letter-spacing: -.02em; }
    h3 { margin: 0; font-size: 17px; }
    p { margin: 0; }
    .lede { max-width: 880px; color: var(--muted); font-size: 17px; }
    .stamp { color: var(--muted); font: 12px/1.45 ui-monospace, SFMono-Regular, Menlo, monospace; text-align: right; white-space: nowrap; }
    .verdict {
      display: grid;
      grid-template-columns: minmax(0, 1.45fr) minmax(260px, .55fr);
      gap: 16px;
      margin-bottom: 18px;
    }
    .verdict-main, .verdict-side, .panel, .stat, .callout, details {
      border: 1px solid var(--line);
      border-radius: 17px;
      background: linear-gradient(145deg, rgb(22 37 54 / 94%), rgb(17 28 40 / 94%));
      box-shadow: var(--shadow);
    }
    .verdict-main { padding: 25px; border-color: rgb(255 126 126 / 44%); }
    .verdict-main .label { color: var(--red); font-weight: 700; }
    .verdict-main strong { display: block; max-width: 820px; margin: 8px 0 10px; font-size: clamp(24px, 3.6vw, 43px); line-height: 1.08; letter-spacing: -.035em; }
    .verdict-main p, .verdict-side p { color: var(--muted); }
    .verdict-side { display: grid; align-content: center; gap: 8px; padding: 23px; }
    .verdict-side strong { font-size: 18px; }
    .stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin: 0 0 28px; }
    .stat { min-height: 112px; padding: 17px; }
    .stat strong { display: block; margin-bottom: 4px; font-size: 31px; line-height: 1.05; letter-spacing: -.035em; }
    .stat span { color: var(--muted); }
    nav { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 34px; }
    nav a { padding: 7px 11px; border: 1px solid var(--line); border-radius: 999px; color: var(--muted); text-decoration: none; }
    nav a:hover { border-color: var(--cyan); color: var(--cyan); }
    section { margin: 0 0 42px; scroll-margin-top: 16px; }
    .section-head { display: flex; justify-content: space-between; gap: 25px; align-items: end; margin-bottom: 15px; }
    .section-head p { max-width: 690px; color: var(--muted); text-align: right; }
    .panel { padding: 20px; margin-bottom: 14px; }
    .panel-head { display: flex; justify-content: space-between; align-items: baseline; gap: 20px; margin-bottom: 14px; }
    .panel-head p { color: var(--muted); font-size: 13px; }
    .chart { min-height: 260px; }
    .chart svg { display: block; width: 100%; height: auto; overflow: visible; }
    .chart .grid { stroke: var(--line); stroke-width: 1; }
    .chart .axis-label, .chart .tick { fill: var(--muted); font: 12px ui-sans-serif, system-ui, sans-serif; }
    .chart .direct-label { fill: var(--ink); font: 12px ui-sans-serif, system-ui, sans-serif; font-weight: 700; }
    .legend { display: flex; flex-wrap: wrap; gap: 13px; color: var(--muted); font-size: 13px; }
    .legend span { display: inline-flex; gap: 6px; align-items: center; }
    .swatch { width: 17px; height: 3px; border-radius: 2px; }
    .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
    .callout { padding: 20px; border-color: rgb(255 193 107 / 37%); }
    .callout strong { color: var(--amber); }
    .callout p + p { margin-top: 9px; }
    .table-wrap { overflow-x: auto; }
    table { width: 100%; border-collapse: collapse; }
    th, td { padding: 10px 11px; border-bottom: 1px solid var(--line); text-align: right; vertical-align: top; }
    th { color: var(--muted); font-size: 12px; font-weight: 700; letter-spacing: .04em; text-transform: uppercase; }
    th:first-child, td:first-child { text-align: left; }
    tbody tr:hover { background: rgb(90 215 208 / 4%); }
    .status { display: inline-flex; padding: 3px 8px; border-radius: 999px; border: 1px solid var(--line); color: var(--muted); font-size: 12px; }
    .status.complete { border-color: rgb(119 223 165 / 40%); color: var(--green); }
    .status.partial { border-color: rgb(255 193 107 / 40%); color: var(--amber); }
    .status.failed { border-color: rgb(255 126 126 / 40%); color: var(--red); }
    .danger { color: var(--red); }
    .warn { color: var(--amber); }
    .good { color: var(--green); }
    .muted { color: var(--muted); }
    .controls { display: flex; flex-wrap: wrap; gap: 12px; align-items: end; margin-bottom: 14px; }
    label { color: var(--muted); font-size: 13px; }
    select { display: block; min-width: 290px; margin-top: 5px; padding: 9px 11px; border: 1px solid var(--line); border-radius: 9px; background: var(--panel); color: var(--ink); font: inherit; }
    .explore-summary { display: flex; flex-wrap: wrap; gap: 8px; margin: 10px 0 16px; }
    .badge { padding: 5px 8px; border: 1px solid var(--line); border-radius: 999px; color: var(--muted); font-size: 12px; }
    details { padding: 14px 16px; margin: 10px 0; }
    summary { cursor: pointer; font-weight: 700; }
    blockquote { margin: 12px 0 0; padding: 13px 15px; border-left: 3px solid var(--cyan); background: rgb(8 16 25 / 42%); color: #dce9ec; white-space: pre-wrap; overflow-wrap: anywhere; }
    .pair { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 12px; }
    .pair div { min-width: 0; }
    .pair p { margin-bottom: 6px; color: var(--muted); font-size: 12px; }
    .pair blockquote { height: 100%; margin: 0; }
    .findings { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }
    .finding { padding: 17px 0; border-top: 1px solid var(--line); }
    .finding strong { display: block; margin-bottom: 6px; }
    .finding p { color: var(--muted); }
    .method-list { display: grid; grid-template-columns: 1fr 1fr; gap: 10px 26px; padding-left: 20px; }
    .method-list li { color: var(--muted); }
    footer { padding-top: 22px; border-top: 1px solid var(--line); color: var(--muted); font-size: 13px; }
    @media (max-width: 850px) {
      header, .verdict, .grid-2 { grid-template-columns: 1fr; }
      .stamp { text-align: left; }
      .stats { grid-template-columns: 1fr 1fr; }
      .section-head { display: block; }
      .section-head p { margin-top: 6px; text-align: left; }
      .findings { grid-template-columns: 1fr; }
      .method-list { grid-template-columns: 1fr; }
    }
    @media (max-width: 560px) {
      .shell { width: min(100% - 20px, 1240px); padding-top: 28px; }
      .stats { grid-template-columns: 1fr; }
      .pair { grid-template-columns: 1fr; }
      select { min-width: 0; width: 100%; }
      .panel { padding: 14px; }
      th, td { padding: 8px; }
    }
  </style>
</head>
<body>
  <main class="shell">
    <header>
      <div>
        <div class="eyebrow">AutoDiscovery · offline rollout audit</div>
        <h1>Reward hacking and hypothesis repetition</h1>
        <p class="lede">An investigation of the main-reward group-size sweep and pseudo-reward controls, with every available training hypothesis embedded for semantic-similarity analysis.</p>
      </div>
      <div class="stamp">Generated __GENERATED__<br>6,506 embedded hypotheses</div>
    </header>

    <div class="verdict">
      <article class="verdict-main">
        <div class="label">Clear reward hacking in one arm</div>
        <strong>The conjunction-keyword g256 policy learns to expose its entire reasoning trace, not to write a better hypothesis.</strong>
        <p>Reward is near zero through step 6, reaches 26.6% at step 7, then becomes 100% at steps 8 and 9. At the same transition, the median extracted “hypothesis” jumps from 56 words to 7,681 words and every extraction is a leaked, unfinished reasoning trace containing the target phrases.</p>
      </article>
      <aside class="verdict-side">
        <strong>Main-reward runs are mixed.</strong>
        <p>g256 shows improved reward and fewer harness failures but also strong semantic convergence. g32 instead develops late truncation and loses reward. Neither is as diagnostic as the keyword exploit.</p>
      </aside>
    </div>

    <div class="stats">
      <div class="stat"><strong class="danger">100%</strong><span>keyword reward at steps 8–9</span></div>
      <div class="stat"><strong class="danger">100%</strong><span>reasoning-misparse rate at steps 8–9</span></div>
      <div class="stat"><strong>7,681</strong><span>median extracted words at step 8, up from 56</span></div>
      <div class="stat"><strong>97.8%</strong><span>rewarded outputs with a semantic neighbor ≥ 0.90</span></div>
    </div>

    <nav aria-label="Report sections">
      <a href="#keyword">Keyword exploit</a>
      <a href="#sweep">Group-size sweep</a>
      <a href="#controls">Pseudo rewards</a>
      <a href="#similarity">Repetition explorer</a>
      <a href="#method">Method and limits</a>
    </nav>

    <section id="keyword">
      <div class="section-head">
        <h2>Keyword exploit: abrupt and mechanistically clear</h2>
        <p><code>pottery form AND copper</code>, g256. Step 9 is partial (177 records); steps 0–8 are saved training steps.</p>
      </div>
      <div class="panel">
        <div class="panel-head"><h3>Reward and parser failure move together</h3><p>Fraction of deduplicated training rollouts</p></div>
        <div id="keyword-rate-chart" class="chart" aria-label="Keyword reward and reasoning-misparse rate by training step"></div>
        <div class="legend"><span><i class="swatch" style="background:var(--red)"></i>keyword reward</span><span><i class="swatch" style="background:var(--amber)"></i>reasoning trace misparsed as hypothesis</span><span><i class="swatch" style="background:var(--violet)"></i>semantic neighbor in prior steps ≥ 0.90</span></div>
      </div>
      <div class="grid-2">
        <div class="panel">
          <div class="panel-head"><h3>Extracted hypothesis length</h3><p>Median words · logarithmic vertical scale</p></div>
          <div id="keyword-length-chart" class="chart" aria-label="Median extracted hypothesis words by training step"></div>
        </div>
        <div class="callout">
          <strong>Root cause</strong>
          <p>The historical keyword reward extracts everything after <code>&lt;/think&gt;</code>. If that marker is missing, it scans the entire response. At steps 8–9 the model runs to a long, unfinished “Thinking Process” trace; because that trace mentions both target terms, it receives reward 1.</p>
          <p>A generic length penalty may reduce the symptom, but the direct fix is to reject truncated/malformed responses and require a bounded final hypothesis before keyword matching.</p>
        </div>
      </div>
      <details open>
        <summary>Representative rewarded outputs across the transition</summary>
        <div id="keyword-examples"></div>
      </details>
    </section>

    <section id="sweep">
      <div class="section-head">
        <h2>Main-reward group-size sweep</h2>
        <p>Comparable main-harness arms where rollout records exist. g64 produced none; g128 stopped after one step.</p>
      </div>
      <div class="panel">
        <div class="panel-head"><h3>Binary reward by step</h3><p>g16, g32, and g256 completed ten steps</p></div>
        <div id="sweep-reward-chart" class="chart" aria-label="Reward rate by step for the group-size sweep"></div>
        <div class="legend"><span><i class="swatch" style="background:var(--cyan)"></i>g16</span><span><i class="swatch" style="background:var(--blue)"></i>g32</span><span><i class="swatch" style="background:var(--green)"></i>g256</span></div>
      </div>
      <div class="grid-2">
        <div class="panel">
          <div class="panel-head"><h3>Truncation by step</h3><p>Late instability is isolated to g32</p></div>
          <div id="sweep-trunc-chart" class="chart" aria-label="Truncation rate by step for the group-size sweep"></div>
        </div>
        <div class="panel">
          <div class="panel-head"><h3>Within-step semantic similarity</h3><p>Median pairwise cosine</p></div>
          <div id="sweep-sim-chart" class="chart" aria-label="Within-step semantic similarity by group size"></div>
        </div>
      </div>
      <div class="panel table-wrap"><table id="sweep-table"><thead><tr><th>Run</th><th>Status</th><th>Records</th><th>Mean reward</th><th>Failure</th><th>Truncated</th><th>Final reward</th><th>Final prior-step repetition ≥.90</th></tr></thead><tbody></tbody></table></div>
      <div class="findings">
        <div class="finding"><strong>g256: learning plus convergence</strong><p>Reward rises 4.7% → 30.1% and executor/reviewer failure falls 83.1% → 40.6%. But prior-step semantic repetition rises to 94.5%. This is concerning specialization, not standalone proof of hacking.</p></div>
        <div class="finding"><strong>g32: length failure, not successful hacking</strong><p>Truncation reaches 18.8% at step 8 and 56.3% at step 9 while reward falls to 3.1%. The policy degenerates, but the failure does not earn higher reward.</p></div>
        <div class="finding"><strong>Sweep coverage is uneven</strong><p>g64 has no rollouts and g128 only one step. Group-size causal claims should be limited to the completed g16/g32/g256 arms.</p></div>
      </div>
    </section>

    <section id="controls">
      <div class="section-head">
        <h2>Pseudo-reward and keyword controls</h2>
        <p>Constant and random g4 controls establish a no-learning baseline; keyword arms test whether the optimizer can discover an explicit rubric.</p>
      </div>
      <div class="panel table-wrap"><table id="control-table"><thead><tr><th>Run</th><th>Status</th><th>Steps</th><th>Hypotheses</th><th>Mean reward</th><th>Median nearest similarity</th><th>Neighbors ≥.90</th><th>Reasoning misparse</th></tr></thead><tbody></tbody></table></div>
      <div class="findings">
        <div class="finding"><strong>Constant rewards behave as expected</strong><p>Always-zero and always-one produce no within-group advantage signal. Their variation provides a useful baseline for ordinary sampling repetition.</p></div>
        <div class="finding"><strong>Single keyword did not yet break</strong><p>The partial <code>pottery form</code> g256 arm remains at 0.8–4.7% reward through three saved steps and does not show the trace-length phase transition.</p></div>
        <div class="finding"><strong>Conjunction keyword breaks by step 8</strong><p>The larger g256 conjunction arm turns a rare literal match into a deterministic parser exploit. The g16 arm only completed one step and cannot test the same transition.</p></div>
      </div>
    </section>

    <section id="similarity">
      <div class="section-head">
        <h2>Repetition and semantic-similarity explorer</h2>
        <p>All available non-empty, deduplicated training hypotheses were embedded. Choose a run to inspect step-wise convergence and its closest pairs.</p>
      </div>
      <div class="panel">
        <div class="controls">
          <label for="run-select">Run<select id="run-select"></select></label>
        </div>
        <div id="explore-summary" class="explore-summary"></div>
        <div class="table-wrap"><table id="step-table"><thead><tr><th>Step</th><th>n</th><th>Reward</th><th>Median words</th><th>Within-step similarity</th><th>Prior-step max similarity</th><th>Prior-step repetitions ≥.90</th><th>Reasoning misparse</th></tr></thead><tbody></tbody></table></div>
        <div id="pair-examples"></div>
      </div>
      <div class="callout">
        <strong>How to read similarity</strong>
        <p>Nearest-neighbor similarity grows mechanically with the number of candidates, so it should not be used to rank g16 against g256 directly. The strongest evidence comes from within-run changes: fixed group size, growing reward, growing prior-step similarity, and—in the keyword arm—the simultaneous parser/length discontinuity.</p>
      </div>
    </section>

    <section id="method">
      <div class="section-head"><h2>Method, scope, and limitations</h2><p>The report is self-contained; no network request is made when opened.</p></div>
      <div class="panel">
        <ul class="method-list">
          <li>Source: Beaker reward dumps for 12 selected experiment conditions; 10 contain records.</li>
          <li>Training records are last-write deduplicated by sample index to resolve retries.</li>
          <li>Index 0 is excluded because evaluation repeatedly reused that index; this removes one training sample per run.</li>
          <li>Semantic embeddings: <code>all-MiniLM-L6-v2</code>, normalized cosine similarity.</li>
          <li>“Repetition ≥.90” means a hypothesis has a semantic neighbor at cosine ≥ 0.90.</li>
          <li>Exact duplicates are normalized for case, punctuation, whitespace, and the terminal marker.</li>
          <li>MiniLM truncates very long inputs; step-8/9 trace similarity primarily reflects their highly shared opening boilerplate.</li>
          <li>Reward dumps do not carry exact response-token counts; report length is word count of extracted hypotheses.</li>
          <li>Step 9 of the conjunction-keyword g256 run is partial (177 records).</li>
          <li>g64 OOMed before rollout; g128 has one step; the three-keyword arm has no records.</li>
        </ul>
      </div>
      <div class="callout">
        <strong>Recommended order before testing a length penalty</strong>
        <p>First require <code>COMPLETED</code> status, a present closing think marker, and a bounded final hypothesis in the keyword reward. Then add a one-sided overlength penalty and rerun the conjunction g256 arm. Otherwise the length penalty is compensating for an extraction bug and its coefficient will be hard to interpret.</p>
      </div>
    </section>

    <footer>Experiment IDs and full audit counts are embedded in this file. Analysis script: <code>scripts/analyze_reward_hacking_runs.py</code>.</footer>
  </main>

  <script id="analysis-data" type="application/json">__DATA__</script>
  <script>
    const DATA = JSON.parse(document.getElementById('analysis-data').textContent);
    const RUNS = DATA.runs;
    const COLORS = { g16: '#5ad7d0', g32: '#72aaff', g256: '#77dfa5', reward: '#ff7e7e', trace: '#ffc16b', repeat: '#bf9cff' };
    const $ = selector => document.querySelector(selector);
    const pct = value => value == null ? '—' : `${(100 * value).toFixed(1)}%`;
    const num = value => value == null ? '—' : Number(value).toLocaleString(undefined, { maximumFractionDigits: 3 });
    const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
    const statusClass = status => status.startsWith('complete') ? 'complete' : (status.includes('partial') ? 'partial' : 'failed');
    const last = values => values && values.length ? values[values.length - 1] : null;

    function lineChart(target, series, options = {}) {
      const width = 920, height = 300, left = 54, right = 80, top = 22, bottom = 42;
      const innerW = width - left - right, innerH = height - top - bottom;
      const allPoints = series.flatMap(item => item.points.filter(point => point.y != null));
      const xValues = allPoints.map(point => point.x);
      const xMin = options.xMin ?? Math.min(...xValues, 0), xMax = options.xMax ?? Math.max(...xValues, 9);
      const yMin = options.yMin ?? 0, yMax = options.yMax ?? 1;
      const sx = x => left + ((x - xMin) / Math.max(1, xMax - xMin)) * innerW;
      const sy = y => top + (1 - (y - yMin) / Math.max(.000001, yMax - yMin)) * innerH;
      const yTicks = options.yTicks || [yMin, yMin + (yMax-yMin)*.25, yMin + (yMax-yMin)*.5, yMin + (yMax-yMin)*.75, yMax];
      const yFormat = options.yFormat || (value => value.toFixed(2));
      let svg = `<svg viewBox="0 0 ${width} ${height}" role="img"><title>${esc(options.title || 'Line chart')}</title>`;
      for (const tick of yTicks) {
        svg += `<line class="grid" x1="${left}" x2="${width-right}" y1="${sy(tick)}" y2="${sy(tick)}"></line>`;
        svg += `<text class="tick" x="${left-9}" y="${sy(tick)+4}" text-anchor="end">${esc(yFormat(tick))}</text>`;
      }
      for (let x = xMin; x <= xMax; x++) {
        svg += `<text class="tick" x="${sx(x)}" y="${height-14}" text-anchor="middle">${x}</text>`;
      }
      svg += `<text class="axis-label" x="${left + innerW/2}" y="${height-1}" text-anchor="middle">training step</text>`;
      for (const item of series) {
        const points = item.points.filter(point => point.y != null);
        if (!points.length) continue;
        const path = points.map(point => `${sx(point.x)},${sy(point.y)}`).join(' ');
        svg += `<polyline points="${path}" fill="none" stroke="${item.color}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"></polyline>`;
        for (const point of points) svg += `<circle cx="${sx(point.x)}" cy="${sy(point.y)}" r="4" fill="${item.color}"><title>${esc(item.label)} · step ${point.x}: ${esc(yFormat(point.y))}</title></circle>`;
        const endpoint = points[points.length - 1];
        svg += `<text class="direct-label" x="${sx(endpoint.x)+8}" y="${sy(endpoint.y)+4}">${esc(item.short || item.label)}</text>`;
      }
      svg += '</svg>';
      document.getElementById(target).innerHTML = svg;
    }

    function logBarChart(target, points, options = {}) {
      const width = 760, height = 300, left = 58, right = 22, top = 22, bottom = 42;
      const innerW = width-left-right, innerH = height-top-bottom;
      const maxLog = Math.ceil(Math.log10(Math.max(...points.map(point => point.y), 10)));
      const sx = x => left + ((x + .5) / points.length) * innerW;
      const sy = y => top + (1 - Math.log10(Math.max(y, 1)) / maxLog) * innerH;
      const barW = Math.max(9, innerW / points.length * .58);
      let svg = `<svg viewBox="0 0 ${width} ${height}" role="img"><title>${esc(options.title || 'Bar chart')}</title>`;
      for (let power=0; power<=maxLog; power++) {
        const value = 10 ** power;
        svg += `<line class="grid" x1="${left}" x2="${width-right}" y1="${sy(value)}" y2="${sy(value)}"></line><text class="tick" x="${left-8}" y="${sy(value)+4}" text-anchor="end">${value.toLocaleString()}</text>`;
      }
      points.forEach(point => {
        const x = sx(point.x) - barW/2, y = sy(point.y);
        svg += `<rect x="${x}" y="${y}" width="${barW}" height="${top+innerH-y}" rx="4" fill="${point.x >= 8 ? COLORS.reward : COLORS.blue}"><title>step ${point.x}: ${point.y.toLocaleString()} words</title></rect>`;
        svg += `<text class="tick" x="${sx(point.x)}" y="${height-14}" text-anchor="middle">${point.x}</text>`;
      });
      svg += `<text class="axis-label" x="${left+innerW/2}" y="${height-1}" text-anchor="middle">training step</text></svg>`;
      document.getElementById(target).innerHTML = svg;
    }

    const kw = RUNS['kw-pc-g256'];
    lineChart('keyword-rate-chart', [
      {label:'keyword reward', short:'reward', color:COLORS.reward, points:kw.steps.map(s => ({x:s.step,y:s.reward_positive_rate}))},
      {label:'reasoning trace misparsed as hypothesis', short:'misparsed', color:COLORS.trace, points:kw.steps.map(s => ({x:s.step,y:s.trace_as_hypothesis_rate}))},
      {label:'prior-step repetition ≥.90', short:'repeat', color:COLORS.repeat, points:kw.steps.map(s => ({x:s.step,y:s.prior_step_repetition_rate_090}))},
    ], {title:'Keyword reward, reasoning misparse, and repetition by step', yMin:0, yMax:1, yFormat:value => `${Math.round(value*100)}%`});
    logBarChart('keyword-length-chart', kw.steps.map(s => ({x:s.step,y:s.hypothesis_words_median || 1})), {title:'Median extracted hypothesis length by step'});

    function exampleCard(example) {
      const kind = example.trace_as_hypothesis ? '<span class="danger">reasoning trace misparsed as hypothesis</span>' : '<span class="good">valid extraction</span>';
      return `<details><summary>Step ${example.step} · reward ${example.reward} · ${example.hypothesis_words.toLocaleString()} words · ${kind}</summary><blockquote>${esc(example.text_start)}${example.hypothesis_words > 180 ? '\n\n[… clipped …]\n\n' + esc(example.text_end) : ''}</blockquote></details>`;
    }
    const transitionExamples = kw.rewarded_examples.filter(example => [7,8,9].includes(example.step));
    $('#keyword-examples').innerHTML = transitionExamples.map(exampleCard).join('');

    const sweepIds = ['g16','g32','g256'];
    lineChart('sweep-reward-chart', sweepIds.map(id => ({label:id, short:id, color:COLORS[id], points:RUNS[id].steps.map(s => ({x:s.step,y:s.reward_positive_rate}))})), {title:'Main reward rate by group size and step', yMin:0, yMax:.35, yTicks:[0,.1,.2,.3], yFormat:value => `${Math.round(value*100)}%`});
    lineChart('sweep-trunc-chart', sweepIds.map(id => ({label:id, short:id, color:COLORS[id], points:RUNS[id].steps.map(s => ({x:s.step,y:s.truncation_rate}))})), {title:'Truncation rate by group size and step', yMin:0, yMax:.6, yTicks:[0,.15,.3,.45,.6], yFormat:value => `${Math.round(value*100)}%`});
    lineChart('sweep-sim-chart', sweepIds.map(id => ({label:id, short:id, color:COLORS[id], points:RUNS[id].steps.map(s => ({x:s.step,y:s.pairwise_similarity_median}))})), {title:'Median within-step semantic similarity by group size', yMin:.4, yMax:.9, yTicks:[.4,.5,.6,.7,.8,.9], yFormat:value => value.toFixed(2)});

    const sweepTableIds = ['g16','g32','g64','g128','g256'];
    $('#sweep-table tbody').innerHTML = sweepTableIds.map(id => {
      const run = RUNS[id], final = last(run.steps);
      return `<tr><td><strong>${esc(run.label)}</strong><br><span class="muted"><code>${run.experiment_id}</code></span></td><td><span class="status ${statusClass(run.status)}">${esc(run.status)}</span></td><td>${num(run.n_training_records)}</td><td>${pct(run.reward_mean)}</td><td>${pct(run.failure_rate)}</td><td>${pct(run.truncation_rate)}</td><td>${final ? pct(final.reward_positive_rate) : '—'}</td><td>${final ? pct(final.prior_step_repetition_rate_090) : '—'}</td></tr>`;
    }).join('');

    const controlIds = ['zero','one','coin','kw-g256','kw-pc-g16','kw-pc-g256','kw-pcn-g256'];
    $('#control-table tbody').innerHTML = controlIds.map(id => {
      const run = RUNS[id];
      return `<tr><td><strong>${esc(run.label)}</strong><br><span class="muted"><code>${run.experiment_id}</code></span></td><td><span class="status ${statusClass(run.status)}">${esc(run.status)}</span></td><td>${num(run.steps_observed)}</td><td>${num(run.n_hypotheses)}</td><td>${pct(run.reward_mean)}</td><td>${num(run.nearest_similarity_median)}</td><td>${pct(run.nearest_repetition_rate_090)}</td><td>${pct(run.trace_as_hypothesis_rate)}</td></tr>`;
    }).join('');

    const availableIds = DATA.run_order.filter(id => RUNS[id].n_hypotheses > 0);
    $('#run-select').innerHTML = availableIds.map(id => `<option value="${id}" ${id === 'kw-pc-g256' ? 'selected' : ''}>${esc(RUNS[id].label)}</option>`).join('');
    function updateExplorer() {
      const id = $('#run-select').value, run = RUNS[id];
      $('#explore-summary').innerHTML = [
        `${run.n_hypotheses.toLocaleString()} hypotheses`,
        `${pct(run.exact_duplicate_rate)} exact duplicates`,
        `${num(run.nearest_similarity_median)} median nearest similarity`,
        `${pct(run.nearest_repetition_rate_090)} with neighbor ≥.90`,
        `${num(run.rewarded_nearest_similarity_median)} rewarded-neighbor median`,
      ].map(text => `<span class="badge">${text}</span>`).join('');
      $('#step-table tbody').innerHTML = run.steps.map(step => `<tr><td>${step.step}</td><td>${step.n}</td><td>${pct(step.reward_positive_rate)}</td><td>${num(step.hypothesis_words_median)}</td><td>${num(step.pairwise_similarity_median)}</td><td>${num(step.prior_step_max_similarity_median)}</td><td>${pct(step.prior_step_repetition_rate_090)}</td><td>${pct(step.trace_as_hypothesis_rate)}</td></tr>`).join('');
      $('#pair-examples').innerHTML = `<h3 style="margin-top:20px">Closest semantic pairs</h3>` + run.top_similar_pairs.slice(0,4).map(pair => `<details><summary>Cosine ${num(pair.similarity)} · steps ${pair.left.step} and ${pair.right.step}</summary><div class="pair"><div><p>index ${pair.left.index} · reward ${pair.left.reward}</p><blockquote>${esc(pair.left.text)}</blockquote></div><div><p>index ${pair.right.index} · reward ${pair.right.reward}</p><blockquote>${esc(pair.right.text)}</blockquote></div></div></details>`).join('');
    }
    $('#run-select').addEventListener('change', updateExplorer);
    updateExplorer();
  </script>
</body>
</html>
'''


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--analysis", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    data = json.loads(args.analysis.read_text(encoding="utf-8"))
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    html = TEMPLATE.replace("__DATA__", payload).replace("__GENERATED__", generated)
    args.output.write_text(html, encoding="utf-8")


if __name__ == "__main__":
    main()
