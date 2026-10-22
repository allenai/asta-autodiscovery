"""Dataset names are shared by uploads and imports without normalization."""

from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

flask = pytest.importorskip("flask")

from runs import runs_api  # noqa: E402
from runs.datasets import is_valid_dataset_filename  # noqa: E402
from utils.auth.models import AuthenticatedUser  # noqa: E402


@pytest.mark.parametrize("filename", [".data.csv", "résultats.csv", "input with spaces.parquet"])
def test_filename_policy_preserves_valid_names(filename):
    assert is_valid_dataset_filename(filename)


@pytest.mark.parametrize("filename", ["bad\x00.csv", "bad\n.csv", "bad\x7f.csv"])
def test_upload_rejects_control_characters_in_dataset_names(filename):
    provider = MagicMock()
    provider.authenticate.return_value = AuthenticatedUser(sub="u1", permissions=[])
    app = flask.Flask(__name__)
    app.register_blueprint(runs_api.create(), url_prefix="/api/runs")
    with (
        patch("utils.auth.decorators.get_auth_provider", return_value=provider),
        patch.object(runs_api, "JobManager") as manager,
    ):
        response = app.test_client().post(
            "/api/runs/upload-dataset",
            data={"runid": "r1", "file": (BytesIO(b"x"), filename)},
        )
    assert response.status_code == 400
    manager.assert_not_called()
