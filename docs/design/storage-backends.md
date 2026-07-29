# Swappable Persistence Backends — Design

Status: **Implemented** · Branch: `swappable-persistence-backends` · Part of
[#34](https://github.com/allenai/asta-autodiscovery/issues/34)

> See [As built](#as-built) at the end for the concrete file layout and operator notes.

## Goal

Make AutoDiscovery's persistence pluggable, with two interchangeable backends selected by
configuration:

1. **`local`** (new default) — a directory on the host, bind-mounted into the containers.
   No cloud account, bucket, or credentials; `docker compose up` persists real run data
   out of the box.
2. **`gcs`** — the existing Google Cloud Storage bucket, unchanged behavior when selected.

This follows the pattern already established for
[auth providers](auth-providers.md) (`AUTH_PROVIDER`), job execution (`JOB_BACKEND`), and
code execution (`CODE_EXECUTION_BACKEND`).

---

## Current state (what we're abstracting)

Everything the app persists lived directly on `google-cloud-storage`:

- `autodiscovery_jobs/gcs.py` (~1100 lines) — job directories, dataset upload/expiry,
  metadata, results, experiment nodes, presigned upload URLs.
- `autodiscovery_jobs/{run_details,user_profile,email_state}.py` — small JSON documents,
  each building its own `bucket.blob(...)`.
- `api/metrics/aggregator.py` — threads a `storage.Bucket` through its job scan and
  persists its cache snapshot as a blob.
- `scripts/send_completion_emails.py` — a cross-process lock built on
  `upload_from_string(..., if_generation_match=0)`.
- `api/runs/runs_api.py` — presigned upload URLs, plus a `gs://`→bucket rewrite for
  Ai2-preloaded datasets.

The **job side is already storage-agnostic**: the AD job reads `metadata.json` and writes
`output/` as ordinary files under `/mnt/gcs`, which Cloud Run supplies as a GCS FUSE
volume and the docker job backend supplies via gcsfuse. Only the webstack talked to GCS
directly.

## The abstraction

One interface — a flat, keyed blob namespace:

```
ObjectStore
  root_uri / uri(key)                     display + logging
  read_bytes / read_text / exists         reads
  download_file(key, local_path)
  write_bytes / write_text / write_stream  writes
  upload_file(key, local_path)
  create_exclusive(key, data) -> bool     atomic create (mutual exclusion)
  delete(key)                             idempotent
  copy(source_key, dest_key)               within the store
  list(prefix, *, match_glob, limit)      -> Iterator[ObjectInfo]
  list_dirs(prefix)                       -> immediate child names
  signed_upload_url(...) -> str | None    None when unsupported
```

Keys are the existing GCS blob names, unchanged, so **the on-disk layout is the same
layout as the bucket** and one can be copied to the other with `gsutil rsync`.

### Making a filesystem behave like an object store

Three GCS behaviors the rest of the code already depended on had to be reproduced:

| GCS behavior | `LocalStore` implementation |
| --- | --- |
| `matchGlob`, where `*` does not cross `/` | `glob_to_regex()` compiles the glob to a regex (`*` → `[^/]*`, `**` → `.*`). Deliberately **not** `fnmatch`, whose `*` crosses `/` and would make `users/*/jobs/*/x.json` match arbitrarily deep keys. |
| No directories — a prefix stops existing once its last object is deleted | Deletes prune the directories they empty; `list_dirs` skips directories with no objects beneath them. Otherwise deleted users/runs would linger in listings. |
| Object writes are atomic; a reader never sees a partial object | Writes stage into a uniquely-named `.ad-staging.*` file in the destination directory and `os.replace` into place; listings skip staging files. This matters because the API polls run files *while the job container writes them*. |
| `if_generation_match=0` for atomic create | `os.open(..., O_CREAT \| O_EXCL)`. |

`created_at` comes from `st_mtime` (POSIX has no portable creation time); these objects are
written once, so it is the same instant in practice. Dataset expiry depends on it.

Keys can originate in user-supplied filenames, so `LocalStore` rejects any key that
resolves outside its root rather than normalizing it away.

### Direct browser uploads

GCS lets the browser `PUT` a dataset straight to a presigned URL, bypassing the API. A
filesystem has no equivalent capability URL, so `signed_upload_url()` returns `None` and
the API falls back to receiving the upload itself:

```
POST /api/runs/<runid>/generate-upload-url
  → { upload_url: "https://storage.googleapis.com/…", same_origin: false }   # gcs
  → { upload_url: "/api/runs/<runid>/datasets/<file>", same_origin: true }   # local
```

`same_origin` tells the client to attach its `Authorization` header to the upload — which
it must **not** do for a third-party storage host, since that would leak the bearer token.
The new endpoint streams `request.stream` into the store, so large uploads are not
buffered in memory. This is why the proxy's `client_max_body_size` for `/api` is
load-bearing again.

### Combinations that cannot work

Two other backends need run data to be reachable from outside the API process, and only
`gcs` can offer that:

| | `STORAGE_BACKEND=local` | `STORAGE_BACKEND=gcs` |
| --- | --- | --- |
| `JOB_BACKEND=docker` | ✅ job container bind-mounts the run's host directory | ✅ job container gcsfuse-mounts the run's prefix |
| `JOB_BACKEND=gcp` | ❌ Cloud Run cannot mount a host directory | ✅ Cloud Run mounts the bucket |
| `CODE_EXECUTION_BACKEND=process`/`local` | ✅ reads the job's own mount | ✅ |
| `CODE_EXECUTION_BACKEND=modal` | ❌ the sandbox mounts the dataset from `gs://` | ✅ |

Both ❌ rows **raise at startup** rather than warning. The likeliest way to hit the first
is a GCS deployment that never sets `STORAGE_BACKEND`: silently defaulting to local disk
there would look like every run and dataset had vanished, which is worse than failing to
boot. (Contrast `_warn_if_unsafe_code_execution`, which only warns — that configuration
*works*, it is just unsafe.)

### Scoping the job container's mount

The docker job backend scopes the job container's data mount to that run's own prefix, so
a container never sees another user's data even when untrusted generated code runs
in-process. Both storage backends keep that property, and both mount at the same
in-container path so the job's CLI arguments are byte-identical either way:

```
local:  bind  $STORAGE_HOST_DIR/users/<uid>/jobs/<jid>  →  /mnt/gcs/users/<uid>/jobs/<jid>
gcs:    gcsfuse --only-dir users/<uid>/jobs/<jid>        →  /mnt/gcs/users/<uid>/jobs/<jid>
```

The bind-mount path needs no FUSE device, no `SYS_ADMIN`, and no credentials, so those are
granted only in the `gcs` case.

`STORAGE_HOST_DIR` exists for the same reason as `GCP_KEY_HOST_PATH`: in
docker-out-of-docker, the API's own container path is not a valid bind source for the host
daemon, so the host path is passed out-of-band by compose.

---

## As built

### File layout

```
packages/autodiscovery_jobs/src/autodiscovery_jobs/
  storage/
    __init__.py        # get_store(config) factory, STORAGE_BACKENDS
    base.py            # ObjectStore ABC, ObjectInfo, glob_to_regex()
    gcs.py             # GcsStore (google-cloud-storage)
    local.py           # LocalStore (filesystem, atomic writes, prefix pruning)
  persistence.py       # functional job-data API (was gcs.py), owns the key layout
  gcs.py               # backward-compat shim re-exporting persistence
  client.py            # cached storage.Client, now only used by GcsStore
```

`autodiscovery_jobs.gcs` remains importable for external consumers of the published
package, mirroring the `cloudrun.py` shim from the job-backend change. In-repo imports all
point at `persistence`; note that patching a name on the shim does **not** affect callers
that imported it from `persistence`, so tests must target the real module.

### Configuration

| Variable | Default | Notes |
| --- | --- | --- |
| `STORAGE_BACKEND` | `local` | `local` or `gcs`. |
| `STORAGE_DIR` | `/mnt/data` | Root of the local store, as seen by the process. Compose mounts the host dir here. |
| `STORAGE_HOST_DIR` | *(unset)* | Host path of that directory, for the docker job backend's bind mounts. Compose sets it; unset means this process is not containerized and `STORAGE_DIR` is already a host path. |

`.env` sets `STORAGE_DIR` to a **host** path (defaulting to `$PWD/data`); compose mounts it
at `/mnt/data` and forwards the host path as `STORAGE_HOST_DIR`. Use an absolute path — the
host daemon has no working directory to resolve a relative bind source against, and the
backend raises a clear error if it is relative.

> **Deployments that keep data in GCS must now set `STORAGE_BACKEND=gcs` explicitly.**
> Together with `JOB_BACKEND=gcp` that is enforced, not silent.

### Deltas from the proposal

- `GCSError` is now an alias of the new `StorageError` rather than being renamed, so
  existing `except GCSError` sites and imports keep working.
- The `generate-upload-url` response keeps its `gcs_path` field name (now carrying a
  `file://` URI under the local backend) rather than breaking the wire format; `same_origin`
  was added alongside it.
- The in-container mount point stays `/mnt/gcs` even for the local backend. The deployed
  Cloud Run job definition pins that path (`--add-volume-mount` in
  `rebuild_and_deploy.sh`), so renaming it would couple this change to a Cloud Run
  redeploy. It is now the single constant `backends.base.JOB_MOUNT_ROOT`, so renaming it
  later is a one-line change plus a redeploy.
- The Asta workspace handoff (`asta_gcs.py`) still writes to a GCS bucket — that bucket is
  Asta's, not ours — but now reads its source through the store, doing a server-side copy
  only when the source is also GCS.
