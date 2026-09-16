#!/usr/bin/env python3
"""Grant a one-time credit top-up to users who have a credit override.

Raises each eligible user's credit allowance by ``GRANT_AMOUNT`` and records
that it did so, both in the user's profile (``users/{userid}/user.json``).

Scope: only users who have an explicit ``granted_credits`` override
---------------------------------------------------------------------
A user with no override, or with the field set to null, falls through to
``DEFAULT_CREDITS_GRANTED`` at read time and is already on the current default.
Those users are skipped. This is why nothing here needs to know what the
default is, before or after it was raised -- the script only ever adds to a
value that is already stored, so there is no way for it to credit someone
against the wrong baseline.

Why the record lives in the profile
-----------------------------------
``granted = granted + N`` compounds, so the script has to know whether it has
already run for a user. Writing that fact into the profile being changed makes
the credit and the record of the credit the same write: there is no window in
which one landed and the other did not, nothing to reconcile on a restart, and
no separate bookkeeping object to purge when a user is erased. The check is by
grant id, so an unrelated edit to the user's credits between runs is simply
irrelevant rather than looking like corruption.

    "grants": [
      {"id": "grant-1000-credits-v1", "amount": 1000,
       "previous_granted": 500, "granted_at": "..."}
    ]

Concurrency
-----------
Each profile is read with its GCS generation and written back with
``if_generation_match``, so a write fails outright if anything else modified
the profile in between rather than silently discarding that change. Such a user
is reported as a conflict and left alone; re-running the script picks them up.

Re-running is safe: users whose profile already carries this grant id are
skipped, so an interrupted run can simply be run again.

Usage:
    uv run python api/scripts/grant_credits.py --dry-run
    uv run python api/scripts/grant_credits.py
    uv run python api/scripts/grant_credits.py --userid "google-oauth2|123"

Environment variables required:
    GCS_BUCKET, GCP_PROJECT and GCS credentials (read/write on user profiles).
"""

import argparse
import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

from autodiscovery_jobs import JobConfig
from autodiscovery_jobs.client import get_storage_client
from autodiscovery_jobs.gcs import list_user_ids
from autodiscovery_jobs.user_profile import get_user_profile_path
from google.api_core.exceptions import PreconditionFailed
from google.cloud.storage import Bucket

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Credits added to each eligible user's override.
GRANT_AMOUNT = 1000

# Identifies this grant in a profile's "grants" list. Bump it for a future
# grant so that one does not read this one as already applied.
GRANT_ID = "grant-1000-credits-v1"


def read_profile(bucket: Bucket, userid: str) -> tuple[dict[str, Any], int] | None:
    """Read a user's profile together with the generation it was read at.

    The content is fetched with the generation as a precondition, so the
    returned document is guaranteed to be the one that generation names.

    Args:
        bucket: Bucket holding user profiles
        userid: User identifier

    Returns:
        Tuple of (profile document, generation), or None if the user has no
        profile

    Raises:
        PreconditionFailed: If the profile changed between the metadata read
            and the content read
        ValueError: If GCS returned no generation, leaving no way to write the
            profile back safely
    """
    blob = bucket.get_blob(get_user_profile_path(userid))
    if blob is None:
        return None
    generation = blob.generation
    if generation is None:
        raise ValueError(f"no generation returned for {get_user_profile_path(userid)}")
    document = json.loads(blob.download_as_text(if_generation_match=generation))
    return document, generation


def is_already_granted(document: dict[str, Any]) -> bool:
    """Check whether this grant has already been applied to a profile.

    Args:
        document: Profile document

    Returns:
        True if the profile already records a grant with this script's ID
    """
    return any(
        entry.get("id") == GRANT_ID
        for entry in document.get("grants") or []
        if isinstance(entry, dict)
    )


def apply_grant(document: dict[str, Any], previous: int) -> dict[str, Any]:
    """Build the updated profile document for a granted user.

    Args:
        document: Profile document as read from GCS
        previous: The user's granted_credits before this grant

    Returns:
        A new document with the credits added and the grant recorded
    """
    now = datetime.now(UTC).isoformat()
    updated = dict(document)
    updated["granted_credits"] = previous + GRANT_AMOUNT
    updated["updated_at"] = now
    updated["grants"] = [
        *(document.get("grants") or []),
        {
            "id": GRANT_ID,
            "amount": GRANT_AMOUNT,
            "previous_granted": previous,
            "granted_at": now,
        },
    ]
    return updated


def grant_user(bucket: Bucket, userid: str, dry_run: bool) -> str:
    """Apply the grant to one user, if they are eligible and have not had it.

    Args:
        bucket: Bucket holding user profiles
        userid: User identifier
        dry_run: When True, report the planned change without writing

    Returns:
        One of "granted", "skipped" or "conflict"
    """
    try:
        result = read_profile(bucket, userid)
    except PreconditionFailed:
        logger.warning(f"CONFLICT {userid}: profile changed while being read")
        return "conflict"

    if result is None:
        logger.info(f"SKIP     {userid}: no profile, already on the default")
        return "skipped"

    document, generation = result

    previous = document.get("granted_credits")
    if previous is None:
        logger.info(f"SKIP     {userid}: no override, already on the default")
        return "skipped"

    if is_already_granted(document):
        logger.info(f"SKIP     {userid}: already granted (granted_credits={previous})")
        return "skipped"

    updated = apply_grant(document, previous)
    new_granted = updated["granted_credits"]

    if dry_run:
        logger.info(f"DRY-RUN  {userid}: {previous} -> {new_granted}")
        return "granted"

    try:
        bucket.blob(get_user_profile_path(userid)).upload_from_string(
            json.dumps(updated, indent=2),
            if_generation_match=generation,
        )
    except PreconditionFailed:
        logger.warning(f"CONFLICT {userid}: profile changed before the write, skipping")
        return "conflict"

    logger.info(f"GRANT    {userid}: {previous} -> {new_granted}")
    return "granted"


def grant_all_users(
    config: JobConfig,
    dry_run: bool = False,
    userid: str | None = None,
) -> dict[str, int]:
    """Apply the grant to every eligible user.

    Args:
        config: Job configuration
        dry_run: When True, report planned changes without writing to GCS
        userid: When set, only process this single user

    Returns:
        Counts keyed by outcome ("granted", "skipped", "conflict", "errors")
    """
    bucket = get_storage_client(config.project_id).bucket(config.bucket)

    if userid:
        user_ids = [userid]
        logger.info(f"Processing single user: {userid}")
    else:
        all_ids = list_user_ids(config=config)
        # Only real Auth0 users have a pipe in their ID (e.g. "auth0|…")
        user_ids = [uid for uid in all_ids if "|" in uid]
        logger.info(
            f"Found {len(user_ids)} Auth0 users "
            f"(skipped {len(all_ids) - len(user_ids)} non-Auth0 IDs)"
        )

    counts = {"granted": 0, "skipped": 0, "conflict": 0, "errors": 0}

    total = len(user_ids)
    for i, uid in enumerate(user_ids, 1):
        logger.debug(f"[{i}/{total}] {uid}")
        try:
            counts[grant_user(bucket, uid, dry_run)] += 1
        except Exception as e:
            logger.error(f"ERROR    {uid}: {e}")
            counts["errors"] += 1

    return counts


def main() -> int:
    """Parse arguments, run the grant and report a summary.

    Returns:
        Process exit code: 0 when nothing errored or conflicted, 1 otherwise
    """
    parser = argparse.ArgumentParser(
        description=(f"Grant {GRANT_AMOUNT} additional credits to users who have a credit override")
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without writing to GCS",
    )
    parser.add_argument(
        "--userid",
        type=str,
        default=None,
        help="Only process this specific user ID",
    )
    args = parser.parse_args()

    config = JobConfig.from_env()

    logger.info("=" * 60)
    logger.info("Credit Grant")
    logger.info(f"Bucket:      {config.bucket}")
    logger.info(f"Grant:       +{GRANT_AMOUNT}")
    logger.info(f"Grant ID:    {GRANT_ID}")
    logger.info(f"Dry run:     {args.dry_run}")
    logger.info(f"User filter: {args.userid or 'all users'}")
    logger.info("=" * 60)

    counts = grant_all_users(config, dry_run=args.dry_run, userid=args.userid)

    logger.info("=" * 60)
    logger.info("Summary:")
    logger.info(f"  Granted:   {counts['granted']}")
    logger.info(f"  Skipped:   {counts['skipped']}")
    logger.info(f"  Conflicts: {counts['conflict']}")
    logger.info(f"  Errors:    {counts['errors']}")
    if counts["conflict"]:
        logger.info("  Conflicting users were left unchanged; re-run to pick them up.")
    if args.dry_run:
        logger.info("  (dry run -- nothing was written)")
    logger.info("=" * 60)

    return 0 if counts["errors"] == 0 and counts["conflict"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
