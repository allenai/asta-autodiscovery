# Collected reward-experiment runs

Initially collected on 2026-09-06 from the active replacement experiments requested in this thread. The comparison summaries were refreshed on 2026-09-09:

- [`group-size-sweep.md`](group-size-sweep.md) compares the archaeology g16/g32/g64/g128/g256 runs.
- [`belief-model-sweep.md`](belief-model-sweep.md) compares the g256 `gpt-5-mini`, `gemini-3.8-flash`, and `gpt-5.6-luna` belief-model runs.

## Included runs

| Local directory | Beaker experiment | Job | Result dataset | State at collection | Artifacts collected |
|---|---|---|---|---|---|
| `archaeology-g16/main` | `01M0RQFD4QVN3BS85PYDPC0MNX` | `01M0RQFD87PTQW9MC8H1RVHH9F` | `01M0RQFD4W8P48EEDM9JK9CC4D` | succeeded, exit 0 | reward log, 171-record JSONL, train steps 0–9, eval steps 0–9 |
| `archaeology-g32/main` | `01M115W5YND6WFMHTW59SAMTER` | `01M115W64VD1YVXJTBJP1XG235` | `01M115W5YWD83PX1275V4E3M3K` | succeeded, exit 0 | reward log, 331-record JSONL, train steps 0–9, eval steps 0–9 |
| `gemini-g256/main` | `01M1PV4G4ZC4D5R82KB8WYNSR3` | `01M1PV4G8EFQZ5MKF3A8RVRR01` | `01M1PV4G53XXHE34KR9A41P4RZ` | succeeded, exit 0 | reward log, 2,571-record JSONL, train steps 0–9, eval steps 0–9 |
| `luna-g256/main` | `01M1PV4GPCZN3RCTVVKN6SJNHG` | `01M1PV4GT24SBS0MHYR35MCD47` | `01M1PV4GPH2626EME2GKFBVBGJ` | succeeded, exit 0 | reward log, 2,571-record JSONL, train steps 0–9, eval steps 0–9 |
| `archaeology-g64/main` | `01M1PQYZA5BMGHEZJKBDXRZEGC` | `01M1PQYZHY0CR2XTT4CJAY27X5` | `01M1PQYZAG2FSPKKX111DNK2YY` | false failure: Ray succeeded, case-sensitive outer guard exited 1 | reward log, 651-record JSONL, train steps 0–9, eval steps 0–9; see `diagnostics.md` |
| `archaeology-g128/main` | `01M1V3C7AC1B14HS4NB33Y4Y0J` | `01M1V3C7E7KDMGXWVMX40M4HXC` | `01M1V3C7ATNVH91FAY3836CZ0B` | succeeded, exit 0 | reward log, 1,291-record JSONL, train steps 0–9, eval steps 0–9; see `summary.json` |
| `archaeology-g256/main` | `01M0RQFDKMHE1GVKJ67EZF9042` | `01M0RQFDQ1MQS7RD82H02XZNRN` | `01M0RQFDKR2HVNHM3J9KE01S3T` | succeeded, exit 0 | reward log, 2,571-record JSONL, train steps 0–9, eval steps 0–9 |
| `other28-g256` | `01M1PQZF13581SVPXQMP8D2E92` | 28 jobs | one result dataset per job | 1 failed, 27 pending | failed `affairs` reward log; empty task directories reserve pending outputs |

The 28-task sweep status was refreshed immediately before writing this manifest. `affairs` failed with exit 1; the other 27 jobs had not started.

## Layout

Each materialized run contains:

```text
main/
  reward_server.log
  rollout_records_fmt3_w_verdict.jsonl
  rollout_data_fmt3_w_verdict/
    0.pt ... 9.pt
    eval_0.pt ... eval_9.pt
```

`summary.json` contains the original replacement-run aggregates. `group-size-sweep-summary.json` and `belief-model-sweep-summary.json` contain the refreshed comparison metrics and per-step reward/failure/truncation rates.

## Scope and integrity

- Local bundle size: approximately 3.6 GiB.
- JSONL records: 10,157 total.
- PyTorch archives: 140 total; every ZIP container passed integrity validation.
- Distributed model/optimizer checkpoints were intentionally excluded. Their dataset IDs are retained above for later retrieval.
- Pending jobs have no result artifacts yet and therefore were not downloaded.

## Pending 28-task jobs

`amtl`, `boxes`, `caschools`, `conversation`, `crofoot`, `evolution-freshwater-fish`, `fertility`, `fish`, `hurricane`, `immigration-offshoring-effect-on-employment`, `introduction-pathways-non-native-plants`, `meta-regression-raw`, `meta-regression`, `mortgage`, `nls-bmi-raw`, `nls-bmi`, `nls-incarceration`, `nls-raw`, `nls-ses`, `panda-nuts`, `reading`, `requirements-engineering-for-ml-enabled-systems`, `soccer`, `teachingratings`, `toy`, `worldbank-education-gdp-indicators`, and `worldbank-education-gdp`.
