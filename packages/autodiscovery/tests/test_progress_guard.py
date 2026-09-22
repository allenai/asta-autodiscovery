"""Unit tests for the stall guard, exercised without driving a whole exploration run."""

import pytest
from autodiscovery.progress import NoProgressError, ProgressGuard


def test_committing_a_node_resets_the_tally():
    guard = ProgressGuard(2, total_to_sample=10)

    guard.check_iteration(0, n_sampled=0)
    assert guard.consecutive_no_progress == 1

    guard.check_iteration(1, n_sampled=1)
    assert guard.consecutive_no_progress == 0

    # The tally restarts, so the next barren iteration is not the second one.
    guard.check_iteration(0, n_sampled=1)
    assert guard.consecutive_no_progress == 1


def test_aborts_at_the_limit_and_names_the_last_failure():
    guard = ProgressGuard(2, total_to_sample=10)
    guard.record_expansion_error("1_0", RuntimeError("quota exhausted"))

    guard.check_iteration(0, n_sampled=0)
    with pytest.raises(NoProgressError) as excinfo:
        guard.check_iteration(0, n_sampled=0)

    assert excinfo.value.iterations == 2
    assert "quota exhausted" in str(excinfo.value)
    assert "0/10 experiments completed" in str(excinfo.value)


def test_a_committed_iteration_forgets_the_earlier_error():
    guard = ProgressGuard(1, total_to_sample=10)
    guard.record_expansion_error("1_0", RuntimeError("transient"))
    guard.check_iteration(1, n_sampled=1)

    with pytest.raises(NoProgressError) as excinfo:
        guard.check_iteration(0, n_sampled=1)

    assert excinfo.value.last_error is None
    assert "no usable experiment was generated" in str(excinfo.value)


def test_exhaustion_is_normal_after_progress():
    guard = ProgressGuard(3, total_to_sample=10)
    guard.check_iteration(1, n_sampled=1)

    # Ran dry with work committed and nothing erroring: a clean early finish.
    guard.check_exhausted(n_sampled=1)


@pytest.mark.parametrize(
    ("n_sampled", "error"),
    [(0, None), (3, RuntimeError("boom"))],
)
def test_exhaustion_is_a_failure_when_nothing_committed_or_expansion_errored(n_sampled, error):
    guard = ProgressGuard(3, total_to_sample=10)
    if error is not None:
        guard.record_expansion_error("1_0", error)
    guard.check_iteration(0, n_sampled=n_sampled)

    with pytest.raises(NoProgressError):
        guard.check_exhausted(n_sampled=n_sampled)
