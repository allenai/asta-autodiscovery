# Data Library

A **data library** holds datasets that runs read **in place**, read-only, instead of
having them uploaded or copied into every run. It suits datasets that are large, that
many runs reuse, or that are trees of many files rather than a single table.

There are two kinds, with the same layout:

| | Where it lives in the store | Who can select it |
| --- | --- | --- |
| **Global** | `datalib/<dirname>/` | every user of the deployment |
| **User** | `users/<userid>/datalib/<dirname>/` | only that user |

Each top-level `<dirname>` is one selectable entry. What is inside it is up to you: one
file, a few related tables, or a deep tree holding several datasets.

```
datalib/
  census/
    README.md            # describes the directory (optional, recommended)
    2019/part-0.csv
    2020/part-0.csv
    codebook.json
users/
  file|alice/
    datalib/
      lab-notebooks/
        README.md
        ...
```

## AutoDiscovery does not write to the data library

**The app provides no way to add, change, or remove data-library files.** It only lists
the directories and mounts the ones a run selects. You populate the library yourself,
directly in the store, with whatever tools you already use for it:

- **`STORAGE_BACKEND=local`**: copy, move or sync files into the store directory
  (`STORAGE_DIR`; `./data` by default with `make dev`):

    ```sh
    mkdir -p data/datalib/census
    cp -r /path/to/census/* data/datalib/census/
    ```

    Anything that can write to that directory works, including an NFS or other network
    mount that `STORAGE_DIR` points at.

- **`STORAGE_BACKEND=gcs`**: write to the bucket:

    ```sh
    gcloud storage cp -r /path/to/census gs://<bucket>/datalib/
    ```

Changes show up the next time a user opens run setup; there is nothing to restart or
register.

### Finding a user's directory

A user's library is keyed by their user id, which comes from the
[authentication provider](authentication.md):

| `AUTH_PROVIDER` | User id |
| --- | --- |
| `none` | `local` |
| `password_file` | `file|<username>` |
| `auth0` | the Auth0 subject, e.g. `auth0|<id>` |

Create `users/<userid>/datalib/` if it does not exist yet. Ids can contain `|`, so quote
the path in shell commands.

## Describing a directory: `README.md`

A `README.md` at the top of a directory plays the role that the description plays for an
uploaded file. It is shown in run setup and given to AutoDiscovery. Write it for a
reader who has not seen the data:

- what the data is, where it came from, and the period or population it covers;
- how the files are organized (one table split across files, separate datasets, ...);
- the meaning of columns or fields that are not self-explanatory, units, and codes;
- known caveats (missing values, changes in definitions over time).

A README is optional, but without one AutoDiscovery has only the file names and layout to
go on.

## How a run uses a directory

When a run selects directories, each is mounted read-only into the run at the path its
key implies under the store root, in every environment the run uses:

```
/mnt/data/datalib/<dirname>                     # global
/mnt/data/users/<userid>/datalib/<dirname>      # user
```

(With `JOB_BACKEND=process` the job reads the store in place, so the store's own
directory stands in for `/mnt/data`, and the files are not protected from writes.)

Unlike an uploaded file, a directory is not described file by file. AutoDiscovery is given
each directory as a whole: its README and an overview of its files (counts, sizes, types,
and a bounded view of the layout). The run's first experiment surveys the directories,
identifies the datasets they hold, and loads what is relevant, reading selectively if it is
large. What each run was shown is saved in its output as `datalib_manifest.json`.

A run can use data-library directories alongside uploaded files, or on their own.

Because directories are read in place, changing their contents affects later runs, not
runs already finished; `datalib_manifest.json` records what an earlier run saw.

## Rules and limits

- Only **top-level** directories are selectable. Files placed directly in `datalib/`
  (rather than in a directory under it) are not offered.
- Directory names must be a single path segment. Names starting with `.` are not listed.
- Run setup shows each directory's file types, e.g. `12 csv, 5 tsv, 2 pdf, 14 others`.
  These are counted over at most the first 2,000 files of a directory, and the listing
  says so when there are more.
- A user directory selected in a run stays tied to that user: if another user forks a
  shared run, user-directory selections are dropped. Global selections carry over.

## Not yet supported

- **Restricting global directories to some users.** Every global directory is visible to
  every user. Per-directory permissions, for example granting a global directory to
  particular users or groups, are a possible future extension; until then, a dataset that
  only some users should see belongs in each of those users' own libraries.
- Adding or managing data-library files from the app.

For how the feature is built, see the [design notes](design/data-library.md).
