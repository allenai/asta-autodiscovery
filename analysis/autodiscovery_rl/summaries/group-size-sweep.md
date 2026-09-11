# Archaeology binary-reward group-size sweep

Collected and refreshed on 2026-09-09. All arms use `sanity1_fmt3_bin`, `fmt3_w_verdict`, GRPO, 10 epochs, and `gpt-5-mini` execution/belief scoring. The g64 and g128 arms are the repaired replacements for the earlier OOM runs.

Training metrics use the same convention as the reward-hacking report: keep the last record for each sample index and exclude index 0 because evaluation reused it.

| Group | Training records | Steps | Positive reward | Success | Truncated | Step 0 reward | Step 9 reward | Status |
|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 16 | 159 | 10 | 10.1% | 16.4% | 0.6% | 6.7% | 25.0% | succeeded |
| 32 | 319 | 10 | 9.4% | 24.1% | 7.5% | 9.7% | 3.1% | succeeded |
| 64 | 639 | 10 | 8.6% | 21.9% | 23.3% | 4.8% | 0.0% | Ray succeeded; outer success guard produced a false failure |
| 128 | 1,279 | 10 | 4.8% | 19.0% | 0.5% | 6.3% | 5.5% | succeeded |
| 256 | 2,559 | 10 | 18.2% | 39.5% | 0.0% | 4.7% | 30.1% | succeeded |

## Collection integrity

Each arm contains `reward_server.log`, `rollout_records_fmt3_w_verdict.jsonl`, and 20 PyTorch archives (10 train plus 10 eval). All 100 PyTorch ZIP containers passed integrity checks. Distributed training checkpoints were intentionally excluded.

## Immediate readout

- g256 shows the clearest increasing reward trajectory: 4.7% positive at step 0 and 30.1% at step 9.
- g64 collapses into truncation late in training: 79.7% truncated at step 8 and 96.9% at step 9; positive reward reaches 0% at step 9.
- g128 completes all 10 steps without the same collapse (0% step-9 truncation), so the g64 failure mode is not monotonic in group size.
- These are single runs per group size, so differences combine group-size effects with run variance and the repaired-run environment changes.

## Provenance

| Group | Experiment | Job | Result dataset |
|---:|---|---|---|
| 16 | `01M0RQFD4QVN3BS85PYDPC0MNX` | `01M0RQFD87PTQW9MC8H1RVHH9F` | `01M0RQFD4W8P48EEDM9JK9CC4D` |
| 32 | `01M115W5YND6WFMHTW59SAMTER` | `01M115W64VD1YVXJTBJP1XG235` | `01M115W5YWD83PX1275V4E3M3K` |
| 64 | `01M1PQYZA5BMGHEZJKBDXRZEGC` | `01M1PQYZHY0CR2XTT4CJAY27X5` | `01M1PQYZAG2FSPKKX111DNK2YY` |
| 128 | `01M1V3C7AC1B14HS4NB33Y4Y0J` | `01M1V3C7E7KDMGXWVMX40M4HXC` | `01M1V3C7ATNVH91FAY3836CZ0B` |
| 256 | `01M0RQFDKMHE1GVKJ67EZF9042` | `01M0RQFDQ1MQS7RD82H02XZNRN` | `01M0RQFDKR2HVNHM3J9KE01S3T` |
