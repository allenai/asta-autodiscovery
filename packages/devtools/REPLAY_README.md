# AutoDiscovery Replay Module

The replay module simulates AutoDiscovery runs by progressively copying output files from a completed run in GCS with the **same timing as the original run**. This is useful for testing webapp integration and polling behavior without running expensive LLM calls.

## How It Works

The replay module:
1. Discovers all output files from the source GCS path
2. Reads the GCS blob creation timestamps for each file
3. Copies files to the target path with delays matching the original timing
4. Uses the actual timestamps from the template run - no synthetic timing needed!

## Usage

### Basic Usage

```python
from autodiscovery.replay import replay_autodiscovery

# Replay at original speed (1x)
replay_autodiscovery(
    source_path="gs://my-bucket/users/alice/jobs/melanoma/output",
    target_path="gs://my-bucket/users/alice/jobs/test-123/output"
)
```

### Accelerated Replay

```python
from autodiscovery.replay import replay_autodiscovery

# Replay 10x faster
replay_autodiscovery(
    source_path="gs://my-bucket/users/alice/jobs/melanoma/output",
    target_path="gs://my-bucket/users/bob/jobs/replay-456/output",
    time_scale=0.1,  # 0.1 = 10x faster, 2.0 = 2x slower
    project_id="my-gcp-project",  # Optional, auto-detected if not provided
    verbose=True
)
```

### Command Line

```bash
# Replay at original speed
python -m autodiscovery.replay \
  gs://my-bucket/users/alice/jobs/melanoma/output \
  gs://my-bucket/users/bob/jobs/test-789/output
```

## How Timing Works

The module reads GCS blob creation timestamps to determine the exact timing of the original run:

```python
# For each file after the first:
delay = (current_file.time_created - previous_file.time_created) * time_scale
time.sleep(delay)
copy_file()
```

This means:
- **No hardcoded delays** - timing comes from the actual run
- **Perfect fidelity** - replays match the original exactly (at 1x speed)
- **Flexible speed** - use `time_scale` to speed up (0.1 = 10x faster) or slow down (2.0 = 2x slower)
- **No AutoDiscovery knowledge** - module is completely agnostic to file meanings

## Integration with Cloud Run Jobs

To use replay mode in the job execution flow, you can add a `test_mode` or `replay_source` parameter:

```python
from autodiscovery_jobs import JobManager

manager = JobManager()

# Normal execution
execution_id = manager.run_job(userid, jobid, n_experiments=100)

# Replay mode (to be implemented in autodiscovery_jobs)
execution_id = manager.run_job(
    userid, jobid,
    test_mode=True,
    replay_source="gs://example-bucket/users/template/jobs/melanoma/output",
    time_scale=0.1  # 10x faster for testing
)
```

## Testing

```python
# Quick test with 10x speed
from autodiscovery.replay import replay_autodiscovery

replay_autodiscovery(
    source_path="gs://example-bucket/users/alice/jobs/melanoma/output",
    target_path="gs://example-bucket/users/alice/jobs/test-run-123/output",
    time_scale=0.1,  # 10x faster
    verbose=True
)
```

## Example Output

```
Replay AutoDiscovery Run
  Source: gs://example-bucket/users/alice/jobs/melanoma/output
  Target: gs://example-bucket/users/bob/jobs/test-123/output
  Files: 206
  Time scale: 0.1x

[t=0.0s] args.json
[t=0.3s] mcts_node_1_0.json
[t=0.3s] node_1_0.json
[t=0.8s] mcts_node_2_0.json
[t=0.8s] node_2_0.json
...
[t=18.2s] mcts_nodes.json
[t=18.2s] mcts_nodes_all.json
[t=18.2s] mcts_nodes.csv

[t=18.2s] Replay complete! 206 files copied.
```

## Notes

- **Timestamp-based**: Delays are computed from GCS blob creation timestamps
- **No configuration needed**: Works with any AutoDiscovery run automatically
- **Time scale**: Speed up or slow down the replay as needed
- **GCS paths**: Both source and target must be GCS paths (start with `gs://`)
- **Authentication**: Uses Application Default Credentials (ADC) or project-specific credentials
