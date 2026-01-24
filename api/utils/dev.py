"""Development utilities for testing and simulation."""

from devtools.cloudrun import run_replay_job

# Source path for simulated runs - template files to replay
REPLAY_SOURCE_PATH = "gs://example-gcp-project/users/test/jobs/melanoma/output"
# REPLAY_SOURCE_PATH = "gs://example-gcp-project/users/google-oauth2|EXAMPLE_USER_ID/jobs/39ca1146-a09b-45d1-966f-dfd503093e80/output"

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
