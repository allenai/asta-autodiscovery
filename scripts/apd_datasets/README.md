# apd_datasets — scrape awesome-public-datasets into GCS

`apd_scrape.py` pulls datasets listed in
[awesomedata/awesome-public-datasets](https://github.com/awesomedata/awesome-public-datasets)
(a big `README.rst` of dataset homepages) and uploads the downloadable ones to a
GCS bucket. Three stages, each reading the previous stage's jsonl so you can
inspect/edit between them:

```
catalog   parse README.rst -> catalog.jsonl   {category,name,description,url,meta_url,icon}
classify  probe each URL   -> plan.jsonl      + handler {direct|github|kaggle|landing} + candidates
fetch     download+upload  -> manifest.jsonl  (dry-run by default; --execute to pull)
```

## Reproduce (biology/chemistry/healthcare/neuroscience → GCS)

```bash
curl -sL https://raw.githubusercontent.com/awesomedata/awesome-public-datasets/master/README.rst -o apd.rst

python3 apd_scrape.py catalog --rst apd.rst \
    --categories Biology Chemistry Healthcare Neuroscience --out catalog.jsonl

python3 apd_scrape.py classify --in catalog.jsonl --out plan.jsonl --discover --workers 16

# dry-run first (no --execute prints the plan); then execute
python3 apd_scrape.py fetch --in plan.jsonl \
    --gcs gs://sijia-adv-exp/datasets/awesome-public-datasets \
    --handlers direct github --max-bytes 2000000000 --execute
```

Uploads land at `gs://<bucket>/<prefix>/<Category>/<dataset-slug>/<filename>` using
your active `gcloud` login/project. `--categories` on `fetch` restricts a run to
one category (used to parallelize across categories).

## Coverage reality

The source is a directory of dataset **homepages**, not a file host, so most
entries can't be auto-downloaded uniformly. For the first four categories
(101 entries): **13 downloaded** (9 `github` tarballs + 4 live `direct` files),
3 `kaggle` (need the Kaggle API), 84 `landing` (per-portal — EBI, Allen Brain,
grand-challenge, CDC Socrata, …). See `manifest_gcs.jsonl` for what's in the
bucket (source_url / gcs_uri / bytes / sha256).

## Handlers

- **direct** — URL (or a link discovered on the page) ends in a strong data ext
  (`.csv/.zip/.parquet/...`); incidental files (`manifest.json`, `humans.txt`, …)
  are filtered out.
- **github** — repo URL → `codeload.../tar.gz/HEAD` default-branch tarball.
- **kaggle** — flagged; needs `KAGGLE_USERNAME`/`KAGGLE_KEY` (not yet implemented).
- **landing** — cataloged but not auto-downloadable; needs a per-site adapter.

To extend to other sections, just pass different `--categories` (the tool knows
all 34 sections in the README).
