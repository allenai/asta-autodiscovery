# AutoDiscovery Replay Module

The replay module simulates AutoDiscovery runs by progressively copying output files from a completed run in GCS. This is useful for testing webapp integration and polling behavior without running expensive LLM calls.

## Usage

### Basic Usage

```python
from autodiscovery.replay import replay_autodiscovery

replay_autodiscovery(
    source_path="gs://my-bucket/users/alice/jobs/melanoma/output",
    target_path="gs://my-bucket/users/alice/jobs/test-123/output"
)
```

### Custom Timing

```python
from autodiscovery.replay import replay_autodiscovery

# Adjust timing delays (all values in seconds)
custom_timing = {
    "args_delay": 0,           # Delay before args.json (immediate)
    "node_delay_min": 30,      # Min delay between nodes
    "node_delay_max": 90,      # Max delay between nodes
    "finalization_delay": 10,  # Delay before final summary files
}

replay_autodiscovery(
    source_path="gs://my-bucket/users/alice/jobs/melanoma/output",
    target_path="gs://my-bucket/users/bob/jobs/replay-456/output",
    timing_config=custom_timing,
    project_id="my-gcp-project",  # Optional, auto-detected if not provided
    verbose=True
)
```

### Command Line

```bash
# Run from the autodiscovery package directory
python -m autodiscovery.replay \
  gs://my-bucket/users/alice/jobs/melanoma/output \
  gs://my-bucket/users/bob/jobs/test-789/output
```

## File Write Sequence

The replay module copies files in the same order as a real AutoDiscovery run:

1. **Startup Phase**
   - `args.json` - Run configuration

2. **Iteration Phase** (repeated for each experiment)
   - `mcts_node_{level}_{idx}.json` - Node state with experiment details
   - `node_{level}_{idx}.json` - Chat messages and execution logs

3. **Finalization Phase**
   - `mcts_nodes.json` - Deduplicated summary
   - `mcts_nodes_all.json` - Complete node list
   - `mcts_nodes.csv` - CSV export

## Integration with Cloud Run Jobs

To use replay mode in the job execution flow, you can add a `test_mode` or `replay_source` parameter to the job configuration:

```python
from autodiscovery_jobs import JobManager

manager = JobManager()

# Normal execution
execution_id = manager.run_job(userid, jobid, n_experiments=100)

# Replay mode (to be implemented in autodiscovery_jobs)
execution_id = manager.run_job(
    userid, jobid,
    test_mode=True,
    replay_source="gs://example-gcp-project/users/template/jobs/melanoma/output"
)
```

## Testing

```python
# Quick test with fast timing
from autodiscovery.replay import replay_autodiscovery

fast_timing = {
    "args_delay": 0,
    "node_delay_min": 0.1,
    "node_delay_max": 0.5,
    "finalization_delay": 1,
}

replay_autodiscovery(
    source_path="gs://example-gcp-project/users/alice/jobs/melanoma/output",
    target_path="gs://example-gcp-project/users/alice/jobs/test-run-123/output",
    timing_config=fast_timing,
    verbose=True
)
```

## Notes

- The replay module discovers all node files from the source GCS path automatically
- Both source and target must be GCS paths (start with `gs://`)
- Node files are sorted by (level, index) to maintain correct execution order
- Random delays between `node_delay_min` and `node_delay_max` add realism
- The module handles varying numbers of experiments (not hardcoded)
- GCS client uses Application Default Credentials (ADC) or project-specific credentials
