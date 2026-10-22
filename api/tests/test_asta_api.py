"""The Asta handoff is self-contained and off unless its context service is configured."""

from unittest.mock import MagicMock, patch

import pytest

# Flask is an api/ dependency, not a workspace one: `make test` layers in
# api/requirements.txt, but a bare `uv run pytest` skips this module.
flask = pytest.importorskip("flask")

from asta import asta_api, context_client  # noqa: E402
from utils.auth.models import AuthenticatedUser  # noqa: E402

DIG_DEEPER = "/api/runs/u1/r1/experiments/node_0_0/dig-deeper"


@pytest.fixture
def client():
    provider = MagicMock()
    provider.authenticate.return_value = AuthenticatedUser(sub="u1", permissions=[])
    app = flask.Flask(__name__)
    app.register_blueprint(asta_api.create(), url_prefix="/api/runs")
    with patch("utils.auth.decorators.get_auth_provider", return_value=provider):
        yield app.test_client()


def test_dig_deeper_unconfigured_returns_503(client):
    with (
        patch.object(context_client, "ASTA_CONTEXT_SERVICE_URL", ""),
        patch.object(context_client, "ASTA_CONTEXT_SERVICE_API_KEY", ""),
        patch.object(asta_api, "JobManager") as job_manager,
    ):
        resp = client.post(DIG_DEEPER, json={"query": "why?"})

    assert resp.status_code == 503
    job_manager.assert_not_called()


def test_dig_deeper_rejects_other_users_run(client):
    with (
        patch.object(context_client, "ASTA_CONTEXT_SERVICE_URL", "https://context.example"),
        patch.object(context_client, "ASTA_CONTEXT_SERVICE_API_KEY", "key"),
    ):
        resp = client.post(
            "/api/runs/someone-else/r1/experiments/node_0_0/dig-deeper", json={"query": "why?"}
        )

    assert resp.status_code == 403
