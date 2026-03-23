"""Development utilities for testing and simulation."""

from devtools.cloudrun import run_replay_job

# Source path for simulated runs - template files to replay
# This should be a real run because the replay is based on the file creation times,
# and also then the data shape will be realistic.
REPLAY_SOURCE_PATH = "gs://example-bucket/users/samples/jobs/nls_bmi/output"

# Time scale for replay (0.1 = 10x faster than original)
REPLAY_TIME_SCALE = 0.1


def run_simulated_job(
    userid: str,
    jobid: str,
    bucket: str,
    project_id: str,
    region: str,
) -> str:
    """Run a simulated AutoDiscovery job by replaying pre-recorded outputs.

    Args:
        userid: User identifier
        jobid: Job identifier
        bucket: Target GCS bucket name
        project_id: GCP project ID
        region: GCP region

    Returns:
        Execution ID from Cloud Run
    """
    return run_replay_job(
        userid=userid,
        jobid=jobid,
        source_path=REPLAY_SOURCE_PATH,
        target_bucket=bucket,
        time_scale=REPLAY_TIME_SCALE,
        project_id=project_id,
        region=region,
    )
