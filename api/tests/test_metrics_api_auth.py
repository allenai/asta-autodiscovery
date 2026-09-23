"""Permission gating on the metrics API endpoints."""

from unittest.mock import MagicMock, patch

import pytest

# Flask is an api/ dependency, not a workspace one, so `make test` skips this module.
flask = pytest.importorskip("flask")

from metrics import metrics_api  # noqa: E402
from utils.auth.models import AuthenticatedUser  # noqa: E402

ADMIN = "enroll:autodiscovery_admin"
METRICS_READ = "read:autodiscovery_metrics"


def _client_with(permissions):
    provider = MagicMock()
    provider.authenticate.return_value = AuthenticatedUser(
        sub="client@clients", permissions=permissions
    )
    app = flask.Flask(__name__)
    app.register_blueprint(metrics_api.create(), url_prefix="/api/metrics")
    return app.test_client(), patch(
        "utils.auth.decorators.get_auth_provider", return_value=provider
    )


@pytest.fixture(autouse=True)
def stub_aggregates():
    empty = MagicMock()
    empty.model_dump.return_value = {}
    with (
        patch.object(metrics_api, "compute_overview", return_value=empty),
        patch.object(metrics_api, "compute_aggregated_usage", return_value=empty),
        patch.object(metrics_api, "compute_users_list", return_value=[]),
        patch.object(metrics_api, "compute_user_detail", return_value=empty),
        patch.object(metrics_api, "compute_run_metrics", return_value={}),
        patch.object(metrics_api, "get_metrics_cache", return_value=MagicMock()),
    ):
        yield


AGGREGATE = [("GET", "/api/metrics/overview"), ("GET", "/api/metrics/usage/aggregated")]
ADMIN_ONLY = [
    ("GET", "/api/metrics/users"),
    ("GET", "/api/metrics/users/u1"),
    ("GET", "/api/metrics/runs/u1/r1"),
    ("GET", "/api/metrics/cache/status"),
    ("POST", "/api/metrics/cache/refresh"),
]


@pytest.mark.parametrize(("method", "path"), AGGREGATE)
def test_metrics_read_can_read_aggregates(method, path):
    client, auth = _client_with([METRICS_READ])
    with auth:
        assert client.open(path, method=method).status_code == 200


@pytest.mark.parametrize(("method", "path"), ADMIN_ONLY)
def test_metrics_read_cannot_reach_admin_only_endpoints(method, path):
    client, auth = _client_with([METRICS_READ])
    with auth:
        assert client.open(path, method=method).status_code == 403


@pytest.mark.parametrize(("method", "path"), AGGREGATE + ADMIN_ONLY)
def test_admin_keeps_access_to_every_endpoint(method, path):
    client, auth = _client_with([ADMIN])
    with auth:
        assert client.open(path, method=method).status_code != 403


@pytest.mark.parametrize(("method", "path"), AGGREGATE + ADMIN_ONLY)
def test_no_permission_is_denied(method, path):
    client, auth = _client_with([])
    with auth:
        assert client.open(path, method=method).status_code == 403
