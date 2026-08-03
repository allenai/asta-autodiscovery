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
  delete(key)                             idempotent
  copy(source_key, dest_key)               within the store
  list(prefix, *, limit)                  -> Iterator[ObjectInfo]
  list_dirs(prefix)                       -> immediate child names
  signed_upload_url(...) -> str | None    None when unsupported
```

Keys are the existing GCS blob names, unchanged, so **the on-disk layout is the same
layout as the bucket** and one can be copied to the other with `gsutil rsync`.

Eight of those are abstract. `upload_file`, `download_file`, and `copy` have working
defaults derived from the primitives, so a minimal backend can skip them and override only
what its service does better — GCS copies server-side, for instance, which matters because
forking a run copies its whole dataset. `read_text`, `write_text`, `uri`, and
`signed_upload_url` are also defaulted.

### Making a filesystem behave like an object store

Two GCS behaviors the rest of the code already depended on had to be reproduced:

| GCS behavior | `FilesystemStore` implementation |
| --- | --- |
| No directories — a prefix stops existing once its last object is deleted | Deletes prune the directories they empty; `list_dirs` skips directories with no objects beneath them. Otherwise deleted users/runs would linger in listings. |
| Object writes are atomic; a reader never sees a partial object | Writes stage into a uniquely-named `.ad-staging.*` file in the destination directory and `os.replace` into place; listings skip staging files. This matters because the API polls run files *while the job container writes them*. |

`created_at` comes from `st_mtime` (POSIX has no portable creation time); these objects are
written once, so it is the same instant in practice. Dataset expiry depends on it.

Two further GCS features were deliberately **left off the interface** rather than
reproduced, because each existed for a handful of rare callers and would have obliged every
backend to implement — or quietly fake — a guarantee it cannot make:

- **`matchGlob`.** Only GCS has server-side pattern matching; S3-compatible stores and
  filesystems do not. Its three callers are all cold paths — the metrics scan's job
  discovery (at most once per five-minute refresh, file-locked to one worker), the
  per-job experiment count (inside an already-narrow `output/` prefix), and the
  shared-run owner lookup's index-miss fallback. They now filter returned keys
  themselves. The cost is a longer listing on a cold path; the benefit is that no
  backend has to reimplement GCS's specific glob semantics (where `*` does not cross
  `/` — note `fnmatch` gets this wrong).
- **Atomic create-if-absent.** One caller: the `--acquire-lock` flag on the
  completion-email job, which only runs in the hosted deployment. It now uses GCS's
  generation precondition directly, in `scripts/send_completion_emails.py`, and refuses
  to run with a non-GCS backend rather than silently degrading. A filesystem can do this
  with `O_EXCL` locally but cannot promise it across machines, which is exactly the kind
  of near-miss that makes a shared interface dangerous.

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

### Capabilities, not backend names

Two things outside the store need to know what a store can do: the job backend (how do I
give a container this data as files?) and the startup validator (can an off-host consumer
read it?). Both ask the store class, never its configured name:

```python
class ObjectStore:
    job_data_mount: JobDataMount = JobDataMount.UNSUPPORTED  # HOST_PATH | GCSFUSE | UNSUPPORTED
    gs_addressable: bool = False
```

Both default to "no", so a backend that declares nothing is **refused with a clear error**
rather than inheriting whichever branch happened to be the fallback. That mattered: an
earlier draft compared `storage_backend == "gcs"` and bind-mounted a host path in the
`else`, which for a hypothetical S3 backend would have launched a job against a directory
that doesn't exist.

`gs_addressable` is narrower than "is remote" deliberately. The two off-host consumers —
Cloud Run's GCS volume mount and the Modal sandbox's `--bucket_path` — understand Google
Cloud Storage specifically, not object storage in general, so an S3-backed store is remote
*and* still unusable by them.

Both are read from the **class**, not an instance: `FilesystemStore.__init__` creates its
root directory, and merely validating configuration shouldn't `mkdir` a possibly-unwritable
`STORAGE_DIR`.

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
    base.py            # ObjectStore ABC, ObjectInfo, JobDataMount
    gcs.py             # GcsStore (google-cloud-storage)
    local.py           # FilesystemStore (atomic writes, prefix pruning)
  persistence.py       # functional job-data API (was gcs.py), owns the key layout
  gcs.py               # backward-compat shim re-exporting persistence
  client.py            # cached storage.Client, now only used by GcsStore
```

`autodiscovery_jobs.gcs` remains importable for external consumers of the published
package, mirroring the `cloudrun.py` shim from the job-backend change. In-repo imports all
point at `persistence`; note that patching a name on the shim does **not** affect callers
that imported it from `persistence`, so tests must target the real module.

### Adding a third backend

There are two levels of effort, and the cheap one is probably the right one.

**Tier 1 — no code.** Mount your storage and use `local`. `FilesystemStore` is a POSIX-tree
implementation, not a "local disk only" one, so anything the operator can mount works: NFS,
s3fs, Azure Files, JuiceFS, a SAN. Point `STORAGE_DIR` at the mount and the whole
application runs — including the job containers, which get a bind mount of the run's
subdirectory and never learn where the bytes actually live.

What you give up, all of it a consequence of a filesystem not being an object store:

| | Cost on a mount |
| --- | --- |
| Presigned uploads | Gone. Every dataset upload streams through the API instead of going browser→storage. |
| Prefix listings | A directory walk rather than one paginated request. The metrics scan lists everything under `users/`; over a mount that's one readdir per directory. |
| `copy` | No server-side copy, so forking a run pulls its dataset down and pushes it back up through the API. |
| Atomic replace | `os.replace` is atomic on a real filesystem; over a FUSE object-store adapter a rename is typically copy+delete, so a reader can observe a partial object. |

For a single-operator or on-prem deployment none of those usually bite: uploads through the
API are fine, and a few hundred runs makes a directory walk cheap. The completion-email job,
which is the one thing that needs a guarantee a mount can't give, only runs in the hosted
deployment and now keeps its own GCS-specific lock.

**Tier 2 — a subclass.** Implement the eight abstract members of `ObjectStore` (~150 lines
for S3/MinIO), declare `job_data_mount` and `gs_addressable`, and register the class in
`_STORES` in `storage/__init__.py`. Worth it when the Tier-1 costs above actually hurt.
A Tier-2 backend that isn't presentable as a POSIX tree also has to answer the job-container
question — leaving `job_data_mount` at `UNSUPPORTED` means jobs are refused, so such a
backend needs a new `JobDataMount` mechanism (e.g. its own FUSE adapter) implemented in the
job backend.

`tests/test_storage.py::MinimalStore` is a dict-backed store implementing exactly those eight
members; `test_persistence_api_works_against_a_minimal_store` runs the functional layer
against it, which is the executable statement of the contract.

Note that registration is still a source edit — there are no entry points. That's a
deliberate stopping point, not an oversight: a plugin mechanism can be added when a third
backend actually exists to justify its shape.

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

- The job backend and the validator ask the store class for capabilities
  (`job_data_mount`, `gs_addressable`) instead of comparing `storage_backend` strings, and
  the factory became a name→class registry so those capabilities are readable without
  constructing a store. This came out of review: the name comparisons meant an unrecognized
  backend silently took a fallback branch rather than being rejected.
- `LocalStore` was renamed `FilesystemStore`, because the Tier-1 story above is "any POSIX
  tree you can mount", not "local dev only". The configured name stays `local`, which
  remains accurate about the constraint that matters (the data is only reachable from this
  host, which is what rules out Cloud Run and Modal).
- `upload_file`, `download_file`, and `copy` moved from abstract to defaulted, and
  `match_glob` / `create_exclusive` were dropped entirely — cutting the required surface
  from twelve members to eight. The two dropped ones each served a few rare callers while
  obliging every backend to reproduce a GCS-specific guarantee; see above.

- `GCSError` is now an alias of the new `StorageError` rather than being renamed, so
  existing `except GCSError` sites and imports keep working.
- The `generate-upload-url` response keeps its `gcs_path` field name (now carrying a
  `file://` URI under the local backend) rather than breaking the wire format. It gained
  `upload_method` / `upload_fields` so the response describes a complete request. Two
  earlier drafts — a dedicated streaming route, then a `same_origin` boolean, then a
  nullable `upload_url` — were dropped in review: `upload-dataset` already did the job, and
  a sentinel still left the client interpreting instead of just executing.
- The in-container mount point stays `/mnt/gcs` even for the local backend. The deployed
  Cloud Run job definition pins that path (`--add-volume-mount` in
  `rebuild_and_deploy.sh`), so renaming it would couple this change to a Cloud Run
  redeploy. It is now the single constant `backends.base.JOB_MOUNT_ROOT`, so renaming it
  later is a one-line change plus a redeploy.
- The Asta workspace handoff (`asta_gcs.py`) still writes to a GCS bucket — that bucket is
  Asta's, not ours — but now reads its source through the store, doing a server-side copy
  only when the source is also GCS.
