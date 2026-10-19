import pytest
from metrics.costs import _FALLBACK_PRICING, _lookup_pricing


@pytest.mark.parametrize(
    "model", ["vertex_ai/gemini-3.8-flash", "vertex_ai/gemini-3.5-flash", "gemini-3.8-flash"]
)
def test_gemini_migration_targets_are_priced(model: str) -> None:
    """Models replacing gemini-3.7-flash must not be costed at the fallback rate."""
    assert _lookup_pricing(model) != _FALLBACK_PRICING


def test_gemini_3_8_flash_pricing() -> None:
    assert _lookup_pricing("vertex_ai/gemini-3.8-flash") == {"input": 0.75, "output": 3.75}
