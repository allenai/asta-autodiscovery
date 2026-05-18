# autodiscovery_jobs

Python package for managing Cloud Run jobs with GCS integration for the autodiscovery system.

## Features

- **GCS Operations**: Create job directories, upload datasets, download results
- **Cloud Run Integration**: Execute jobs, monitor status, retrieve logs

### Environment Variables

```bash
# GCS and GCP Configuration
export AUTODISCOVERY_BUCKET="your-bucket"  # or GCS_BUCKET
export GCP_PROJECT="your-project-id"
export GCP_REGION="us-west1"
export CLOUDRUN_JOB_NAME="autodiscovery-job"

# Authentication (see Authentication section below)
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account-key.json"

# Modal Configuration (for sandbox execution)
export MODAL_APP_NAME="asta-autodiscovery"
export MODAL_BUCKET_SECRET="example-bucket-secret"
```

### Programmatic Configuration

```python
from autodiscovery_jobs import JobManager, JobConfig

# Use defaults
manager = JobManager()

# Or customize
config = JobConfig(
    bucket="my-custom-bucket",
    region="us-central1",
    project_id="my-project"
)
manager = JobManager(config)
```

## Usage

### Using JobManager

Use the `JobManager` class for stateful operations with persistent configuration:

```python
from autodiscovery_jobs import JobManager
from pathlib import Path

# Initialize manager
manager = JobManager()

# Create job
manager.create_job("user123", "experiment_1")

# Upload dataset
manager.upload_dataset("user123", "experiment_1", Path("./data/my_dataset.csv"))

# Upload metadata
manager.upload_metadata("user123", "experiment_1", {
    "datasets": [{
        "name": "my_dataset.csv",
        "description": "My experimental dataset"
    }]
})

# Run job
execution_id = manager.run_job(
    "user123", "experiment_1",
    n_experiments=8,
    model="gpt-4o",
    belief_model="gpt-4o",
    temperature=1.0,
    k_experiments=8
)

print(f"Started job: {execution_id}")

# Download results when complete
results = manager.download_results("user123", "experiment_1", Path("./results"))
print(f"Downloaded {len(results)} files")
```

### Functional API

Use standalone functions for one-off operations:

```python
from autodiscovery_jobs import (
    create_job_directory,
    upload_dataset,
    upload_metadata,
    run_job,
    download_job_results
)
from pathlib import Path

# Create and setup job
create_job_directory("user123", "quick_test")
upload_dataset("user123", "quick_test", Path("./data.csv"))
upload_metadata("user123", "quick_test", {
    "datasets": [{"name": "data.csv", "description": "Test"}]
})

# Run job
execution_id = run_job("user123", "quick_test", n_experiments=4, model="gpt-4o")

# Download results
results = download_job_results("user123", "quick_test", Path("./results"))
```

### All-in-One Convenience Method

```python
from autodiscovery_jobs import JobManager
from pathlib import Path

manager = JobManager()

# Setup and run in one call
execution_id = manager.setup_and_run(
    userid="user123",
    jobid="quick_experiment",
    dataset_path=Path("./data/"),
    metadata={"datasets": [{"name": "data.csv", "description": "Test data"}]},
    n_experiments=4,
    model="gpt-4o",
    temperature=1.0
)
```

## Monitoring Workflows

### Poll Job Status

```python
from autodiscovery_jobs import JobManager
import time

manager = JobManager()

# Start a job
execution_id = manager.run_job("user123", "experiment_1", n_experiments=8)
print(f"Started job: {execution_id}")

# Poll for status
while True:
    status = manager.get_job_status(execution_id)
    state = status.get("status", {}).get("phase", "UNKNOWN")
    print(f"Job status: {state}")

    if state in ["SUCCEEDED", "FAILED", "CANCELLED"]:
        break

    time.sleep(30)  # Check every 30 seconds

# Get logs
logs = manager.get_job_logs(execution_id, limit=100)
for log in logs:
    print(log)

# Download results if successful
if state == "SUCCEEDED":
    results = manager.download_results("user123", "experiment_1", Path("./results"))
    print(f"Downloaded {len(results)} result files")
```

### Cancel Running Job

```python
from autodiscovery_jobs import JobManager

manager = JobManager()

# Start a job
execution_id = manager.run_job("user123", "experiment_1", n_experiments=8)

# Cancel it
manager.cancel_job(execution_id)
print(f"Cancelled job: {execution_id}")
```

### View Recent Logs

```python
from autodiscovery_jobs import JobManager

manager = JobManager()

# Get recent logs for all executions
logs = manager.get_job_logs(limit=50)
for log in logs:
    print(log)

# Get logs for specific execution
logs = manager.get_job_logs(execution_id="autodiscovery-job-abc123", limit=100)
```

## Job Management

### List User's Jobs

```python
from autodiscovery_jobs import JobManager

manager = JobManager()

# List all jobs for a user
jobs = manager.list_jobs("user123")
print(f"Jobs: {jobs}")
```

### Check if Job Exists

```python
from autodiscovery_jobs import JobManager

manager = JobManager()

if manager.job_exists("user123", "experiment_1"):
    print("Job exists!")
else:
    print("Job not found")
```

### Delete Job

```python
from autodiscovery_jobs import JobManager

manager = JobManager()

# Delete job and all its contents
manager.delete_job("user123", "old_experiment")
```

## Error Handling

```python
from autodiscovery_jobs import (
    JobManager,
    JobNotFoundError,
    JobAlreadyExistsError,
    GCSError,
    CloudRunError
)

manager = JobManager()

try:
    manager.create_job("user123", "experiment_1")
except JobAlreadyExistsError:
    print("Job already exists, using existing job")
    pass

try:
    results = manager.download_results("user123", "nonexistent_job", Path("./results"))
except JobNotFoundError as e:
    print(f"Job not found: {e}")

try:
    manager.upload_dataset("user123", "job1", Path("./data.csv"))
except GCSError as e:
    print(f"GCS operation failed: {e}")

try:
    execution_id = manager.run_job("user123", "job1", n_experiments=4)
except CloudRunError as e:
    print(f"Cloud Run operation failed: {e}")
```

## Cloud Run Arguments

The `run_job()` method supports the following arguments (see `cloudrun.run_job()` docstring for full details):

### Required Arguments
- `n_experiments`: Number of experiments to run
- `model`: Model to use (e.g., "gpt-4o", "o4-mini")

### Optional Explicit Parameters
- `belief_model`: Model for belief distribution (default: "gpt-4o")
- `temperature`: Temperature for agents (default: 1.0)
- `belief_temperature`: Temperature for belief agent (default: 1.0)
- `k_experiments`: Branching factor (default: 8)
- `mcts_selection`: Selection method (default: "pw")
  - Choices: "ucb1", "beam_search", "pw", "pw_all", "ucb1_recursive"
- `reasoning_effort`: For o-series models (default: "medium")
  - Choices: "low", "medium", "high"
- `exploration_weight`: UCB1 exploration weight (default: 2.0)
- `code_timeout`: Timeout in seconds (default: 1800)
- `n_warmstart`: Number of warmstart experiments (default: 0)

### Additional Arguments via **kwargs

Any additional argument can be passed via **kwargs:

```python
manager.run_job(
    "user123", "experiment_1",
    n_experiments=4,
    model="gpt-4o",
    # Explicit parameters
    belief_model="gpt-4o",
    temperature=1.0,
    k_experiments=8,
    # Via kwargs
    pw_k=1.0,
    pw_alpha=0.5,
    use_binary_reward=True
)
```

## GCS Directory Structure

The package creates and manages the following structure:

```
gs://example-bucket/
└── users/
    └── {userid}/
        └── jobs/
            └── {jobid}/
                ├── data/              # Dataset files (mounted in Modal sandbox)
                │   ├── file1.csv
                │   └── file2.csv
                ├── metadata.json      # Dataset metadata
                └── output/            # Job results (written by Cloud Run)
                    ├── mcts_nodes.json
                    ├── results.csv
                    └── ...
```

## Authentication

The `autodiscovery_jobs` package uses Google Cloud client libraries which rely on [Application Default Credentials (ADC)](https://cloud.google.com/docs/authentication/application-default-credentials) for authentication.

### Service Account Key

Get the service account key from 1Password and then **set the environment variable** to point to your key file:
```bash
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account-key.json"
```
