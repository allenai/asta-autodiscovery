"""Asta integration: dataset imports and the "dig deeper" experiment handoff.

Everything that talks to Asta lives in this package, so a deployment with no
Asta behind it carries no Asta code paths outside it. The rest of the API
touches it in two places only: ``app.py`` registers :func:`asta_api.create`, and
the runs API reports :func:`is_enabled` so the UI can hide the entry points.
"""

from asta.context_client import is_configured as is_enabled

__all__ = ["is_enabled"]
