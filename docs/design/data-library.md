# Data Library — Design

Status: **First pass** · Branch: `feature/user-datalib-mounts`

## Goal

Let a run read a user's large or reused datasets **in place**, read-only, instead of
uploading or copying them into every run. A user's data library is a set of
directories in the store:

```
users/<userid>/datalib/<dirname>/...          # any tree: one dataset or many
users/<userid>/datalib/<dirname>/README.md    # its description (optional)
```

The top-level directories are what a run selects, any number of them; what is inside
each is up to the user. A run may use data-library directories alongside uploaded or
preloaded datasets, or **instead of** them.

The library is populated out of band for now; the webapp only lists and selects it.

## One path, everywhere

A data-library directory appears at the path its key implies under the mount root, in
every environment that sees it:

```
/mnt/data/users/<userid>/datalib/<dirname>
```

This is the same rule the job containers already follow for a run's own directory
(`JOB_MOUNT_ROOT`, see [Swappable Persistence Backends](storage-backends.md#scoping-the-job-containers-mount)):
the store's layout is decided once and each environment mirrors it, rather than each
inventing its own mapping.

| Environment | How the directory gets there |
| --- | --- |
| Docker job container (`JOB_BACKEND=docker`) | A read-only bind of `$STORAGE_HOST_DIR/users/<uid>/datalib/<dir>`, beside the run's own read-write bind. |
| Cloud Run job container (`JOB_BACKEND=gcp`) | Already there: the job definition mounts the whole bucket at `/mnt/data`. |
| Modal sandbox (`CODE_EXECUTION_BACKEND=modal`) | A read-only `CloudShare` of `gs://<bucket>/users/<uid>/datalib/<dir>/` at the same path. |
| `process` / `local` code execution | Runs in the job container, so reads the container's path directly. |

On Cloud Run the mount is the bucket's job-level volume, which is neither read-only nor
scoped to the user. That is an existing property of the Cloud Run job definition, not
something this feature introduces; code running in a Modal sandbox sees only its
read-only shares.

The Modal sandbox still mounts a run's *uploads* at `/data`, the one place the layout
rule is not yet followed; aligning it is tracked separately.

## How a run describes the library to the agents

A dataset in `metadata.json` is a filename plus a free-text description, and it reaches
the agents only through the prompts: the first experiment of every run is "load the
dataset(s) and summarize them", with the descriptions included, and every later
hypothesis builds on it.

A data-library directory can hold any number of datasets in any layout, so it is not
treated as one more dataset entry (the first experiment would try to load a directory as
a table). Instead the job builds a **manifest** of each directory at startup:

- the directory's `README.md` (truncated), which plays the role of an upload's
  description;
- file and subdirectory counts, total size, and counts by file extension;
- a bounded view of the file tree (a few levels, a few entries per directory).

The walk is bounded by entries visited, not just by what is shown, since the directory
may be very large and is often a network mount; a partial count says so.

The manifest is used in two places:

1. **The first experiment** gains a step to survey the directories — use the README and
   layout to identify the datasets, then load the relevant ones, reading selectively if
   they are large — and its objective includes the full manifest. For a run with no
   uploaded datasets this is the only loading step, and the empty dataset-metadata
   section is omitted.
2. **Agent system prompts** (generator, programmer, reviser) get one short paragraph
   naming the directories' paths, saying they are provided data and read-only, and
   advising selective reads. Without a data library the prompts are unchanged.

The job writes the manifests to `output/datalib_manifest.json`. The directories are read
in place and can change between runs, so this records what a given run was shown.

## Interfaces

| Layer | Change |
| --- | --- |
| Keys | `keys.datalib_prefix`, `keys.datalib_dir`, and `keys.validate_datalib_dirname`, which rejects anything but a single, non-dot path segment. |
| Persistence / `JobManager` | `list_datalib_dirs(userid)` → `DatalibDir(name, description)`; `missing_datalib_dirs(userid, names)`. |
| API | `GET /api/user/me/datalib` → `{"dirs": [{"name", "description"}]}`. Run metadata gains `datalib_dirs: [name, ...]`. |
| Submit | Checks every selected directory exists in the **submitting user's** library (400 otherwise), and that the run has at least one dataset or directory. |
| Job args | `--datalib_dir=/mnt/data/users/<uid>/datalib/<dir>`, repeatable. With `modal`, also `--store_root=/mnt/data --store_uri=gs://<bucket>`, from which the job derives each directory's `gs://` source by the same key. |
| Fork | Keeps `datalib_dirs` when the owner forks their own run; drops them when another user forks a shared run, since the names refer to the owner's library. A run with only data-library directories has no uploads to copy, so it can be forked without them. |
| Dataset expiry | Expiry deletes a run's own uploads only, so a run with only data-library directories reports no expiry. |
| UI | A "Data library" multi-select in run setup (shown when the user has any directories), with each README as secondary text; the run's parameters view lists the selection. |

The standalone CLI takes `--datalib_dir` too, with any local directory.

## Open questions

- Whether to snapshot, rather than just record, what a run read (e.g. object
  generations on GCS), for stronger reproducibility.
- A UI for adding to the library.
- Whether preloaded datasets, which are copied into every run today, should become a
  shared read-only library.
