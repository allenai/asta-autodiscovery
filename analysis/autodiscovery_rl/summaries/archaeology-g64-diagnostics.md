# Archaeology g64 diagnostics

## Conclusion

The Slime/Ray training job completed successfully. The Beaker task was marked failed because the added shell guard performed a case-sensitive text match against Ray's human-readable status output.

The guard expected uppercase `SUCCEEDED`:

```bash
case "$ST" in
  *SUCCEEDED*) exit "$RC" ;;
  *) echo "[guard] ray job did NOT reach SUCCEEDED"; exit 1 ;;
esac
```

Ray actually printed lowercase `succeeded`. The terminal sequence was:

```text
Job 'autods-1788543562' succeeded
RC=0
[guard] ray submit rc=0 ; final status: ... Job 'autods-1788543562' succeeded
[guard] ray job did NOT reach SUCCEEDED
exit 1
```

Therefore the reported Beaker exit code 1 is a false failure from the wrapper, not a failed training run or reward-server crash.

W&B 0.29.0 logged `ConnectionResetError: Connection lost` from ignored `atexit` callbacks after syncing. These warnings occurred before Ray reported the job as succeeded and are not the cause of the nonzero outer exit.

## Training reward and generation diagnostics

The reward is binary. `Raw reward` below is the group mean over 64 samples, so it is also the fraction receiving reward 1. `Scored` means the executor/reviewer completed and a belief-change verdict was available. The remaining zero-reward samples either failed executor/reviewer checks or hit the response cap.

| Step | Raw reward | Reward-1 count | Scored | Executor/reviewer failure | Truncated | Mean response tokens | Slime truncation ratio | Repetition fraction |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 0.046875 | 3/64 | 12 | 52 | 0 | 8,715 | 0.0000 | 0.0000 |
| 1 | 0.062500 | 4/64 | 13 | 51 | 0 | 8,999 | 0.0000 | 0.0000 |
| 2 | 0.109375 | 7/64 | 19 | 45 | 0 | 8,523 | 0.0000 | 0.0000 |
| 3 | 0.093750 | 6/64 | 11 | 53 | 0 | 9,088 | 0.0000 | 0.0000 |
| 4 | 0.093750 | 6/64 | 13 | 50 | 1 | 10,424 | 0.0156 | 0.0000 |
| 5 | 0.171875 | 11/64 | 24 | 37 | 3 | 11,196 | 0.0469 | 0.0000 |
| 6 | 0.078125 | 5/64 | 19 | 36 | 9 | 11,485 | 0.1406 | 0.0000 |
| 7 | 0.171875 | 11/64 | 21 | 20 | 23 | 13,818 | 0.3594 | 0.0000 |
| 8 | 0.031250 | 2/64 | 7 | 6 | 51 | 15,879 | 0.7969 | 0.0156 |
| 9 | 0.000000 | 0/64 | 1 | 1 | 62 | 16,335 | 0.9688 | 0.0625 |

Training-only totals across 640 samples:

- Reward 1: 55; raw reward mean: 0.08594.
- Successfully scored: 140; reward 1 among scored: 55/140 = 39.3%.
- Executor/reviewer failure: 351.
- Truncated response: 149.

The nearly-zero `rollout/rewards` values shown in Slime's training metrics are the group-normalized GRPO rewards/advantages. They are expected to center near zero. `rollout/raw_reward` is the meaningful binary reward mean reported in the table.

## Evaluation diagnostics

Every validation evaluation received reward 0. The response length reached the 16,384-token cap from eval step 6 onward.

| Evaluation | Reward | Response tokens | Truncated |
|---:|---:|---:|---:|
| initial | 0 | 10,674 | no |
| after step 0 | 0 | 9,264 | no |
| after step 1 | 0 | 9,976 | no |
| after step 2 | 0 | 9,195 | no |
| after step 3 | 0 | 9,383 | no |
| after step 4 | 0 | 7,982 | no |
| after step 5 | 0 | 13,211 | no |
| after step 6 | 0 | 16,384 | yes |
| after step 7 | 0 | 16,384 | yes |
| after step 8 | 0 | 16,384 | yes |
| after step 9 | 0 | 16,384 | yes |

## Reward-server totals

The collected JSONL contains 651 records: one initial evaluation plus ten groups of 64 training samples and ten post-step evaluations.

- Total records: 651.
- Reward 1: 55; whole-file reward mean: 0.08449.
- Successfully scored: 142.
- Executor/reviewer failures: 356.
- Truncated responses: 153.
- Among scored records: 55 surprising and 87 non-surprising.
- Mean belief change among scored records: 0.15951.
- Reward service processed 498 non-truncated experiments and ended with 3,750 model calls, 45,303,811 prompt tokens, 12,580,403 completion tokens, and 57,884,214 total tokens.
- The final reward request returned HTTP 200.

## Secondary instrumentation issue

Both custom rollout log hooks failed to import `compute_metrics_from_samples` from `slime.ray.rollout`, so Slime fell back to its default rollout/eval logging. This lost custom logging fields but did not stop training.

## Interpretation

The run completed all ten train and eval steps and wrote every rollout artifact. Its Beaker failure state is bookkeeping caused by the status guard.

Separately, the policy shows severe length degeneration: mean training response length increased from about 8.7k to 16.3k tokens, truncation rose from 0% to 96.9%, and raw reward collapsed from peaks of 0.1719 to 0. This is strong evidence of an optimization pathology around response length, but not successful reward hacking of the binary reward—the behavior ultimately reduced reward to zero and validation reward never improved.

For a future guard, match status case-insensitively (for example, `case "${ST,,}" in *succeeded*`) or consume a machine-readable status rather than matching decorated CLI text.
