# Open-ended Scientific Discovery via Bayesian Surprise

> Link to our NeurIPS 2025 paper: [AutoDiscovery: Open-ended Scientific Discovery via Bayesian Surprise](https://openreview.net/pdf?id=kJqTkj2HhF)

## Deployment

### Image Tagging Strategy

The autodiscovery Docker image follows an environment-based tagging strategy:
- **Dev environment** (`main` branch): `:dev`, `:dev-${commit_sha}`
- **Prod environment** (`env/prod` branch): `:prod`, `:prod-${commit_sha}`

Images are automatically built and pushed by GitHub Actions when changes merge to `main` or `env/prod`.

**Note:** We do not use `:latest` tags. All deployments must explicitly specify `:dev` or `:prod` to prevent accidental environment mixing.

### Deploying to Cloud Run

Deploy or update the Cloud Run Job from the root of the repo:

**For development environment:**
```bash
make deploy-autodiscovery
# Or with explicit env tag:
ENV_TAG=dev SKIP_BUILD=true make deploy-autodiscovery
```

**For production environment:**
```bash
ENV_TAG=prod SKIP_BUILD=true make deploy-autodiscovery
```

The `SKIP_BUILD=true` flag skips building the image (uses the image already built by GitHub Actions). Omit it to build locally.

## Datasets

### DiscoveryBench

```sh
git clone https://github.com/allenai/discoverybench.git temp_db
cp -r temp_db/discoverybench discoverybench
rm -rf temp_db
```

### Blade

```sh
git clone https://github.com/behavioral-data/BLADE.git temp_db
cp -r temp_db/blade_bench/datasets blade
rm -rf temp_db
```

### BYO-Datasets!
You can also use your own datasets. To do this, pass in a dataset metadata JSON file containing descriptions of the paths of datasets (relative to the metadata file) and their column descriptions in natural language. You can have a look at the metadata files in the `DiscoveryBench` directory from above as examples.

## Run AutoDS (MCTS-based hypothesis search and verification)

For example, to explore the DiscoveryBench NLS SES dataset, the following command can be used:

```sh
# From the repo root
uv run --package autodiscovery python -m autodiscovery.run \
    --work_dir="work" \
    --out_dir="outputs" \
    --dataset_metadata="discoverybench/real/test/nls_ses/metadata.json" \
    --n_experiments=16 \
    --model="gemini-3-flash-preview" \
    --belief_model="gemini-3-flash-preview" \
    --vision_model="gemini-3-flash-preview"
```

To resume a previous exploration, use the `--continue_from_dir` flag to specify the directory containing the previous
exploration logs. This will allow the script to continue from where it left off, using the MCTS nodes it had generated
so far.

## ✍️ Get in touch!

Please reach out to us on email or open a GitHub issue in case of any issues running the code: dagarwal@cs.umass.edu **(Dhruv Agarwal)**, bodhisattwam@allenai.org **(Bodhisattwa Prasad Majumder)**.

## 📄 Citation
If you find our work useful, please cite our paper:
```
@inproceedings{
agarwal2025autodiscovery,
title={AutoDiscovery: Open-ended Scientific Discovery via Bayesian Surprise},
author={Dhruv Agarwal and Bodhisattwa Prasad Majumder and Reece Adamson and Megha Chakravorty and Satvika Reddy Gavireddy and Aditya Parashar and Harshit Surana and Bhavana Dalvi Mishra and Andrew McCallum and Ashish Sabharwal and Peter Clark},
booktitle={The Thirty-ninth Annual Conference on Neural Information Processing Systems},
year={2025},
url={https://openreview.net/forum?id=kJqTkj2HhF}
}
```
