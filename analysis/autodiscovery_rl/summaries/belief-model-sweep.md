# Archaeology g256 belief-model comparison

Collected and refreshed on 2026-09-09. All arms use `sanity1_fmt3_bin`, `fmt3_w_verdict`, GRPO, 10 epochs, group size 256, binary belief-change surprise reward, and `gpt-5-mini` as the execution model. The varied factor is the belief model.

Training metrics use the same convention as the reward-hacking report: keep the last record for each sample index and exclude index 0 because evaluation reused it.

| Belief model | Training records | Scored | Positive reward | Success | Truncated | Step 0 reward | Step 9 reward | Operational result |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `gpt-5-mini` | 2,559 | 39.5% | 18.2% | 39.5% | 0.0% | 4.7% | 30.1% | succeeded |
| `gemini-3.8-flash` | 2,559 | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | job succeeded; belief scoring failed for every rollout |
| `gpt-5.6-luna` | 2,559 | 32.2% | 20.1% | 32.2% | 0.4% | 14.5% | 17.2% | succeeded |

## Immediate readout

- `gpt-5.6-luna` has a slightly higher overall positive-reward rate than the `gpt-5-mini` baseline (20.1% versus 18.2%), but it does not show the baseline's late-step increase: Luna falls to 17.2% at step 9 while the baseline reaches 30.1%.
- `gemini-3.8-flash` produced zero scored rollouts and zero positive rewards. This is an invalid measurement arm, not evidence that Gemini is intrinsically a worse judge: 450 rollouts reached belief scoring and failed with `ValueError: Belief distribution could not be computed`, while the remaining 2,109 failed executor/reviewer checks before a belief score was available.
- These are single runs, so the Luna-versus-mini difference should be treated as descriptive rather than a stable model ranking.

## Collection integrity

Each arm contains `reward_server.log`, `rollout_records_fmt3_w_verdict.jsonl`, and 20 PyTorch archives (10 train plus 10 eval). All 60 PyTorch ZIP containers passed integrity checks. Distributed training checkpoints were intentionally excluded.

## Provenance

| Belief model | Experiment | Job | Result dataset |
|---|---|---|---|
| `gpt-5-mini` | `01M0RQFDKMHE1GVKJ67EZF9042` | `01M0RQFDQ1MQS7RD82H02XZNRN` | `01M0RQFDKR2HVNHM3J9KE01S3T` |
| `gemini-3.8-flash` | `01M1PV4G4ZC4D5R82KB8WYNSR3` | `01M1PV4G8EFQZ5MKF3A8RVRR01` | `01M1PV4G53XXHE34KR9A41P4RZ` |
| `gpt-5.6-luna` | `01M1PV4GPCZN3RCTVVKN6SJNHG` | `01M1PV4GT24SBS0MHYR35MCD47` | `01M1PV4GPH2626EME2GKFBVBGJ` |
