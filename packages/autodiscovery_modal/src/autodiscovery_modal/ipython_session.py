"""Modal image helpers for IPython-based sandbox execution."""

from collections.abc import Iterable

import modal
from asta_sandbox import build_modal_ephemeral_image


def build_sandbox_image(
    extra_packages: Iterable[str] | None = None,
    *,
    python_version: str = "3.13",
) -> modal.Image:
    """Build a Modal image for IPython-based execution.

    Thin wrapper around build_modal_ephemeral_image from asta_sandbox.

    Args:
        extra_packages: Optional additional packages to install.
        python_version: Python version for the base image.

    Returns:
        A Modal image with IPython and asta_sandbox sources.
    """
    return build_modal_ephemeral_image(
        extra_packages=list(extra_packages) if extra_packages else None,
        python_version=python_version,
    )


image = build_sandbox_image()
