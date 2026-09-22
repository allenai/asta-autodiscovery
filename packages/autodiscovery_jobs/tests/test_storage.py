"""Tests for the swappable object-store backends.

The contract tests run against :class:`FilesystemStore` on a real temp directory,
since that is the default backend and the one whose semantics have to be talked
into matching GCS. The GCS-specific tests below cover the translation layer
(which client call each operation makes) against a mocked client.
"""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from autodiscovery_jobs.config import JobConfig
from autodiscovery_jobs.exceptions import (
    ObjectNotFoundError,
    StorageBackendError,
    StorageError,
)
from autodiscovery_jobs.storage import (
    FilesystemStore,
    GcsStore,
    get_store,
    glob_to_regex,
)

# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def test_get_store_default_is_local(tmp_path):
    # storage_backend unset -> the JobConfig default (local) is used.
    store = get_store(JobConfig(storage_dir=str(tmp_path)))
    assert isinstance(store, FilesystemStore)


def test_get_store_gcs(mock_config):
    assert isinstance(get_store(mock_config), GcsStore)


def test_get_store_unknown():
    with pytest.raises(StorageBackendError):
        get_store(JobConfig(storage_backend="s3"))


def test_local_store_constructs_without_touching_disk(tmp_path):
    """Validation constructs a store just to inspect it; that must not mkdir."""
    root = tmp_path / "nested" / "data"
    store = FilesystemStore(root)
    assert not root.exists()
    assert list(store.list()) == []
    assert store.list_dirs("users/") == []

    store.write_text("users/u1/a.json", "{}")
    assert root.is_dir()


# ---------------------------------------------------------------------------
# Glob semantics (must match GCS matchGlob)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "pattern,key,matches",
    [
        ("users/*/jobs/*/run_details.json", "users/u1/jobs/j1/run_details.json", True),
        # `*` must not cross `/` -- fnmatch would get this wrong.
        ("users/*/jobs/*/run_details.json", "users/u1/x/jobs/j1/run_details.json", False),
        ("users/*/jobs/*/run_details.json", "users/u1/jobs/j1/output/run_details.json", False),
        ("users/**/run_details.json", "users/u1/jobs/j1/run_details.json", True),
        (
            "users/u1/jobs/j1/output/mcts_node_*_*.json",
            "users/u1/jobs/j1/output/mcts_node_1_2.json",
            True,
        ),
        (
            "users/u1/jobs/j1/output/mcts_node_*_*.json",
            "users/u1/jobs/j1/output/rich_outputs/mcts_node_1_2.json",
            False,
        ),
        # `?` is one non-slash character; regex metachars in the pattern are literal.
        ("a?c.json", "abc.json", True),
        ("a?c.json", "a/c.json", False),
        ("a.json", "aXjson", False),
    ],
)
def test_glob_to_regex(pattern, key, matches):
    assert bool(glob_to_regex(pattern).fullmatch(key)) is matches


# ---------------------------------------------------------------------------
# Store contract (FilesystemStore)
# ---------------------------------------------------------------------------


@pytest.fixture
def store(tmp_path):
    return FilesystemStore(tmp_path / "store")


def test_read_write_round_trip(store):
    store.write_text("users/u1/jobs/j1/metadata.json", '{"name": "run"}')
    assert store.read_text("users/u1/jobs/j1/metadata.json") == '{"name": "run"}'
    assert store.read_bytes("users/u1/jobs/j1/metadata.json") == b'{"name": "run"}'
    assert store.exists("users/u1/jobs/j1/metadata.json")


def test_read_missing_raises_object_not_found(store):
    with pytest.raises(ObjectNotFoundError):
        store.read_text("users/u1/nope.json")
    assert store.exists("users/u1/nope.json") is False


def test_write_replaces_existing(store):
    store.write_text("k", "first")
    store.write_text("k", "second")
    assert store.read_text("k") == "second"


def test_write_leaves_no_temp_files_behind(store, tmp_path):
    store.write_text("users/u1/a.json", "x")
    names = {p.name for p in (tmp_path / "store" / "users" / "u1").iterdir()}
    assert names == {"a.json"}


def test_list_hides_writes_in_flight(store, tmp_path):
    """A staged, not-yet-renamed write is not an object; GCS writes are atomic."""
    store.write_text("users/u1/a.json", "x")
    (tmp_path / "store" / "users" / "u1" / ".ad-staging.b.json.xyz").write_text("partial")

    assert {info.key for info in store.list("users/")} == {"users/u1/a.json"}


def test_concurrent_writes_to_one_key_do_not_corrupt_it(store):
    """Staging files are unique per writer, so same-key writers can't clobber each other."""
    from concurrent.futures import ThreadPoolExecutor

    payloads = [json.dumps({"writer": i, "pad": "x" * 5000}) for i in range(8)]
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda p: store.write_text("users/u1/run_details.json", p), payloads))

    # Whichever writer landed last, the object is exactly one of the payloads.
    assert store.read_text("users/u1/run_details.json") in payloads


def test_uri_is_absolute_file_url(store):
    assert store.uri("users/u1/a.json").startswith("file:///")
    assert store.uri("users/u1/a.json").endswith("/users/u1/a.json")


@pytest.mark.parametrize("key", ["../escape.json", "users/../../escape.json", "users/u1/"])
def test_keys_cannot_escape_the_root(store, key):
    with pytest.raises(StorageError):
        store.write_text(key, "x")


def test_delete_is_idempotent_and_prunes_empty_dirs(store, tmp_path):
    store.write_text("users/u1/jobs/j1/metadata.json", "{}")
    store.delete("users/u1/jobs/j1/metadata.json")
    store.delete("users/u1/jobs/j1/metadata.json")  # no error on a missing key

    # An emptied prefix must stop existing, like a GCS prefix with no objects.
    assert store.list_dirs("users/") == []
    assert not (tmp_path / "store" / "users").exists()


def test_delete_keeps_dirs_with_remaining_objects(store):
    store.write_text("users/u1/jobs/j1/metadata.json", "{}")
    store.write_text("users/u1/jobs/j1/data/x.csv", "a,b")
    store.delete("users/u1/jobs/j1/metadata.json")
    assert store.list_dirs("users/") == ["u1"]


def test_copy(store):
    store.write_text("users/u1/jobs/j1/data/x.csv", "a,b")
    store.copy("users/u1/jobs/j1/data/x.csv", "users/u2/jobs/j2/data/x.csv")
    assert store.read_text("users/u2/jobs/j2/data/x.csv") == "a,b"
    # Source survives.
    assert store.exists("users/u1/jobs/j1/data/x.csv")


def test_copy_missing_source(store):
    with pytest.raises(ObjectNotFoundError):
        store.copy("nope", "dest")


def test_upload_and_download_file(store, tmp_path):
    src = tmp_path / "in.csv"
    src.write_text("col1,col2\n1,2")
    store.upload_file("users/u1/jobs/j1/data/in.csv", src)

    dest = tmp_path / "out.csv"
    store.download_file("users/u1/jobs/j1/data/in.csv", dest)
    assert dest.read_text() == "col1,col2\n1,2"


def test_download_file_missing(store, tmp_path):
    with pytest.raises(ObjectNotFoundError):
        store.download_file("nope", tmp_path / "out.csv")


def test_write_stream(store, tmp_path):
    src = tmp_path / "in.bin"
    src.write_bytes(b"\x00\x01\x02")
    with open(src, "rb") as fh:
        store.write_stream("users/u1/jobs/j1/data/in.bin", fh)
    assert store.read_bytes("users/u1/jobs/j1/data/in.bin") == b"\x00\x01\x02"


def test_list_by_prefix(store):
    store.write_text("users/u1/jobs/j1/metadata.json", "{}")
    store.write_text("users/u1/jobs/j1/output/a.json", "{}")
    store.write_text("users/u2/jobs/j2/metadata.json", "{}")

    keys = {info.key for info in store.list("users/u1/")}
    assert keys == {"users/u1/jobs/j1/metadata.json", "users/u1/jobs/j1/output/a.json"}

    # A prefix that is not a directory boundary still filters correctly.
    assert {i.key for i in store.list("users/u1/jobs/j1/met")} == {
        "users/u1/jobs/j1/metadata.json"
    }


def test_list_empty_prefix_lists_everything(store):
    store.write_text("a.json", "{}")
    store.write_text("users/u1/b.json", "{}")
    assert {i.key for i in store.list()} == {"a.json", "users/u1/b.json"}


def test_list_missing_prefix_is_empty(store):
    assert list(store.list("users/nobody/")) == []


def test_list_respects_limit(store):
    for i in range(5):
        store.write_text(f"users/u1/jobs/j1/output/n{i}.json", "{}")
    assert len(list(store.list("users/u1/", limit=2))) == 2


def test_list_with_match_glob(store):
    store.write_text("users/u1/jobs/j1/run_details.json", "{}")
    store.write_text("users/u1/jobs/j1/metadata.json", "{}")
    store.write_text("users/u1/jobs/j1/output/run_details.json", "{}")  # wrong depth
    store.write_text("users/u2/jobs/j2/run_details.json", "{}")

    keys = {i.key for i in store.list("users/", match_glob="users/*/jobs/*/run_details.json")}
    assert keys == {"users/u1/jobs/j1/run_details.json", "users/u2/jobs/j2/run_details.json"}


def test_list_reports_size_and_created_at(store):
    store.write_text("k", "12345")
    (info,) = list(store.list("k"))
    assert info.size == 5
    assert datetime.now(UTC) - info.created_at < timedelta(minutes=5)


def test_list_dirs_ignores_empty_directories(store, tmp_path):
    store.write_text("users/u1/jobs/j1/metadata.json", "{}")
    # A directory with no objects beneath it does not exist as far as GCS is
    # concerned, so it must not show up here either.
    (tmp_path / "store" / "users" / "ghost").mkdir(parents=True)

    assert store.list_dirs("users/") == ["u1"]
    assert store.list_dirs("users/u1/jobs/") == ["j1"]
    assert store.list_dirs("users/nobody/jobs/") == []


def test_create_exclusive(store):
    assert store.create_exclusive("scripts/lock", b"first") is True
    assert store.create_exclusive("scripts/lock", b"second") is False
    assert store.read_bytes("scripts/lock") == b"first"  # loser did not clobber
    store.delete("scripts/lock")
    assert store.create_exclusive("scripts/lock", b"third") is True


def test_create_exclusive_is_atomic_under_contention(store):
    from concurrent.futures import ThreadPoolExecutor

    def try_create(i: int) -> bool:
        return store.create_exclusive("lock", str(i).encode())

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(try_create, range(8)))
    assert results.count(True) == 1


def test_local_import_from_gs_streams_the_blob(store, monkeypatch):
    from unittest.mock import Mock

    blob = Mock()
    blob.download_to_file.side_effect = lambda fh: fh.write(b"a,b\n1,2\n")
    monkeypatch.setattr("autodiscovery_jobs.storage.local.gs_blob", lambda uri: blob)

    store.import_from_gs("gs://datasets/iris.csv", "users/u1/jobs/j1/data/iris.csv")

    assert store.read_bytes("users/u1/jobs/j1/data/iris.csv") == b"a,b\n1,2\n"


def test_local_export_to_gs_uploads_the_file(store, monkeypatch):
    from unittest.mock import Mock

    blob = Mock()
    seen = {}
    monkeypatch.setattr(
        "autodiscovery_jobs.storage.local.gs_blob", lambda uri: seen.setdefault(uri, blob)
    )
    store.write_text("users/u1/jobs/j1/data/x.csv", "a,b")

    store.export_to_gs("users/u1/jobs/j1/data/x.csv", "gs://asta/owners/o/t/data/x.csv")

    assert list(seen) == ["gs://asta/owners/o/t/data/x.csv"]
    (path,), _ = blob.upload_from_filename.call_args
    assert path.endswith("/users/u1/jobs/j1/data/x.csv")


def test_local_export_to_gs_missing_source(store):
    with pytest.raises(ObjectNotFoundError):
        store.export_to_gs("nope", "gs://asta/x")


def test_local_store_has_no_signed_upload_url(store):
    assert store.signed_upload_url("users/u1/jobs/j1/data/x.csv", "text/csv", 3600) is None


# ---------------------------------------------------------------------------
# GcsStore translation layer
# ---------------------------------------------------------------------------


def test_gcs_store_root_uri(mock_config):
    assert GcsStore(bucket="test-bucket").root_uri == "gs://test-bucket"
    assert GcsStore(bucket="test-bucket").uri("a/b.json") == "gs://test-bucket/a/b.json"


def test_gcs_read_missing_maps_to_object_not_found(mock_storage_client):
    from google.cloud.exceptions import NotFound

    _, bucket = mock_storage_client
    bucket.blob.return_value.download_as_bytes.side_effect = NotFound("nope")

    with pytest.raises(ObjectNotFoundError):
        GcsStore(bucket="test-bucket").read_text("missing.json")


def test_gcs_delete_tolerates_missing(mock_storage_client):
    from google.cloud.exceptions import NotFound

    _, bucket = mock_storage_client
    bucket.blob.return_value.delete.side_effect = NotFound("nope")

    GcsStore(bucket="test-bucket").delete("missing.json")  # does not raise


def test_gcs_list_pushes_prefix_glob_and_limit_to_the_api(mock_storage_client):
    _, bucket = mock_storage_client
    bucket.list_blobs.return_value = iter([])

    list(GcsStore(bucket="test-bucket").list("users/", match_glob="users/*/x", limit=3))

    kwargs = bucket.list_blobs.call_args.kwargs
    assert kwargs["prefix"] == "users/"
    assert kwargs["match_glob"] == "users/*/x"
    assert kwargs["max_results"] == 3


def test_gcs_signed_upload_url(mock_storage_client):
    _, bucket = mock_storage_client
    bucket.blob.return_value.generate_signed_url.return_value = "https://signed"

    url = GcsStore(bucket="test-bucket").signed_upload_url("k", "text/csv", 60)

    assert url == "https://signed"
    kwargs = bucket.blob.return_value.generate_signed_url.call_args.kwargs
    assert kwargs["method"] == "PUT"
    assert kwargs["content_type"] == "text/csv"
    assert kwargs["expiration"] == timedelta(seconds=60)


def test_gcs_upload_file_passes_path(mock_storage_client, tmp_path):
    _, bucket = mock_storage_client
    src = tmp_path / "in.csv"
    src.write_text("a")

    GcsStore(bucket="test-bucket").upload_file("k", src)

    bucket.blob.return_value.upload_from_filename.assert_called_once_with(str(src))


def test_gcs_download_file_passes_path(mock_storage_client, tmp_path):
    _, bucket = mock_storage_client
    dest = Path(tmp_path / "out.csv")

    GcsStore(bucket="test-bucket").download_file("k", dest)

    bucket.blob.return_value.download_to_filename.assert_called_once_with(str(dest))


def test_gcs_create_exclusive_uses_generation_precondition(mock_storage_client):
    from google.api_core.exceptions import PreconditionFailed

    _, bucket = mock_storage_client
    blob = bucket.blob.return_value

    assert GcsStore(bucket="test-bucket").create_exclusive("lock", b"x") is True
    assert blob.upload_from_string.call_args.kwargs["if_generation_match"] == 0

    blob.upload_from_string.side_effect = PreconditionFailed("exists")
    assert GcsStore(bucket="test-bucket").create_exclusive("lock", b"x") is False


def test_gcs_import_and_export_rewrite_server_side(mock_storage_client):
    """Both directions go through the rewrite API, so no bytes reach this process."""
    client, bucket = mock_storage_client
    other_bucket = client.bucket.return_value  # the mock returns the same bucket for any name
    other_bucket.blob.return_value.rewrite.return_value = (None, 3, 3)

    GcsStore(bucket="test-bucket").import_from_gs("gs://datasets/iris.csv", "users/u1/x.csv")
    GcsStore(bucket="test-bucket").export_to_gs("users/u1/x.csv", "gs://asta/o/t/x.csv")

    assert other_bucket.blob.return_value.rewrite.call_count == 2


@pytest.mark.parametrize("bad", ["s3://b/k", "gs://bucket-only", "gs:///k", "bucket/key"])
def test_split_gs_uri_rejects_non_object_uris(bad):
    from autodiscovery_jobs.storage import split_gs_uri

    with pytest.raises(StorageError):
        split_gs_uri(bad)


def test_split_gs_uri():
    from autodiscovery_jobs.storage import split_gs_uri

    assert split_gs_uri("gs://b/path/to/obj.csv") == ("b", "path/to/obj.csv")
