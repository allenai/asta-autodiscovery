"""The Asta user UUID, recorded next to the Auth0 subject runs are keyed on."""

import logging

from autodiscovery_jobs import JobConfig, get_user_profile, update_user_profile

logger = logging.getLogger(__name__)


def remember_asta_user_uuid(userid: str, asta_user_uuid: str | None, config: JobConfig) -> None:
    """Store the caller's Asta user UUID in their profile, if it is new.

    Best effort: a failure is logged and never fails the request.
    """
    if not asta_user_uuid:
        return
    try:
        profile = get_user_profile(userid, config)
        if profile and profile.asta_user_uuid == asta_user_uuid:
            return
        update_user_profile(userid, {"asta_user_uuid": asta_user_uuid}, config)
    except Exception as e:
        logger.warning(f"Could not record the Asta user UUID for {userid}: {e}")
