"""Utilities for collecting results from concurrent futures."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from concurrent.futures import Future, as_completed
from typing import TypeVar

T = TypeVar("T")


def gather_completed_futures(
    future_labels: Mapping[Future[T | None], str],
    *,
    on_error: Callable[[str, Exception], None] | None = None,
) -> list[T]:
    """Collect successful results from futures while continuing after failures.

    Args:
        future_labels: Mapping of futures to human-readable labels for error reporting.
        on_error: Optional callback invoked with the label and exception when a
            future fails.

    Returns:
        List of non-``None`` results from futures that completed successfully.

    Raises:
        KeyboardInterrupt: Re-raised immediately to preserve interrupt behavior.
    """
    results: list[T] = []
    for future in as_completed(future_labels):
        label = future_labels[future]
        try:
            result = future.result()
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            if on_error is not None:
                on_error(label, exc)
            continue
        if result is not None:
            results.append(result)
    return results
