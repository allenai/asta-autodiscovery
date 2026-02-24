"""Credit management and validation for autodiscovery experiments.

This module centralizes all credit-related logic including:
- Credit calculation for individual jobs
- User-level credit aggregation
- Credit validation (boolean and exception-based)

Example usage:
    # Check credits with boolean
    if can_start_experiments(10, userid, config):
        manager.run_job(...)

    # Check credits with exception
    try:
        check_experiment_limits(10, userid, config)
        manager.run_job(...)
    except InvalidExperimentCountError as e:
        return jsonify({"error": e.message}), 400
    except ExperimentLimitExceededError as e:
        return jsonify({"error": e.message}), 400
    except InsufficientCreditsError as e:
        return jsonify({"error": e.message}), 402

    # Get full credit details
    credits = get_user_credits(userid, config)
    print(f"Available: {credits.available}")
"""

from typing import Any, NamedTuple

from autodiscovery_jobs import JobConfig
from autodiscovery_jobs.gcs import (
    count_experiment_results,
    get_job_args,
    get_metadata,
    list_user_jobs,
)
from autodiscovery_jobs.run_details import get_run_details
from autodiscovery_jobs.user_profile import get_user_granted_credits

# Credit configuration
DEFAULT_CREDITS_GRANTED = 1000

# Max number of experiments that can run in a single job
DEFAULT_EXPERIMENT_LIMIT = 500


class JobStats(NamedTuple):
    """Statistics about a job's experiments.

    Attributes:
        job_args: Job arguments dictionary
        num_experiments_requested: Number of experiments requested
        num_experiments_completed: Number of experiments completed
        num_experiments_pending: Number of experiments pending
    """

    job_args: dict[str, Any]
    num_experiments_requested: int
    num_experiments_completed: int
    num_experiments_pending: int


class UserCredits(NamedTuple):
    """Complete credit information for a user.

    Attributes:
        granted: Total credits granted to user
        consumed: Credits already consumed (completed experiments)
        pending: Credits reserved for running experiments
        available: Credits available for new experiments (granted - consumed - pending)
    """

    granted: int
    consumed: int
    pending: int
    available: int


class InsufficientCreditsError(Exception):
    """Raised when user does not have sufficient credits for an operation.

    Attributes:
        requested: Number of credits requested
        available: Number of credits available
        message: Descriptive error message
    """

    def __init__(self, requested: int, available: int):
        self.requested = requested
        self.available = available
        self.message = (
            f"Insufficient credits: requested {requested}, but only {available} available"
        )
        super().__init__(self.message)


class InvalidExperimentCountError(Exception):
    """Raised when experiment count is invalid (n <= 0).

    Attributes:
        requested: Number of experiments requested
        message: Descriptive error message
    """

    def __init__(self, requested: int):
        self.requested = requested
        self.message = (
            f"Invalid experiment count: {requested}. Must be greater than 0."
        )
        super().__init__(self.message)


class ExperimentLimitExceededError(Exception):
    """Raised when experiment count exceeds maximum allowed limit.

    Attributes:
        requested: Number of experiments requested
        limit: Maximum experiments allowed
        message: Descriptive error message
    """

    def __init__(self, requested: int, limit: int):
        self.requested = requested
        self.limit = limit
        self.message = (
            f"Experiment limit exceeded: requested {requested}, but maximum allowed is {limit}"
        )
        super().__init__(self.message)


def get_user_credits_granted(userid: str, config: JobConfig | None = None) -> int:
    """Get the number of credits granted to a user.

    Checks for custom allocation in GCS (users/{userid}/user.json).
    Falls back to DEFAULT_CREDITS_GRANTED if no custom allocation exists.

    Args:
        userid: User identifier
        config: Job configuration (uses default if None)

    Returns:
        Number of credits granted to user

    Example:
        >>> credits_granted = get_user_credits_granted("user123")
        >>> print(f"User has {credits_granted} total credits")
    """
    # Try to get custom allocation from user profile
    custom_credits = get_user_granted_credits(userid, config)

    # Fall back to default if no custom allocation
    if custom_credits is None:
        return DEFAULT_CREDITS_GRANTED

    return custom_credits


def get_job_stats(userid: str, jobid: str, config: JobConfig | None = None) -> JobStats | None:
    """Get statistics about a job's experiments.

    Args:
        userid: User identifier
        jobid: Job identifier
        config: Configuration (uses default if None)

    Returns:
        JobStats object containing job arguments and experiment counts,
        or None if metadata is missing or invalid.
    """
    config = config or JobConfig()

    metadata = get_metadata(userid=userid, jobid=jobid, config=config)
    if metadata is None:
        return None

    completed = count_experiment_results(userid=userid, jobid=jobid, config=config)
    requested = metadata.get("n_experiments", None)
    if requested is None:
        args = get_job_args(userid=userid, jobid=jobid, config=config) or {}
        requested = args.get("n_experiments", 0)
    pending = max(0, requested - completed)

    job_stats = JobStats(
        job_args=metadata,
        num_experiments_requested=requested,
        num_experiments_completed=completed,
        num_experiments_pending=pending,
    )
    return job_stats


def calculate_job_credits(
    userid: str, jobid: str, config: JobConfig | None = None
) -> tuple[int, int]:
    """Calculate consumed and pending credits for a single job.

    This function is migrated from autodiscovery_jobs.gcs module to
    centralize credit logic in the API layer.

    Args:
        userid: User identifier
        jobid: Job identifier
        config: Configuration (uses default if None)

    Returns:
        Tuple of (consumed_credits, pending_credits)

    Example:
        >>> consumed, pending = calculate_job_credits("user123", "job456")
        >>> print(f"Job has consumed {consumed} and pending {pending} credits")
    """
    job_stats = get_job_stats(userid=userid, jobid=jobid, config=config)
    if job_stats is None:
        return (0, 0)

    consumed = job_stats.num_experiments_completed
    pending = job_stats.num_experiments_pending
    return (consumed, pending)


def get_user_credits(userid: str, config: JobConfig | None = None) -> UserCredits:
    """Calculate complete credit information for a user across all jobs.

    This function aggregates credit usage across all jobs owned by the user
    and calculates all relevant credit metrics.

    Args:
        userid: User identifier
        config: Configuration (uses default if None)

    Returns:
        UserCredits object with all credit metrics

    Example:
        >>> credits = get_user_credits("user123")
        >>> print(f"Available: {credits.available}, Consumed: {credits.consumed}")
    """
    total_consumed = 0
    total_pending = 0

    # Get all jobs for the user
    job_ids = list_user_jobs(userid=userid, config=config)

    # Aggregate credits across all jobs
    for job_id in job_ids:
        try:
            run_details = get_run_details(userid=userid, runid=job_id, config=config)
            run_status = run_details.status if run_details is not None else None
            if run_status is None or run_status in ["CREATED"]:
                continue
            consumed, pending = calculate_job_credits(userid=userid, jobid=job_id, config=config)
            total_consumed += consumed
            if run_status in ["PENDING", "QUEUED", "RUNNING"]:
                total_pending += pending
        except Exception:
            # Continue processing other jobs if one fails
            # This matches the error handling in user_api.py line 100
            pass

    # Get credits granted for this user
    credits_granted = get_user_credits_granted(userid)

    # Calculate derived metrics
    available = max(0, credits_granted - total_consumed - total_pending)

    return UserCredits(
        granted=credits_granted,
        consumed=total_consumed,
        pending=total_pending,
        available=available,
    )


def can_start_experiments(n_experiments: int, userid: str, config: JobConfig | None = None) -> bool:
    """Check if user has sufficient credits to start N experiments.

    Uses the conservative 'available' metric (granted - used - pending)
    which accounts for both completed and pending experiments.

    Args:
        n_experiments: Number of experiments to check
        userid: User identifier
        config: Configuration (uses default if None)

    Returns:
        True if user has sufficient available credits, False otherwise

    Example:
        >>> if can_start_experiments(10, "user123"):
        ...     print("User can start 10 experiments")
        ... else:
        ...     print("Insufficient credits")
    """
    credits = get_user_credits(userid=userid, config=config)
    return credits.available >= n_experiments


def check_experiment_limits(
    n_experiments: int, userid: str, config: JobConfig | None = None
) -> UserCredits:
    """Verify experiment count is valid and user has sufficient credits.

    Performs three validation checks in order:
    1. Validates n_experiments > 0
    2. Validates n_experiments <= DEFAULT_EXPERIMENT_LIMIT (500)
    3. Validates user has sufficient available credits

    Uses the conservative 'available' metric (granted - used - pending).
    This function is useful in API endpoints where you want to fail fast
    with specific, descriptive exceptions.

    Args:
        n_experiments: Number of experiments to check
        userid: User identifier
        config: Configuration (uses default if None)

    Returns:
        UserCredits object if all checks pass

    Raises:
        InvalidExperimentCountError: If n_experiments <= 0
        ExperimentLimitExceededError: If n_experiments > DEFAULT_EXPERIMENT_LIMIT
        InsufficientCreditsError: If user does not have enough available credits

    Example:
        >>> try:
        ...     credits = check_experiment_limits(10, "user123")
        ...     print(f"All checks passed, user has {credits.available} available")
        ... except InvalidExperimentCountError as e:
        ...     print(f"Invalid count: {e.message}")
        ... except ExperimentLimitExceededError as e:
        ...     print(f"Limit exceeded: {e.message}")
        ... except InsufficientCreditsError as e:
        ...     print(f"No credits: {e.message}")
    """
    # Validation 1: Check n_experiments > 0
    if n_experiments <= 0:
        raise InvalidExperimentCountError(requested=n_experiments)

    # Validation 2: Check n_experiments <= DEFAULT_EXPERIMENT_LIMIT
    if n_experiments > DEFAULT_EXPERIMENT_LIMIT:
        raise ExperimentLimitExceededError(
            requested=n_experiments,
            limit=DEFAULT_EXPERIMENT_LIMIT
        )

    # Validation 3: Check sufficient credits (existing logic)
    credits = get_user_credits(userid=userid, config=config)

    if credits.available < n_experiments:
        raise InsufficientCreditsError(requested=n_experiments, available=credits.available)

    return credits
