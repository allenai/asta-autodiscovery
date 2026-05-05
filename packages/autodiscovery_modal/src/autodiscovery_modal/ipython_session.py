"""Modal image helpers for IPython-based sandbox execution."""

from collections.abc import Iterable

import modal


def build_sandbox_image(
    extra_packages: Iterable[str] | None = None,
    *,
    python_version: str = "3.13",
) -> modal.Image:
    """Build a Modal image for IPython-based execution.

    Args:
        extra_packages: Optional additional packages to install via uv.
        python_version: Python version for the base image.

    Returns:
        A Modal image with IPython and local code_execution sources.
    """
    packages = ["ipython>=9.8.0"]
    if extra_packages:
        packages.extend(extra_packages)
    return (
        modal.Image.debian_slim(python_version=python_version)
        .uv_pip_install(*packages)
        .add_local_python_source("code_execution")
    )


image = build_sandbox_image()
