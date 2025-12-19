"""Modal-adjacent helpers for running code execution workloads."""

from .ipython_session import run_ipython_cell

__all__ = ["run_ipython_cell"]


def hello() -> str:
    """Return a friendly greeting from the modal package."""
    return "Hello from modal!"
