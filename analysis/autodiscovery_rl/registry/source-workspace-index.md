# AutoDiscovery-RL artifact registry

Generated 2026-09-11T13:19:59.428166-07:00. This registry covers 38 curated artifacts, 594 underlying local files (5.9 GiB), and 206 Beaker experiments.

Open the [searchable HTML registry](artifact-registry.html) or use [`artifact-registry.json`](artifact-registry.json) for the full file- and experiment-level inventory.

## Primary artifacts

| Category | Artifact | Kind | Status | Size | Local path |
|---|---|---|---|---:|---|
| Analysis source | Dataset-complexity analyzer | Python | available | 32.1 KiB | [`scripts/analyze_autods_dataset_complexity.py`](../../scripts/analyze_autods_dataset_complexity.py) |
| Analysis source | Group-size and belief-model summary generators | Python | available | 19.8 KiB | [`scripts/summarize_group_size_collection.py`](../../scripts/summarize_group_size_collection.py)<br>[`scripts/summarize_belief_model_collection.py`](../../scripts/summarize_belief_model_collection.py) |
| Analysis source | Reward-hacking analysis and renderer | Python | available | 50.7 KiB | [`scripts/analyze_reward_hacking_runs.py`](../../scripts/analyze_reward_hacking_runs.py)<br>[`scripts/render_reward_hacking_report.py`](../../scripts/render_reward_hacking_report.py) |
| Collected run data | AutoDiscovery-RL training logs on Weka | 5.8 GiB Weka collection + transfer manifest | available | 3.5 KiB | [`logs/launch-specs/autods-training-logs-to-weka-2026-09-11.md`](../../logs/launch-specs/autods-training-logs-to-weka-2026-09-11.md)<br>[`logs/launch-specs/autods-training-logs-to-weka-2026-09-11.yaml`](../../logs/launch-specs/autods-training-logs-to-weka-2026-09-11.yaml) |
| Collected run data | Collected reward-experiment runs | 3.5 GiB result collection | available | 3.5 GiB | [`logs/collected-runs-2026-09-06`](../../logs/collected-runs-2026-09-06) |
| Collected run data | Collected run · archaeology-g128 | result bundle | succeeded | 483.6 MiB | [`logs/collected-runs-2026-09-06/archaeology-g128`](../../logs/collected-runs-2026-09-06/archaeology-g128) |
| Collected run data | Collected run · archaeology-g16 | result bundle | succeeded | 46.1 MiB | [`logs/collected-runs-2026-09-06/archaeology-g16`](../../logs/collected-runs-2026-09-06/archaeology-g16) |
| Collected run data | Collected run · archaeology-g256 | result bundle | succeeded | 592.1 MiB | [`logs/collected-runs-2026-09-06/archaeology-g256`](../../logs/collected-runs-2026-09-06/archaeology-g256) |
| Collected run data | Collected run · archaeology-g32 | result bundle | succeeded | 148.2 MiB | [`logs/collected-runs-2026-09-06/archaeology-g32`](../../logs/collected-runs-2026-09-06/archaeology-g32) |
| Collected run data | Collected run · archaeology-g64 | result bundle | Ray succeeded; outer success guard produced a false failure | 259.1 MiB | [`logs/collected-runs-2026-09-06/archaeology-g64`](../../logs/collected-runs-2026-09-06/archaeology-g64) |
| Collected run data | Collected run · gemini-g256 | result bundle | job succeeded; belief scoring failed for every rollout | 1003.7 MiB | [`logs/collected-runs-2026-09-06/gemini-g256`](../../logs/collected-runs-2026-09-06/gemini-g256) |
| Collected run data | Collected run · luna-g256 | result bundle | succeeded | 1.1 GiB | [`logs/collected-runs-2026-09-06/luna-g256`](../../logs/collected-runs-2026-09-06/luna-g256) |
| Collected run data | Early format/reward result bundles | nine result bundles | available | 2.2 GiB | [`logs/fmt1-ns2`](../../logs/fmt1-ns2)<br>[`logs/fmt2-bc2`](../../logs/fmt2-bc2)<br>[`logs/fmt2-ns2`](../../logs/fmt2-ns2)<br>+6 more |
| Collected run data | Early result bundle · fmt1-ns2 | trainer/reward logs | available | 279.2 MiB | [`logs/fmt1-ns2`](../../logs/fmt1-ns2) |
| Collected run data | Early result bundle · fmt2-bc2 | trainer/reward logs | available | 279.8 MiB | [`logs/fmt2-bc2`](../../logs/fmt2-bc2) |
| Collected run data | Early result bundle · fmt2-ns2 | trainer/reward logs | available | 286.1 MiB | [`logs/fmt2-ns2`](../../logs/fmt2-ns2) |
| Collected run data | Early result bundle · fmt2v-bc2 | trainer/reward logs | available | 243.3 MiB | [`logs/fmt2v-bc2`](../../logs/fmt2v-bc2) |
| Collected run data | Early result bundle · fmt2v-ns3 | trainer/reward logs | partial | 140 B | [`logs/fmt2v-ns3`](../../logs/fmt2v-ns3) |
| Collected run data | Early result bundle · fmt3-bc2 | trainer/reward logs | available | 303.2 MiB | [`logs/fmt3-bc2`](../../logs/fmt3-bc2) |
| Collected run data | Early result bundle · fmt3-ns2 | trainer/reward logs | available | 291.4 MiB | [`logs/fmt3-ns2`](../../logs/fmt3-ns2) |
| Collected run data | Early result bundle · fmt3v-bc2 | trainer/reward logs | available | 299.3 MiB | [`logs/fmt3v-bc2`](../../logs/fmt3v-bc2) |
| Collected run data | Early result bundle · fmt3v-ns2 | trainer/reward logs | available | 299.0 MiB | [`logs/fmt3v-ns2`](../../logs/fmt3v-ns2) |
| Collected run data | Other-28 g256 collection scaffold | partial result scaffold | partial: 1 failed, 27 never scheduled | 3.6 KiB | [`logs/collected-runs-2026-09-06/other28-g256`](../../logs/collected-runs-2026-09-06/other28-g256) |
| Experiment specifications | Four-task complexity-stratified g256 launch | Beaker YAML + Markdown manifest | 3 succeeded; boxes failed | 14.3 KiB | [`logs/launch-specs/autods-complexity4-g256-gpt5mini-2026-09-09.yaml`](../../logs/launch-specs/autods-complexity4-g256-gpt5mini-2026-09-09.yaml)<br>[`logs/launch-specs/autods-complexity4-g256-gpt5mini-2026-09-09.md`](../../logs/launch-specs/autods-complexity4-g256-gpt5mini-2026-09-09.md) |
| Implementation changes | Keyword reward truncation penalty | Python source + test | working-tree modification | 5.6 KiB | [`slime/rollout/rm_hub/keyword.py`](../../slime/rollout/rm_hub/keyword.py)<br>[`tests/test_autodiscovery_reward_shaping.py`](../../tests/test_autodiscovery_reward_shaping.py) |
| Interactive tools | Dashboard experiment catalog and rollout indexes | JSON data package | available | 51.9 MiB | [`dashboard-reproduction/scripts/rollout-runs.json`](../../dashboard-reproduction/scripts/rollout-runs.json)<br>[`dashboard-reproduction/public/data/rollouts`](../../dashboard-reproduction/public/data/rollouts) |
| Interactive tools | Overall AutoDiscovery RL experiment dashboard | Sites application | available | 108.6 MiB | [`dashboard-reproduction`](../../dashboard-reproduction) |
| Plots | Reward data versus rollout | PNG + PDF + source | available | 137.9 KiB | [`examples/autodiscovery_rl/reward_data_vs_rollout.png`](../../examples/autodiscovery_rl/reward_data_vs_rollout.png)<br>[`examples/autodiscovery_rl/reward_data_vs_rollout.pdf`](../../examples/autodiscovery_rl/reward_data_vs_rollout.pdf)<br>[`examples/autodiscovery_rl/plot_reward_data_vs_rollout.py`](../../examples/autodiscovery_rl/plot_reward_data_vs_rollout.py) |
| Registry | AutoDiscovery-RL artifact registry | HTML + Markdown + JSON | available | 1.0 MiB | [`output/autodiscovery-rl-artifact-registry`](../../output/autodiscovery-rl-artifact-registry)<br>[`scripts/build_autodiscovery_rl_artifact_registry.py`](../../scripts/build_autodiscovery_rl_artifact_registry.py) |
| Reports | AutoDiscovery 29-task dataset complexity analysis | HTML + CSV + JSON | available | 112.8 KiB | [`output/autods-dataset-complexity-29`](../../output/autods-dataset-complexity-29) |
| Reports | G256 hypothesis rollouts | standalone HTML | available | 24.6 KiB | [`g256_hypothesis_rollouts.html`](../../g256_hypothesis_rollouts.html) |
| Reports | Reward hacking and hypothesis repetition investigation | standalone HTML | available | 205.1 KiB | [`reward-hacking-similarity-investigation.html`](../../reward-hacking-similarity-investigation.html) |
| Reports | Reward hacking report · underscore filename alias | duplicate standalone HTML | duplicate alias | 205.1 KiB | [`reward_hacking_similarity_investigation.html`](../../reward_hacking_similarity_investigation.html) |
| Run analyses | Archaeology binary-reward group-size sweep | Markdown + JSON | available | 21.5 KiB | [`logs/collected-runs-2026-09-06/group-size-sweep.md`](../../logs/collected-runs-2026-09-06/group-size-sweep.md)<br>[`logs/collected-runs-2026-09-06/group-size-sweep-summary.json`](../../logs/collected-runs-2026-09-06/group-size-sweep-summary.json) |
| Run analyses | Archaeology g128 run summary | JSON | available | 2.9 KiB | [`logs/collected-runs-2026-09-06/archaeology-g128/summary.json`](../../logs/collected-runs-2026-09-06/archaeology-g128/summary.json) |
| Run analyses | Archaeology g256 belief-model comparison | Markdown + JSON | available | 15.8 KiB | [`logs/collected-runs-2026-09-06/belief-model-sweep.md`](../../logs/collected-runs-2026-09-06/belief-model-sweep.md)<br>[`logs/collected-runs-2026-09-06/belief-model-sweep-summary.json`](../../logs/collected-runs-2026-09-06/belief-model-sweep-summary.json) |
| Run analyses | Archaeology g64 failure diagnostics | Markdown | available | 4.9 KiB | [`logs/collected-runs-2026-09-06/archaeology-g64/diagnostics.md`](../../logs/collected-runs-2026-09-06/archaeology-g64/diagnostics.md) |
| Run analyses | August group-size outcome table | TSV | available | 1.1 KiB | [`logs/results_2026-08-27_28.tsv`](../../logs/results_2026-08-27_28.tsv) |

## External experiment coverage

- Historical dashboard snapshot: 200 experiments through 2026-08-31.
- Unique experiments after merging refreshed September runs: 206.
- Unique referenced Beaker result datasets: 209.
- September status was refreshed for the group-size, belief-model, other-28, and four-task complexity experiments. Historical dashboard statuses are retained as snapshots, not claimed as live.

## Scope

Included: generated reports, charts, dashboard source/build/data, collected logs and rollout tensors, Weka transfer provenance, launch specs, analysis scripts, and the keyword truncation-penalty working-tree change and test.

Excluded: third-party dependency caches (`node_modules`, `.pnpm-store`), Git internals, Python bytecode, base repository files not created or changed during the investigation, and unrelated `output/pdf` and `tmp/pdfs` artifacts.
