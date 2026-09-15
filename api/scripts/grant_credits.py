#!/usr/bin/env python3
"""Grant a one-time credit top-up to every existing user.

Adds ``GRANT_CREDITS`` to each existing user's ``granted_credits`` override in
GCS (``users/{userid}/user.json``). Running experiments became cheaper, so the
saving is passed back to users as additional credits.

Why this is a grant and not a reset
-----------------------------------
There is no stored balance. Only ``granted_credits`` is persisted, and the
balance is derived at read time as ``available = granted - consumed - pending``.
Adding to ``granted`` therefore needs one read and one write per user, and no
user's balance can decrease. Resetting everyone to a fixed available balance
would instead require aggregating every job the user has ever run.

The pinned old default
----------------------
``DEFAULT_CREDITS_GRANTED`` in ``utils.credits`` is the balance a user gets
when they have no profile at all, and it has already been raised to the new
value. This script must therefore *not* import it: a user with no profile has
to be credited against the default they had **before** that change, or they
would be counted from the new default and granted twice. ``OLD_DEFAULT_CREDITS``
below pins that previous value, which also makes this script independent of
whether the default change has shipped yet.

Existing users vs. new signups
------------------------------
Raising the default already moved every profile-less user to the new balance,
and that fallback is evaluated lazily on each read. A user who signed up after
that shipped is therefore already where they should be and must be skipped;
only users who predate it are owed the top-up. Users with a profile are
identified by ``created_at``; users without one are dated by their oldest
object in GCS. ``--cutoff`` sets the boundary.

Re-running
----------
``granted = granted + N`` compounds, so this script is not naturally idempotent.
Each grant writes a marker to ``migrations/{MIGRATION_ID}/{userid}.json``
recording the before and after values. On a later run a user whose profile
still matches the recorded "after" is skipped; one that still matches the
recorded "before" is treated as an interrupted write and retried; anything else
is left alone and reported for review. A crash partway through is therefore
safe to resume by simply running the script again.

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
from pathlib import Path

# Add api/ to path so we can import from utils
sys.path.insert(0, str(Path(__file__).parent.parent))

from autodiscovery_jobs import JobConfig
from autodiscovery_jobs.client import get_storage_client
from autodiscovery_jobs.gcs import list_user_ids
from autodiscovery_jobs.user_profile import get_user_profile, update_user_profile

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Credits added to every existing user's grant.
GRANT_CREDITS = 1000

# The value DEFAULT_CREDITS_GRANTED held *before* it was raised. Deliberately a
# literal rather than an import -- see the module docstring.
OLD_DEFAULT_CREDITS = 500

# Identifies this migration's markers in GCS. Bump it for a future grant so the
# new run does not read this one's markers.
MIGRATION_ID = "grant-1000-credits-v1"

# When the raised default shipped. Users first seen at or after this already
# receive the new default and are not owed a top-up.
DEFAULT_CUTOFF = "2026-09-15T23:01:52+00:00"


def get_marker_path(userid: str) -> str:
    """Get the GCS blob path for this migration's marker for a user.

    Args:
        userid: User identifier

    Returns:
        Blob path for the marker
    """
    return f"migrations/{MIGRATION_ID}/{userid}.json"


def read_marker(userid: str, config: JobConfig) -> dict | None:
    """Read this migration's marker for a user.

    Args:
        userid: User identifier
        config: Job configuration

    Returns:
        The marker dict, or None if the user has not been granted yet
    """
    client = get_storage_client(config.project_id)
    blob = client.bucket(config.bucket).blob(get_marker_path(userid))
    try:
        return json.loads(blob.download_as_text(retry=None))
    except Exception:
        return None


def write_marker(userid: str, previous: int, new: int, config: JobConfig) -> None:
    """Record that a user has been granted, and what their values were.

    Args:
        userid: User identifier
        previous: granted_credits before the grant
        new: granted_credits after the grant
        config: Job configuration
    """
    client = get_storage_client(config.project_id)
    blob = client.bucket(config.bucket).blob(get_marker_path(userid))
    blob.upload_from_string(
        json.dumps(
            {
                "migration": MIGRATION_ID,
                "userid": userid,
                "previous_granted": previous,
                "new_granted": new,
                "granted_at": datetime.now(UTC).isoformat(),
            },
            indent=2,
        )
    )


def _parse_created_at(created_at: str) -> datetime | None:
    """Parse a profile's created_at into an aware datetime.

    Args:
        created_at: ISO timestamp, possibly empty on older profiles

    Returns:
        Timezone-aware datetime, or None if absent or unparseable
    """
    if not created_at:
        return None
    try:
        parsed = datetime.fromisoformat(created_at)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def get_first_seen(userid: str, config: JobConfig) -> datetime | None:
    """Get the creation time of a user's oldest object in GCS.

    Used to date users who have no profile, since they have no ``created_at``.
    A user only appears in the bucket once they have run something, so this is
    a lower bound on when they started using the product.

    Args:
        userid: User identifier
        config: Job configuration

    Returns:
        Creation time of the oldest object, or None if the user has none
    """
    client = get_storage_client(config.project_id)
    times = [
        blob.time_created
        for blob in client.list_blobs(config.bucket, prefix=f"users/{userid}/")
        if blob.time_created is not None
    ]
    return min(times) if times else None


def resolve_base_credits(
    userid: str, cutoff: datetime, config: JobConfig
) -> tuple[int | None, str]:
    """Determine the grant's starting point for a user.

    Args:
        userid: User identifier
        cutoff: Users first seen at or after this are new and get nothing
        config: Job configuration

    Returns:
        Tuple of (base credits, reason). Base is None when the user should be
        skipped, and reason explains the decision either way.
    """
    profile = get_user_profile(userid, config)

    if profile is not None and profile.granted_credits is not None:
        return profile.granted_credits, "has profile override"

    # No usable override: the user is on the default. Only top them up if they
    # predate the raised default, otherwise they already have it. Prefer the
    # profile's own timestamp when there is one; fall back to listing the
    # user's objects, which costs a request per user.
    first_seen = _parse_created_at(profile.created_at) if profile is not None else None
    if first_seen is None:
        first_seen = get_first_seen(userid, config)

    if first_seen is None:
        return None, "cannot date user (no profile timestamp, no objects)"
    if first_seen >= cutoff:
        return None, f"first seen {first_seen.date()}, at/after cutoff (new user)"

    return OLD_DEFAULT_CREDITS, f"no override, first seen {first_seen.date()}"


def grant_user(
    userid: str,
    cutoff: datetime,
    config: JobConfig,
    dry_run: bool,
) -> str:
    """Grant one user their top-up, if they are owed one.

    Args:
        userid: User identifier
        cutoff: Users first seen at or after this are new and get nothing
        config: Job configuration
        dry_run: When True, log the planned change without writing

    Returns:
        One of "granted", "skipped" or "needs_review"
    """
    base, reason = resolve_base_credits(userid, cutoff, config)
    if base is None:
        logger.info(f"SKIP    {userid}: {reason}")
        return "skipped"

    new_granted = base + GRANT_CREDITS

    # Already processed? Compare the profile against what we recorded to tell a
    # completed grant from one that was interrupted mid-write.
    marker = read_marker(userid, config)
    if marker is not None:
        if base == marker.get("new_granted"):
            logger.info(f"SKIP    {userid}: already granted ({base})")
            return "skipped"
        if base != marker.get("previous_granted"):
            logger.warning(
                f"REVIEW  {userid}: granted={base} matches neither the recorded "
                f"before ({marker.get('previous_granted')}) nor after "
                f"({marker.get('new_granted')}); changed since the grant, leaving alone"
            )
            return "needs_review"
        logger.warning(f"RETRY   {userid}: previous grant was interrupted, re-applying")
        new_granted = marker["new_granted"]

    if dry_run:
        logger.info(f"DRY-RUN {userid}: {base} -> {new_granted} ({reason})")
        return "granted"

    # Marker first, profile second. A crash between the two then leaves a marker
    # whose "before" still matches the profile, which the next run recognises as
    # an interrupted write and retries. Writing the profile first would instead
    # leave a granted user with no marker, indistinguishable from one who has
    # not been granted yet -- and the next run would grant them a second time.
    write_marker(userid, previous=base, new=new_granted, config=config)
    update_user_profile(userid, {"granted_credits": new_granted}, config)
    logger.info(f"GRANT   {userid}: {base} -> {new_granted} ({reason})")
    return "granted"


def grant_credits(
    config: JobConfig,
    cutoff: datetime,
    dry_run: bool = False,
    userid: str | None = None,
) -> dict[str, int]:
    """Grant the top-up to every existing user.

    Args:
        config: Job configuration
        cutoff: Users first seen at or after this are new and get nothing
        dry_run: When True, log planned changes without writing to GCS
        userid: When set, only process this single user

    Returns:
        Counts keyed by outcome ("granted", "skipped", "needs_review", "errors")
    """
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

    counts = {"granted": 0, "skipped": 0, "needs_review": 0, "errors": 0}

    total = len(user_ids)
    for i, uid in enumerate(user_ids, 1):
        logger.debug(f"[{i}/{total}] {uid}")
        try:
            counts[grant_user(uid, cutoff, config, dry_run)] += 1
        except Exception as e:
            logger.error(f"ERROR   {uid}: {e}")
            counts["errors"] += 1

    return counts


def main() -> int:
    """Parse arguments, run the grant and report a summary.

    Returns:
        Process exit code: 0 when no user errored, 1 otherwise
    """
    parser = argparse.ArgumentParser(
        description=f"Grant {GRANT_CREDITS} additional credits to every existing user"
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
    parser.add_argument(
        "--cutoff",
        type=str,
        default=DEFAULT_CUTOFF,
        help=(
            "ISO timestamp when the raised default shipped. Users without a "
            f"profile first seen at or after it are new and are skipped "
            f"(default: {DEFAULT_CUTOFF})"
        ),
    )
    args = parser.parse_args()

    cutoff = datetime.fromisoformat(args.cutoff)
    if cutoff.tzinfo is None:
        cutoff = cutoff.replace(tzinfo=UTC)

    config = JobConfig.from_env()

    logger.info("=" * 60)
    logger.info("Credit Grant")
    logger.info(f"Bucket:        {config.bucket}")
    logger.info(f"Grant:         +{GRANT_CREDITS}")
    logger.info(f"Old default:   {OLD_DEFAULT_CREDITS} (pinned)")
    logger.info(f"New-user cutoff: {cutoff.isoformat()}")
    logger.info(f"Migration:     {MIGRATION_ID}")
    logger.info(f"Dry run:       {args.dry_run}")
    logger.info(f"User filter:   {args.userid or 'all users'}")
    logger.info("=" * 60)

    counts = grant_credits(
        config,
        cutoff=cutoff,
        dry_run=args.dry_run,
        userid=args.userid,
    )

    logger.info("=" * 60)
    logger.info("Summary:")
    logger.info(f"  Granted:      {counts['granted']}")
    logger.info(f"  Skipped:      {counts['skipped']}")
    logger.info(f"  Needs review: {counts['needs_review']}")
    logger.info(f"  Errors:       {counts['errors']}")
    if args.dry_run:
        logger.info("  (dry run -- nothing was written)")
    logger.info("=" * 60)

    return 0 if counts["errors"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
