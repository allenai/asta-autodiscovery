"""Object-key layout for everything a run persists.

Every module that reads or writes run data builds its keys here, so the layout
is spelled out once. The same keys are used unchanged by every storage backend,
so a bucket and a data directory hold identical trees::

    users/<userid>/user.json                            # user profile
    users/<userid>/jobs/<jobid>/metadata.json           # run configuration
    users/<userid>/jobs/<jobid>/run_details.json        # execution state
    users/<userid>/jobs/<jobid>/email_state.json        # notification state
    users/<userid>/jobs/<jobid>/data/<filename>         # uploaded datasets
    users/<userid>/jobs/<jobid>/output/args.json        # resolved job args
    users/<userid>/jobs/<jobid>/output/mcts_node_*.json # experiment results
    users/<userid>/datalib/<dirname>/...                # read-only data library
    users/<userid>/datalib/<dirname>/README.md          # its description
    index/shared-runs/<jobid>                           # shared-run owner index

The job container sees ``users/<userid>/jobs/<jobid>/`` as a directory mounted
at :data:`~autodiscovery_jobs.backends.base.JOB_MOUNT_ROOT`, and each data-library
directory a run selects, read-only, at the same key path under that root.

The data library holds a user's large or reused datasets. It is populated out of
band, and a run mounts the directories it selects instead of copying them into
its own ``data/``. Only its top-level directories are selectable.
"""

from __future__ import annotations


def user_prefix(userid: str) -> str:
    """Key prefix (trailing slash) holding everything for one user."""
    return f"users/{userid}/"


def job_dir(userid: str, jobid: str) -> str:
    """One run's subtree, without a trailing slash.

    Use this where the value is a path segment (container mount points, host
    bind-mount sources); use :func:`job_prefix` for listings.
    """
    return f"{user_prefix(userid)}jobs/{jobid}"


def job_prefix(userid: str, jobid: str) -> str:
    """Key prefix (trailing slash) holding everything for one run."""
    return f"{job_dir(userid, jobid)}/"


def job_key(userid: str, jobid: str, name: str) -> str:
    """Key of one object inside a run, e.g. ``job_key(u, j, "output/args.json")``."""
    return f"{job_prefix(userid, jobid)}{name}"


def datalib_prefix(userid: str) -> str:
    """Key prefix (trailing slash) holding a user's data-library directories."""
    return f"{user_prefix(userid)}datalib/"


def datalib_dir(userid: str, dirname: str) -> str:
    """One data-library directory, without a trailing slash.

    ``dirname`` must already be a single path segment
    (see :func:`validate_datalib_dirname`).
    """
    return f"{datalib_prefix(userid)}{dirname}"


def validate_datalib_dirname(dirname: str) -> str:
    """Return ``dirname`` if it names a single top-level data-library directory.

    Selections arrive from the client and become mount paths and object keys, so
    anything that could step outside ``datalib/`` is rejected rather than
    normalized.

    Raises:
        ValueError: If ``dirname`` is empty, ``.``/``..``, contains a slash or a
            NUL, or starts with a dot.
    """
    if (
        not isinstance(dirname, str)
        or not dirname
        or dirname.startswith(".")
        or "/" in dirname
        or "\\" in dirname
        or "\0" in dirname
    ):
        raise ValueError(f"Invalid data library directory name: {dirname!r}")
    return dirname


def shared_run_index_key(jobid: str) -> str:
    """Key of the shared-run index entry naming a run's owner."""
    return f"index/shared-runs/{jobid}"
