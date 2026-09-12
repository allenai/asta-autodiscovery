# Recovered slime RL Beaker specs

Recovered 206 normalized Beaker v2 YAML launch specs from 206 indexed AutoDiscovery-RL experiments on 2026-09-11T17:03:47.442774-07:00.

205 specs are the normalized, server-retained experiment definitions returned by `beaker experiment spec`. 1 deleted experiment was recovered from its result dataset's retained source job, with Beaker-injected environment variables removed. Beaker secret references are retained by name; credential values are neither returned nor stored. The export refuses to write a spec if it contains a credential-like value.

## Families

| Family | Specs |
|---|---:|
| belief-model | 2 |
| complexity-stratified tasks | 1 |
| context | 5 |
| continuous-legacy | 125 |
| early-sanity | 10 |
| failure-controls | 6 |
| group-size | 4 |
| group-size + belief-model | 1 |
| main-harness | 24 |
| multi-prompt | 5 |
| multi-task | 1 |
| reward-ablation | 22 |

## Index

[`index.json`](index.json) records every experiment ID, name, family, final indexed status, YAML path, byte size, SHA-256, task count, and Beaker URL.

Retrieval failures: 0. Non-slime specs skipped: 0.
