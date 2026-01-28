"""Tests for normalized surprisal theoretical maximum calculations."""

import numpy as np

from autodiscovery.run import _theoretical_max_boolean_cat


def _brute_force_max(
    n_samples: int,
    evidence_weight: float,
    prior_params: tuple[float, float],
    step: float = 0.1,
) -> float:
    """Brute force compute the maximum for |mu2 - mu1|."""
    alpha, beta = prior_params
    s = alpha + beta

    # Grid for n, m in {0,...,N} (with fractional step to model abstentions)
    n_vals = np.arange(0.0, n_samples + step, step)
    m_vals = np.arange(0.0, n_samples + step, step)

    # Create meshgrid
    n_grid, m_grid = np.meshgrid(n_vals, m_vals, indexing="ij")

    # Initialize difference grid
    diff_grid = np.zeros_like(n_grid, dtype=float)

    # Compute the max mean difference at each possible (n,m) by comparing 2 extreme cases
    for i, n in enumerate(n_vals):
        for j, m in enumerate(m_vals):
            # Case 1: Stage 1 all false (x=0), Stage 2 all true (y=m)
            mu1_case1 = (alpha) / (n + s) if (n + s) > 0 else 0.0
            mu2_case1 = (alpha + evidence_weight * m) / (n + evidence_weight * m + s)
            diff1 = abs(mu2_case1 - mu1_case1)

            # Case 2: Stage 1 all true (x=n), Stage 2 all false (y=0)
            mu1_case2 = (n + alpha) / (n + s) if (n + s) > 0 else 0.0
            mu2_case2 = (n + alpha) / (n + evidence_weight * m + s)
            diff2 = abs(mu2_case2 - mu1_case2)

            diff_grid[i, j] = max(diff1, diff2)

    return float(np.max(diff_grid))


def test_theoretical_max_boolean_cat_matches_bruteforce() -> None:
    """Ensure the closed-form maximum upper-bounds the discrete brute-force search."""
    cases = [
        (5, 1.0, (0.5, 0.5)),
        (8, 0.5, (2.0, 2.0)),
        (10, 1.0, (5.0, 1.0)),
        (10, 1.0, (0.1, 2.0)),
    ]
    for n_samples, evidence_weight, prior_params in cases:
        theoretical = _theoretical_max_boolean_cat(
            n_samples, evidence_weight, prior_params=prior_params
        )
        brute = _brute_force_max(n_samples, evidence_weight, prior_params, step=0.1)
        assert theoretical + 1e-9 >= brute
        assert abs(theoretical - brute) <= 2e-3


def test_theoretical_max_boolean_cat_zero_when_no_evidence() -> None:
    """Confirm empty sample/evidence inputs return zero."""
    assert _theoretical_max_boolean_cat(0, 1.0) == 0.0
    assert _theoretical_max_boolean_cat(5, 0.0) == 0.0


def test_theoretical_max_boolean_cat_manual_case() -> None:
    """Confirm the manual closed-form value for N=30, w=1 with Jeffreys prior."""
    value = _theoretical_max_boolean_cat(30, 1.0, prior_params=(0.5, 0.5))
    assert value == 0.7729916774697783
