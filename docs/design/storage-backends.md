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
`output/` as ordinary files under a mount point, which Cloud Run supplies as a GCS volume
(and which the docker job backend, at the time, supplied via gcsfuse). Only the webstack
talked to GCS directly.

## The abstraction

One interface — a flat, keyed blob namespace:

```
ObjectStore
  root_uri / uri(key)                     display + logging
  read_bytes / read_text / exists         reads
  download_file(key, local_path)
  write_bytes / write_text / write_stream  writes
  upload_file(key, local_path)
  delete(key)                             idempotent
  copy(source_key, dest_key)               within the store
  create_exclusive(key, data) -> bool     atomic create-if-absent (locks)
  list(prefix, *, match_glob, limit)      -> Iterator[ObjectInfo]
  list_dirs(prefix)                       -> immediate child names
  import_from_gs(uri, key)                 transfers to/from GCS, which two
  export_to_gs(key, uri)                   neighbouring systems always are
  signed_upload_url(...) -> str | None    None when unsupported
```

Keys are the existing GCS blob names, unchanged, so **the on-disk layout is the same
layout as the bucket** and one can be copied to the other with `gsutil rsync`.

`read_text`, `write_text`, `uri`, and `signed_upload_url` (default `None`) are derived;
everything else each backend implements. Keys are built in one place,
`autodiscovery_jobs/keys.py`, so the layout is spelled out once.

### Making a filesystem behave like an object store

Four GCS behaviors the rest of the code already depended on had to be reproduced:

| GCS behavior | `FilesystemStore` implementation |
| --- | --- |
| No directories — a prefix stops existing once its last object is deleted | Deletes prune the directories they empty; `list_dirs` skips directories with no objects beneath them. Otherwise deleted users/runs would linger in listings. |
| `matchGlob` on listings, where `*` does not cross `/` | `glob_to_regex()` (`*` → `[^/]*`, `**` → `.*`), applied while walking. Deliberately **not** `fnmatch`, whose `*` crosses `/` and would make `users/*/jobs/*/x.json` match arbitrarily deep keys. On GCS the glob is pushed to the API, so the metrics scan and the shared-run owner lookup return one object per run instead of listing the whole bucket. |
| Object writes are atomic; a reader never sees a partial object | Writes stage into a uniquely-named `.ad-staging.*` file in the destination directory and `os.replace` into place; listings skip staging files. This matters because the API polls run files *while the job container writes them*. |
| Create-if-absent via `if_generation_match=0` | `os.open(..., O_CREAT \| O_EXCL)`, bypassing the staging path (a rename would clobber). Backs the completion-email job's `--acquire-lock`, which therefore works on either backend. |

`created_at` comes from `st_mtime` (POSIX has no portable creation time); these objects are
written once, so it is the same instant in practice. Dataset expiry depends on it.

Two systems next to AutoDiscovery are GCS whatever the run store is: the Ai2-curated
preloaded datasets a run can start from, and the Asta workspace bucket a run's dataset is
handed to. Rather than have those callers `isinstance`-check the store and reach for the
GCS client themselves, the interface carries `import_from_gs` / `export_to_gs`. `GcsStore`
does both as a server-side rewrite; `FilesystemStore` streams through the process. The
methods are named for GCS honestly, because that is what the other side is.

Keys can originate in user-supplied filenames, so `FilesystemStore` rejects any key that
resolves outside its root rather than normalizing it away.

### Direct browser uploads

GCS lets the browser `PUT` a dataset straight to a presigned URL, bypassing the API. A
filesystem has no equivalent capability URL, so `signed_upload_url()` returns `None` and the
upload has to come through the API instead. Those two requests differ in more than their
URL — method, body encoding, and whether credentials are attached — so
`generate-upload-url` returns the **whole request** rather than a URL the client has to
interpret:

```
POST /api/runs/<runid>/generate-upload-url

  { upload_url: "https://storage.googleapis.com/…?X-Goog-Signature=…",   # gcs
    upload_method: "PUT", upload_fields: null }

  { upload_url: "/api/runs/upload-dataset",                              # local
    upload_method: "POST", upload_fields: { runid: "…" } }
```

The client performs what it is handed: `fields` present means multipart with the file
appended, absent means the raw body. So it holds no per-backend knowledge and no endpoint
path, and there is no sentinel value to interpret. The second case targets the **existing**
authenticated `POST /api/runs/upload-dataset`, so no upload route was added.

This shape is also what a presigned-POST backend needs — S3's `generate_presigned_post`
returns exactly a url plus form fields — so a future store fits without changing the client.

The one thing the client decides for itself is credentials: it attaches its bearer token
only when the URL resolves to its own origin. That rule stays client-side deliberately. An
earlier draft had the server send a `same_origin: true` flag, which amounts to the server
telling the client where its bearer token may be sent — if that value were ever wrong, the
token would go to a third party. All of this lives in one module
(`ui/src/app/api/datasetUpload.ts`).

Clients should still call `generate-upload-url` first in both cases, because that is where
the run is checked to exist and the requested size is screened.

Two things were fixed on `upload-dataset` when it became the default backend's real upload
path: it enforced **no size limit at all** (the check in `generate-upload-url` is on a
client-asserted size, so it cannot be the only one), and it buffered the whole file to a
temp file before storing it — a second full copy of a multi-GB upload on the API
container's disk. It now streams `file.stream` into the store. This is also why the proxy's
`client_max_body_size` for `/api` is load-bearing again.

### The one backend check

Exactly one place outside the store needs to know which backend is active: the startup
validator (can Cloud Run, Modal, or a local job container reach this data?). It calls
`get_store(config)` and `isinstance`s the result against `GcsStore`. Constructing a store is
side-effect-free — `FilesystemStore` creates its root on first write, not in `__init__` —
so validating configuration never touches the filesystem. Everything else talks to the
store through its interface.

### Combinations that cannot work

Each job backend is tied to one store, and Modal needs `gs://`:

| | `STORAGE_BACKEND=local` | `STORAGE_BACKEND=gcs` |
| --- | --- | --- |
| `JOB_BACKEND=docker` | ✅ job container bind-mounts the run's host directory | ❌ a bucket has no host directory to bind |
| `JOB_BACKEND=gcp` | ❌ Cloud Run cannot mount a host directory | ✅ Cloud Run mounts the bucket |
| `CODE_EXECUTION_BACKEND=process`/`local` | ✅ reads the job's own mount | ✅ |
| `CODE_EXECUTION_BACKEND=modal` | ❌ the sandbox mounts the dataset from `gs://` | ✅ |

Every ❌ cell **raises at startup** rather than warning. The likeliest way to hit the first
is a GCS deployment that never sets `STORAGE_BACKEND`: silently defaulting to local disk
there would look like every run and dataset had vanished, which is worse than failing to
boot. (Contrast `_warn_if_unsafe_code_execution`, which only warns — that configuration
*works*, it is just unsafe.)

### Scoping the job container's mount

The docker job backend scopes the job container's data mount to that run's own prefix, so
a container never sees another user's data even when untrusted generated code runs
in-process. It mounts at the same in-container path Cloud Run uses, so the job's CLI
arguments are byte-identical across job backends:

```
bind  $STORAGE_HOST_DIR/users/<uid>/jobs/<jid>  →  /mnt/data/users/<uid>/jobs/<jid>
```

A bind mount needs no FUSE device, no extra capabilities, and no credentials. The only
credential a docker job container receives is the GCP key, bind-mounted when
`GCP_KEY_HOST_PATH` is set, for Google-hosted models.

`STORAGE_HOST_DIR` exists for the same reason as `GCP_KEY_HOST_PATH`: in
docker-out-of-docker, the API's own container path is not a valid bind source for the host
daemon, so the host path is passed out-of-band by compose.

Before this change the docker backend gcsfuse-mounted the bucket into the job container,
which needed gcsfuse in the job image, `/dev/fuse`, `CAP_SYS_ADMIN`, and an unconfined
AppArmor profile. That was the only way to run jobs locally when GCS was the only store. It
is gone: `docker` + `gcs` is rejected at startup, and the job image no longer installs
gcsfuse or carries an entrypoint wrapper.

---

## As built

### File layout

```
packages/autodiscovery_jobs/src/autodiscovery_jobs/
  storage/
    __init__.py        # get_store(config) factory, STORAGE_BACKENDS
    base.py            # ObjectStore ABC, ObjectInfo, glob_to_regex
    gcs.py             # GcsStore (google-cloud-storage)
    local.py           # FilesystemStore (atomic writes, prefix pruning)
  keys.py              # the key layout, built in one place
  persistence.py       # functional job-data API (was gcs.py)
  client.py            # cached storage.Client, now only used by GcsStore
```

`autodiscovery_jobs.gcs` is gone; imports point at `persistence`.

### Using other storage

`FilesystemStore` is a POSIX-tree implementation, not a "local disk only" one, so anything
the operator can mount works with no code: NFS, s3fs, Azure Files, JuiceFS, a SAN. Point
`STORAGE_DIR` at the mount and the whole application runs, job containers included.

What a mount gives up, all of it a consequence of a filesystem not being an object store:

| | Cost on a mount |
| --- | --- |
| Presigned uploads | Gone. Every dataset upload streams through the API instead of going browser→storage. |
| Prefix and glob listings | A directory walk rather than one paginated request. |
| `copy` | No server-side copy, so forking a run reads the dataset and writes it back through the API. |
| Atomic replace | `os.replace` is atomic on a real filesystem; over a FUSE object-store adapter a rename is typically copy+delete, so a reader can observe a partial object. |

For a single-operator or on-prem deployment none of those usually bite. If they do, a native
backend is a subclass of `ObjectStore` plus a branch in `get_store()`, and the validator
above is where it would need to say how job containers reach its data. There is no
registry or plugin mechanism, on purpose: one can be added when a third backend exists to
justify its shape.

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

- `LocalStore` was renamed `FilesystemStore`, because the story above is "any POSIX tree you
  can mount", not "local dev only". The configured name stays `local`, which remains
  accurate about the constraint that matters (the data is only reachable from this host,
  which is what rules out Cloud Run and Modal).
- An intermediate draft replaced the backend-name checks with declared capabilities on the
  store class (`job_data_mount`, `gs_addressable`) and a name→class registry, and dropped
  `match_glob` from the interface. Both were reverted in review: the capabilities were
  machinery for a third backend that does not exist, and removing `match_glob` turned the
  shared-run owner lookup and the metrics discovery into full-bucket listings on GCS.
- `create_exclusive` was dropped from an intermediate draft, which kept the completion-email
  lock on the GCS client directly and refused to run on other backends. Review put it back
  on the interface, implemented per backend, so the lock works everywhere.
- `import_from_gs` / `export_to_gs` were added in review in place of two `isinstance`
  checks (the preloaded-dataset sync and the Asta handoff) that reached for the GCS client
  when the store happened to be GCS.
- The `docker` + `gcs` pairing was dropped. The intermediate draft kept the docker backend's
  gcsfuse path alongside the new bind mount so local job containers could still run against
  the bucket, but that exercised a mount mechanism production never uses (Cloud Run supplies
  a platform volume), at the cost of gcsfuse in the job image and `SYS_ADMIN` on the
  container. Each job backend now maps to exactly one store.
- `GCSError` is renamed `StorageError` outright; an intermediate draft kept an alias, which
  review dropped along with the `autodiscovery_jobs.gcs` re-export shim.
- The `generate-upload-url` response field `gcs_path` is renamed `storage_path` (it carries
  a `file://` URI under the local backend); the UI is updated to match. The response also
  gained `upload_method` / `upload_fields` so it describes a complete request. Two
  earlier drafts — a dedicated streaming route, then a `same_origin` boolean, then a
  nullable `upload_url` — were dropped in review: `upload-dataset` already did the job, and
  a sentinel still left the client interpreting instead of just executing.
- The in-container mount point is renamed from `/mnt/gcs` to `/mnt/data`
  (`backends.base.JOB_MOUNT_ROOT`), since it is a GCS volume only on Cloud Run. **The
  deployed Cloud Run job definition pins that path**, so `rebuild_and_deploy.sh` (updated
  here) must be run when this lands; until it is, Cloud Run jobs launched by the new API
  will look for their data at a path the old job definition does not mount.
- The Asta workspace handoff (`asta_gcs.py`) still writes to a GCS bucket — that bucket is
  Asta's, not ours — but does so through `export_to_gs`, so it is server-side when the run
  store is GCS and streamed otherwise.
