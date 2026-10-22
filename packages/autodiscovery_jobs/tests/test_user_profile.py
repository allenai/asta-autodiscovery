"""Tests for user.json profile handling."""

import json

from autodiscovery_jobs.storage import get_store
from autodiscovery_jobs.user_profile import get_user_profile_path, update_user_profile

GRANTS = [
    {
        "id": "grant-1000-credits-v1",
        "amount": 1000,
        "previous_granted": 500,
        "granted_at": "2026-01-02T00:00:00+00:00",
    }
]


def test_update_keeps_grants(local_config):
    """A save through the class must not drop the record that blocks a double grant."""
    store = get_store(local_config)
    key = get_user_profile_path("u")
    store.write_text(
        key,
        json.dumps(
            {
                "granted_credits": 1500,
                "created_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-02T00:00:00+00:00",
                "grants": GRANTS,
            }
        ),
    )

    profile = update_user_profile("u", {"granted_credits": 2000}, local_config)

    written = json.loads(store.read_text(key))
    assert written["granted_credits"] == 2000
    assert written["grants"] == GRANTS
    assert profile.grants == GRANTS
