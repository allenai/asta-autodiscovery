"""Shared, cached Google Cloud Storage client.

Constructing a :class:`google.cloud.storage.Client` is surprisingly expensive:
each instance re-runs credential/session setup (tens of milliseconds apiece).
The credit and run endpoints call many small GCS helpers per request, and each
helper used to build its own client, so a single request could construct dozens
of clients and spend seconds purely on client setup.

A ``storage.Client`` is safe to share across threads for the read/write blob
operations used here, and the Google client libraries recommend reusing a
single long-lived client (it transparently refreshes credentials). We therefore
cache one client per ``project_id`` for the lifetime of the process.
"""

from __future__ import annotations

import threading

from google.cloud import storage

from .config import JobConfig

_clients: dict[str | None, storage.Client] = {}
_lock = threading.Lock()


def get_storage_client(config: JobConfig | None = None) -> storage.Client:
    """Return a process-wide cached ``storage.Client`` for the config's project.

    Reuses a single client per ``project_id`` to avoid repeated credential and
    HTTP-session setup. Thread-safe.

    Args:
        config: Job configuration (uses default if None).

    Returns:
        A shared ``storage.Client`` scoped to ``config.project_id``.
    """
    config = config or JobConfig()
    project_id = config.project_id

    client = _clients.get(project_id)
    if client is not None:
        return client

    with _lock:
        # Re-check inside the lock in case another thread just created it.
        client = _clients.get(project_id)
        if client is None:
            client = storage.Client(project=project_id)
            _clients[project_id] = client
        return client
