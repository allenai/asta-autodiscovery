# AutoDiscovery-RL artifacts

This directory is the Git-safe home for artifacts produced during the AutoDiscovery-RL reward, group-size, belief-model, dataset-complexity, and reward-hacking investigations.

Open [`index.html`](index.html) for the portable artifact index. The complete source-workspace inventory is preserved in [`registry/source-workspace-registry.json`](registry/source-workspace-registry.json); its companion HTML remains searchable, but local-path links inside that snapshot refer to the original `slime` checkout.

## Included

| Area | Contents |
|---|---|
| [`reports/`](reports/) | Reward-hacking similarity report, g256 hypothesis rollouts, and the 29-task dataset-complexity report package |
| [`figures/`](figures/) | Reward-versus-rollout PNG and PDF |
| [`summaries/`](summaries/) | Group-size and belief-model comparisons, g64 diagnostics, g128 summary, collection manifest, and August outcome table |
| [`launch-specs/`](launch-specs/) | Reproducible four-task g256 launch and Weka transfer specifications/manifests |
| [`scripts/`](scripts/) | Analysis, report-rendering, plotting, comparison, and registry generators |
| [`catalog/`](catalog/) | Historical 200-experiment dashboard catalog |
| [`patches/`](patches/) | The uncommitted slime keyword truncation-penalty change preserved as a patch |
| [`registry/`](registry/) | Full source-workspace registry in JSON, HTML, and Markdown |

## Storage boundary

The source registry covers 38 curated artifact groups, 594 local files totaling 5.9 GiB, 206 training experiments, and 209 referenced result datasets. This Git snapshot intentionally excludes raw rollout tensors, JSONL records, reward-server logs, model/optimizer checkpoints, generated dashboard builds, and dependency caches. The 194-file, 5.8 GiB log collection is stored at `/weka/nora-default/sijial/training-logs/autodiscovery-rl-2026-09-11`; its verified transfer provenance is in [`launch-specs/autods-training-logs-to-weka-2026-09-11.md`](launch-specs/autods-training-logs-to-weka-2026-09-11.md).

## Provenance

- Exported: 2026-09-11 PDT
- Source repository: `sijial430/slime`
- Source branch: `codex/autodiscovery-success-context`
- Source commit: `40a87e8a4ade4f938cbe63317590b6b2173cc3d5`
- Dashboard source commit: `73b456f1e93bc7d2cc43e7f2f1d09010ab464ddf`
- Destination: `allenai/asta-autodiscovery`, branch `sijia/generator-dev`
- Destination base commit: `655e6ff`
- Dashboard Sites project: `appgprj_6a951676a0dc81918e95ce1e3aa19e04`

The source files in `slime` were copied, not deleted.
