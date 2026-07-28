# dataset_mining — mine public datasets into GCS

`mine.py` pulls public research datasets into a GCS bucket from two source
shapes, with one CLI.

## A) URL directory — awesome-public-datasets

[awesomedata/awesome-public-datasets](https://github.com/awesomedata/awesome-public-datasets)
is a `README.rst` of dataset **homepages**. Three stages, each reading the
previous stage's jsonl:

```
catalog   parse README.rst -> catalog.jsonl   {category,name,description,url,meta_url,icon}
classify  probe each URL   -> plan.jsonl      + handler {direct|github|kaggle|landing} + candidates
fetch     download+upload  -> manifest.jsonl  (dry-run by default; --execute to pull)
```

```bash
curl -sL https://raw.githubusercontent.com/awesomedata/awesome-public-datasets/master/README.rst -o apd.rst
python3 mine.py catalog  --rst apd.rst --categories Biology Chemistry Healthcare Neuroscience --out catalog.jsonl
python3 mine.py classify --in catalog.jsonl --out plan.jsonl --discover --workers 16
python3 mine.py fetch    --in plan.jsonl --gcs gs://sijia-adv-exp/datasets/awesome-public-datasets \
                         --handlers direct github --execute
```

Handlers: **direct** (URL/discovered link ends in a strong data ext, incidental
files like `manifest.json`/`humans.txt` filtered), **github** (repo →
`codeload.../tar.gz/HEAD`), **kaggle** (flagged, needs the Kaggle API),
**landing** (cataloged only — needs a per-site adapter). Most entries are
homepages, so coverage is partial: the first four categories gave **13/101**
auto-downloaded (see `manifest_apd.jsonl`).

## B) Data repos — DiscoveryBench & BLADE

These repos ship the actual data files with a fixed layout the autodiscovery
loaders require, so `repo` mirrors the subtree **verbatim** (filenames and
folders preserved):

- `discoverybench` → `discoverybench/real/<split>/<dataset>/` : `metadata_<i>.json`
  + every file in its `datasets[].name` (csv/dta/txt), same folder.
- `blade` → `blade/<dataset>/` : `info.json` + `data.csv` (the `is_blade` loader
  hardcodes `data.csv` beside `info.json`).

```bash
python3 mine.py repo --gcs gs://sijia-adv-exp/datasets            # both sources; --dry-run to preview
python3 mine.py registry --gcs gs://sijia-adv-exp/datasets --out registry_dbench_blade.json
```

First run mirrored **14 DiscoveryBench** (13.9 MB) + **15 BLADE** (57.3 MB) —
see `manifest_dbench_blade.jsonl`.

## Registry for the reward server

`registry` enumerates the mirrored data and emits a `dataset_id -> {dataset_metadata,
dataset_metadata_type}` map (29 datasets: 14 `dbench` + 15 `blade`). Paths use a
`${DATA_ROOT}` placeholder because the autodiscovery loader opens **local/weka**
paths, not `gs://` — sync the GCS data to that root on the reward-server node and
substitute it, then point the server at the registry:

```bash
python -m autodiscovery.slime_reward --dataset_registry registry_dbench_blade.json --port 8000
```

`dataset_metadata_type` is `dbench` (reads `datasets[].name` from `metadata_<i>.json`)
or `blade` (reads `info.json` + sibling `data.csv`). Both are already understood
by `autodiscovery/dataset.py`.

## GCS layout (bucket `sijia-adv-exp`)

```
datasets/awesome-public-datasets/<Category>/<dataset-slug>/<file>
datasets/discoverybench/real/<split>/<dataset>/<metadata_i.json + data files>
datasets/blade/<dataset>/{info.json,data.csv,...}
```

Uploads use your active `gcloud` login/project. All fetch/repo commands accept
`--dry-run`/no-`--execute` to preview first.
