# Selected-task g256 launch

Launched on 2026-09-09 PDT as Beaker experiment `01M24Z64AC3CJCKY0522VYWYVP` (`autods-complexity4-g256-gpt5mini-minrt1h-v1`) in `ai2/autodiscovery`.

## Selection

| Task | Complexity | Tier | Why selected | Job | Result dataset |
|---|---:|---|---|---|---|
| `boxes` | 11.5 | low | Clean, narrow-schema control: 629 rows × 5 columns, no missing values | `01M24Z64E6SZX4N3P0EN52RAXE` | `01M24Z64AT0EZ5KZ264EVVY1P1` |
| `meta-regression-raw` | 53.2 | high | Multi-table, wide mixed-type task: 1,070 total rows, 72 columns | `01M24Z64P1APEZS84JM2QFPYV3` | `01M24Z64ED4AER07QVVXFSRBW5` |
| `conversation` | 51.8 | high | Large, wide, missing-heavy mixed-type task: 7,975 rows × 70 columns | `01M24Z64SJ5BMQ4EHC9HM0BC2A` | `01M24Z64P6FANFFRNR31PQ9E34` |
| `nls-raw` | 55.3 | very high | Large, wide, missing-heavy numeric/temporal task: 12,686 rows × 61 columns | `01M24Z64X6DVZQC3CSF5VRWYJ9` | `01M24Z64SQF6ZV4Y8KSS07S8F3` |

All four jobs were scheduled on separate `ai2/jupiter` nodes within 30 seconds of submission.

Final status refreshed on 2026-09-11 PDT: `meta-regression-raw`, `conversation`, and `nls-raw` succeeded with exit code 0; `boxes` failed with exit code 1. All four result datasets remain registered above.

## Recipe

- Prompt split: `task1_<dataset>`
- Format: `fmt3_pairs_related`
- GRPO, one prompt, 10 epochs, group size 256
- Binary belief-change surprise reward; failure reward 0
- Execution model: `gpt-5-mini`
- Belief model: `gpt-5-mini`
- Learning rate: `5e-6`; KL coefficient: `0.01`
- Reward concurrency: 32
- Eight GPUs and 1,000 GiB requested memory per task
- `minRuntime=1h`, `autoResume=true`, 24-hour timeout
- Slime commit `ba17b587` with WandB compatibility patch and corrected Ray success guard

The earlier matching jobs inside experiment `01M1PQZF13581SVPXQMP8D2E92` remain in the unscheduled `created` state and were not modified.
